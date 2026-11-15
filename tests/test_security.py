"""Tests for the ClearPath-lite SecurityAgent."""

from __future__ import annotations

import networkx as nx

from clearpath.agents.security import SecurityAgent
from clearpath.agents.tokens import issue_token
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import PreemptionRequest, RevokePreemption, Telemetry
from clearpath.config import SimConfig

SECRET = "test-secret"


def _graph() -> nx.DiGraph:
    """Two edges: an eastbound arterial and a northbound residential street."""
    graph = nx.DiGraph()
    graph.add_node("j_0_0", x=0.0, y=0.0)
    graph.add_node("j_0_1", x=200.0, y=0.0)
    graph.add_node("j_1_0", x=0.0, y=200.0)
    graph.add_edge(
        "j_0_0",
        "j_0_1",
        length_m=200.0,
        speed_limit_mps=16.7,
        road_class="arterial",
        bearing_deg=90.0,
    )
    graph.add_edge(
        "j_0_0",
        "j_1_0",
        length_m=200.0,
        speed_limit_mps=11.1,
        road_class="residential",
        bearing_deg=0.0,
    )
    return graph


def _agent(now: list[float], fleet: tuple[str, ...] = ("AMB_1",)) -> SecurityAgent:
    """Build an agent whose clock reads and advances through ``now[0]``."""
    config = SimConfig(
        hmac_secret=SECRET,
        token_ttl_s=60,
        authorized_vehicle_ids=frozenset(fleet),
    )
    return SecurityAgent(
        "security", MessageBus(seed=1), config, _graph(), clock=lambda: now[0]
    )


def _request(
    vehicle_id: str = "AMB_1",
    nonce: str = "n1",
    ts: float = 0.0,
    token: str | None = None,
    **overrides: object,
) -> PreemptionRequest:
    """Build a preemption request with sane defaults on the arterial edge."""
    fields: dict[str, object] = {
        "x": 100.0,
        "y": 0.0,
        "speed_mps": 10.0,
        "accel_mps2": 0.0,
        "heading_deg": 90.0,
        "edge_id": "j_0_0_j_0_1",
        "lane": 0,
        "vehicle_id": vehicle_id,
    }
    fields.update(overrides)
    if token is None:
        token = issue_token(vehicle_id, nonce, ts, SECRET)
    return PreemptionRequest(
        vehicle_id=vehicle_id,
        token=token,
        nonce=nonce,
        telemetry=Telemetry(**fields),  # type: ignore[arg-type]
        sender="ambulance",
    )


def test_valid_request_allowed() -> None:
    """A properly signed request with sane telemetry is accepted."""
    result = _agent([0.0]).authenticate(_request())

    assert result.is_authenticated is True
    assert result.reasons == []
    assert result.risk_score == 0.0


def test_tampered_signature_blocked() -> None:
    """Flipping one signature character is rejected."""
    token = issue_token("AMB_1", "n1", 0.0, SECRET)
    head, signature = token.rsplit(".", 1)
    tampered = head + "." + ("A" if signature[-1] != "A" else "B")

    result = _agent([0.0]).authenticate(_request(token=tampered))

    assert result.is_authenticated is False
    assert "TOKEN" in result.reasons


def test_expired_token_blocked() -> None:
    """A token older than token_ttl_s is rejected."""
    result = _agent([0.0]).authenticate(_request(ts=-120.0))

    assert result.is_authenticated is False
    assert "TOKEN" in result.reasons


def test_replayed_nonce_blocked() -> None:
    """The same nonce cannot be used twice."""
    agent = _agent([0.0])

    assert agent.authenticate(_request()).is_authenticated is True
    replay = agent.authenticate(_request())

    assert replay.is_authenticated is False
    assert "TOKEN" in replay.reasons


def test_unknown_vehicle_blocked() -> None:
    """A correctly signed token from a vehicle outside the fleet is rejected."""
    result = _agent([0.0]).authenticate(_request(vehicle_id="AMB_9"))

    assert result.is_authenticated is False
    assert "TOKEN" in result.reasons


