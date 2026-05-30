"""BtwMiddleware — non-blocking context injection via Redis side-channel.

Hooks into `before_model()` so that every LLM call first drains the
/btw Redis queue for the current thread.  If messages are pending they
are injected as a SystemMessage; otherwise the middleware is a no-op.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import SystemMessage

from deep_agent.src.btw.store import consume_btw_messages
from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()


class BtwMiddleware:
    """Inject queued /btw messages into the LLM context.

    This middleware runs *before* each model call.  It reads all pending
    messages from the Redis queue, formats them as a single
    ``SystemMessage``, and appends it to the messages list.  When the
    queue is empty the cost is one ``LRANGE`` on an empty key (~0.1 ms).
    """

    def before_model(
        self,
        *,
        state: dict[str, Any],
        config: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Drain /btw queue and inject as SystemMessage.

        Args:
            state: Current agent state containing ``messages``.
            config: Run config with ``configurable.thread_id``.

        Returns:
            The (possibly modified) state dict.
        """
        thread_id = _extract_thread_id(config)
        if thread_id is None:
            return state

        try:
            messages = consume_btw_messages(thread_id)
        except Exception:
            logger.debug("btw_consume_failed", exc_info=True)
            return state

        if not messages:
            return state

        injection = _format_injection(messages)
        state_messages = state.get("messages", [])
        state_messages.append(SystemMessage(content=injection))
        state["messages"] = state_messages

        logger.info(
            "btw_injected",
            thread_id=thread_id,
            message_count=len(messages),
        )
        return state


def _extract_thread_id(config: dict[str, Any]) -> str | None:
    """Extract thread_id from LangGraph run config."""
    configurable = config.get("configurable", {})
    thread_id = configurable.get("thread_id")
    if not thread_id:
        return None
    return str(thread_id)


def _format_injection(messages: list[dict[str, Any]]) -> str:
    """Format consumed /btw messages into a system-message string.

    Multiple messages are combined chronologically so the LLM sees the
    full context in a single injection.
    """
    if len(messages) == 1:
        return (
            f"[Real-time user update]: {messages[0]['message']}"
        )

    parts = [
        f"[Real-time user update {i + 1}/{len(messages)}]: {m['message']}"
        for i, m in enumerate(messages)
    ]
    return "\n".join(parts)
