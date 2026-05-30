"""Convert a plan-review resume payload into a SystemMessage for the LLM.

When a user reviews a plan (approve/reject/add steps), the frontend sends
a ``plan_decision`` resume payload.  This module converts that payload into
a clear ``SystemMessage`` so the LLM knows which steps to execute, skip,
and what new steps the user requested.
"""

from __future__ import annotations

from typing import Any

from deep_agent.utils.pylogger import get_python_logger

logger = get_python_logger()


def build_plan_decision_message(decision: dict[str, Any]) -> str:
    """Build a human-readable instruction string from a plan decision payload.

    Args:
        decision: Dict with keys ``approved_steps``, ``rejected_steps``,
            ``added_steps``, and optionally ``feedback``.

    Returns:
        Formatted instruction string to be wrapped in a SystemMessage.
    """
    approved: list[int] = decision.get("approved_steps", [])
    rejected: list[int] = decision.get("rejected_steps", [])
    added: list[dict[str, Any]] = decision.get("added_steps", [])
    feedback: str = decision.get("feedback", "")

    parts: list[str] = ["[Plan Review Decision from User]"]

    if approved:
        step_list = ", ".join(str(s) for s in sorted(approved))
        parts.append(f"APPROVED steps: {step_list} — execute these as planned.")

    if rejected:
        step_list = ", ".join(str(s) for s in sorted(rejected))
        parts.append(f"REJECTED steps: {step_list} — skip these entirely.")

    if added:
        parts.append("USER-ADDED steps (incorporate into your plan):")
        for i, step in enumerate(added, start=1):
            desc = step.get("description", "")
            insert_after = step.get("insert_after", "end")
            if insert_after == 0:
                position = "at the beginning"
            else:
                position = f"after step {insert_after}"
            parts.append(f"  {i}. {desc} (insert {position})")

    if feedback:
        parts.append(f"Additional feedback: {feedback}")

    parts.append(
        "Re-plan incorporating the above decisions, then proceed with execution."
    )

    message = "\n".join(parts)

    logger.info(
        "plan_decision_message_built",
        approved_count=len(approved),
        rejected_count=len(rejected),
        added_count=len(added),
        has_feedback=bool(feedback),
    )

    return message


def is_plan_decision(resume_value: Any) -> bool:
    """Check if a resume payload is a plan decision."""
    if not isinstance(resume_value, dict):
        return False
    return resume_value.get("type") == "plan_decision"
