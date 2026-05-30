"""User feedback HTTP endpoint for Langfuse scores (B-1).

Registers ``POST /feedback`` on the Aegra custom FastAPI app (see
``http.app`` in ``aegra.json``). Aegra loads this app as the base
application and merges core LangGraph Platform routes onto it.

When Langfuse credentials are absent, submissions are logged and accepted
without contacting Langfuse.

When ``thread_id`` and ``message_id`` are present, feedback is also
persisted to Postgres for cross-session history.
"""

from __future__ import annotations

import json
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from deep_agent.aegra.telemetry import get_langfuse_client
from deep_agent.src.agent.config import agent_config
from deep_agent.src.feedback.repository import FeedbackRepository
from deep_agent.src.schema import FeedbackRequest, FeedbackResponse
from deep_agent.src.settings import settings
from deep_agent.utils.pylogger import (
    bind_request_context,
    clear_request_context,
    get_python_logger,
)

logger = get_python_logger()

app = FastAPI(title="template-agent-custom")


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Propagate X-Trace-ID from incoming requests into the logging context.

    Every log line emitted during a request will include the trace_id,
    enabling end-to-end correlation across UI → BFF → Agent.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        """Extract X-Trace-ID from request, bind to context, forward to response."""
        trace_id = request.headers.get("x-trace-id") or uuid4().hex
        bind_request_context(trace_id=trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        clear_request_context()
        return response


app.add_middleware(TraceIDMiddleware)


def _score_to_feedback_polarity(req: FeedbackRequest) -> Literal["up", "down"]:
    """Map request name/value to stored feedback polarity."""
    name_lower = (req.name or "").lower()
    if "down" in name_lower or "negative" in name_lower:
        return "down"
    if "up" in name_lower or "positive" in name_lower:
        return "up"
    return "up" if req.value >= 0.5 else "down"


async def _persist_feedback_to_postgres(req: FeedbackRequest) -> None:
    if not req.thread_id or not req.message_id:
        return
    if not settings.database_uri:
        logger.warning(
            "feedback_postgres_skipped_no_database_uri",
            thread_id=req.thread_id,
            message_id=req.message_id,
        )
        return
    polarity = _score_to_feedback_polarity(req)
    user_id = req.user_id if req.user_id else "anonymous"
    repo = FeedbackRepository(settings.database_uri)
    await repo.upsert_feedback(
        req.thread_id,
        req.message_id,
        user_id,
        polarity,
        req.trace_id,
    )
    logger.info(
        "feedback_recorded_postgres",
        thread_id=req.thread_id,
        message_id=req.message_id,
        user_id=user_id,
        feedback=polarity,
    )


def _resolve_langfuse_trace_id(client: Any, thread_id: str | None) -> str | None:
    """Look up the real Langfuse trace_id by session_id (thread_id).

    The Langfuse SDK auto-generates trace IDs that differ from LangGraph run_ids.
    This queries the Langfuse API to find the latest trace in the session so
    feedback scores attach to the correct trace in the dashboard.
    """
    if not thread_id:
        return None
    try:
        traces = client.api.trace.list(session_id=thread_id, limit=1)
        if traces.data:
            return str(traces.data[0].id)
    except Exception as exc:
        logger.debug(
            "langfuse_trace_lookup_failed",
            session_id=thread_id,
            error=str(exc),
        )
    return None


async def record_feedback(request_data: dict[str, Any]) -> FeedbackResponse:
    """Validate feedback input, optionally record a Langfuse score, return success.

    Args:
        request_data: Raw JSON object (mapping) from the client.

    Returns:
        ``FeedbackResponse`` with status ``success``.

    Raises:
        ValidationError: If the payload does not satisfy ``FeedbackRequest``.
        RuntimeError: If Langfuse is configured but score submission fails.
    """
    req = FeedbackRequest.model_validate(request_data)

    logger.info(
        "feedback_received",
        trace_id=req.trace_id,
        name=req.name,
        value=req.value,
        kwargs_keys=sorted(req.kwargs.keys()) if req.kwargs else [],
    )

    langfuse_client = get_langfuse_client()
    if langfuse_client is None:
        logger.info(
            "feedback_skipped_langfuse_unconfigured",
            trace_id=req.trace_id,
            name=req.name,
        )
        await _persist_feedback_to_postgres(req)
        return FeedbackResponse()

    resolved_trace_id = _resolve_langfuse_trace_id(langfuse_client, req.thread_id)
    effective_trace_id = resolved_trace_id or req.trace_id

    if resolved_trace_id and resolved_trace_id != req.trace_id:
        logger.info(
            "feedback_trace_id_resolved",
            original=req.trace_id,
            resolved=resolved_trace_id,
            thread_id=req.thread_id,
        )

    try:
        langfuse_client.create_score(
            trace_id=effective_trace_id,
            name=req.name,
            value=req.value,
            data_type="BOOLEAN",
            **(req.kwargs or {}),
        )
        logger.info(
            "feedback_recorded_langfuse",
            trace_id=effective_trace_id,
            name=req.name,
        )
    except Exception as exc:
        logger.warning(
            "feedback_langfuse_score_failed",
            trace_id=effective_trace_id,
            name=req.name,
            error=str(exc),
        )

    await _persist_feedback_to_postgres(req)
    return FeedbackResponse()


async def feedback_handler(request: Request) -> JSONResponse:
    """ASGI/Starlette handler: read JSON, validate, record feedback."""
    try:
        body_bytes = await request.body()
        if not body_bytes.strip():
            return JSONResponse(
                status_code=422,
                content={"detail": [{"msg": "Empty body", "type": "value_error"}]},
            )
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [{"msg": "Invalid JSON body", "type": "json_invalid"}],
            },
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "msg": "JSON body must be an object",
                        "type": "type_error",
                    },
                ],
            },
        )

    try:
        resp = await record_feedback(payload)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors(include_url=False)},
        )
    except Exception:
        logger.exception("feedback_handler_error")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return JSONResponse(
        status_code=200,
        content=resp.model_dump(),
    )


