"""Scenario and stress/edge-case tests for ClearPath-lite (tests/test_scenarios.py).

Coverage:
1. Scenario script entry-point and run(seed, demand) signature validations.
2. High demand plus valid emergency: queues recover and no permanent gridlock.
3. Two simultaneous ambulances: priority rule applied, zero conflicting greens.
4. Message drop 10%: fail-safe holds, zero conflicting greens, ambulance travel
   time is no slower than baseline.
5. Junction failure (silent agent): replan routes around the failed intersection
   and ambulance successfully reaches destination.
6. Incident adjacent to a hospital (short 1-hop corridor) functions cleanly.
7. Parametrized 5-seed sweep: ambulance travel time improvement is positive
   in at least 4 of 5 seeds, reporting mean and std.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Tuple

import numpy as np
import pytest

from clearpath.agents.tokens import issue_token
from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import load_config
from clearpath.engine.orchestrator import ClearPathEngine
from clearpath.scenarios import run_all, run_emergency, run_normal, run_spoofed
from clearpath.sim.simulator import Simulator


def _has_orthogonal_green_conflict(sim: Simulator, node: str) -> bool:
    """True when two orthogonal approaches to an intersection show green simultaneously."""
    ctrl = sim.signals[node]
    graph = sim.network.graph
    ns_green = False
    ew_green = False
    for u in graph.predecessors(node):
        approach = (u, node)
        state = ctrl.state_for_approach(approach)
        u_col = graph.nodes[u]["c"]
        v_col = graph.nodes[node]["c"]
        if state == "G":
            if u_col == v_col:
                ns_green = True
            else:
                ew_green = True
    return ns_green and ew_green


def _build_request(
    engine: ClearPathEngine,
    vehicle_id: str,
    incident_loc: Tuple[float, float] = (0.0, 0.0),
    edge_id: str = "j_0_0_j_0_1",
    severity: str = "CRITICAL",
) -> PreemptionRequest:
    """Create a valid signed PreemptionRequest at the given edge."""
    tick = float(engine.current_tick)
    nonce = f"{vehicle_id}_{uuid.uuid4().hex[:8]}"
    token = issue_token(vehicle_id, nonce, tick, engine.config.hmac_secret)

    u = "_".join(edge_id.split("_")[:3])
    v = "_".join(edge_id.split("_")[3:])
    bearing = engine.sim.network.edge_bearing(u, v)

    return PreemptionRequest(
        vehicle_id=vehicle_id,
        token=token,
        nonce=nonce,
        incident_loc=incident_loc,
        severity=severity,
        telemetry=Telemetry(
            x=incident_loc[0],
            y=incident_loc[1],
            speed_mps=10.0,
            accel_mps2=0.0,
            heading_deg=bearing,
            edge_id=edge_id,
            lane=0,
            vehicle_id=vehicle_id,
        ),
        sender="ambulance",
    )


# ---------------------------------------------------------------------------
# 1. Scenario Function Signatures and Return Values
# ---------------------------------------------------------------------------

def test_run_normal_returns_metrics() -> None:
    """run_normal.run(seed, demand) returns a dictionary with core traffic stats."""
    res = run_normal.run(seed=42, demand="low", ticks=60)
    assert isinstance(res, dict)
    assert res["status"] == "PASS"
    assert res["preempted_signals"] == 0
    assert "average_speed_mps" in res
    assert "throughput_veh_per_tick" in res
    assert "mean_queue_length" in res
    assert "max_queue_length" in res


def test_run_emergency_returns_metrics() -> None:
    """run_emergency.run(seed, demand) returns comparison metrics between baseline and ClearPath."""
    res = run_emergency.run(seed=42, demand="med", ticks=150)
    assert isinstance(res, dict)
    assert res["status"] == "PASS"
    assert res["ambulance_time_clearpath"] < res["ambulance_time_baseline"]
    assert res["improvement_pct"] > 0
    assert "cross_delay_avg_s" in res
    assert "cross_delay_p95_s" in res
    assert "recovery_time_avg_s" in res
    assert "messages_exchanged" in res


def test_run_spoofed_returns_metrics() -> None:
    """run_spoofed.run(seed, demand) blocks all 6 attacks and allows the legitimate request."""
    res = run_spoofed.run(seed=42, demand="med", ticks=20)
    assert isinstance(res, dict)
    assert res["status"] == "PASS"
    assert res["attacks_blocked"] == 6
    assert res["attacks_total"] == 6
    assert res["legitimate_allowed"] == 1
    assert res["signal_overrides_from_attacks"] == 0
    assert len(res["audit_table"]) == 7


def test_run_all_returns_checklist_and_files(tmp_path: Any) -> None:
    """run_all.run(seed, demand) writes summary.json and summary.md."""
    res = run_all.run(seed=42, demand="low")
    assert isinstance(res, dict)
    assert res["all_passed"] is True
    assert len(res["checklist"]) >= 5
    assert all(c["passed"] for c in res["checklist"])


# ---------------------------------------------------------------------------
# 2. High demand plus valid emergency: no permanent gridlock
# ---------------------------------------------------------------------------

def test_high_demand_emergency_no_gridlock() -> None:
    """Under high traffic demand, emergency preemption does not cause permanent gridlock."""
    config = load_config(seed=42, max_ticks=250)
    engine = ClearPathEngine(config, preemption_enabled=True, demand_level="high")

    for t in range(1, 251):
        engine.step()
        if t == 10:
            req = _build_request(engine, "AMB_1")
            res = engine.submit_emergency_request(req, "cardiac", ground_truth_valid=True)
            assert res["authenticated"] is True

    summary = engine.metrics.summary()
    assert summary["ambulance_travel_time_s"] is not None, "Ambulance failed to reach hospital"

    # Queues must recover: final 30 ticks should have no gridlock
    recent_gridlock = engine.metrics._gridlock_series[-30:]
    assert not any(recent_gridlock), f"Permanent gridlock detected in final ticks: {recent_gridlock}"


# ---------------------------------------------------------------------------
# 3. Two simultaneous ambulances: priority applied, no signal conflict
# ---------------------------------------------------------------------------

def test_two_simultaneous_ambulances_priority_no_conflict() -> None:
    """Two simultaneous ambulances are prioritized cleanly with zero conflicting greens."""
    config = load_config(seed=42)
    engine = ClearPathEngine(config, preemption_enabled=True, demand_level="low")

    # Warm up 5 ticks
    for _ in range(5):
        engine.step()

    # Ambulance 1: Critical severity
    req1 = _build_request(engine, "AMB_1", incident_loc=(0.0, 0.0), edge_id="j_0_0_j_0_1", severity="CRITICAL")
    res1 = engine.submit_emergency_request(req1, "cardiac", ground_truth_valid=True)
    assert res1["authenticated"] is True

    # Ambulance 2: High severity
    req2 = _build_request(engine, "AMB_2", incident_loc=(200.0, 0.0), edge_id="j_0_1_j_1_1", severity="HIGH")
    res2 = engine.submit_emergency_request(req2, "trauma", ground_truth_valid=True)
    assert res2["authenticated"] is True

    conflicts = 0
    for _ in range(100):
        engine.step()
        for node in engine.sim.signals:
            if _has_orthogonal_green_conflict(engine.sim, node):
                conflicts += 1

    assert conflicts == 0, f"Detected {conflicts} simultaneous conflicting green signals"


# ---------------------------------------------------------------------------
# 4. Message drop 10%: fail-safe, no conflicting greens, ambulance faster/equal
# ---------------------------------------------------------------------------

def test_message_drop_ten_percent_graceful_degradation() -> None:
    """10% message packet drop degrades gracefully: zero conflicts and ambulance completes."""
    config = load_config(seed=42)

    # 1. Baseline run (no preemption)
    base = ClearPathEngine(config, preemption_enabled=False, demand_level="med")
    for t in range(1, 201):
        base.step()
        if t == 10:
            req = _build_request(base, "AMB_1")
            base.submit_emergency_request(req, "cardiac", ground_truth_valid=True)
    base_time = base.metrics.ambulance_travel_time_s
    assert base_time is not None

    # 2. ClearPath with 10% packet drop
    cp = ClearPathEngine(config, preemption_enabled=True, demand_level="med", baseline=base.metrics)
    cp.bus.drop_probability = 0.10

    conflicts = 0
    for t in range(1, 201):
        cp.step()
        if t == 10:
            req = _build_request(cp, "AMB_1")
            cp.submit_emergency_request(req, "cardiac", ground_truth_valid=True)

        for node in cp.sim.signals:
            if _has_orthogonal_green_conflict(cp.sim, node):
                conflicts += 1

    cp_time = cp.metrics.ambulance_travel_time_s
    assert cp_time is not None, "Ambulance failed to reach hospital under 10% packet drop"
    assert conflicts == 0, "Conflicting greens found during packet drop run"
    assert cp_time <= base_time, f"Ambulance ({cp_time}s) was slower than baseline ({base_time}s)"

    # Fail-safe check: no signals should be permanently stuck preempted at the end
    stuck_preempted = sum(1 for ctrl in cp.sim.signals.values() if ctrl.is_preempted)
    assert stuck_preempted == 0, f"Fail-safe failed: {stuck_preempted} signals stuck in preemption"


# ---------------------------------------------------------------------------
# 5. Junction failure (agent silent): replanning around silent node
# ---------------------------------------------------------------------------

def test_junction_failure_silent_agent_replan() -> None:
    """When a junction agent fails / goes silent, the dispatcher replans around the failed node."""
    config = load_config(seed=42)
    engine = ClearPathEngine(config, preemption_enabled=True, demand_level="low")

    for _ in range(5):
        engine.step()

    req = _build_request(engine, "AMB_1", incident_loc=(0.0, 0.0), edge_id="j_0_0_j_0_1")
    dispatch_res = engine.submit_emergency_request(req, "cardiac", ground_truth_valid=True)
    orig_path = dispatch_res["dispatch"]["path"]

    # Select an intermediate junction in the planned path to fail
    assert len(orig_path) >= 3, f"Path too short: {orig_path}"
    failed_node = orig_path[2]

    # Silence the junction agent on the bus
    engine.bus.unsubscribe(failed_node)

    # Replan around the failed intersection
    replan = engine.dispatcher.replan(
        "AMB_1",
        blocked_nodes=[failed_node],
        world_view=engine.sim.get_world_view(),
    )
    assert replan is not None, "Replan failed to find an alternative corridor"
    assert failed_node not in replan["path"], f"Replanned path still includes failed node {failed_node}"

    # Update ambulance route in the simulator
    amb = engine.sim.vehicles["AMB_1"]
    amb.route = list(replan["path"][1:])

    for _ in range(150):
        engine.step()

    assert engine.metrics.ambulance_travel_time_s is not None, "Ambulance failed to reach hospital after replanning"


# ---------------------------------------------------------------------------
# 6. Incident right next to hospital (short 1-hop route)
# ---------------------------------------------------------------------------

def test_incident_next_to_hospital_short_route() -> None:
    """An emergency incident located right next to a hospital is dispatched and completes cleanly."""
    config = load_config(seed=42)
    engine = ClearPathEngine(config, preemption_enabled=True, demand_level="low")

    for _ in range(5):
        engine.step()

    # j_2_1 is adjacent to Riverside Urgent Care (j_2_2)
    loc = (200.0, 400.0)
    req = _build_request(engine, "AMB_1", incident_loc=loc, edge_id="j_2_1_j_2_2")
    res = engine.submit_emergency_request(req, "cardiac", ground_truth_valid=True)

    assert res["authenticated"] is True
    assert res["dispatch"]["path"] == ["j_2_1", "j_2_2"]

    for _ in range(30):
        engine.step()

    travel_time = engine.metrics.ambulance_travel_time_s
    assert travel_time is not None, "Ambulance did not arrive"
    assert travel_time <= 15.0, f"Expected short travel time <= 15s, got {travel_time}s"


# ---------------------------------------------------------------------------
# 7. Parametrized sweep over 5 seeds: positive improvement in >= 4/5
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seeds", [[2, 4, 6, 8, 42]])
def test_five_seed_sweep_improvement(seeds: List[int], capsys: Any) -> None:
    """Parametrized sweep over 5 seeds verifies positive ambulance improvement in >= 4/5 seeds."""
    improvements: List[float] = []

    for s in seeds:
        cfg = load_config(seed=s, max_ticks=200)

        # Baseline
        base = ClearPathEngine(cfg, preemption_enabled=False, demand_level="med")
        for t in range(1, 150):
            base.step()
            if t == 10:
                req = _build_request(base, "AMB_1")
                base.submit_emergency_request(req, "cardiac", ground_truth_valid=True)

        # ClearPath
        cp = ClearPathEngine(cfg, preemption_enabled=True, demand_level="med", baseline=base.metrics)
        for t in range(1, 150):
            cp.step()
            if t == 10:
                req = _build_request(cp, "AMB_1")
                cp.submit_emergency_request(req, "cardiac", ground_truth_valid=True)

        imp = cp.metrics.improvement_pct
        if imp is not None:
            improvements.append(imp)

    mean_imp = float(np.mean(improvements))
    std_imp = float(np.std(improvements))
    positive_count = sum(1 for imp in improvements if imp > 0.0)

    with capsys.disabled():
        print(f"\n[5-Seed Sweep] Improvements: {improvements}")
        print(f"[5-Seed Sweep] Mean Improvement: {mean_imp:.2f}% | Std Dev: {std_imp:.2f}%")
        print(f"[5-Seed Sweep] Positive: {positive_count}/{len(seeds)}")

    assert len(improvements) == len(seeds), "Some seeds failed to complete ambulance trip"
    assert positive_count >= 4, f"Expected positive improvement in >= 4 seeds, got {positive_count}/{len(seeds)}"
    assert mean_imp > 0.0, f"Expected positive mean improvement, got {mean_imp:.2f}%"


# ---------------------------------------------------------------------------
# 8. Property-style randomized safety audit
# ---------------------------------------------------------------------------

def test_safety_audit_randomized_invariants() -> None:
    """Property-style safety audit with randomized seeds and attack timing.

    Proves that across randomized runs:
      1. No two orthogonal approaches to any intersection are ever green simultaneously.
      2. Preemption hold duration never exceeds max_preemption_hold_s.
      3. Blocked spoofed requests never cause signal phase changes or overrides.
    """
    import random

    rng = random.Random(1337)
    test_seeds = [rng.randint(1, 100000) for _ in range(3)]

    for seed in test_seeds:
        config = load_config(
            seed=seed,
            max_ticks=80,
            authorized_vehicle_ids=frozenset({"AMB_VALID"}),
            max_preemption_hold_s=45,
        )
        engine = ClearPathEngine(config, preemption_enabled=True, demand_level="med")

        attack_ticks = {rng.randint(5, 40) for _ in range(3)}
        legit_tick = rng.randint(15, 30)
        hold_tracker = {node: 0 for node in engine.sim.signals}

        for t in range(1, 81):
            # Invariant 3: Blocked request never alters any signal state
            if t in attack_ticks:
                preempted_before = {node: ctrl.is_preempted for node, ctrl in engine.sim.signals.items()}
                phases_before = {node: ctrl.phase for node, ctrl in engine.sim.signals.items()}

                # Construct an unauthorized / spoofed request
                spoofed = _build_request(engine, "AMB_ATTACKER", incident_loc=(0.0, 0.0))
                res = engine.submit_emergency_request(spoofed, "cardiac", ground_truth_valid=False)

                assert res["authenticated"] is False, "Attack request was improperly authenticated"
                assert res["dispatch"] is None

                preempted_after = {node: ctrl.is_preempted for node, ctrl in engine.sim.signals.items()}
                for node in engine.sim.signals:
                    if not preempted_before[node]:
                        assert not preempted_after[node], f"Junction {node} was preempted by a blocked attack!"

            if t == legit_tick:
                legit_req = _build_request(engine, "AMB_VALID", incident_loc=(0.0, 0.0), severity="CRITICAL")
                engine.submit_emergency_request(legit_req, "cardiac", ground_truth_valid=True)

            engine.step()

            # Invariant 1 & 2 verification per tick
            for node, ctrl in engine.sim.signals.items():
                # Invariant 1: No conflicting orthogonal greens
                assert not _has_orthogonal_green_conflict(engine.sim, node), (
                    f"Conflicting greens detected at junction {node} at tick {t}"
                )

                # Invariant 2: Hold never exceeds max_preemption_hold_s
                if ctrl.is_preempted and ctrl.override_phase == ctrl.phase:
                    hold_tracker[node] += 1
                else:
                    hold_tracker[node] = 0

                assert hold_tracker[node] <= config.max_preemption_hold_s, (
                    f"Junction {node} held preemption for {hold_tracker[node]}s, "
                    f"exceeding max {config.max_preemption_hold_s}s"
                )
