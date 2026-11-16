"""Scenario 1: Baseline normal traffic operations without emergency preemption.

Demonstrates 600 ticks of normal traffic at low, medium, and high demand
with no emergency. Reports average speed, throughput, and queue statistics.
Acts as a sanity baseline proving traffic signals cycle correctly without
agents interfering.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from clearpath.config import load_config
from clearpath.engine.orchestrator import ClearPathEngine

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scenarios.run_normal")


def run(seed: int = 42, demand: str = "med", ticks: int = 600) -> Dict[str, Any]:
    """Execute baseline normal traffic simulation for designated ticks and return summary metrics.

    Parameters
    ----------
    seed : int
        Random seed for deterministic traffic generation and route choices.
    demand : str
        Traffic demand level: 'low', 'med', or 'high'.
    ticks : int
        Number of 1-second simulation ticks to execute (default 600).

    Returns
    -------
    dict
        Dictionary containing average speed, throughput, queue statistics,
        completed vehicle counts, and simulation configuration details.
    """
    logger.info("Initializing Scenario 1: Normal Traffic Baseline (%d ticks, seed=%d, demand=%s)", ticks, seed, demand)
    config = load_config(seed=seed, max_ticks=ticks)
    engine = ClearPathEngine(config, preemption_enabled=False, demand_level=demand)

    queue_length_samples: List[float] = []

    for t in range(1, ticks + 1):
        engine.step()
        wv = engine.sim.get_world_view()
        avg_q = sum(wv.queues.values()) / max(1, len(wv.queues)) if wv.queues else 0.0
        queue_length_samples.append(avg_q)

    summary = engine.metrics.summary()
    mean_queue = sum(queue_length_samples) / max(1, len(queue_length_samples))
    completed = engine.sim.completed_vehicles
    avg_speed = summary.get("network_avg_speed_mps", 0.0)
    throughput = summary.get("network_throughput", 0.0)
    max_queue = summary.get("network_max_queue", 0)

    # Prove signals worked without agent interference
    preempted_signals = sum(1 for ctrl in engine.sim.signals.values() if ctrl.is_preempted)
    assert preempted_signals == 0, f"Expected 0 preempted signals, found {preempted_signals}"

    return {
        "status": "PASS",
        "scenario": "run_normal",
        "demand": demand,
        "seed": seed,
        "ticks": ticks,
        "average_speed_mps": avg_speed,
        "throughput_veh_per_tick": throughput,
        "mean_queue_length": round(mean_queue, 2),
        "max_queue_length": max_queue,
        "completed_vehicles": completed,
        "gridlock_ticks": summary.get("network_gridlock_ticks", 0),
        "preempted_signals": preempted_signals,
        "metrics_summary": summary,
    }


def _print_table(results: List[Dict[str, Any]]) -> None:
    """Print formatted summary table comparing demand levels."""
    sep = "=" * 70
    div = "-" * 70
    print("\n" + sep)
    print("CLEARPATH-LITE NORMAL TRAFFIC BASELINE REPORT (600 TICKS)")
    print(sep)
    print(f"{'Demand':<10} {'Avg Speed':<14} {'Throughput':<14} {'Mean Queue':<14} {'Max Queue':<12}")
    print(f"{'Level':<10} {'(m/s)':<14} {'(veh/tick)':<14} {'(veh/appr)':<14} {'(vehicles)':<12}")
    print(div)
    for res in results:
        print(
            f"{res['demand']:<10} "
            f"{res['average_speed_mps']:<14.2f} "
            f"{res['throughput_veh_per_tick']:<14.3f} "
            f"{res['mean_queue_length']:<14.2f} "
            f"{res['max_queue_length']:<12d}"
        )
    print(sep)
    print("Preempted signals: 0 across all runs (signals cycle autonomously)")
    print("[PASS] Normal traffic operations validated across all demand levels.\n")


def main() -> None:
    """Run baseline normal traffic across low, medium, and high demand levels."""
    print("\nExecuting Scenario 1: Normal Traffic Baseline across demand levels...")
    results = []
    for d in ["low", "med", "high"]:
        print(f"  Running 600 ticks at demand={d}...")
        res = run(seed=42, demand=d, ticks=600)
        results.append(res)
    _print_table(results)


if __name__ == "__main__":
    main()