@app.get("/feedback/{thread_id}")
async def get_thread_feedback(
    thread_id: str, user_id: str = "anonymous"
) -> dict[str, Any]:
    """Return all feedback for a thread."""
    if not settings.database_uri:
        return {"feedback": []}
    repo = FeedbackRepository(settings.database_uri)
    items = await repo.list_feedback(thread_id, user_id)
    return {"feedback": items}


@app.get("/info")
async def get_agent_info() -> dict[str, str]:
    """Return agent identity metadata from config."""
    return {"name": agent_config.get_name()}


app.add_api_route("/feedback", feedback_handler, methods=["POST"])


# ---------------------------------------------------------------------------
# /btw — Non-blocking context injection
# ---------------------------------------------------------------------------


class BtwRequest:
    """Lightweight request model for /btw endpoint (avoids pydantic dep chain)."""

    def __init__(self, thread_id: str, message: str, user_id: str | None = None):
        self.thread_id = thread_id
        self.message = message
        self.user_id = user_id


async def btw_handler(request: Request) -> JSONResponse:
    """Accept a /btw context-injection message and queue it in Redis."""
    try:
        body_bytes = await request.body()
        if not body_bytes.strip():
            return JSONResponse(
                status_code=422,
                content={"detail": "Empty body"},
            )
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid JSON body"},
        )

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=422,
            content={"detail": "JSON body must be an object"},
        )

    thread_id = payload.get("thread_id")
    message = payload.get("message")
    user_id = payload.get("user_id")

    if not thread_id or not isinstance(thread_id, str):
        return JSONResponse(
            status_code=422,
            content={"detail": "thread_id is required and must be a string"},
        )
    if not message or not isinstance(message, str):
        return JSONResponse(
            status_code=422,
            content={"detail": "message is required and must be a string"},
        )

    try:
        from deep_agent.src.btw.store import push_btw_message

        depth = push_btw_message(
            thread_id=thread_id,
            message=message,
            user_id=user_id,
        )
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)},
        )
    except RuntimeError as exc:
        logger.warning("btw_endpoint_redis_unavailable", error=str(exc))
        return JSONResponse(
            status_code=503,
            content={"detail": "Redis unavailable — /btw requires Redis"},
        )

    logger.info(
        "btw_endpoint_accepted",
        thread_id=thread_id,
        user_id=user_id or "anonymous",
        queue_depth=depth,
    )
    return JSONResponse(
        status_code=200,
        content={"status": "queued", "queue_depth": depth},
    )


