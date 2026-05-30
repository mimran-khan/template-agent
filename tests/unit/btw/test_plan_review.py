"""Unit tests for PlanReviewMiddleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from deep_agent.src.btw.plan_review import (
    PlanReviewMiddleware,
    _build_plan_payload,
    _detect_tool_in_step,
    _extract_content,
    _extract_steps,
    _has_trigger_keyword,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_with_thread() -> dict[str, Any]:
    return {"configurable": {"thread_id": "thread-plan-123"}}


@pytest.fixture()
def middleware() -> PlanReviewMiddleware:
    return PlanReviewMiddleware(min_steps=3)


PLAN_TEXT_3_STEPS = """\
I'll do the following plan to complete your request:

1. Query the database for matching records
2. Filter the results by date range
3. Send notification emails to all matches
"""

PLAN_TEXT_5_STEPS = """\
Here are the steps I'll follow:

1. Gather requirements from the user
2. Design the schema
3. Implement the API using `create_api`
4. Write tests
5. Deploy the service using deploy_tool
"""

PLAN_TEXT_2_STEPS = """\
Here's my plan:

1. Read the file
2. Parse the contents
"""

NO_PLAN_TEXT = "Sure, I can help you with that. Let me look into it."

PLAN_WITHOUT_KEYWORDS = """\
Here's what I need to do:

