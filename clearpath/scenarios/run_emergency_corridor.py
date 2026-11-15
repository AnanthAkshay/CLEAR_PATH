"""Full emergency run: authenticated dispatch, green corridor, recovery."""

from __future__ import annotations

from clearpath.agents.tokens import issue_token
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    EtaNotice, PreemptionRequest, RecoveryDone, RecoveryStarted, RoutePlan, Telemetry,
)
from clearpath.config import load_config
from clearpath.engine.orchestrator import Orchestrator


def _needed_phase(approach: tuple[str, str]) -> str:
    """Signal phase value that serves an approach running along one grid axis."""
    u, v = approach
    return "NS_GREEN" if u.split("_")[-1] == v.split("_")[-1] else "EW_GREEN"


def main() -> None:
    """Dispatch an ambulance and watch its junctions hold green, then recover."""
    config = load_config()
    orchestrator = Orchestrator(config, MessageBus(seed=config.seed))
    for _ in range(30):
        orchestrator.step()

    tick = orchestrator.sim.current_tick
    nonce = f"AMB_1-{tick}"
    request = PreemptionRequest(
        vehicle_id="AMB_1",
        token=issue_token("AMB_1", nonce, float(tick), config.hmac_secret),
        nonce=nonce,
        incident_loc=(0.0, 0.0),
        telemetry=Telemetry(
            x=0.0, y=0.0, speed_mps=5.0, heading_deg=90.0,
            edge_id="j_0_0_j_0_1", vehicle_id="AMB_1",
        ),
        sender="ambulance",
    )

    outcome = orchestrator.handle_preemption_request(request, "trauma")
    dispatch = outcome["dispatch"]
    path = dispatch["path"]
    print(f"authenticated={outcome['auth'].is_authenticated}")
    print(f"hospital={dispatch['hospital_id']} degraded={dispatch['degraded']}")
    print(f"path={' -> '.join(path)}")

    ambulance = orchestrator.sim.spawn_ambulance(path[0], path[-1], route=path)
    print(f"ambulance={ambulance} spawned heading {path[0]} -> {path[-1]}\n")

    corridors = [((path[i - 1], path[i]), path[i]) for i in range(1, len(path))]
    green_ticks = {node: 0 for _, node in corridors}
    held_ticks = {node: 0 for _, node in corridors}
    arrival_tick = None
    settle = 0

    for _ in range(240):
        orchestrator.step()
        for approach, node in corridors:
            signal = orchestrator.sim.signals[node]
            if signal.state_for_approach(approach) == "G":
                green_ticks[node] += 1
            # is_preempted also covers clearance and the cross-street recovery
            # green, so only count ticks where the override serves this approach.
            held = str(getattr(signal.override_phase, "value", ""))
            if signal.is_preempted and held == _needed_phase(approach):
                held_ticks[node] += 1
        if ambulance not in orchestrator.sim.vehicles:
            if arrival_tick is None:
                arrival_tick = orchestrator.sim.current_tick
            # Let the junctions finish their recovery windows before reporting.
            settle += 1
            if settle > 2 * config.recovery_s:
                break

    print(f"{'junction':<10}{'approach':<20}{'green ticks':>12}{'held green':>11}")
    for (u, v), node in corridors:
        print(
            f"{node:<10}{f'{u}->{v}':<20}"
            f"{green_ticks[node]:>12}{held_ticks[node]:>11}"
        )

    plans = [m for m in orchestrator.bus.message_log if isinstance(m, RoutePlan)]
    notices = [m for m in orchestrator.bus.message_log if isinstance(m, EtaNotice)]
    started = [m for m in orchestrator.bus.message_log if isinstance(m, RecoveryStarted)]
    done = [m for m in orchestrator.bus.message_log if isinstance(m, RecoveryDone)]
    print(
        f"\nRoutePlan={len(plans)} EtaNotice={len(notices)} "
        f"RecoveryStarted={len(started)} RecoveryDone={len(done)}"
    )

    if arrival_tick is None:
        print("ambulance still in transit after 240 ticks")
    else:
        print(
            f"ambulance arrived at tick {arrival_tick} "
            f"(dispatch tick {tick}) after {arrival_tick - tick} s"
        )


if __name__ == "__main__":
    main()
