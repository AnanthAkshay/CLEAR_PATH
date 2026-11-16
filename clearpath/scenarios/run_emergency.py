"""Scenario: Baseline vs. ClearPath emergency preemption comparison.

Runs the SAME seeded traffic scenario twice:
  1. Baseline  — preemption_enabled=False (no signal override)
  2. ClearPath — preemption_enabled=True  (full HMAC-authenticated preemption)

A formatted metrics summary table is printed at the end comparing both runs.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any, Dict, Optional

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scenarios.run_emergency")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEED = 42
TICKS = 300
AMB_ORIGIN = "j_0_0"
AMB_DEST = "j_5_5"
AMB_SPAWN_TICK = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Return Δ string between ClearPath and Baseline values."""
    if baseline is None or clearpath is None:
        return "—"
    try:
        diff = float(clearpath) - float(baseline)
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff:.1f}{unit}"
    except (TypeError, ValueError):
        return "—"


def _build_preemption_request(engine: Any, amb_id: str) -> Optional[Any]:
    """Construct a valid PreemptionRequest for the given ambulance.

    Returns the request object or None if construction fails.
    """
    try:
        from clearpath.agents.tokens import issue_token
        from clearpath.bus.messages import PreemptionRequest, Telemetry

        vehicle = engine.sim.vehicles.get(amb_id)
        if vehicle is None:
            logger.warning("Ambulance %s not found in simulator vehicles.", amb_id)
            return None

        tick = engine.current_tick
        x, y = engine.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
        nonce = str(uuid.uuid4())
        token = issue_token(amb_id, nonce, float(tick), engine.config.hmac_secret)
        bearing = engine.sim.network.edge_bearing(*vehicle.edge)

        req = PreemptionRequest(
            vehicle_id=amb_id,
            token=token,
            nonce=nonce,
            incident_loc=(x, y),
            severity="CRITICAL",
            telemetry=Telemetry(
                x=x,
                y=y,
                speed_mps=vehicle.speed,
                accel_mps2=0.0,
                heading_deg=bearing,
                edge_id=f"{vehicle.edge[0]}_{vehicle.edge[1]}",
                lane=vehicle.lane,
                vehicle_id=amb_id,
            ),
            sender="ambulance",
        )
        return req
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to build PreemptionRequest: %s", exc)
        return None


