"""The Judge — prompt cards, the fenced user message, and the Bedrock call.

PLAN §9. The Judge scores a prompt on five bars and explains each in words a
12-year-old understands. This module owns everything between "we have the
user's text" and "we have a validated dict of scores": which card to send, how
to wrap the text so its contents cannot become instructions, the Bedrock call,
and the parse. It does not own scoring policy and it never touches a route.

PRIVACY INVARIANT — this module does not import `logging` and must not. The
user's text passes through here, and so does the model's raw output; neither
may be written anywhere except the return value. app.py logs lengths and status
codes only. Same rule as lints_ja.py: there is no logger to misuse.

TWO MODELS, TWO DOORS (probed live 2026-08-12, ap-northeast-1)
--------------------------------------------------------------
Claude Haiku 4.5 in Tokyo is INFERENCE_PROFILE only — it has no ON_DEMAND
inference type, so Converse cannot be called on the bare foundation-model id.
The Japan-domestic profile `jp.anthropic.claude-haiku-4-5-20251001-v1:0` routes
between ap-northeast-1 and ap-northeast-3 and is what Converse must be given.

But CountTokens REJECTS that same profile id:

    ValidationException: The provided model doesn't support counting tokens

...and works on the bare foundation-model id, which Converse in turn refuses.
So the two calls need two different identifiers for the same model. They arrive
as two environment variables — COUNT_MODEL_ID (app.py, counting) and
JUDGE_MODEL_ID (here, judging) — declared as two template parameters. This is
not redundancy; a single id cannot satisfy both APIs.
"""

import uuid
import os
import boto3
import json
from pathlib import Path

# --- Prompt cards ----------------------------------------------------------
#
# src/prompts/ is INSIDE `CodeUri: src/`, so the cards are packaged into the
# Lambda zip automatically — unlike the lexicon, which needed relocating.
# Resolved relative to this file so the path is identical in the repo and at
# /var/task.
_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

SUPPORTED_LANGS = ("ja", "en")


def _load_card(lang: str) -> str:
    """Read one judge card. Loud on failure, for the same reason the lexicon
    loader is: a missing card would otherwise mean every prompt gets judged by
    an empty system prompt, which looks like a working endpoint returning
    nonsense."""
    path = _PROMPTS_DIR / f"judge_{lang}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Judge card not found at {path}")
    return path.read_text(encoding="utf-8")


# Both cards read once at import — once per cold start, not once per request.
JUDGE_CARDS = {lang: _load_card(lang) for lang in SUPPORTED_LANGS}


# --- The judged-text wrapper ----------------------------------------------
#
# WHY THE DELIMITER IS RANDOM. The cards say "grade only what is inside the
# delimiter". With a fixed delimiter, a prompt containing that delimiter closes
# the wrapper early and everything after it reads as instructions to the
# judge — and this product's whole input surface is prompts, i.e. text that
# plausibly contains code fences and markers on purpose.
#
# A uuid4 hex is 32 random characters. The user cannot include it because it
# does not exist until after their text has already arrived. No stripping, no
# rejection, no rewriting — the text is graded exactly as written, which for a
# prompt-analysis tool is the whole point.
#
# The cards therefore say the delimiter "is specified in the message" rather
# than naming one, and neither card contains a literal fence anywhere.
_WRAPPER_JA = "採点対象は次の {delim} で囲まれた部分だけです。\n{delim}\n{text}\n{delim}"
_WRAPPER_EN = (
    "The text to grade is only the part enclosed by {delim} below.\n"
    "{delim}\n{text}\n{delim}"
)
_WRAPPERS = {"ja": _WRAPPER_JA, "en": _WRAPPER_EN}


def build_user_message(text: str, lang: str) -> str:
    """Wrap the user's text in a per-request random delimiter.

    Language-matched on purpose: the card is written in the input's language,
    so the sentence naming the delimiter has to be too, or the JA judge reads
    an English instruction as part of the material it is grading.
    """
    delim = uuid.uuid4().hex
    return _WRAPPERS[lang].format(delim=delim, text=text)


# --- Judge output contract -------------------------------------------------

# The five rubric bars, in PLAN §9 order. 0-5, NOT 0-20 — the §9 text is a
# known erratum and both cards already say 0-5. Gate is ±1.
SUBSCORE_KEYS = (
    "instruction",
    "context",
    "input_data",
    "output_indicator",
    "specificity",
)
SUBSCORE_MIN = 0
SUBSCORE_MAX = 5

# PLAN §8: "judge output ≤ 1,500 tokens · every invoke has max_tokens".
MAX_JUDGE_TOKENS = 1500
# Low, not zero-by-accident: the judge should grade the same prompt the same
# way twice (the Day 3 gate is 3 runs, spread ≤ ±1). Scoring is not a place
# for sampling variety.
JUDGE_TEMPERATURE = 0.0


