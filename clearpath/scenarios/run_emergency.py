"""Scenario 2: Emergency Preemption vs. Baseline Comparison.

Executes the SAME seeded traffic scenario twice:
  1. Baseline  — preemption_enabled=False (standard fixed-time traffic signals)
  2. ClearPath — preemption_enabled=True  (HMAC-authenticated dynamic preemption corridor)

Evaluates a valid cardiac incident located at a far corner of the grid (j_0_0).
Compares:
  - Ambulance travel time
  - Ambulance stops
  - Cross-traffic delay (average and p95)
  - Max queue length
  - Recovery duration
  - Inter-agent negotiation messages exchanged

Asserts:
  - The ClearPath ambulance is strictly faster than baseline.
  - The network throughput recovers to within 10% of baseline throughput
    within recovery_s + 60 seconds after ambulance arrival.
"""

from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from clearpath.agents.tokens import issue_token
from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import load_config
from clearpath.engine.orchestrator import ClearPathEngine

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scenarios.run_emergency")

AMB_SPAWN_TICK = 10
INCIDENT_LOC = (0.0, 0.0)
INCIDENT_TYPE = "cardiac"
AMB_ID = "AMB_1"


def _fmt(value: Any, unit: str = "") -> str:
    """Format a metric value for table display."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.1f}{unit}"
    if isinstance(value, int):
        return f"{value}{unit}"
    return str(value)


def _delta(baseline: Any, clearpath: Any, unit: str = "") -> str:
    """Return delta string between ClearPath and Baseline values."""
    if baseline is None or clearpath is None:
        return "—"
    try:
        diff = float(clearpath) - float(baseline)
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff:.1f}{unit}"
    except (TypeError, ValueError):
        return "—"


def _execute_run(
    seed: int,
    demand: str,
    ticks: int,
    preemption_enabled: bool,
    baseline_metrics: Optional[Any] = None,
) -> Dict[str, Any]:
    """Execute one simulation pass with or without signal preemption."""
    config = load_config(seed=seed, max_ticks=ticks)
    engine = ClearPathEngine(
        config,
        preemption_enabled=preemption_enabled,
        demand_level=demand,
        baseline=baseline_metrics,
    )

    request_result: Optional[Dict[str, Any]] = None

    for t in range(1, ticks + 1):
        engine.step()

        # Submit emergency preemption request at AMB_SPAWN_TICK
        if t == AMB_SPAWN_TICK and request_result is None:
            nonce = str(uuid.uuid4())
            token = issue_token(AMB_ID, nonce, float(t), config.hmac_secret)
            req = PreemptionRequest(
                vehicle_id=AMB_ID,
                token=token,
                nonce=nonce,
                incident_loc=INCIDENT_LOC,
                severity="CRITICAL",
                telemetry=Telemetry(
                    x=0.0,
                    y=0.0,
                    speed_mps=10.0,
                    accel_mps2=0.0,
                    heading_deg=90.0,
                    edge_id="j_0_0_j_0_1",
                    lane=0,
                    vehicle_id=AMB_ID,
                ),
                sender="ambulance",
            )
            request_result = engine.submit_emergency_request(
                req,
                incident_type=INCIDENT_TYPE,
                ground_truth_valid=True,
            )

    summary = engine.metrics.summary()
    summary["_engine"] = engine
    summary["_request_result"] = request_result
    return summary


def run(seed: int = 42, demand: str = "med", ticks: int = 300) -> Dict[str, Any]:
    """Run emergency preemption comparison scenario (Baseline vs ClearPath).

    Parameters
    ----------
    seed : int
        RNG seed for simulation determinism.
    demand : str
        Traffic demand level ('low', 'med', 'high').
    ticks : int
        Simulation duration in seconds/ticks (default 300).

    Returns
    -------
    dict
        Combined comparison metrics and validation outcome.
    """
    logger.info("Starting Scenario 2: Emergency Preemption (seed=%d, demand=%s, ticks=%d)", seed, demand, ticks)

    # 1. Baseline run (no preemption)
    base_summary = _execute_run(seed, demand, ticks, preemption_enabled=False)
    base_engine: ClearPathEngine = base_summary.pop("_engine")

    # 2. ClearPath run (preemption enabled)
    cp_summary = _execute_run(
        seed,
        demand,
        ticks,
        preemption_enabled=True,
        baseline_metrics=base_engine.metrics,
    )
    cp_engine: ClearPathEngine = cp_summary.pop("_engine")

    # 3. Extract core metrics
    base_travel = base_summary.get("ambulance_travel_time_s")
    cp_travel = cp_summary.get("ambulance_travel_time_s")
    base_stops = base_summary.get("ambulance_stops", 0)
    cp_stops = cp_summary.get("ambulance_stops", 0)
    cross_avg = cp_summary.get("cross_delay_avg_s", 0.0)
    cross_p95 = cp_summary.get("cross_delay_p95_s", 0.0)
    base_max_q = base_summary.get("network_max_queue", 0)
    cp_max_q = cp_summary.get("network_max_queue", 0)
    messages_sent = cp_summary.get("negotiation_messages_sent", 0)
    imp_pct = cp_summary.get("ambulance_improvement_pct", 0.0)

    # Recovery durations
    recovery_times_map = cp_summary.get("recovery_times", {})
    all_rec_times: List[float] = [t for times in recovery_times_map.values() for t in times]
    avg_recovery_s = sum(all_rec_times) / max(1, len(all_rec_times)) if all_rec_times else float(cp_engine.config.recovery_s)

    # 4. Throughput recovery evaluation within recovery_s + 60 s
    arrival_tick = AMB_SPAWN_TICK + int(cp_travel) if cp_travel is not None else 60
    eval_tick = min(ticks, arrival_tick + cp_engine.config.recovery_s + 60)

    base_ts = base_summary.get("ts_completed", [])
    cp_ts = cp_summary.get("ts_completed", [])

    base_comp_eval = base_ts[eval_tick - 1] if len(base_ts) >= eval_tick else base_ts[-1]
    cp_comp_eval = cp_ts[eval_tick - 1] if len(cp_ts) >= eval_tick else cp_ts[-1]

    base_tp_eval = base_comp_eval / max(1, eval_tick)
    cp_tp_eval = cp_comp_eval / max(1, eval_tick)

    # Assertions
    is_faster = (cp_travel is not None and base_travel is not None and cp_travel < base_travel)
    throughput_ratio = cp_tp_eval / max(1e-6, base_tp_eval)
    # Network recovers to within 10% of baseline throughput (i.e. cp_tp >= 0.90 * base_tp)
    is_recovered = throughput_ratio >= 0.90

    # 5. Print Comparison Table
    sep = "=" * 66
    div = "-" * 66
    col_w = 14

    def row(label: str, b_val: Any, c_val: Any, unit: str = "") -> str:
        b_str = _fmt(b_val, unit)
        c_str = _fmt(c_val, unit)
        d_str = _delta(b_val, c_val, unit)
        return f"{label:<32} {b_str:<{col_w}} {c_str:<{col_w}} {d_str}"

    print("\n" + sep)
    print("CLEARPATH-LITE EMERGENCY PREEMPTION REPORT")
    print(sep)
    print(f"{'Metric':<32} {'Baseline':<{col_w}} {'ClearPath':<{col_w}} Δ")
    print(div)
    print(row("Ambulance travel time", base_travel, cp_travel, " s"))
    print(row("Ambulance stops", base_stops, cp_stops))
    print(row("Ambulance stopped time", base_summary.get("ambulance_stopped_time_s"), cp_summary.get("ambulance_stopped_time_s"), " s"))
    print(div)
    print(row("Cross-traffic delay (avg)", base_summary.get("cross_delay_avg_s", 0.0), cross_avg, " s"))
    print(row("Cross-traffic delay (p95)", base_summary.get("cross_delay_p95_s", 0.0), cross_p95, " s"))
    print(row("Network max queue", base_max_q, cp_max_q, " veh"))
    print(row("Recovery duration (avg)", "—", avg_recovery_s, " s"))
    print(row("Messages exchanged", base_summary.get("negotiation_messages_sent", 0), messages_sent))
    print(div)
    print(row("Network throughput", base_summary.get("network_throughput"), cp_summary.get("network_throughput"), " veh/t"))
    print(row("Throughput @ recovery+60s", base_tp_eval, cp_tp_eval, " veh/t"))
    print(row("Network avg speed", base_summary.get("network_avg_speed_mps"), cp_summary.get("network_avg_speed_mps"), " m/s"))
    print(div)
    print(f"{'Ambulance travel improvement':<32} {imp_pct:.1f}%")
    print(f"{'Throughput recovery ratio':<32} {throughput_ratio * 100.0:.1f}% of baseline")
    print(sep)

    # Assert in output
    print(f"[ASSERT {'PASS' if is_faster else 'FAIL'}] Ambulance is faster: ClearPath={cp_travel:.1f}s < Baseline={base_travel:.1f}s")
    print(
        f"[ASSERT {'PASS' if is_recovered else 'FAIL'}] Network recovered to within 10% of baseline throughput "
        f"at tick {eval_tick} (recovery_s + 60s): ClearPath={cp_tp_eval:.3f} veh/t vs Baseline={base_tp_eval:.3f} veh/t "
        f"({throughput_ratio * 100.0:.1f}% of baseline)\n"
    )

    assert is_faster, f"ClearPath ambulance ({cp_travel}s) was not faster than baseline ({base_travel}s)"
    assert is_recovered, f"Throughput did not recover to within 10% of baseline: ratio was {throughput_ratio:.2%}"

    return {
        "status": "PASS" if is_faster and is_recovered else "FAIL",
        "scenario": "run_emergency",
        "seed": seed,
        "demand": demand,
        "ticks": ticks,
        "ambulance_time_baseline": base_travel,
        "ambulance_time_clearpath": cp_travel,
        "ambulance_stops_baseline": base_stops,
        "ambulance_stops_clearpath": cp_stops,
        "cross_delay_avg_s": cross_avg,
        "cross_delay_p95_s": cross_p95,
        "max_queue_baseline": base_max_q,
        "max_queue_clearpath": cp_max_q,
        "recovery_time_avg_s": round(avg_recovery_s, 2),
        "recovery_times": recovery_times_map,
        "messages_exchanged": messages_sent,
        "improvement_pct": imp_pct,
        "throughput_recovery_eval_tick": eval_tick,
        "throughput_recovery_ratio": round(throughput_ratio, 4),
        "baseline_throughput_at_recovery": round(base_tp_eval, 4),
        "clearpath_throughput_at_recovery": round(cp_tp_eval, 4),
        "baseline": base_summary,
        "clearpath": cp_summary,
    }


def main() -> None:
    """Run emergency preemption comparison scenario."""
    run(seed=42, demand="med", ticks=300)


if __name__ == "__main__":
    main()
