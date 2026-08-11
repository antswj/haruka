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

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum
from pydantic import BaseModel, Field

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
        modelId=os.environ["JUDGE_MODEL_ID"],
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


# lifespan="off": Mangum otherwise runs the ASGI lifespan protocol
# (startup/shutdown) around EVERY invocation. We have no startup work, so
# that is pure per-request overhead. Load-once work belongs at module scope,
# which runs once per cold start.
handler = Mangum(app, lifespan="off")
