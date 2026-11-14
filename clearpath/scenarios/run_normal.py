"""Scenario 1: Baseline normal traffic operations without emergency preemption."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List

# Ensure repository root is on sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from clearpath.config import load_config
from clearpath.sim.simulator import Simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scenarios.run_normal")


def run(ticks: int = 300, seed: int = 42) -> dict[str, float]:
    """Execute baseline normal traffic simulation for designated ticks and return summary metrics."""
    logger.info("Initializing Scenario 1: Normal Traffic Baseline (%d ticks, seed=%d)", ticks, seed)
    config = load_config(seed=seed, max_ticks=ticks)
    sim = Simulator(config, demand_level="med")

    active_vehicle_counts: List[int] = []
    queue_length_samples: List[float] = []

    for t in range(1, ticks + 1):
        sim.step()
        wv = sim.get_world_view()
        active_vehicle_counts.append(len(wv.vehicles))

        avg_queue = sum(wv.queues.values()) / max(1, len(wv.queues)) if wv.queues else 0.0
        queue_length_samples.append(avg_queue)

        if t % 60 == 0 or t == ticks:
            logger.info(
                "Tick %3d/%d | Active Cars: %3d | Completed: %3d | Avg Approach Queue: %.2f | Total Wait: %.1fs",
                t,
                ticks,
                len(wv.vehicles),
                sim.completed_vehicles,
                avg_queue,
                sim.total_wait_time_s,
            )

    mean_active_cars = sum(active_vehicle_counts) / len(active_vehicle_counts)
    mean_queue_length = sum(queue_length_samples) / len(queue_length_samples)
    mean_wait_time = sim.total_wait_time_s / max(1, sim.completed_vehicles + len(sim.vehicles))

    print("\n" + "=" * 60)
    print("CLEARPATH-LITE HEADLESS SIMULATION REPORT (300 TICKS)")
    print("=" * 60)
    print(f"Simulation Ticks Completed : {ticks}")
    print(f"Mean Active Vehicles/Tick  : {mean_active_cars:.2f}")
    print(f"Total Completed Trips      : {sim.completed_vehicles}")
    print(f"Mean Approach Queue Length : {mean_queue_length:.2f} vehicles")
    print(f"Mean Vehicle Wait Time     : {mean_wait_time:.2f} s")
    print("=" * 60 + "\n")

    return {
        "mean_active_cars": mean_active_cars,
        "mean_queue_length": mean_queue_length,
        "completed_vehicles": float(sim.completed_vehicles),
        "mean_wait_time_s": mean_wait_time,
    }


if __name__ == "__main__":
    run()