def test_speeding_on_residential_blocked() -> None:
    """150 km/h (41.67 m/s) exceeds the residential allowance of 11.1 * 1.2."""
    result = _agent([0.0]).authenticate(
        _request(
            x=0.0,
            y=100.0,
            speed_mps=41.67,
            heading_deg=0.0,
            edge_id="j_0_0_j_1_0",
        )
    )

    assert result.is_authenticated is False
    assert "SPEED_LIMIT" in result.reasons


def test_teleport_blocked() -> None:
    """Jumping ~224 m to another edge in one second is rejected as discontinuous."""
    now = [0.0]
    agent = _agent(now)

    assert agent.authenticate(_request()).is_authenticated is True

    now[0] = 1.0
    jumped = agent.authenticate(
        _request(
            nonce="n2",
            ts=1.0,
            x=0.0,
            y=200.0,
            heading_deg=0.0,
            edge_id="j_0_0_j_1_0",
        )
    )

    assert jumped.is_authenticated is False
    assert "CONTINUITY" in jumped.reasons


def test_acceleration_flags_without_risk_and_heading_blocks() -> None:
    """ACCELERATION only appends a reason code; heading drift is the sole risk source."""
    accel_only = _agent([0.0]).authenticate(_request(accel_mps2=6.0))

    assert "ACCELERATION" in accel_only.reasons
    assert accel_only.risk_score == 0.0
    assert accel_only.is_authenticated is True

    drift = _agent([0.0]).authenticate(_request(heading_deg=0.0))

    assert "HEADING_MATCH" in drift.reasons
    assert drift.risk_score == 1.0
    assert drift.is_authenticated is False


def test_off_road_position_blocked() -> None:
    """A 60 m lateral offset from the named edge exceeds position_tolerance_m."""
    result = _agent([0.0]).authenticate(_request(y=60.0))

    assert result.is_authenticated is False
    assert "POSITION_ON_ROAD" in result.reasons


def test_rate_limit_flood_blocked() -> None:
    """The seventh request inside 60 s is refused (quota is 6 per minute)."""
    agent = _agent([0.0])

    for i in range(6):
        assert agent.authenticate(_request(nonce=f"n{i}")).is_authenticated is True

    seventh = agent.authenticate(_request(nonce="n6"))

    assert seventh.is_authenticated is False
    assert "RATE_LIMIT" in seventh.reasons


def test_forged_token_flood_is_throttled_without_consuming_quota() -> None:
    """Forgery gets its own coarse bucket and never eats the verified quota."""
    agent = _agent([0.0])
    token = issue_token("AMB_1", "forged", 0.0, SECRET)
    head, signature = token.rsplit(".", 1)
    tampered = head + "." + ("A" if signature[-1] != "A" else "B")

    # One genuine request marks AMB_1 as verified, exempting it from the
    # claimed-id pre-check for good.
    assert agent.authenticate(_request(nonce="first")).is_authenticated is True

    for i in range(6):
        forged = agent.authenticate(_request(nonce=f"x{i}", token=tampered))
        assert forged.is_authenticated is False
        assert forged.reasons == ["TOKEN"]

    # Past the coarse limit, further forgeries are rejected as RATE_LIMIT.
    for i in range(6, 10):
        throttled = agent.authenticate(_request(nonce=f"x{i}", token=tampered))
        assert throttled.is_authenticated is False
        assert throttled.reasons == ["RATE_LIMIT"]
        assert throttled.risk_score == 0.0

    # The rest of the verified quota is still available to the real vehicle.
    for i in range(5):
        assert agent.authenticate(_request(nonce=f"ok{i}")).is_authenticated is True

    seventh = agent.authenticate(_request(nonce="ok5"))

    assert seventh.is_authenticated is False
    assert "RATE_LIMIT" in seventh.reasons
    # The verified quota, not the coarse bucket, is what stopped it.
    assert "rate limited" in seventh.security_log
    assert "failure budget" not in seventh.security_log
    assert agent.total_requests == 17
    assert agent.allowed == 6
    assert agent.blocked == 11


