"""Trust-aware HITL middleware.

Subclasses ``HumanInTheLoopMiddleware`` so that when a session has
``approve_all`` trust, tool calls are auto-approved without
calling ``interrupt()``.
"""

from __future__ import annotations

from typing import Any, TypeVar

from langchain.agents.middleware.human_in_the_loop import (
    HumanInTheLoopMiddleware,
    InterruptOnConfig,
)
from langchain.agents.middleware.types import AgentState
from langgraph.runtime import Runtime

from deep_agent.src.btw.trust import is_trusted
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

ContextT = TypeVar("ContextT")


class TrustAwareHITLMiddleware(HumanInTheLoopMiddleware):
    """HITL middleware that respects session-level ``approve_all`` trust.

    When the Redis key ``trust:{thread_id}`` is set to ``"approve_all"``,
    all tool calls bypass the interrupt gate and execute immediately.
    Otherwise, the parent :class:`HumanInTheLoopMiddleware` behaviour
    applies (interrupt + wait for user decision).
    """

    def after_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[ContextT],
    ) -> dict[str, Any] | None:
        thread_id = _extract_thread_id(runtime)
        if thread_id and is_trusted(thread_id):
            logger.info(
                "hitl_auto_approved",
                thread_id=thread_id,
                reason="session_trust_approve_all",
            )
            return None
        return super().after_model(state, runtime)


def _extract_thread_id(runtime: Runtime[Any]) -> str | None:
    """Best-effort extraction of thread_id from the runtime config."""
    try:
        cfg = getattr(runtime, "config", None) or {}
        configurable = cfg.get("configurable", {})
        return configurable.get("thread_id")
    except Exception:
        return None
