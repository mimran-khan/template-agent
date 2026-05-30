"""Unit tests for btw trust level module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from deep_agent.src.btw.trust import (
    get_trust_level,
    is_trusted,
    revoke_trust,
    set_trust_level,
)


@pytest.fixture()
def mock_redis():
    """Provide a mock Redis client returned by get_redis_client()."""
    client = MagicMock()
    with patch("deep_agent.src.btw.trust.get_redis_client", return_value=client):
        yield client


class TestGetTrustLevel:
    def test_returns_level_string(self, mock_redis):
        mock_redis.get.return_value = "approve_all"
        assert get_trust_level("t1") == "approve_all"

    def test_returns_none_when_key_absent(self, mock_redis):
        mock_redis.get.return_value = None
        assert get_trust_level("t1") is None

    def test_decodes_bytes_to_str(self, mock_redis):
        mock_redis.get.return_value = b"approve_all"
        assert get_trust_level("t1") == "approve_all"

    def test_returns_none_when_redis_unavailable(self):
        with patch("deep_agent.src.btw.trust.get_redis_client", return_value=None):
            assert get_trust_level("t1") is None


class TestSetTrustLevel:
    def test_sets_key_with_ttl(self, mock_redis):
        set_trust_level("t1", "approve_all")
        mock_redis.set.assert_called_once()
        args, kwargs = mock_redis.set.call_args
        assert args[0].endswith("t1")
        assert args[1] == "approve_all"
        assert kwargs.get("ex") is not None

    def test_custom_ttl(self, mock_redis):
        set_trust_level("t1", "approve_all", ttl=300)
        _, kwargs = mock_redis.set.call_args
        assert kwargs["ex"] == 300

    def test_raises_when_redis_unavailable(self):
        with patch("deep_agent.src.btw.trust.get_redis_client", return_value=None):
            with pytest.raises(RuntimeError, match="Redis unavailable"):
                set_trust_level("t1", "approve_all")


class TestRevokeTrust:
    def test_deletes_key(self, mock_redis):
        revoke_trust("t1")
        mock_redis.delete.assert_called_once()

    def test_raises_when_redis_unavailable(self):
        with patch("deep_agent.src.btw.trust.get_redis_client", return_value=None):
            with pytest.raises(RuntimeError, match="Redis unavailable"):
                revoke_trust("t1")


class TestIsTrusted:
    def test_true_when_approve_all(self, mock_redis):
        mock_redis.get.return_value = "approve_all"
        assert is_trusted("t1") is True

    def test_false_when_no_trust(self, mock_redis):
        mock_redis.get.return_value = None
        assert is_trusted("t1") is False

    def test_false_when_different_level(self, mock_redis):
        mock_redis.get.return_value = "some_other_level"
        assert is_trusted("t1") is False
