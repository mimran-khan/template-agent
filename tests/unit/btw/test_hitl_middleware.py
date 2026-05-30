"""Unit tests for TrustAwareHITLMiddleware."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def _mock_trust_module():
    """Patch trust functions at the middleware import location."""
    with patch(
        "deep_agent.src.btw.hitl_middleware.is_trusted"
    ) as mock_is_trusted:
        yield mock_is_trusted


@pytest.fixture()
def runtime_with_thread():
    """Build a mock runtime with configurable thread_id."""
    rt = MagicMock()
    rt.config = {"configurable": {"thread_id": "thread-abc"}}
    return rt


@pytest.fixture()
def runtime_without_thread():
    rt = MagicMock()
    rt.config = {"configurable": {}}
    return rt


class TestTrustAwareHITLMiddleware:
    def _make_middleware(self):
        from deep_agent.src.btw.hitl_middleware import (
            TrustAwareHITLMiddleware,
        )

        return TrustAwareHITLMiddleware(
            interrupt_on={"send_email": True, "deploy": True}
        )

    def test_auto_approves_when_trusted(
        self, _mock_trust_module, runtime_with_thread
    ):
        """When session trust is active, after_model returns None (skip interrupt)."""
        _mock_trust_module.return_value = True
        mw = self._make_middleware()

        state = {"messages": [MagicMock()]}
        result = mw.after_model(state, runtime_with_thread)

        assert result is None
        _mock_trust_module.assert_called_once_with("thread-abc")

    def test_delegates_to_parent_when_not_trusted(
        self, _mock_trust_module, runtime_with_thread
    ):
        """When no trust, delegates to parent (which checks tool calls)."""
        _mock_trust_module.return_value = False
        mw = self._make_middleware()

        state = {"messages": []}
        result = mw.after_model(state, runtime_with_thread)

        assert result is None
        _mock_trust_module.assert_called_once_with("thread-abc")

    def test_delegates_when_no_thread_id(
        self, _mock_trust_module, runtime_without_thread
    ):
        """When thread_id is missing, delegates to parent."""
        mw = self._make_middleware()

        state = {"messages": []}
        result = mw.after_model(state, runtime_without_thread)

        assert result is None
        _mock_trust_module.assert_not_called()


class TestExtractThreadId:
    def test_extracts_from_runtime_config(self):
        from deep_agent.src.btw.hitl_middleware import _extract_thread_id

        rt = MagicMock()
        rt.config = {"configurable": {"thread_id": "t-123"}}
        assert _extract_thread_id(rt) == "t-123"

    def test_returns_none_for_missing_configurable(self):
        from deep_agent.src.btw.hitl_middleware import _extract_thread_id

        rt = MagicMock()
        rt.config = {}
        assert _extract_thread_id(rt) is None

    def test_returns_none_for_no_config(self):
        from deep_agent.src.btw.hitl_middleware import _extract_thread_id

        rt = MagicMock(spec=[])
        assert _extract_thread_id(rt) is None
