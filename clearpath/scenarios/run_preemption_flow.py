"""End-to-end preemption flow: authenticate -> dispatch -> RoutePlan/EtaNotices."""

from __future__ import annotations

from typing import Tuple

from clearpath.agents.tokens import issue_token
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    EtaNotice, PreemptionRequest, RoutePlan, Telemetry,
)
from clearpath.config import load_config
from clearpath.engine.orchestrator import Orchestrator


def _request(
    orchestrator: Orchestrator, vehicle_id: str, forged: bool = False
) -> Tuple[PreemptionRequest, str]:
    """Build a request from the ambulance's live simulator state."""
    vehicle = orchestrator.sim.vehicles[vehicle_id]
    tick = orchestrator.sim.current_tick
    x, y = orchestrator.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
    nonce = f"{vehicle_id}-{tick}"
    token = issue_token(vehicle_id, nonce, float(tick), orchestrator.config.hmac_secret)
    if forged:
        head, signature = token.rsplit(".", 1)
        token = head + "." + ("A" if signature[-1] != "A" else "B")

    telemetry = Telemetry(
        x=x,
        y=y,
        speed_mps=vehicle.speed,
        accel_mps2=0.0,
        heading_deg=orchestrator.sim.network.edge_bearing(*vehicle.edge),
        edge_id=f"{vehicle.edge[0]}_{vehicle.edge[1]}",
        lane=vehicle.lane,
        vehicle_id=vehicle_id,
    )
    request = PreemptionRequest(
        vehicle_id=vehicle_id,
        token=token,
        telemetry=telemetry,
        incident_loc=(x, y),
        severity="CRITICAL",
        nonce=nonce,
        sender="ambulance",
    )
    return request, "trauma"


def main() -> None:
    """Run the simulated grid, then push one request and one forgery through it."""
    config = load_config()
    orchestrator = Orchestrator(config, MessageBus(seed=config.seed))

    for _ in range(30):
        orchestrator.step()

    ambulance = orchestrator.sim.spawn_ambulance("j_0_0", "j_0_4")
    world = orchestrator.sim.get_world_view()
    print(f"tick={world.tick} vehicles={len(world.vehicles)} ambulance={ambulance}")

    request, incident_type = _request(orchestrator, ambulance)
    outcome = orchestrator.handle_preemption_request(request, incident_type)
    auth = outcome["auth"]
    print(f"\n[1] security.authenticate -> {auth.security_log}")

    dispatch = outcome["dispatch"]
    print(f"[2] dispatcher.dispatch({incident_type}) -> degraded={dispatch['degraded']}")
    for rank, entry in enumerate(dispatch["ranked"], start=1):
        print(
            f"      {rank}. {entry['hospital_id']:<15} score={entry['score']:.3f} "
            f"travel={entry['travel_time_s']:>6.1f}s wait={entry['hospital_wait_s']:>6.0f}s"
        )
    print(f"[3] chosen={dispatch['hospital_id']} total_eta={dispatch['total_eta_s']:.1f}s")
    print(f"      path={' -> '.join(dispatch['path'])}")

    plans = [m for m in orchestrator.bus.message_log if isinstance(m, RoutePlan)]
    notices = [m for m in orchestrator.bus.message_log if isinstance(m, EtaNotice)]
    print(f"      RoutePlan published={len(plans)} EtaNotice published={len(notices)}")
    for notice in notices[:3]:
        print(
            f"        {notice.junction_id}: eta_t={notice.eta_t:.1f}s "
            f"{notice.approach_edge} -> {notice.exit_edge or 'END'}"
        )

    for _ in range(3):
        orchestrator.step()
    delivered = [m for m in orchestrator.bus.message_log if isinstance(m, EtaNotice)]
    print(f"[4] after 3 ticks: {len(delivered)} EtaNotices on the bus log")

    forged, forged_type = _request(orchestrator, ambulance, forged=True)
    refused = orchestrator.handle_preemption_request(forged, forged_type)
    print(f"\n[5] forged token -> authenticated={refused['auth'].is_authenticated} "
          f"reasons={refused['auth'].reasons} dispatch={refused['dispatch']}")
    print(
        "      RoutePlan count still "
        f"{len([m for m in orchestrator.bus.message_log if isinstance(m, RoutePlan)])}"
    )


if __name__ == "__main__":
    main()
