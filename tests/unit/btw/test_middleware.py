"""Unit tests for BtwMiddleware."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from deep_agent.src.btw.middleware import BtwMiddleware, _extract_thread_id, _format_injection


@pytest.fixture()
def middleware():
    return BtwMiddleware()


@pytest.fixture()
def config():
    return {"configurable": {"thread_id": "t1"}}


@pytest.fixture()
def state():
    return {"messages": [HumanMessage(content="hello")]}


class TestExtractThreadId:
    def test_extracts_thread_id(self):
        assert _extract_thread_id({"configurable": {"thread_id": "abc"}}) == "abc"

    def test_returns_none_when_missing(self):
        assert _extract_thread_id({"configurable": {}}) is None

    def test_returns_none_when_no_configurable(self):
        assert _extract_thread_id({}) is None

    def test_coerces_int_to_str(self):
        assert _extract_thread_id({"configurable": {"thread_id": 42}}) == "42"


class TestFormatInjection:
    def test_single_message(self):
        result = _format_injection([{"message": "hello"}])
        assert result == "[Real-time user update]: hello"

    def test_multiple_messages(self):
        msgs = [{"message": "a"}, {"message": "b"}]
        result = _format_injection(msgs)
        assert "[Real-time user update 1/2]: a" in result
        assert "[Real-time user update 2/2]: b" in result


class TestBtwMiddlewareBeforeModel:
    def test_injects_messages_into_state(self, middleware, config, state):
        msgs = [{"message": "use the production DB", "user_id": "u1", "timestamp": 1.0}]
        with patch("deep_agent.src.btw.middleware.consume_btw_messages", return_value=msgs):
            result = middleware.before_model(state=state, config=config)
        assert len(result["messages"]) == 2
        injected = result["messages"][-1]
        assert isinstance(injected, SystemMessage)
        assert "use the production DB" in injected.content

    def test_noop_when_queue_empty(self, middleware, config, state):
        with patch("deep_agent.src.btw.middleware.consume_btw_messages", return_value=[]):
            result = middleware.before_model(state=state, config=config)
        assert len(result["messages"]) == 1

    def test_noop_when_no_thread_id(self, middleware, state):
        config_no_tid = {"configurable": {}}
        result = middleware.before_model(state=state, config=config_no_tid)
        assert len(result["messages"]) == 1

    def test_noop_when_consume_raises(self, middleware, config, state):
        with patch(
            "deep_agent.src.btw.middleware.consume_btw_messages",
            side_effect=Exception("redis boom"),
        ):
            result = middleware.before_model(state=state, config=config)
        assert len(result["messages"]) == 1

    def test_multiple_messages_single_injection(self, middleware, config, state):
        msgs = [
            {"message": "first", "user_id": "u1", "timestamp": 1.0},
            {"message": "second", "user_id": "u1", "timestamp": 2.0},
        ]
        with patch("deep_agent.src.btw.middleware.consume_btw_messages", return_value=msgs):
            result = middleware.before_model(state=state, config=config)
        assert len(result["messages"]) == 2
        injected = result["messages"][-1]
        assert "1/2" in injected.content
        assert "2/2" in injected.content

    def test_preserves_existing_messages(self, middleware, config):
        existing = [HumanMessage(content="a"), HumanMessage(content="b")]
        state = {"messages": list(existing)}
        msgs = [{"message": "inject", "user_id": "u1", "timestamp": 1.0}]
        with patch("deep_agent.src.btw.middleware.consume_btw_messages", return_value=msgs):
            result = middleware.before_model(state=state, config=config)
        assert len(result["messages"]) == 3
        assert result["messages"][0].content == "a"
        assert result["messages"][1].content == "b"

    def test_creates_messages_list_if_missing(self, middleware, config):
        state = {}
        msgs = [{"message": "inject", "user_id": "u1", "timestamp": 1.0}]
        with patch("deep_agent.src.btw.middleware.consume_btw_messages", return_value=msgs):
            result = middleware.before_model(state=state, config=config)
        assert len(result["messages"]) == 1
