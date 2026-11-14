"""Traffic signal state machines and phase controller interfaces.

Implements fixed-time signal cycles with per-junction offsets and safe
emergency preemption state machines that strictly enforce clearance intervals
(yellow and all-red) before switching phases.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from clearpath.config import SimConfig


class SignalPhase(str, Enum):
    """Traffic signal state machine phases."""

    NS_GREEN = "NS_GREEN"
    NS_YELLOW = "NS_YELLOW"
    ALL_RED_TO_EW = "ALL_RED_TO_EW"
    EW_GREEN = "EW_GREEN"
    EW_YELLOW = "EW_YELLOW"
    ALL_RED_TO_NS = "ALL_RED_TO_NS"


class SignalController:
    """Manages cycle timing and preemption transitions for an intersection.

    Attributes:
        junction_id: Unique intersection identifier.
        config: Simulation timing configuration.
        offset_s: Phase cycle offset to prevent synchronized grid shockwaves.
        phase: Current active phase of the state machine.
        time_in_phase_s: Seconds elapsed in the active phase.
        is_preempted: Whether preemption lock or transition is currently active.
    """

    def __init__(
        self,
        junction_id: str,
        config: SimConfig,
        offset_s: float = 0.0,
    ) -> None:
        """Initialize controller with junction ID, timing config, and cycle offset."""
        self.junction_id = junction_id
        self.config = config
        self.offset_s = offset_s % config.cycle_s

        self.phase: SignalPhase = SignalPhase.NS_GREEN
        self.time_in_phase_s: float = 0.0

        # Preemption override tracking
        self.is_preempted: bool = False
        self.override_phase: Optional[SignalPhase] = None
        self.override_reason: str = ""
        self.preemption_start_t: float = 0.0
        self.pending_target: Optional[SignalPhase] = None

        # Initialize phase state according to offset
        self._init_phase_from_offset(self.offset_s)

    def _init_phase_from_offset(self, offset: float) -> None:
        """Place controller into initial phase state based on cycle offset."""
        g = float(self.config.green_s)
        y = float(self.config.yellow_s)
        r = float(self.config.all_red_s)

        t = offset % self.config.cycle_s
        if t < g:
            self.phase = SignalPhase.NS_GREEN
            self.time_in_phase_s = t
        elif t < g + y:
            self.phase = SignalPhase.NS_YELLOW
            self.time_in_phase_s = t - g
        elif t < g + y + r:
            self.phase = SignalPhase.ALL_RED_TO_EW
            self.time_in_phase_s = t - (g + y)
        elif t < 2 * g + y + r:
            self.phase = SignalPhase.EW_GREEN
            self.time_in_phase_s = t - (g + y + r)
        elif t < 2 * g + 2 * y + r:
            self.phase = SignalPhase.EW_YELLOW
            self.time_in_phase_s = t - (2 * g + y + r)
        else:
            self.phase = SignalPhase.ALL_RED_TO_NS
            self.time_in_phase_s = t - (2 * g + 2 * y + r)

    def current_phase(self) -> SignalPhase:
        """Return the current active signal phase."""
        return self.phase

    def time_in_phase(self) -> float:
        """Return elapsed seconds in the current phase."""
        return self.time_in_phase_s

    def set_phase_override(
        self,
        target_phase: SignalPhase | str,
        reason: str = "",
        t: float = 0.0,
    ) -> None:
        """Request emergency preemption override for designated movement corridor.

        Ensures preemption safely transitions through clearance phases (yellow and
        all-red) if the intersection is currently in a conflicting phase.

        Args:
            target_phase: Desired movement corridor ('NS', 'EW', NS_GREEN, or EW_GREEN).
            reason: Diagnostic explanation for logging.
            t: Simulation timestamp when preemption was initiated.
        """
        # Normalize target green phase
        if isinstance(target_phase, str):
            target_str = target_phase.upper()
            if "NS" in target_str:
                desired = SignalPhase.NS_GREEN
            elif "EW" in target_str:
                desired = SignalPhase.EW_GREEN
            else:
                desired = SignalPhase[target_str]
        else:
            desired = (
                SignalPhase.NS_GREEN
                if target_phase in (SignalPhase.NS_GREEN, SignalPhase.NS_YELLOW)
                else SignalPhase.EW_GREEN
            )

        self.is_preempted = True
        self.override_phase = desired
        self.override_reason = reason
        self.preemption_start_t = t

        # If already in desired green phase, lock into it
        if self.phase == desired:
            self.pending_target = None
            return

        # If conflicting movement is currently green, trigger yellow clearance
        if desired == SignalPhase.NS_GREEN:
            if self.phase == SignalPhase.EW_GREEN:
                self.phase = SignalPhase.EW_YELLOW
                self.time_in_phase_s = 0.0
            self.pending_target = SignalPhase.NS_GREEN
        else:  # desired == SignalPhase.EW_GREEN
            if self.phase == SignalPhase.NS_GREEN:
                self.phase = SignalPhase.NS_YELLOW
                self.time_in_phase_s = 0.0
            self.pending_target = SignalPhase.EW_GREEN

    def clear_override(self) -> None:
        """Release preemption lock and resume normal signal cycling."""
        self.is_preempted = False
        self.override_phase = None
        self.override_reason = ""
        self.pending_target = None

    def state_for_approach(self, edge: Tuple[str, str] | str) -> str:
        """Return signal display indicator ('G', 'Y', 'R') for an inbound approach edge.

        Args:
            edge: Approach edge specified as (u, v) tuple or string 'u_v'.

        Returns:
            'G' for Green, 'Y' for Yellow, 'R' for Red.
        """
        if isinstance(edge, tuple):
            u, v = edge
        else:
            parts = edge.split("_")
            u, v = parts[0], parts[1]

        # Determine if approach is North-South or East-West
        # Based on junction naming convention 'j_r_c'
        is_ns = self._is_north_south_approach(u, v)

        if is_ns:
            if self.phase == SignalPhase.NS_GREEN:
                return "G"
            elif self.phase == SignalPhase.NS_YELLOW:
                return "Y"
            else:
                return "R"
        else:
            if self.phase == SignalPhase.EW_GREEN:
                return "G"
            elif self.phase == SignalPhase.EW_YELLOW:
                return "Y"
            else:
                return "R"

    def _is_north_south_approach(self, u: str, v: str) -> bool:
        """Helper to deduce if edge (u, v) is a North-South movement."""
        try:
            u_parts = u.split("_")
            v_parts = v.split("_")
            if len(u_parts) >= 3 and len(v_parts) >= 3:
                u_r, u_c = int(u_parts[1]), int(u_parts[2])
                v_r, v_c = int(v_parts[1]), int(v_parts[2])
                if u_c == v_c:
                    return True
                if u_r == v_r:
                    return False
        except (ValueError, IndexError):
            pass
        return True

    def step(self, dt: float = 1.0) -> None:
        """Advance controller state machine by dt seconds (default 1.0s)."""
        self.time_in_phase_s += dt

        g = float(self.config.green_s)
        y = float(self.config.yellow_s)
        r = float(self.config.all_red_s)
        max_hold = float(self.config.max_preemption_hold_s)

        # If holding a preemption green phase
        if self.is_preempted and self.override_phase == self.phase and self.pending_target is None:
            # Check maximum safety hold limit
            if self.time_in_phase_s >= max_hold:
                # Force release of preemption hold for cross-street safety
                self.clear_override()
            else:
                # Hold green until cleared
                return

        # State transitions
        if self.phase == SignalPhase.NS_GREEN:
            if self.time_in_phase_s >= g:
                self.phase = SignalPhase.NS_YELLOW
                self.time_in_phase_s = 0.0

        elif self.phase == SignalPhase.NS_YELLOW:
            if self.time_in_phase_s >= y:
                self.phase = SignalPhase.ALL_RED_TO_EW
                self.time_in_phase_s = 0.0

        elif self.phase == SignalPhase.ALL_RED_TO_EW:
            if self.time_in_phase_s >= r:
                # Check if we were preempted towards NS or normal EW
                if self.is_preempted and self.pending_target == SignalPhase.NS_GREEN:
                    self.phase = SignalPhase.NS_GREEN
                    self.pending_target = None
                else:
                    self.phase = SignalPhase.EW_GREEN
                self.time_in_phase_s = 0.0

        elif self.phase == SignalPhase.EW_GREEN:
            if self.time_in_phase_s >= g:
                self.phase = SignalPhase.EW_YELLOW
                self.time_in_phase_s = 0.0

        elif self.phase == SignalPhase.EW_YELLOW:
            if self.time_in_phase_s >= y:
                self.phase = SignalPhase.ALL_RED_TO_NS
                self.time_in_phase_s = 0.0

        elif self.phase == SignalPhase.ALL_RED_TO_NS:
            if self.time_in_phase_s >= r:
                # Check if we were preempted towards EW or normal NS
                if self.is_preempted and self.pending_target == SignalPhase.EW_GREEN:
                    self.phase = SignalPhase.EW_GREEN
                    self.pending_target = None
                else:
                    self.phase = SignalPhase.NS_GREEN
                self.time_in_phase_s = 0.0