def _run_once(
    preemption_enabled: bool, baseline_engine: Optional[Any] = None
) -> Dict[str, Any]:
    """Execute a single seeded scenario run and return the metrics summary dict.

    Args:
        preemption_enabled: Whether the ClearPath signal preemption subsystem
            is active during this run.
        baseline_engine: Previously-run baseline engine whose metrics can be
            passed to the ClearPath run for delta calculations.

    Returns:
        A dict of collected metrics, or a minimal fallback dict on failure.
    """
    label = "ClearPath" if preemption_enabled else "Baseline"
    logger.info("Starting %s run (preemption_enabled=%s).", label, preemption_enabled)

    try:
        from clearpath.config import load_config
        from clearpath.engine.orchestrator import ClearPathEngine
        from clearpath.agents.tokens import issue_token
        from clearpath.bus.messages import PreemptionRequest, Telemetry
    except ImportError as exc:
        logger.error("Could not import required modules: %s", exc)
        return {"_error": str(exc)}

    try:
        config = load_config(seed=SEED, max_ticks=TICKS)
        baseline_m = baseline_engine.metrics if baseline_engine else None
        engine = ClearPathEngine(
            config,
            preemption_enabled=preemption_enabled,
            demand_level="med",
            baseline=baseline_m,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialise ClearPathEngine: %s", exc)
        return {"_error": str(exc)}

    amb_id = "AMB_1"
    request_result: Optional[Dict[str, Any]] = None

    # -----------------------------------------------------------------------
    # Tick loop
    # -----------------------------------------------------------------------
    for _ in range(TICKS):
        try:
            engine.step()
        except Exception as exc:  # noqa: BLE001
            logger.error("Engine step raised an error at tick %d: %s", engine.current_tick, exc)
            break

        # Spawn/submit ambulance preemption request at AMB_SPAWN_TICK
        if engine.current_tick == AMB_SPAWN_TICK and request_result is None:
            nonce = str(uuid.uuid4())
            token = issue_token(amb_id, nonce, float(engine.current_tick), engine.config.hmac_secret)
            req = PreemptionRequest(
                vehicle_id=amb_id,
                token=token,
                nonce=nonce,
                incident_loc=(0.0, 0.0),
                severity="CRITICAL",
                telemetry=Telemetry(
                    x=0.0,
                    y=0.0,
                    speed_mps=10.0,
                    accel_mps2=0.0,
                    heading_deg=90.0,
                    edge_id="j_0_0_j_0_1",
                    lane=0,
                    vehicle_id=amb_id,
                ),
                sender="ambulance",
            )
            try:
                request_result = engine.submit_emergency_request(req, "cardiac", ground_truth_valid=True)
                auth_ok = request_result.get("authenticated", False)
                logger.info(
                    "[%s] submit_emergency_request returned authenticated=%s.",
                    label,
                    auth_ok,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] submit_emergency_request failed: %s", label, exc)
                request_result = {"authenticated": False, "_error": str(exc)}

    # -----------------------------------------------------------------------
    # Collect metrics
    # -----------------------------------------------------------------------
    summary: Dict[str, Any] = {}
    try:
        summary = engine.metrics.summary()
    except Exception as exc:  # noqa: BLE001
        logger.error("metrics.summary() raised: %s", exc)
        summary = {"_error": str(exc), "ticks_elapsed": engine.current_tick}

    summary["_request_result"] = request_result
    summary["_amb_id"] = amb_id
    summary["_engine"] = engine
    return summary


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(baseline: Dict[str, Any], clearpath: Dict[str, Any]) -> None:
    """Print a formatted comparison table to stdout."""
    SEP = "=" * 62
    DIV = "-" * 62
    COL_W = 14  # Width for each value column

    def row(label: str, b_val: Any, c_val: Any, unit: str = "") -> str:
        b_str = _fmt(b_val, unit)
        c_str = _fmt(c_val, unit)
        d_str = _delta(b_val, c_val, unit)
        return f"{label:<30}  {b_str:<{COL_W}} {c_str:<{COL_W}} {d_str}"

    print(SEP)
    print("CLEARPATH-LITE EMERGENCY PREEMPTION REPORT")
    print(SEP)
    print(f"{'Metric':<30}  {'Baseline':<{COL_W}} {'ClearPath':<{COL_W}} Δ")
    print(DIV)

    # -- Ambulance metrics ---------------------------------------------------
    print(row(
        "Ambulance travel time (s)",
        baseline.get("ambulance_travel_time_s"),
        clearpath.get("ambulance_travel_time_s"),
        " s",
    ))
    print(row(
        "Ambulance stops",
        baseline.get("ambulance_stops"),
        clearpath.get("ambulance_stops"),
    ))
    print(row(
        "Ambulance stopped time (s)",
        baseline.get("ambulance_stopped_time_s"),
        clearpath.get("ambulance_stopped_time_s"),
        " s",
    ))
    print(DIV)

    # -- Security metrics ----------------------------------------------------
    print(row(
        "Security requests",
        baseline.get("security_total_requests"),
        clearpath.get("security_total_requests"),
    ))
    print(row(
        "Security blocked",
        baseline.get("security_blocked"),
        clearpath.get("security_blocked"),
    ))
    print(row(
        "Security block rate",
        baseline.get("security_block_rate"),
        clearpath.get("security_block_rate"),
        "%",
    ))
    print(DIV)

    # -- Network metrics -----------------------------------------------------
    print(row(
        "Network throughput (veh/tick)",
        baseline.get("network_throughput"),
        clearpath.get("network_throughput"),
    ))
    print(row(
        "Network avg speed (m/s)",
        baseline.get("network_avg_speed_mps") or baseline.get("network_avg_speed"),
        clearpath.get("network_avg_speed_mps") or clearpath.get("network_avg_speed"),
        " m/s",
    ))
    print(row(
        "Network max queue",
        baseline.get("network_max_queue"),
        clearpath.get("network_max_queue"),
    ))
    print(row(
        "Cross-traffic extra delay (avg)",
        baseline.get("cross_delay_avg_s"),
        clearpath.get("cross_delay_avg_s"),
        " s",
    ))
    print(DIV)

    # -- Negotiation metrics -------------------------------------------------
    print(row(
        "Negotiation messages",
        baseline.get("negotiation_messages_sent") or baseline.get("negotiation_messages"),
        clearpath.get("negotiation_messages_sent") or clearpath.get("negotiation_messages"),
    ))
    print(row(
        "Negotiation NACKs",
        baseline.get("negotiation_nack_count"),
        clearpath.get("negotiation_nack_count"),
    ))
    print(DIV)

    # -- Simulation metadata -------------------------------------------------
    print(row(
        "Ticks elapsed",
        baseline.get("ticks_elapsed"),
        clearpath.get("ticks_elapsed"),
    ))

    # -- Request outcome (ClearPath only) ------------------------------------
    rr = clearpath.get("_request_result")
    amb_id = clearpath.get("_amb_id")
    if amb_id:
        print(DIV)
        auth_flag = "YES" if (rr and rr.get("authenticated")) else "NO"
        dispatch = rr.get("dispatch") if rr else None
        print(f"{'Ambulance ID':<30}  {str(amb_id)}")
        print(f"{'Preemption authenticated':<30}  {auth_flag}")
        if dispatch:
            hospital = dispatch.get("hospital_id", dispatch.get("hospital", "—"))
            eta = dispatch.get("total_eta_s", dispatch.get("eta_s"))
            print(f"{'Dispatched to hospital':<30}  {hospital}")
            if eta is not None:
                print(f"{'Estimated arrival (s)':<30}  {_fmt(eta, ' s')}")
        imp = clearpath.get("ambulance_improvement_pct")
        if imp is not None:
            print(f"{'Travel time improvement':<30}  {imp:.1f}%")

    print(SEP)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Run the emergency preemption comparison scenario."""
    print("\nRunning BASELINE scenario (no preemption)…")
    baseline_metrics = _run_once(preemption_enabled=False)

    if "_error" in baseline_metrics:
        print(f"[ERROR] Baseline run failed: {baseline_metrics['_error']}", file=sys.stderr)

    base_eng = baseline_metrics.get("_engine")
    print("Running CLEARPATH scenario (preemption enabled)…\n")
    clearpath_metrics = _run_once(preemption_enabled=True, baseline_engine=base_eng)

    if "_error" in clearpath_metrics:
        print(f"[ERROR] ClearPath run failed: {clearpath_metrics['_error']}", file=sys.stderr)

    _print_report(baseline_metrics, clearpath_metrics)


if __name__ == "__main__":
    run()
