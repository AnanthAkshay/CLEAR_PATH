"""End-to-end preemption flow through the simulation orchestrator."""

from __future__ import annotations

from clearpath.agents.tokens import issue_token
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    EtaNotice, PreemptionRequest, RoutePlan, Telemetry,
)
from clearpath.config import load_config
from clearpath.engine.orchestrator import Orchestrator


def _request(
    orchestrator: Orchestrator, vehicle_id: str, forged: bool = False
) -> PreemptionRequest:
    """Build a request from the ambulance's live simulator state."""
    vehicle = orchestrator.sim.vehicles[vehicle_id]
    tick = orchestrator.sim.current_tick
    x, y = orchestrator.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
    nonce = f"{vehicle_id}-{tick}"
    token = issue_token(vehicle_id, nonce, float(tick), orchestrator.config.hmac_secret)
    if forged:
        head, signature = token.rsplit(".", 1)
        token = head + "." + ("A" if signature[-1] != "A" else "B")

    return PreemptionRequest(
        vehicle_id=vehicle_id,
        token=token,
        nonce=nonce,
        incident_loc=(x, y),
        telemetry=Telemetry(
            x=x,
            y=y,
            speed_mps=vehicle.speed,
            accel_mps2=0.0,
            heading_deg=orchestrator.sim.network.edge_bearing(*vehicle.edge),
            edge_id=f"{vehicle.edge[0]}_{vehicle.edge[1]}",
            lane=vehicle.lane,
            vehicle_id=vehicle_id,
        ),
        sender="ambulance",
    )


def test_handle_preemption_request_end_to_end() -> None:
    """A verified request announces the corridor; a forged one announces nothing."""
    config = load_config()
    orchestrator = Orchestrator(config, MessageBus(seed=config.seed))
    for _ in range(5):
        orchestrator.step()
    ambulance = orchestrator.sim.spawn_ambulance("j_0_0", "j_0_4")

    valid = orchestrator.handle_preemption_request(_request(orchestrator, ambulance), "trauma")

    assert valid["authenticated"] is True
    path = valid["dispatch"]["path"]
    assert len(path) > 1

    plans = [msg for msg in orchestrator.bus.message_log if isinstance(msg, RoutePlan)]
    notices = [msg for msg in orchestrator.bus.message_log if isinstance(msg, EtaNotice)]

    assert len(plans) == 1
    assert plans[0].vehicle_id == ambulance
    assert plans[0].path_nodes == path
    assert len(notices) == len(path) - 1
    assert [notice.junction_id for notice in notices] == path[1:]
    assert all(notice.vehicle_id == ambulance for notice in notices)
    assert all(notice.ts == valid["auth"].ts for notice in notices)

    forged = orchestrator.handle_preemption_request(
        _request(orchestrator, ambulance, forged=True), "trauma"
    )

    assert forged["authenticated"] is False
    assert forged["dispatch"] is None
    assert "TOKEN" in forged["auth"].reasons
    assert len([m for m in orchestrator.bus.message_log if isinstance(m, RoutePlan)]) == 1
    assert len([m for m in orchestrator.bus.message_log if isinstance(m, EtaNotice)]) == len(notices)
