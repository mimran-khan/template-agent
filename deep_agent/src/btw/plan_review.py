"""PlanReviewMiddleware — interrupt when the LLM proposes a multi-step plan.

Hooks into ``after_model()`` to detect plans in the LLM's output.  When a
plan with enough steps is found, ``interrupt()`` is called with a structured
``plan_review`` payload so the frontend can present an approval UI.

Opt-in via ``plan_review.enabled: true`` in ``agent.yaml``.
"""

from __future__ import annotations

import re
from typing import Any

from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()

_DEFAULT_MIN_STEPS = 3
_DEFAULT_TRIGGER_KEYWORDS = ("plan", "steps", "I'll do the following")

_NUMBERED_STEP_RE = re.compile(
    r"^\s*(?:\d+[\.\)]\s+|\*\s+|-\s+)(.+)$",
    re.MULTILINE,
)


class PlanReviewMiddleware:
    """Detect multi-step plans and interrupt for user review.

    The middleware inspects the last AI message after each model call.
    If the message contains a numbered/bulleted list with at least
    ``min_steps`` entries **and** one of the trigger keywords appears
    in the surrounding text, an ``interrupt()`` is raised with a
    structured plan payload.
    """

    def __init__(
        self,
        *,
        min_steps: int = _DEFAULT_MIN_STEPS,
        trigger_keywords: tuple[str, ...] | list[str] = _DEFAULT_TRIGGER_KEYWORDS,
    ) -> None:
        self.min_steps = min_steps
        self.trigger_keywords = tuple(kw.lower() for kw in trigger_keywords)

    def after_model(
        self,
        *,
        state: dict[str, Any],
        config: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Check LLM output for a plan and interrupt if found.

        Returns ``None`` (no state modification) when no plan is detected
        or the plan is too small.  When a qualifying plan is found,
        raises ``interrupt()`` with the plan payload.
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        content = _extract_content(last_msg)
        if not content:
            return None

        if not _has_trigger_keyword(content, self.trigger_keywords):
            return None

        steps = _extract_steps(content)
        if len(steps) < self.min_steps:
            return None

        plan_payload = _build_plan_payload(steps, content)

        logger.info(
            "plan_review_triggered",
            step_count=len(steps),
            thread_id=config.get("configurable", {}).get("thread_id"),
        )

        try:
            from langgraph.types import interrupt

            interrupt(plan_payload)
        except ImportError:
            logger.warning(
                "plan_review_interrupt_unavailable",
                reason="langgraph.types.interrupt not importable",
            )
            return None

        return None


def _extract_content(message: Any) -> str | None:
    """Get string content from a LangChain message object."""
    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            ]
            return "\n".join(text_parts)
    return None


def _has_trigger_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    """Check whether the text contains any of the plan-trigger keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _extract_steps(text: str) -> list[dict[str, Any]]:
    """Parse numbered/bulleted steps from text.

    Returns a list of dicts with ``step`` (1-indexed) and ``description``.
    """
    matches = _NUMBERED_STEP_RE.findall(text)
    steps: list[dict[str, Any]] = []
    for i, desc in enumerate(matches, start=1):
        desc_clean = desc.strip()
        tool = _detect_tool_in_step(desc_clean)
        steps.append({
            "step": i,
            "description": desc_clean,
            "tool": tool,
        })
    return steps


def _detect_tool_in_step(description: str) -> str | None:
    """Heuristic: detect tool name references in a step description.

    Looks for common patterns like ``using tool_name`` or backtick-quoted
    tool names.  Returns ``None`` if no tool is detected.
    """
    backtick_match = re.search(r"`(\w+)`", description)
    if backtick_match:
        return backtick_match.group(1)

    using_match = re.search(r"\busing\s+(\w+)\b", description, re.IGNORECASE)
    if using_match:
        candidate = using_match.group(1)
        if candidate.lower() not in ("the", "a", "an", "this", "that"):
            return candidate

    return None


def _build_plan_payload(
    steps: list[dict[str, Any]],
    original_text: str,
) -> dict[str, Any]:
    """Build the structured interrupt payload for plan review."""
    return {
        "interrupt_type": "plan_review",
        "plan_steps": steps,
        "original_text": original_text,
        "resumable": True,
    }
