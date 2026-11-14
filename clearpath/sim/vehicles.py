"""Vehicle kinematics, lane positions, and trajectory representations.

Implements an IDM-lite car-following model ensuring collision-free progression,
emergency vehicle preemption behavior, and civilian yield responses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Vehicle:
    """Represents an active vehicle within the simulation.

    Attributes:
        id: Unique identifier for the vehicle.
        kind: 'car' or 'ambulance'.
        edge: Current directed edge occupied (u, v).
        offset_m: Longitudinal position along edge in meters from node u.
        speed: Instantaneous velocity in meters per second.
        lane: Current lane index (0 = right/shoulder, 1 = inner/passing).
        route: Ordered list of remaining junction nodes to traverse.
        is_stopped: Flag indicating vehicle speed < 0.1 m/s.
        wait_time: Cumulative seconds spent stationary.
        yield_until_t: Simulation timestamp until which car yields to emergency traffic.
        length_m: Physical vehicle length in meters.
        max_speed: Maximum achievable velocity in m/s.
        max_accel: Maximum forward acceleration in m/s^2.
        comfortable_decel: Desired braking deceleration in m/s^2.
        crawl_speed_mps: Reduced speed when ambulance is blocked by traffic.
    """

    id: str
    kind: str = "car"
    edge: Tuple[str, str] = ("", "")
    offset_m: float = 0.0
    speed: float = 0.0
    lane: int = 0
    route: List[str] = field(default_factory=list)
    is_stopped: bool = False
    wait_time: float = 0.0
    yield_until_t: float = 0.0
    length_m: float = 7.5
    max_speed: float = 16.7
    max_accel: float = 2.5
    comfortable_decel: float = 3.0
    crawl_speed_mps: float = 4.0

    @property
    def is_ambulance(self) -> bool:
        """Return True if this vehicle is an emergency ambulance."""
        return self.kind == "ambulance"

    def compute_idm_accel(
        self,
        v0: float,
        leader: Optional[Vehicle],
        stop_line_dist: Optional[float],
        dt: float = 1.0,
    ) -> float:
        """Compute IDM-lite acceleration with respect to leader or red stop line.

        Args:
            v0: Desired speed limit (m/s).
            leader: Immediate leading vehicle in same lane, if any.
            stop_line_dist: Distance to mandatory red/yellow stop bar, if any.
            dt: Time step duration.

        Returns:
            Acceleration rate in m/s^2, bounded between -6.0 and max_accel.
        """
        # Determine closest constraint
        min_gap = float("inf")
        rel_speed = 0.0

        if leader is not None:
            # Physical gap to leader bumper
            gap_to_leader = leader.offset_m - self.offset_m - leader.length_m
            min_gap = gap_to_leader
            rel_speed = self.speed - leader.speed

        if stop_line_dist is not None:
            # Stop line acts as a stationary leader at bumper clearance
            gap_to_line = stop_line_dist - self.length_m
            if gap_to_line < min_gap:
                min_gap = gap_to_line
                rel_speed = self.speed  # Leader is stationary (speed = 0)

        # IDM-lite calculation
        s0 = 2.5  # minimum bumper distance (m)
        t_headway = 1.2  # desired time headway (s)

        if min_gap < float("inf"):
            s_star = s0 + max(
                0.0,
                self.speed * t_headway
                + (self.speed * rel_speed) / (2.0 * math.sqrt(max(0.1, self.max_accel * self.comfortable_decel))),
            )
            gap_ratio = (s_star / max(0.5, min_gap)) ** 2
        else:
            gap_ratio = 0.0

        vel_ratio = (self.speed / max(0.1, v0)) ** 4 if v0 > 0 else 1.0
        accel = self.max_accel * (1.0 - vel_ratio - gap_ratio)

        # Clamp between emergency deceleration and max acceleration
        return max(-6.0, min(self.max_accel, accel))
