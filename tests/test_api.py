"""Unit tests for FastAPI REST API endpoints (clearpath.api.server)."""

from __future__ import annotations

import asyncio
import uuid
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from clearpath.agents.tokens import issue_token
from clearpath.api.server import app, create_engine
from clearpath.config import load_config


@pytest.fixture
def client() -> TestClient:
    create_engine(load_config(seed=42), preemption_enabled=True)
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "clearpath-lite"
    assert "tick" in data


def test_state_endpoint(client: TestClient) -> None:
    res = client.get("/state")
    assert res.status_code == 200
    data = res.json()
    assert "tick" in data
    assert "vehicles" in data
    assert "signals" in data
    assert "queues" in data
    assert "densities" in data


def test_metrics_endpoint(client: TestClient) -> None:
    res = client.get("/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "ticks_elapsed" in data
    assert "network_throughput" in data
    assert "network_avg_speed_mps" in data


def test_messages_endpoint(client: TestClient) -> None:
    res = client.get("/messages?limit=10")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_step_endpoint(client: TestClient) -> None:
    res = client.post("/step?n=5")
    assert res.status_code == 200
    data = res.json()
    assert data["tick"] == 5


def test_reset_endpoint(client: TestClient) -> None:
    client.post("/step?n=10")
    res = client.post("/reset?seed=99")
    assert res.status_code == 200
    assert res.json()["status"] == "reset"
    assert res.json()["tick"] == 0


def test_emergency_endpoint(client: TestClient) -> None:
    config = load_config(seed=42)
    nonce = str(uuid.uuid4())
    token = issue_token("AMB_1", nonce, 0.0, config.hmac_secret)

    payload = {
        "vehicle_id": "AMB_1",
        "token": token,
        "nonce": nonce,
        "incident_loc": [0.0, 0.0],
        "severity": "CRITICAL",
        "telemetry": {
            "x": 0.0,
            "y": 0.0,
            "speed_mps": 10.0,
            "accel_mps2": 0.0,
            "heading_deg": 90.0,
            "edge_id": "j_0_0_j_0_1",
            "lane": 0,
            "vehicle_id": "AMB_1",
        },
    }

    res = client.post("/emergency", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is True
    assert data["auth"]["is_authenticated"] is True
    assert data["dispatch"]["dispatched"] is True


def test_concurrent_step_calls_consistency() -> None:
    create_engine(load_config(seed=42), preemption_enabled=True)

    async def _run() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            tasks = [ac.post("/step?n=2") for _ in range(10)]
            responses = await asyncio.gather(*tasks)
            for res in responses:
                assert res.status_code == 200

    asyncio.run(_run())
    client = TestClient(app)
    state = client.get("/state").json()
    assert state["tick"] == 20


def test_health_etag_and_caching(client: TestClient) -> None:
    res1 = client.get("/health")
    assert res1.status_code == 200
    assert "ETag" in res1.headers
    assert "Cache-Control" in res1.headers
    etag = res1.headers["ETag"]

    res2 = client.get("/health", headers={"If-None-Match": etag})
    assert res2.status_code == 304


def test_metrics_etag_and_caching(client: TestClient) -> None:
    res1 = client.get("/metrics")
    assert res1.status_code == 200
    assert "ETag" in res1.headers
    assert "Cache-Control" in res1.headers
    etag = res1.headers["ETag"]

    res2 = client.get("/metrics", headers={"If-None-Match": etag})
    assert res2.status_code == 304


def test_state_fields_filtering(client: TestClient) -> None:
    res_full = client.get("/state")
    assert res_full.status_code == 200
    assert len(res_full.json().keys()) > 3

    res_trimmed = client.get("/state?fields=tick,vehicles")
    assert res_trimmed.status_code == 200
    data = res_trimmed.json()
    assert set(data.keys()) == {"tick", "vehicles"}


def test_contact_endpoint_success(client: TestClient) -> None:
    payload = {
        "name": "Traffic Ops Chief",
        "email": "ops@traffic.gov",
        "message": "Inquiry regarding ClearPath pilot deployment.",
        "utm_source": "newsletter",
        "utm_campaign": "pilot2026",
    }
    res = client.post("/contact", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "id" in data
    assert "received_at" in data


def test_contact_endpoint_validation_errors(client: TestClient) -> None:
    # Invalid email
    res1 = client.post("/contact", json={"name": "Alice", "email": "bad-email", "message": "Valid length message"})
    assert res1.status_code == 422
    errs = res1.json()["detail"]
    assert any("email" in str(e["loc"]) for e in errs)

    # Empty name
    res2 = client.post("/contact", json={"name": "   ", "email": "alice@city.gov", "message": "Valid length message"})
    assert res2.status_code == 422

    # Short message
    res3 = client.post("/contact", json={"name": "Bob", "email": "bob@city.gov", "message": "Hi"})
    assert res3.status_code == 422
