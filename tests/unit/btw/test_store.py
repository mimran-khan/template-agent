"""Unit tests for btw Redis store module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from deep_agent.src.btw.store import (
    MAX_MESSAGE_LENGTH,
    MAX_QUEUE_DEPTH,
    consume_btw_messages,
    get_queue_depth,
    push_btw_message,
)


@pytest.fixture()
def mock_redis():
    """Provide a mock Redis client that is returned by get_redis_client()."""
    client = MagicMock()
    pipe = MagicMock()
    client.pipeline.return_value = pipe
    pipe.execute.return_value = [1, True, True]
    with patch("deep_agent.src.btw.store.get_redis_client", return_value=client):
        yield client, pipe


class TestPushBtwMessage:
    def test_push_returns_queue_depth(self, mock_redis):
        client, pipe = mock_redis
        pipe.execute.return_value = [3, True, True]
        depth = push_btw_message("t1", "hello")
        assert depth == 3

    def test_push_calls_rpush_ltrim_expire(self, mock_redis):
        client, pipe = mock_redis
        push_btw_message("t1", "hello", user_id="u1")
        pipe.rpush.assert_called_once()
        pipe.ltrim.assert_called_once()
        pipe.expire.assert_called_once()

    def test_push_envelope_contains_required_fields(self, mock_redis):
        client, pipe = mock_redis
        push_btw_message("t1", "hello", user_id="u1")
        raw = pipe.rpush.call_args[0][1]
        envelope = json.loads(raw)
        assert envelope["message"] == "hello"
        assert envelope["user_id"] == "u1"
        assert "timestamp" in envelope

    def test_push_empty_message_raises_value_error(self, mock_redis):
        with pytest.raises(ValueError, match="empty"):
            push_btw_message("t1", "")

    def test_push_whitespace_only_raises_value_error(self, mock_redis):
        with pytest.raises(ValueError, match="empty"):
            push_btw_message("t1", "   ")

    def test_push_too_long_message_raises_value_error(self, mock_redis):
        with pytest.raises(ValueError, match=str(MAX_MESSAGE_LENGTH)):
            push_btw_message("t1", "x" * (MAX_MESSAGE_LENGTH + 1))

    def test_push_raises_runtime_when_redis_unavailable(self):
        with patch(
            "deep_agent.src.btw.store.get_redis_client", return_value=None
        ):
            with pytest.raises(RuntimeError, match="Redis unavailable"):
                push_btw_message("t1", "hello")

    def test_push_trims_to_max_queue_depth(self, mock_redis):
        _client, pipe = mock_redis
        push_btw_message("t1", "hello")
        pipe.ltrim.assert_called_once()
        args = pipe.ltrim.call_args[0]
        assert args[1] == -MAX_QUEUE_DEPTH
        assert args[2] == -1

    def test_push_default_user_id_is_anonymous(self, mock_redis):
        _client, pipe = mock_redis
        push_btw_message("t1", "hello")
        raw = pipe.rpush.call_args[0][1]
        envelope = json.loads(raw)
        assert envelope["user_id"] == "anonymous"


class TestConsumeBtwMessages:
    def test_consume_returns_messages(self, mock_redis):
        client, pipe = mock_redis
        msg = json.dumps({"message": "hi", "user_id": "u1", "timestamp": 1.0})
        pipe.execute.return_value = [[msg], 1]
        result = consume_btw_messages("t1")
        assert len(result) == 1
        assert result[0]["message"] == "hi"

    def test_consume_returns_empty_when_no_messages(self, mock_redis):
        _client, pipe = mock_redis
        pipe.execute.return_value = [[], 0]
        assert consume_btw_messages("t1") == []

    def test_consume_returns_empty_when_redis_unavailable(self):
        with patch(
            "deep_agent.src.btw.store.get_redis_client", return_value=None
        ):
            assert consume_btw_messages("t1") == []

    def test_consume_skips_corrupt_messages(self, mock_redis):
        _client, pipe = mock_redis
        good = json.dumps({"message": "ok", "user_id": "u1", "timestamp": 1.0})
        pipe.execute.return_value = [["not-json", good], 1]
        result = consume_btw_messages("t1")
        assert len(result) == 1
        assert result[0]["message"] == "ok"

    def test_consume_calls_lrange_and_delete(self, mock_redis):
        _client, pipe = mock_redis
        pipe.execute.return_value = [[], 0]
        consume_btw_messages("t1")
        pipe.lrange.assert_called_once()
        pipe.delete.assert_called_once()


class TestGetQueueDepth:
    def test_returns_depth(self, mock_redis):
        client, _pipe = mock_redis
        client.llen.return_value = 5
        assert get_queue_depth("t1") == 5

    def test_returns_zero_when_redis_unavailable(self):
        with patch(
            "deep_agent.src.btw.store.get_redis_client", return_value=None
        ):
            assert get_queue_depth("t1") == 0
