"""Unit tests for plan_decision module."""

from __future__ import annotations

import pytest

from deep_agent.src.btw.plan_decision import (
    build_plan_decision_message,
    is_plan_decision,
)


class TestIsPlanDecision:
    def test_valid_plan_decision(self):
        assert is_plan_decision({"type": "plan_decision", "approved_steps": [1, 2]})

    def test_wrong_type(self):
        assert not is_plan_decision({"type": "tool_approval"})

    def test_not_dict(self):
        assert not is_plan_decision("plan_decision")

    def test_missing_type(self):
        assert not is_plan_decision({"approved_steps": [1]})

    def test_none(self):
        assert not is_plan_decision(None)


class TestBuildPlanDecisionMessage:
    def test_approved_only(self):
        msg = build_plan_decision_message({
            "approved_steps": [1, 2, 3],
            "rejected_steps": [],
            "added_steps": [],
        })
        assert "APPROVED steps: 1, 2, 3" in msg
        assert "REJECTED" not in msg
        assert "Re-plan" in msg

    def test_rejected_only(self):
        msg = build_plan_decision_message({
            "approved_steps": [],
            "rejected_steps": [2, 3],
            "added_steps": [],
        })
        assert "REJECTED steps: 2, 3" in msg
        assert "APPROVED" not in msg

    def test_mixed_approve_reject(self):
        msg = build_plan_decision_message({
            "approved_steps": [1, 2],
            "rejected_steps": [3],
            "added_steps": [],
        })
        assert "APPROVED steps: 1, 2" in msg
        assert "REJECTED steps: 3" in msg

    def test_added_steps(self):
        msg = build_plan_decision_message({
            "approved_steps": [1],
            "rejected_steps": [],
            "added_steps": [
                {"description": "Export to CSV", "insert_after": 2},
                {"description": "Notify manager", "insert_after": 0},
            ],
        })
        assert "Export to CSV" in msg
        assert "after step 2" in msg
        assert "Notify manager" in msg
        assert "at the beginning" in msg

    def test_feedback_included(self):
        msg = build_plan_decision_message({
            "approved_steps": [1],
            "rejected_steps": [],
            "added_steps": [],
            "feedback": "Please be careful with the database",
        })
        assert "Please be careful with the database" in msg
        assert "Additional feedback" in msg

    def test_empty_decision(self):
        msg = build_plan_decision_message({
            "approved_steps": [],
            "rejected_steps": [],
            "added_steps": [],
        })
        assert "Plan Review Decision" in msg
        assert "Re-plan" in msg

    def test_steps_sorted(self):
        msg = build_plan_decision_message({
            "approved_steps": [3, 1, 2],
            "rejected_steps": [5, 4],
            "added_steps": [],
        })
        assert "APPROVED steps: 1, 2, 3" in msg
        assert "REJECTED steps: 4, 5" in msg

    def test_full_decision(self):
        msg = build_plan_decision_message({
            "type": "plan_decision",
            "approved_steps": [1, 2],
            "rejected_steps": [3],
            "added_steps": [
                {"description": "Export results to CSV", "insert_after": 2},
            ],
            "feedback": "Skip emails, export instead",
        })
        assert "APPROVED steps: 1, 2" in msg
        assert "REJECTED steps: 3" in msg
        assert "Export results to CSV" in msg
        assert "after step 2" in msg
        assert "Skip emails, export instead" in msg
