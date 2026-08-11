"""Haruka — bilingual prompt analysis API.

One FastAPI app behind an API Gateway HTTP API. Mangum is the adapter that
translates Lambda's (event, context) calling convention into ASGI, so
everything below is an ordinary FastAPI route — nothing Lambda-shaped.

Entry point is `handler` at the bottom of this file (template.yaml ->
Handler: app.handler).
"""

from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(title="Haruka", version="0.1.0")


@app.get("/hello")
def hello():
    """Liveness route. Same JSON payload as Day 1 on purpose: if the parsed
    response changes, the FastAPI+Mangum swap is what changed it.

    Note the raw bytes DO differ — json.dumps() wrote `", "` separators,
    FastAPI's JSONResponse writes compact `","`. Compare parsed JSON, not
    a byte diff.
    """
    return {"message": "Haruka: hello from Tokyo", "day": 1}


# lifespan="off": Mangum otherwise runs the ASGI lifespan protocol
# (startup/shutdown) around EVERY invocation. We have no startup work, so
# that is pure per-request overhead. Load-once work belongs at module scope,
# which runs once per cold start.
handler = Mangum(app, lifespan="off")
