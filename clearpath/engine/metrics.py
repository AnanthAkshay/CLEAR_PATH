"""Metrics collection and performance tracking for ClearPath-lite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SimulationMetrics:
    """Historical and aggregated metrics for the simulation."""

    ticks_elapsed: int = 0
    total_vehicles_served: int = 0
    average_wait_time_s: float = 0.0
    emergency_travel_time_s: float = 0.0
    preemption_events: int = 0
    rejected_requests: int = 0
    junction_delays: Dict[str, float] = field(default_factory=dict)
    speed_time_series: List[float] = field(default_factory=list)

