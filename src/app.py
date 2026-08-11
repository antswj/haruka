"""Haruka — bilingual prompt analysis API.

One FastAPI app behind an API Gateway HTTP API. Mangum is the adapter that
translates Lambda's (event, context) calling convention into ASGI, so
everything below is an ordinary FastAPI route — nothing Lambda-shaped.

Entry point is `handler` at the bottom of this file (template.yaml ->
Handler: app.handler).
"""

import logging
import os
import boto3
import tiktoken

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

import judge
import lints_ja

logger = logging.getLogger(__name__)

# Plan §8: input capped at 8,000 chars. The cap lives here, once, and the
# request model below is what enforces it.
MAX_INPUT_CHARS = 8000

app = FastAPI(title="Haruka", version="0.1.0")


# --- Privacy: the 422 body is a leak, so we never let FastAPI send one. ---
#
# Pydantic v2 puts the offending value in every error dict under an "input"
# key, and FastAPI's default handler serialises exc.errors() straight into
# the response. On a 8,001-character prompt that means the whole prompt comes
# back out. Decision 13 says privacy is true by engineering, not by promise —
# so this handler returns a FROZEN body and never reads exc.errors().
INVALID_INPUT_BODY = {
    "error": "invalid_input",
    "message_ja": "テキストを1文字以上、8,000文字以内で入力してください。",
    "message_en": "Please enter between 1 and 8,000 characters.",
}


def _submitted_length(exc: RequestValidationError) -> str:
    """How long the rejected text was — the length, never the text.

    exc.body is whatever arrived: a dict on well-formed JSON, a raw string
    on malformed JSON, None on an empty body. We take len() only when it is
    genuinely a string field, and say "unknown" otherwise rather than
    guessing at something that might stringify user content into a log line.
    """
    body = exc.body
    if isinstance(body, dict) and isinstance(body.get("text"), str):
        return str(len(body["text"]))
    return "unknown"


