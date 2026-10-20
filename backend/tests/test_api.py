import pytest
from fastapi.testclient import TestClient

from autoapply.config import config
from autoapply.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("API_TOKEN", "test-token-is-at-least-24-chars")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'api.db'}")
    config.cache_clear()
    with TestClient(app) as c:
        yield c
    config.cache_clear()


AUTH = {"Authorization": "Bearer test-token-is-at-least-24-chars"}


def test_auth_boundary(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/jobs", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_profile_board_and_idempotent_queue(client):
    assert client.put("/api/profile", headers=AUTH, json={"name": "Alex"}).status_code == 200
    assert client.get("/api/profile", headers=AUTH).json()["name"] == "Alex"
    payload = {"provider": "lever", "slug": "team", "employer": "Team"}
    r = client.post("/api/boards", headers=AUTH, json=payload)
    assert r.status_code == 201
    assert client.post("/api/boards", headers=AUTH, json=payload).status_code == 409
    identifier = r.json()["id"]
    first = client.post(f"/api/boards/{identifier}/discover", headers=AUTH)
    second = client.post(f"/api/boards/{identifier}/discover", headers=AUTH)
    assert first.json()["id"] == second.json()["id"]


def test_policy_and_emergency_stop(client):
    assert client.put("/api/settings", headers=AUTH, json={"auto_submit": True}).status_code == 422
    assert client.put("/api/settings", headers=AUTH, json={"dry_run": False}).status_code == 422
    assert (
        client.put("/api/settings", headers=AUTH, json={"review_score": 90, "minimum_score": 80}).status_code
        == 422
    )
    assert client.post("/api/stop", headers=AUTH).json()["emergency_stop"]
    assert client.get("/api/settings", headers=AUTH).json()["enabled"] is False


def test_unknown_record_and_input_validation(client):
    assert client.post("/api/jobs/999/score", headers=AUTH).status_code == 404
    assert (
        client.post(
            "/api/boards", headers=AUTH, json={"provider": "lever", "slug": "../internal", "employer": "Team"}
        ).status_code
        == 422
    )
