"""Unit tests for /btw and /trust FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from deep_agent.aegra.feedback import app


@pytest.fixture()
def client():
    return TestClient(app)


class TestBtwEndpoint:
    def test_success_returns_queued(self, client):
        with patch(
            "deep_agent.src.btw.store.push_btw_message",
            return_value=3,
        ):
            resp = client.post(
                "/btw",
                json={"thread_id": "t1", "message": "context update"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"
        assert data["queue_depth"] == 3

    def test_empty_body_returns_422(self, client):
        resp = client.post("/btw", content=b"")
        assert resp.status_code == 422

    def test_invalid_json_returns_422(self, client):
        resp = client.post("/btw", content=b"not-json", headers={"content-type": "application/json"})
        assert resp.status_code == 422

    def test_missing_thread_id_returns_422(self, client):
        resp = client.post("/btw", json={"message": "hello"})
        assert resp.status_code == 422
        assert "thread_id" in resp.json()["detail"]

    def test_missing_message_returns_422(self, client):
        resp = client.post("/btw", json={"thread_id": "t1"})
        assert resp.status_code == 422
        assert "message" in resp.json()["detail"]

    def test_message_too_long_returns_422(self, client):
        with patch(
            "deep_agent.src.btw.store.push_btw_message",
            side_effect=ValueError("Message exceeds 2000 characters"),
        ):
            resp = client.post(
                "/btw",
                json={"thread_id": "t1", "message": "x" * 2001},
            )
        assert resp.status_code == 422

    def test_redis_unavailable_returns_503(self, client):
        with patch(
            "deep_agent.src.btw.store.push_btw_message",
            side_effect=RuntimeError("Redis unavailable"),
        ):
            resp = client.post(
                "/btw",
                json={"thread_id": "t1", "message": "hello"},
            )
        assert resp.status_code == 503

    def test_non_object_body_returns_422(self, client):
        resp = client.post("/btw", json=["array"])
        assert resp.status_code == 422


class TestTrustEndpoint:
    def test_approve_all_success(self, client):
        with patch("deep_agent.src.btw.trust.set_trust_level") as mock_set:
            resp = client.post(
                "/trust",
                json={"thread_id": "t1", "action": "approve_all"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approve_all"
        mock_set.assert_called_once_with("t1", "approve_all")

    def test_revoke_success(self, client):
        with patch("deep_agent.src.btw.trust.revoke_trust") as mock_revoke:
            resp = client.post(
                "/trust",
                json={"thread_id": "t1", "action": "revoke"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoke"
        mock_revoke.assert_called_once_with("t1")

    def test_missing_thread_id_returns_422(self, client):
        resp = client.post("/trust", json={"action": "approve_all"})
        assert resp.status_code == 422

    def test_invalid_action_returns_422(self, client):
        resp = client.post(
            "/trust",
            json={"thread_id": "t1", "action": "invalid"},
        )
        assert resp.status_code == 422
        assert "action" in resp.json()["detail"]

    def test_redis_unavailable_returns_503(self, client):
        with patch(
            "deep_agent.src.btw.trust.set_trust_level",
            side_effect=RuntimeError("Redis unavailable"),
        ):
            resp = client.post(
                "/trust",
                json={"thread_id": "t1", "action": "approve_all"},
            )
        assert resp.status_code == 503

    def test_empty_body_returns_422(self, client):
        resp = client.post("/trust", content=b"")
        assert resp.status_code == 422