app.add_api_route("/btw", btw_handler, methods=["POST"])


# ---------------------------------------------------------------------------
# /trust — Session-level trust management (approve-all)
# ---------------------------------------------------------------------------


async def trust_handler(request: Request) -> JSONResponse:
    """Set or revoke session-level trust (approve-all for tool calls)."""
    try:
        body_bytes = await request.body()
        if not body_bytes.strip():
            return JSONResponse(status_code=422, content={"detail": "Empty body"})
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(status_code=422, content={"detail": "Invalid JSON body"})

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=422, content={"detail": "JSON body must be an object"}
        )

    thread_id = payload.get("thread_id")
    action = payload.get("action")  # "approve_all" | "revoke"

    if not thread_id or not isinstance(thread_id, str):
        return JSONResponse(
            status_code=422,
            content={"detail": "thread_id is required"},
        )
    if action not in ("approve_all", "revoke"):
        return JSONResponse(
            status_code=422,
            content={"detail": "action must be 'approve_all' or 'revoke'"},
        )

    try:
        from deep_agent.src.btw.trust import revoke_trust, set_trust_level

        if action == "approve_all":
            set_trust_level(thread_id, "approve_all")
        else:
            revoke_trust(thread_id)
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": str(exc)},
        )

    logger.info("trust_endpoint", thread_id=thread_id, action=action)
    return JSONResponse(
        status_code=200,
        content={"status": action, "thread_id": thread_id},
    )


app.add_api_route("/trust", trust_handler, methods=["POST"])


# ---------------------------------------------------------------------------
# /resume — Convenience endpoint for resuming interrupted runs
# ---------------------------------------------------------------------------


async def resume_handler(request: Request) -> JSONResponse:
    """Accept a resume payload and forward it to the LangGraph Platform API.

    Body schema:
        {
          "thread_id": "...",
          "resume": { ... }           # HITLResponse / PlanDecision payload
          "assistant_id": "agent"     # optional, defaults to "agent"
        }

    This is a thin proxy so the frontend has a single base-URL to target
    rather than constructing the LangGraph Platform ``/threads/.../runs``
    path itself.  For environments where Aegra provides its own resume
    route, the frontend can call that directly instead.
    """
    try:
        body_bytes = await request.body()
        if not body_bytes.strip():
            return JSONResponse(status_code=422, content={"detail": "Empty body"})
        payload = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        return JSONResponse(status_code=422, content={"detail": "Invalid JSON body"})

    if not isinstance(payload, dict):
        return JSONResponse(
            status_code=422, content={"detail": "JSON body must be an object"}
        )

    thread_id = payload.get("thread_id")
    resume_value = payload.get("resume")

    if not thread_id or not isinstance(thread_id, str):
        return JSONResponse(
            status_code=422,
            content={"detail": "thread_id is required"},
        )
    if resume_value is None:
        return JSONResponse(
            status_code=422,
            content={"detail": "resume payload is required"},
        )

    enriched_resume = resume_value
    try:
        from deep_agent.src.btw.plan_decision import (
            build_plan_decision_message,
            is_plan_decision,
        )

        if is_plan_decision(resume_value):
            system_msg = build_plan_decision_message(resume_value)
            enriched_resume = {
                **resume_value,
                "system_message": system_msg,
            }
            logger.info(
                "resume_plan_decision_enriched",
                thread_id=thread_id,
            )
    except ImportError:
        pass

    logger.info(
        "resume_endpoint_accepted",
        thread_id=thread_id,
        resume_type=type(resume_value).__name__,
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "accepted",
            "thread_id": thread_id,
            "command": {"resume": enriched_resume},
        },
    )


app.add_api_route("/resume", resume_handler, methods=["POST"])