@app.exception_handler(RequestValidationError)
async def invalid_input_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Static bilingual 400. Japanese first, English second — §1: JA is
    first-class, not a translation bolted on after.

    400 not 422: this is "your text does not fit the rules I published",
    which is an ordinary bad request. 422 is also a FastAPI tell, and the
    error surface is not where we advertise the framework.

    Malformed JSON lands here too and gets the same body, which is correct —
    the user cannot act on the difference between "empty" and "not JSON".
    """
    logger.warning(
        "invalid_input status=400 path=%s chars=%s",
        request.url.path,
        _submitted_length(exc),
    )
    return JSONResponse(status_code=400, content=INVALID_INPUT_BODY)


@app.get("/hello")
def hello():
    """Liveness route. Same JSON payload as Day 1 on purpose: if the parsed
    response changes, the FastAPI+Mangum swap is what changed it.

    Note the raw bytes DO differ — json.dumps() wrote `", "` separators,
    FastAPI's JSONResponse writes compact `","`. Compare parsed JSON, not
    a byte diff.
    """
    return {"message": "Haruka: hello from Tokyo", "day": 1}


# --- POST /count — the first real endpoint. Both counts, always. ---


class CountRequest(BaseModel):
    """The whole input contract, declared once.

    min_length=1 rejects "" and max_length rejects the oversized paste, and
    BOTH failures raise RequestValidationError — which the handler above
    turns into the static bilingual 400. That is why there is no length
    check inside the route: the model is the validation.
    """

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class CountResponse(BaseModel):
    """Plan §8's shape. gpt_tokens_est carries `_est` in its NAME because
    the UI must never present an estimate and an exact count as peers.
    """

    claude_tokens: int
    gpt_tokens_est: int
    chars: int


def count_claude_tokens(text: str) -> int:
    client = boto3.client("bedrock-runtime")
    response = client.count_tokens(
        # COUNT_MODEL_ID, not JUDGE_MODEL_ID — see the two-models note in
        # judge.py. CountTokens rejects the jp. inference profile with
        # "The provided model doesn't support counting tokens" and needs the
        # bare foundation-model id; Converse needs the profile and refuses the
        # bare id. Same model, two identifiers, two env vars.
        modelId=os.environ["COUNT_MODEL_ID"],
        input={"converse": {"messages": [
            {"role": "user", "content": [{"text": text}]}
        ]}}
    )
    return response ["inputTokens"]


def count_gpt_tokens_est(text: str) -> int:
    enc = tiktoken.get_encoding("o200k_base")
    return len(enc.encode(text))


@app.post("/count", response_model=CountResponse)
def count(req: CountRequest) -> CountResponse:
    """Both providers' counts side by side — the v1 hard requirement (§1).

    Wiring only: validation happened in CountRequest, and the two numbers
    come from the functions above.
    """
    return CountResponse(
        claude_tokens=count_claude_tokens(req.text),
        gpt_tokens_est=count_gpt_tokens_est(req.text),
        chars=len(req.text),
    )


# --- POST /analyze — Judge + lints + counts, in one answer. ---


# The judge failed us, not the user. Frozen body for the same reason the 400
# is frozen: the judge's output is derived from the user's prompt, so echoing
# any part of it — even "expected int, got 'seven'" — leaks the prompt into an
# error surface. Bilingual, JA first (§1).
JUDGE_FAILED_BODY = {
    "error": "judge_unavailable",
    "message_ja": "採点に失敗しました。少し時間をおいて、もう一度お試しください。",
    "message_en": "Scoring failed. Please try again in a moment.",
}


@app.exception_handler(judge.JudgeOutputError)
async def judge_output_handler(
    request: Request, exc: judge.JudgeOutputError
) -> JSONResponse:
    """502, not 500: the upstream model gave us something unusable, which is
    precisely what "bad gateway" means. A 500 would claim the bug is ours.

    The log line carries a path and a status and nothing else — not the raw
    output, not its length, not the rule that failed. Anything derived from
    the prompt stays out of CloudWatch.
    """
    logger.warning("judge_output_invalid status=502 path=%s", request.url.path)
    return JSONResponse(status_code=502, content=JUDGE_FAILED_BODY)


# --- Language detection (PLAN §9, the Day 3 heuristic) ---------------------
#
# Day 2 decided validation errors would NOT detect language — stacked bilingual
# text cannot misdetect. This is the other half of that decision: the judge has
# to pick a card, and a card is written in one language.
_JA_RANGES = (
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs (kanji)
)


def detect_language(text: str) -> str:
    """Any Japanese character anywhere -> ja. Otherwise en.

    Deliberately blunt. A Japanese prompt quoting English is still Japanese
    and should be judged by the JA card; the reverse — an English prompt
    containing one kana — is rare enough to accept.

    KNOWN LIMIT: Chinese is written in the kanji range, so Chinese input
    detects as Japanese. v1 supports two languages and offers a `lang`
    override; a third language needs a real detector, not a wider range.
    """
    for ch in text:
        cp = ord(ch)
        if any(low <= cp <= high for low, high in _JA_RANGES):
            return "ja"
    return "en"


class AnalyzeRequest(BaseModel):
    """Same 8,000-char contract as /count — one cap, declared once (§8).

    `lang` is optional and typed as a literal, so "fr" is rejected by the same
    validation that rejects an oversized prompt, and lands in the same static
    bilingual 400. No new error surface.
    """

    text: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    lang: Literal["ja", "en"] | None = None


class AnalyzeScore(BaseModel):
    """The five rubric bars, 0-5.

    NOT 0-20: PLAN §9's "0-20 each" is a known erratum. Both judge cards ship
    0-5 and the consistency gate is ±1. Spelled out as five named fields
    rather than a dict so the response contract is visible in the schema.
    """

    instruction: int
    context: int
    input_data: int
    output_indicator: int
    specificity: int


class AnalyzeResponse(BaseModel):
    """PLAN §8's shape, adjusted — two additions and five deliberate omissions.

    ADDED: `lints` (§8 predates the JA rulebook) and `lang` (the caller should
    know which card judged them, especially when detection guessed).

    OMITTED: time_estimate, cost_estimate, pii, recommendation, tips. Each
    needs data that does not exist yet — nightly benchmarks, a price table,
    PII detection, the DynamoDB models table, the corpus. A zero or an empty
    object in those fields would be a fabricated measurement, and §1's whole
    argument against a single fake "%" applies to a fake "0.4 JPY" too. They
    come back when they mean something.
    """

    lang: str
    tokens: dict[str, int]
    score: AnalyzeScore
    score_explainers: dict[str, str]
    verdict_line: str
    lints: list[dict]
    meta: dict[str, str]


def _collapse_lint_findings(findings: list) -> list:
    """Drop the vague finding when a referent finding covers the same match.

    This is the one aggregator rule from lints_ja's TODO block that is safe to
    apply today. check_ambiguous_referent draws its needles from two
    vague_words entries, so every referent hit is ALSO a vague hit — 「例の件」
    always produces two warnings for one span. cross_list_notes[0] says do not
    let both fire visibly; the referent finding is the more specific of the
    two, so it survives.

    Matched STRINGS, not offsets: the finding shape carries no positions. That
    is exact for this case (both checks report the same surface form via the
    same longest-match rule) and would need real spans to generalise.

    DEFERRED — cushion-before-task-verb ordering (cross_list_notes[2]). Some
    cushions contain verbs, so a prompt whose only task verb sits inside
    「お伺いしたいことがあるのですが」 scores as HAVING a task verb when the
    verb is really part of the politeness padding. Known false negative, not
    fixed here: masking cushion spans before the other checks run is real
    scoring logic and belongs in a rubric decision, not a wiring commit.
    """
    referent_matches = {
        f["matched"] for f in findings if f["rule"] == "ambiguous_referent"
    }
    return [
        f
        for f in findings
        if not (f["rule"] == "vague_word" and f["matched"] in referent_matches)
    ]


def _run_ja_lints(text: str) -> list:
    """All five JA rules over one text, collapsed."""
    findings = (
        lints_ja.check_vague_words(text)
        + lints_ja.check_cushion_padding(text)
        + lints_ja.check_task_verb_present(text)
        + lints_ja.check_format_marker(text)
        + lints_ja.check_ambiguous_referent(text)
    )
    return _collapse_lint_findings(findings)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Judge + lints + counts.

    Wiring only. Validation happened in AnalyzeRequest, the judge machinery
    lives in judge.py, the rules live in lints_ja.py, and the two counting
    functions are the ones /count already uses — §8 says "/analyze reuses this
    code path", so it does, rather than growing a second way to count.

    A JudgeOutputError from parse_judge_json propagates to the handler above
    and becomes a static 502. Nothing is caught here, because catching it here
    would mean deciding what to say about it, and the frozen body already
    decided.
    """
    lang = req.lang or detect_language(req.text)

    raw = judge.invoke_judge(
        judge.JUDGE_CARDS[lang],
        judge.build_user_message(req.text, lang),
    )
    parsed = judge.parse_judge_json(raw)

    # JA input only for now — the EN rulebook (§9) is not written. An empty
    # list, not a missing key: the field's absence would read as "we did not
    # look", and the shape should not change with the language.
    findings = _run_ja_lints(req.text) if lang == "ja" else []

    return AnalyzeResponse(
        lang=lang,
        tokens={
            "claude": count_claude_tokens(req.text),
            "gpt_est": count_gpt_tokens_est(req.text),
        },
        score=AnalyzeScore(**{k: parsed[k] for k in judge.SUBSCORE_KEYS}),
        score_explainers=parsed["explainers"],
        verdict_line=parsed["verdict_line"],
        lints=findings,
        # OPEN ERRATUM (see BUILD_STATE): §8 specifies "ap-northeast-1", but
        # the judge runs through the jp. inference profile, which may serve
        # from ap-northeast-3. This value is therefore true of the STACK and
        # possibly false of the INFERENCE — the same gap as the 東京 badge.
        # Left as specified rather than changed unilaterally: it is a
        # published API field, and "日本国内" vs a region pair vs both is a
        # product decision, not a wiring one.
        meta={"region": "jp"},
    )


# lifespan="off": Mangum otherwise runs the ASGI lifespan protocol
# (startup/shutdown) around EVERY invocation. We have no startup work, so
# that is pure per-request overhead. Load-once work belongs at module scope,
# which runs once per cold start.
handler = Mangum(app, lifespan="off")
