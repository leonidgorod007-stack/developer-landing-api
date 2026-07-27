"""
End-to-end API tests.

They run against a fresh app configured with a temp data dir, AI disabled
(so the deterministic fallback is exercised) and email in console mode — no
network, no API key, fully hermetic. Covers the happy path, validation errors,
rate limiting, and the health/metrics endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        log_file=str(tmp_path / "data" / "logs" / "app.log"),
        anthropic_api_key="",          # force AI fallback
        ai_enabled=False,
        smtp_host="",                  # console email mode
        rate_limit_max_requests=3,
        rate_limit_window_seconds=60,
        cors_origins=["http://localhost"],
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


VALID = {
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "phone": "+1 (555) 123-4567",
    "comment": "I really enjoyed your portfolio and would love to collaborate.",
}


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["dependencies"]["ai"] == "fallback"
    assert body["dependencies"]["email"] == "console"


def test_contact_happy_path(client):
    r = client.post("/api/contact", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True
    assert len(body["id"]) == 16
    assert body["analysis"]["ai_available"] is False        # fallback used
    assert body["analysis"]["sentiment"] in {"positive", "neutral", "negative"}
    assert body["email"]["owner_notified"] is True
    assert body["email"]["user_notified"] is True
    assert "X-Request-ID" in r.headers


def test_validation_errors(client):
    bad = {"name": "A", "email": "not-an-email", "comment": "short"}
    r = client.post("/api/contact", json=bad)
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    fields = {d["field"] for d in body["error"]["details"]}
    assert {"name", "email", "comment"} <= fields


def test_invalid_phone_rejected(client):
    payload = {**VALID, "phone": "abc-not-a-phone"}
    r = client.post("/api/contact", json=payload)
    assert r.status_code == 422


def test_rate_limiting(client):
    # Limit is 3/window; the 4th must be rejected with 429 + Retry-After.
    for _ in range(3):
        assert client.post("/api/contact", json=VALID).status_code == 201
    r = client.post("/api/contact", json=VALID)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "rate_limited"
    assert int(r.headers["Retry-After"]) >= 1


def test_metrics_accumulate(client):
    client.post("/api/contact", json=VALID)
    client.post("/api/contact", json={**VALID, "comment": "This has a terrible bug and I am disappointed."})
    r = client.get("/api/metrics")
    assert r.status_code == 200
    body = r.json()
    assert body["total_submissions"] == 2
    assert body["ai_fallback"] == 2
    assert sum(body["by_sentiment"].values()) == 2