1. Read the file
2. Parse the contents
3. Generate the output
"""


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestExtractContent:
    def test_string_content(self):
        msg = MagicMock()
        msg.content = "hello"
        assert _extract_content(msg) == "hello"

    def test_list_content(self):
        msg = MagicMock()
        msg.content = [{"text": "part1"}, {"text": "part2"}]
        result = _extract_content(msg)
        assert "part1" in result
        assert "part2" in result

    def test_no_content_attr(self):
        msg = object()
        assert _extract_content(msg) is None


class TestHasTriggerKeyword:
    def test_keyword_present(self):
        assert _has_trigger_keyword("Here is the plan:", ("plan",))

    def test_keyword_case_insensitive(self):
        assert _has_trigger_keyword("Here are the STEPS:", ("steps",))

    def test_keyword_absent(self):
        assert not _has_trigger_keyword("Just do it.", ("plan", "steps"))


class TestExtractSteps:
    def test_numbered_steps(self):
        steps = _extract_steps(PLAN_TEXT_3_STEPS)
        assert len(steps) == 3
        assert steps[0]["step"] == 1
        assert "database" in steps[0]["description"].lower()

    def test_five_steps(self):
        steps = _extract_steps(PLAN_TEXT_5_STEPS)
        assert len(steps) == 5

    def test_two_steps(self):
        steps = _extract_steps(PLAN_TEXT_2_STEPS)
        assert len(steps) == 2

    def test_no_steps(self):
        steps = _extract_steps(NO_PLAN_TEXT)
        assert len(steps) == 0

    def test_bullet_steps(self):
        text = "My plan:\n- Step one\n- Step two\n- Step three"
        steps = _extract_steps(text)
        assert len(steps) == 3


class TestDetectToolInStep:
    def test_backtick_tool(self):
        assert _detect_tool_in_step("Use `send_email` to notify") == "send_email"

    def test_using_tool(self):
        assert _detect_tool_in_step("Deploy using deploy_tool") == "deploy_tool"

    def test_using_common_word(self):
        assert _detect_tool_in_step("Process using the data") is None

    def test_no_tool(self):
        assert _detect_tool_in_step("Just read the file") is None


class TestBuildPlanPayload:
    def test_payload_structure(self):
        steps = [{"step": 1, "description": "test", "tool": None}]
        payload = _build_plan_payload(steps, "original text")
        assert payload["interrupt_type"] == "plan_review"
        assert payload["plan_steps"] == steps
        assert payload["resumable"] is True
        assert "original_text" in payload


# ---------------------------------------------------------------------------
# Middleware integration tests
# ---------------------------------------------------------------------------


class TestPlanReviewMiddleware:
    def test_no_messages(self, middleware, config_with_thread):
        result = middleware.after_model(state={"messages": []}, config=config_with_thread)
        assert result is None

    def test_no_plan_in_message(self, middleware, config_with_thread):
        msg = MagicMock()
        msg.content = NO_PLAN_TEXT
        result = middleware.after_model(
            state={"messages": [msg]}, config=config_with_thread
        )
        assert result is None

    def test_plan_below_min_steps(self, middleware, config_with_thread):
        msg = MagicMock()
        msg.content = PLAN_TEXT_2_STEPS
        result = middleware.after_model(
            state={"messages": [msg]}, config=config_with_thread
        )
        assert result is None

    def test_plan_without_trigger_keyword(self, middleware, config_with_thread):
        msg = MagicMock()
        msg.content = PLAN_WITHOUT_KEYWORDS
        result = middleware.after_model(
            state={"messages": [msg]}, config=config_with_thread
        )
        assert result is None

    def test_plan_triggers_interrupt(self, middleware, config_with_thread):
        """Plan with 3+ steps and trigger keyword should call interrupt()."""
        mock_interrupt = MagicMock(return_value=None)

        msg = MagicMock()
        msg.content = PLAN_TEXT_3_STEPS

        with patch.dict(
            "sys.modules",
            {"langgraph.types": MagicMock(interrupt=mock_interrupt)},
        ):
            import importlib
            from deep_agent.src.btw import plan_review as pr_mod

            importlib.reload(pr_mod)
            mw = pr_mod.PlanReviewMiddleware(min_steps=3)
            result = mw.after_model(
                state={"messages": [msg]}, config=config_with_thread
            )

        mock_interrupt.assert_called_once()
        payload = mock_interrupt.call_args[0][0]
        assert "plan_steps" in payload
        assert len(payload["plan_steps"]) == 3
        assert payload["resumable"] is True
        assert result is None

    def test_five_step_plan(self, middleware, config_with_thread):
        mock_interrupt = MagicMock(return_value=None)

        msg = MagicMock()
        msg.content = PLAN_TEXT_5_STEPS

        with patch.dict(
            "sys.modules",
            {"langgraph.types": MagicMock(interrupt=mock_interrupt)},
        ):
            import importlib
            from deep_agent.src.btw import plan_review as pr_mod

            importlib.reload(pr_mod)
            mw = pr_mod.PlanReviewMiddleware(min_steps=3)
            mw.after_model(
                state={"messages": [msg]}, config=config_with_thread
            )

        mock_interrupt.assert_called_once()
        payload = mock_interrupt.call_args[0][0]
        assert len(payload["plan_steps"]) == 5
        steps_with_tools = [s for s in payload["plan_steps"] if s["tool"]]
        assert len(steps_with_tools) >= 1

    def test_custom_min_steps(self, config_with_thread):
        mw = PlanReviewMiddleware(min_steps=5)
        msg = MagicMock()
        msg.content = PLAN_TEXT_3_STEPS
        result = mw.after_model(
            state={"messages": [msg]}, config=config_with_thread
        )
        assert result is None

    def test_custom_trigger_keywords(self, config_with_thread):
        mw = PlanReviewMiddleware(
            min_steps=3, trigger_keywords=["custom_keyword"]
        )
        msg = MagicMock()
        msg.content = PLAN_TEXT_3_STEPS
        result = mw.after_model(
            state={"messages": [msg]}, config=config_with_thread
        )
        assert result is None

    def test_interrupt_import_failure_graceful(self, config_with_thread):
        """If langgraph.types.interrupt can't be imported, fail gracefully."""
        import importlib
        import sys

        msg = MagicMock()
        msg.content = PLAN_TEXT_3_STEPS

        saved = sys.modules.get("langgraph.types")
        sys.modules["langgraph.types"] = None  # type: ignore[assignment]
        try:
            from deep_agent.src.btw import plan_review as pr_mod

            importlib.reload(pr_mod)
            mw = pr_mod.PlanReviewMiddleware(min_steps=3)
            result = mw.after_model(
                state={"messages": [msg]}, config=config_with_thread
            )
            assert result is None
        finally:
            if saved is not None:
                sys.modules["langgraph.types"] = saved
            else:
                sys.modules.pop("langgraph.types", None)
