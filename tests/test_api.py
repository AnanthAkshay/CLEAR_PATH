"""Unit tests for FastAPI REST API endpoints (clearpath.api.server)."""

from __future__ import annotations

import uuid
from fastapi.testclient import TestClient
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
