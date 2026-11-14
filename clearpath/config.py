"""Configuration module for the ClearPath-lite simulation platform.

Provides deterministic simulation parameters, vehicle physical constraints,
traffic signal phase limits, security thresholds, and route planning weights.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SimConfig:
    """Frozen configuration holding all parameters for ClearPath-lite simulation.

    Attributes:
        grid_rows: Number of horizontal grid axes/streets.
        grid_cols: Number of vertical grid axes/avenues.
        block_length_m: Distance between adjacent intersections in meters.
        tick_seconds: Simulation time advanced per discrete tick.
        max_ticks: Maximum ticks before simulation terminates.
        seed: Random seed for deterministic execution.
        arterial_mps: Maximum speed limit on arterial roads (m/s).
        residential_mps: Maximum speed limit on residential roads (m/s).
        ambulance_max_mps: Maximum emergency vehicle velocity (m/s).
        ambulance_max_accel: Maximum emergency vehicle acceleration (m/s^2).
        vehicle_length_m: Standard vehicle spatial length in meters.
        cycle_s: Total signal cycle time in seconds.
        green_s: Standard green phase duration in seconds.
        yellow_s: Standard yellow transition phase duration in seconds.
        all_red_s: Clearance all-red interval in seconds.
        window_s: Lookahead arrival window for green wave reservation (seconds).
        min_green_for_cross_s: Minimum green duration guaranteed to cross traffic.
        queue_flush_threshold: Vehicle queue count triggering proactive flushing.
        recovery_s: Duration of post-preemption signal recovery phase (seconds).
        max_preemption_hold_s: Maximum hold time for an active preemption lock (seconds).
        alpha: Weight assigned to travel time vs. hospital wait time in routing (0.0 to 1.0).
        hmac_secret: Shared secret for preemption token verification.
        token_ttl_s: Time-to-live expiration limit for cryptographic tokens (seconds).
        heading_tolerance_deg: Allowed discrepancy between reported heading and road vector.
        position_tolerance_m: Allowed distance deviation between reported GPS and road segment.
        rate_limit_per_vehicle_per_min: Maximum permitted preemption requests per vehicle per minute.
    """

    # Grid topology
    grid_rows: int = 6
    grid_cols: int = 6
    block_length_m: float = 200.0

    # Simulation engine parameters
    tick_seconds: float = 1.0
    max_ticks: int = 900
    seed: int = 42

    # Speed limits and vehicle dynamics
    arterial_mps: float = 16.7
    residential_mps: float = 11.1
    ambulance_max_mps: float = 25.0
    ambulance_max_accel: float = 4.0
    vehicle_length_m: float = 7.5

    # Signal timing parameters
    cycle_s: int = 60
    green_s: int = 26
    yellow_s: int = 3
    all_red_s: int = 1

    # Preemption and recovery parameters
    window_s: int = 25
    min_green_for_cross_s: int = 8
    queue_flush_threshold: int = 12
    recovery_s: int = 20
    max_preemption_hold_s: int = 45

    # Dispatcher routing weights
    alpha: float = 0.7

    # Security verification parameters
    hmac_secret: str = field(
        default_factory=lambda: os.environ.get(
            "CLEARPATH_SECRET", "clearpath-dev-secret-key-12345"
        )
    )
    token_ttl_s: int = 60
    heading_tolerance_deg: float = 35.0
    position_tolerance_m: float = 30.0
    rate_limit_per_vehicle_per_min: int = 6


def load_config(**overrides: Any) -> SimConfig:
    """Load simulation configuration with optional keyword parameter overrides.

    Args:
        **overrides: Key-value pairs overriding default SimConfig attributes.

    Returns:
        A frozen SimConfig instance with overrides applied.
    """
    return SimConfig(**overrides)