class JudgeOutputError(Exception):
    """The judge returned something we cannot use.

    Raised by parse_judge_json for anything that fails the contract: not JSON,
    missing a key, a subscore that is not an int, a subscore out of range, a
    missing explainer, a missing verdict_line.

    CARRIES NO USER TEXT AND NO MODEL OUTPUT. The route turns this into a
    static 502 and logs a length, so anything placed in the message would be
    one refactor away from a privacy leak. Say what rule broke, never what the
    text was.
    """


# --- Stub 1: the Bedrock call ---------------------------------------------

def invoke_judge(system_prompt: str, user_text: str) -> str:
    """Send one prompt to the judge model and return its raw text output.

    ANTHONY WRITES THIS BODY. The request shape below was verified against
    live AWS documentation on 2026-08-12 (freshness rule):
      https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
      https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html

    Verified request shape:

        client = boto3.client("bedrock-runtime")
        resp = client.converse(
            modelId=os.environ["JUDGE_MODEL_ID"],     # the jp. PROFILE id
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            system=[{"text": system_prompt}],
            inferenceConfig={
                "maxTokens": MAX_JUDGE_TOKENS,
                "temperature": JUDGE_TEMPERATURE,
            },
        )
        return resp["output"]["message"]["content"][0]["text"]

    Three things worth knowing before you write it:

    1. `system` is a TOP-LEVEL parameter, a sibling of `messages` — not a
       message with role "system". The boto3 reference lists "system" among
       the valid message roles, which is misleading; the card belongs in the
       `system` list, shaped [{"text": ...}].

    2. THE max_tokens TRAP. `resp["stopReason"]` is one of end_turn,
       max_tokens, stop_sequence, tool_use, guardrail_intervened,
       content_filtered, malformed_model_output, malformed_tool_use,
       model_context_window_exceeded. A `max_tokens` stop means the judge was
       CUT OFF mid-JSON — the output is truncated, so parse_judge_json will
       fail on it, and the 502 would blame the model for our cap. Worth
       distinguishing: it means raise MAX_JUDGE_TOKENS or shorten the card,
       not "the model misbehaved".

    3. `user_text` arriving here is ALREADY WRAPPED by build_user_message().
       Do not wrap it again and do not concatenate anything onto it — the
       delimiter is what keeps its contents from being read as instructions.

    Also available on the response if you want them later:
    `resp["usage"]["inputTokens" | "outputTokens" | "totalTokens"]` and
    `resp["metrics"]["latencyMs"]` — the measured latency PLAN §8's
    time_estimate will eventually need.
    """
    client = boto3.client("bedrock-runtime")
    resp = client.converse(
        modelId=os.environ["JUDGE_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        system=[{"text": system_prompt}],
        inferenceConfig={"maxTokens": MAX_JUDGE_TOKENS, "temperature": JUDGE_TEMPERATURE},
    )
    if resp["stopReason"] == "max_tokens":
        raise JudgeOutputError("truncated")
    return resp["output"]["message"]["content"][0]["text"]


# --- Stub 2: the parse ------------------------------------------------------

def parse_judge_json(raw: str) -> dict:
    """Validate the judge's raw output into a trusted dict.

    ANTHONY WRITES THIS BODY. The contract, from both cards:

        {
          "instruction": <int 0-5>,      # SUBSCORE_KEYS, SUBSCORE_MIN/MAX
          "context": <int 0-5>,
          "input_data": <int 0-5>,
          "output_indicator": <int 0-5>,
          "specificity": <int 0-5>,
          "explainers": { one line per bar, in the input's language },
          "verdict_line": "one line summing up the whole prompt"
        }

    Every failure raises JudgeOutputError — never returns a partial dict, never
    lets a ValueError or KeyError escape. The route catches exactly this type
    and returns a static bilingual 502, so anything that escapes uncaught
    becomes a Starlette 500 instead and the bilingual contract breaks.

    NEVER put `raw` in the exception message, a return value, or a log line.
    The judge's output is derived from the user's prompt; leaking it into an
    error surface leaks the prompt. Report which rule failed, not what broke
    it — "subscore out of range" and not "got 47 for instruction in <text>".

    Two things the cards ask for but cannot guarantee, so validate both:
      - The card forbids code-block markers, but models emit fenced JSON
        anyway. Decide whether to strip a wrapping fence before json.loads or
        to fail — failing is stricter and makes the card's compliance visible
        rather than silently papering over it.
      - "0-5" is an instruction, not a constraint. A 7 or a "4" (string) is a
        contract violation you have to catch here; nothing upstream does.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        first_newline = raw.find("\n")
        if first_newline != -1 and raw.endswith("```"):
            raw = raw[first_newline + 1 : -3].strip()
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise JudgeOutputError("not json")
    for key in SUBSCORE_KEYS:
        v = data.get(key)
        if not isinstance(v, int) or not (SUBSCORE_MIN <= v <= SUBSCORE_MAX):
            raise JudgeOutputError("bad score")
    if "explainers" not in data or "verdict_line" not in data:
        raise JudgeOutputError("missing keys")
    return data