def test_mid_route_revocation_published() -> None:
    """Invalid telemetry from an authorized vehicle publishes RevokePreemption."""
    now = [0.0]
    agent = _agent(now)
    assert agent.authenticate(_request()).is_authenticated is True

    now[0] = 1.0
    clean = Telemetry(
        x=120.0,
        y=0.0,
        speed_mps=12.0,
        heading_deg=90.0,
        edge_id="j_0_0_j_0_1",
        vehicle_id="AMB_1",
    )
    assert agent.validate_stream(clean) is True

    speeding = Telemetry(
        x=100.0,
        y=0.0,
        speed_mps=41.67,
        heading_deg=90.0,
        edge_id="j_0_0_j_0_1",
        vehicle_id="AMB_1",
    )
    assert agent.validate_stream(speeding) is False

    revocations = [
        msg for msg in agent.bus.message_log if isinstance(msg, RevokePreemption)
    ]
    assert len(revocations) == 1
    assert revocations[0].vehicle_id == "AMB_1"
    assert "SPEED_LIMIT" in revocations[0].reason
    # Issue time travels on the inherited Message.ts, not a dedicated field.
    assert revocations[0].ts == 1.0


def test_failure_budget_is_not_per_claimed_id() -> None:
    """Rotating fake ids must not buy extra attempts: the budget is global."""
    agent = _agent([0.0])
    token = issue_token("AMB_1", "forged", 0.0, SECRET)
    head, signature = token.rsplit(".", 1)
    tampered = head + "." + ("A" if signature[-1] != "A" else "B")

    reasons = []
    for i in range(10):
        forged = agent.authenticate(
            _request(vehicle_id=f"FAKE_{i}", nonce=f"f{i}", token=tampered)
        )
        assert forged.is_authenticated is False
        reasons.append(forged.reasons)

    assert reasons[:6] == [["TOKEN"]] * 6
    assert reasons[6:] == [["RATE_LIMIT"]] * 4

    # A real vehicle is still untroubled by the forgery.
    assert agent.authenticate(_request(nonce="n1")).is_authenticated is True


def test_saturated_claimed_id_is_rejected_before_signature_check() -> None:
    """An id that never authenticated is refused pre-HMAC, even with a good token."""
    agent = _agent([0.0])
    token = issue_token("AMB_1", "forged", 0.0, SECRET)
    head, signature = token.rsplit(".", 1)
    tampered = head + "." + ("A" if signature[-1] != "A" else "B")

    for i in range(6):
        agent.authenticate(_request(vehicle_id="FAKE_9", nonce=f"x{i}", token=tampered))

    good = issue_token("FAKE_9", "good", 0.0, SECRET)
    blocked = agent.authenticate(_request(vehicle_id="FAKE_9", nonce="good", token=good))

    assert blocked.is_authenticated is False
    assert blocked.reasons == ["RATE_LIMIT"]
    assert "claimed id" in blocked.security_log

    # A different, untouched vehicle still authenticates normally.
    assert agent.authenticate(_request(nonce="n1")).is_authenticated is True


def test_counters_and_audit_trail() -> None:
    """Counters, reason histogram and audit trail track every decision."""
    agent = _agent([0.0])
    token = issue_token("AMB_1", "n1", 0.0, SECRET)
    head, signature = token.rsplit(".", 1)
    tampered = head + "." + ("A" if signature[-1] != "A" else "B")

    assert agent.authenticate(_request()).is_authenticated is True
    assert agent.authenticate(_request(nonce="n2", token=tampered)).is_authenticated is False

    assert agent.total_requests == 2
    assert agent.allowed == 1
    assert agent.blocked == 1
    assert agent.reason_counts["TOKEN"] == 1
    assert len(agent.audit_trail) == 2
    assert agent.audit_trail[0]["allowed"] is True
    assert agent.audit_trail[0]["risk_score"] == 0.0
    assert agent.audit_trail[1]["reasons"] == ["TOKEN"]
