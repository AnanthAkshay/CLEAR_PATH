"""GuidanceAgent: Synthesizes driver advisories to clear emergency vehicle corridors.

Each tick the agent scans a 150 m look-ahead zone in front of the ambulance,
classifies every civilian vehicle it finds, and emits deduplicated
GuidanceAdvisory messages.  It also calls ``simulator.apply_yield()`` through
the actuator so affected vehicles actually slow or pull aside, and maintains a
rolling feed of the last 50 advisories for the dashboard together with a
per-junction VMS board broadcast text.

Look-ahead zone
---------------
* Current edge: vehicles that are **ahead** of the ambulance (offset_m >
  ambulance offset_m) and within 150 m of the ambulance.
* Next edge of the route: all vehicles, up to 150 m minus the remaining
  distance on the current edge.

Classification (in priority order)
------------------------------------
1. Same lane, same edge, within 80 m              → "Clear lane N" (move aside)
2. Single-lane road, same edge ahead              → "Pull over to the left shoulder and stop"
3. At red-light queue in the ambulance's path     → "Hold position … leave a gap" / "Slow down"
4. Different lane, same or next edge, 80-150 m   → "Slow down, emergency vehicle approaching"
5. Crossing street (approaches to next junction) → "Stop. Do not enter the intersection"

Drive-side convention
---------------------
India default: drive on the **left**.  Lane 0 = left-most (shoulder), Lane 1 =
passing lane.  "Pull over" means move to lane 0.  On a right-hand-traffic road
lane assignments are flipped, so the agent picks the direction automatically
from the ``drive_left`` flag.

Severity by distance
---------------------
>100 m  → INFO
50-100 m → WARN
<50 m   → CRITICAL
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

from clearpath.agents.base import Agent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import GuidanceAdvisory, Message

# ── tuneable constants ────────────────────────────────────────────────────────
_LOOKAHEAD_M: float = 150.0          # maximum advisory distance ahead
_CLOSE_M: float = 80.0               # same-lane critical distance
_DEDUP_WINDOW_S: float = 5.0         # do not repeat the same advisory within N s
_ADVISORY_FEED_SIZE: int = 50        # rolling dashboard feed length
_YIELD_DURATION_S: float = 15.0      # how long to hold a yield order (seconds)

# Severity thresholds (distance in metres)
_THRESH_CRITICAL: float = 50.0
_THRESH_WARN: float = 100.0


# ── tiny helpers ──────────────────────────────────────────────────────────────

def _severity(dist_m: float) -> str:
    if dist_m < _THRESH_CRITICAL:
        return "CRITICAL"
    if dist_m < _THRESH_WARN:
        return "WARN"
    return "INFO"


def _bearing_to_compass(bearing_deg: float) -> str:
    """Return the cardinal/intercardinal compass label for a bearing in [0, 360)."""
    idx = int((bearing_deg + 22.5) / 45.0) % 8
    return ["NORTH", "NORTHEAST", "EAST", "SOUTHEAST",
            "SOUTH", "SOUTHWEST", "WEST", "NORTHWEST"][idx]


# ── data class for a deduplicated advisory key ─────────────────────────────────

@dataclass(frozen=True)
class _AdvisoryKey:
    vehicle_id: str
    text_template: str   # text without the vehicle id so identical instructions collapse


# ── rolling feed entry ─────────────────────────────────────────────────────────

@dataclass
class AdvisoryRecord:
    """One entry in the dashboard feed."""
    t: float
    vehicle_ids: List[str]
    text: str
    lane: int
    severity: str


# ── main agent ────────────────────────────────────────────────────────────────

class GuidanceAgent(Agent):
    """Produces tactical lane-level advisories for civilian and emergency vehicles.

    Parameters
    ----------
    agent_id : str
        Unique agent identifier (e.g. ``"guidance"``).
    bus : MessageBus
        Shared message bus used for all published advisories.
    network : Any
        ``RoadNetwork`` instance for edge-geometry queries.
    actuator : Any
        Object exposing ``apply_yield(vehicle_ids, until_t)`` mirroring the
        ``Simulator`` interface.
    drive_left : bool
        ``True`` (default, India) → lane 0 is the left shoulder vehicles pull
        towards.  ``False`` (right-hand traffic) → lane 0 is the right shoulder.
    """

    def __init__(
        self,
        agent_id: str,
        bus: MessageBus,
        network: Any = None,
        actuator: Any = None,
        drive_left: bool = True,
    ) -> None:
        """Initialise the GuidanceAgent."""
        super().__init__(agent_id, bus)
        self.network = network
        self.actuator = actuator
        self.drive_left = drive_left

        # deduplication: maps _AdvisoryKey → last-issued simulation time
        self._last_issued: Dict[_AdvisoryKey, float] = {}

        # rolling dashboard feed
        self.advisory_feed: Deque[AdvisoryRecord] = deque(maxlen=_ADVISORY_FEED_SIZE)

        # latest VMS board text (per junction node)
        self.vms_board: Dict[str, str] = {}

        # ambulance id currently being tracked (set from world view each tick)
        self._ambulance_id: Optional[str] = None

    # ── Agent interface ───────────────────────────────────────────────────────

    def on_message(self, msg: Message) -> None:
        """No incoming messages consumed by this agent."""

    def step(self, world_view: Any, t: int) -> None:
        """Execute one tick of guidance logic.

        Parameters
        ----------
        world_view : WorldView
            Immutable simulation snapshot (vehicles, queues, signals, densities).
        t : int
            Current simulation tick (seconds).
        """
        if world_view is None:
            return

        vehicles = getattr(world_view, "vehicles", []) or []
        queues   = getattr(world_view, "queues",   {}) or {}
        signals  = getattr(world_view, "signals",  {}) or {}

        # ── 1. Locate the ambulance ────────────────────────────────────────────
        ambulance = None
        for v in vehicles:
            if getattr(v, "kind", "") == "ambulance":
                ambulance = v
                self._ambulance_id = v.id
                break

        if ambulance is None:
            return

        amb_edge:   Tuple[str, str] = ambulance.edge
        amb_offset: float           = float(ambulance.offset_m)
        amb_lane:   int             = int(ambulance.lane)
        amb_speed:  float           = float(ambulance.speed_mps)

        # ── 2. Determine route head (next node) ───────────────────────────────
        # The ambulance vehicle carries a `route` attribute in the simulator but
        # WorldView snapshots do not expose it.  We reconstruct the next edge
        # from the full vehicle list by finding the ambulance Vehicle object in
        # the actuator's vehicles dict when available, otherwise we skip next-
        # edge scanning.
        next_edge: Optional[Tuple[str, str]] = None
        edge_len: float = 0.0
        if self.network is not None and self.network.graph.has_edge(*amb_edge):
            edge_len = float(self.network.graph[amb_edge[0]][amb_edge[1]]["length_m"])
            # Try to read ambulance route from the actuator (Simulator)
            if self.actuator is not None:
                amb_veh = getattr(self.actuator, "vehicles", {}).get(ambulance.id)
                if amb_veh is not None and amb_veh.route:
                    next_node = amb_veh.route[0]
                    candidate = (amb_edge[1], next_node)
                    if self.network.graph.has_edge(*candidate):
                        next_edge = candidate

        remaining_on_current = edge_len - amb_offset  # metres left on the ambulance's edge

        # ── 3. Collect affected vehicles ──────────────────────────────────────
        # Key: vehicle snapshot → distance ahead (metres)
        targets: List[Tuple[Any, float, str]] = []  # (snapshot, dist_m, zone)

        for v in vehicles:
            if v.id == ambulance.id:
                continue
            if getattr(v, "kind", "") == "ambulance":
                continue

            if v.edge == amb_edge:
                # Must be strictly ahead of the ambulance
                dist = float(v.offset_m) - amb_offset
                if 0 < dist <= _LOOKAHEAD_M:
                    targets.append((v, dist, "current"))

            elif next_edge is not None and v.edge == next_edge:
                # Vehicles on the next edge; ambulance still needs to reach it
                dist_ahead = remaining_on_current + float(v.offset_m)
                if dist_ahead <= _LOOKAHEAD_M:
                    targets.append((v, dist_ahead, "next"))

        # ── 4. Also collect vehicles on crossing streets at the approaching junction ─
        # Ambulance is heading toward amb_edge[1]; cars approaching that same
        # junction from *different* approaches should not enter it.
        crossing_vids: List[str] = []
        if self.network is not None:
            # The junction the ambulance is currently heading toward
            approaching_junction = amb_edge[1]
            crossing_edges = [
                (u, approaching_junction)
                for u in self.network.graph.predecessors(approaching_junction)
                if (u, approaching_junction) != amb_edge
            ]
            for v in vehicles:
                if v.id == ambulance.id:
                    continue
                if getattr(v, "kind", "") == "ambulance":
                    continue
                if v.edge in crossing_edges:
                    crossing_vids.append(v.id)

        # ── 5. Build & emit advisories ────────────────────────────────────────
        advisories_this_tick: List[GuidanceAdvisory] = []

        # Edge lane count (for single-lane detection)
        edge_lanes = 1
        if self.network is not None and self.network.graph.has_edge(*amb_edge):
            edge_lanes = int(self.network.graph[amb_edge[0]][amb_edge[1]].get("lanes", 1))

        for v, dist_m, zone in targets:
            v_lane: int = int(v.lane)
            same_lane = (v_lane == amb_lane)
            is_stopped = getattr(v, "is_stopped", False)
            at_queue = (
                queues.get(v.edge, 0) > 0
                and not is_stopped
                or (is_stopped and dist_m <= _LOOKAHEAD_M)
            )
            # Queue in path: vehicle on the ambulance's edge/next edge near stop line
            in_path_queue = (
                zone in ("current", "next")
                and queues.get(v.edge, 0) > 0
            )

            # ── classify ──────────────────────────────────────────────────────
            if same_lane and dist_m <= _CLOSE_M:
                if edge_lanes == 1:
                    text = "Pull over to the left shoulder and stop"
                else:
                    side = self._pull_side(amb_lane, edge_lanes)
                    text = f"Clear lane {amb_lane}: move to the {side}"
            elif in_path_queue and is_stopped:
                text = "Hold position, creep forward and leave a gap"
            elif in_path_queue and not is_stopped:
                text = "Slow down"
            elif not same_lane and dist_m > _CLOSE_M:
                text = "Slow down, emergency vehicle approaching"
            else:
                # same lane, beyond close zone
                side = self._pull_side(amb_lane, edge_lanes)
                text = f"Clear lane {amb_lane}: move to the {side}"

            sev = _severity(dist_m)
            adv = self._make_advisory([v.id], text, v_lane, sev, t)
            if adv is not None:
                advisories_this_tick.append(adv)

        # ── 5b. Crossing-street advisory ──────────────────────────────────────
        if crossing_vids:
            adv = self._make_advisory(
                crossing_vids,
                "Stop. Do not enter the intersection",
                0,
                "CRITICAL",
                t,
            )
            if adv is not None:
                advisories_this_tick.append(adv)

        # ── 6. Publish and apply yield ─────────────────────────────────────────
        yield_ids: List[str] = []
        for adv in advisories_this_tick:
            self.bus.publish(adv)
            yield_ids.extend(adv.target_vehicle_ids)

        if yield_ids and self.actuator is not None:
            self.actuator.apply_yield(yield_ids, float(t) + _YIELD_DURATION_S)

        # ── 7. VMS board text ─────────────────────────────────────────────────
        if next_edge is not None:
            next_junction = next_edge[1]
            # Determine approach compass direction
            bearing = 0.0
            if self.network is not None:
                bearing = float(
                    self.network.graph[amb_edge[0]][amb_edge[1]].get("bearing_deg", 0.0)
                )
            direction = _bearing_to_compass(bearing)
            lane_side = "LEFT" if self.drive_left else "RIGHT"
            self.vms_board[next_junction] = (
                f"AMBULANCE APPROACHING FROM {direction} - CLEAR {lane_side} LANE"
            )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _pull_side(self, amb_lane: int, num_lanes: int) -> str:
        """Return 'left shoulder' or 'right shoulder' based on drive-side convention."""
        # India (drive left): pull to lane 0 = left shoulder
        # Right-hand traffic: pull to lane 0 = right shoulder
        if self.drive_left:
            # Ambulance takes the right/inner lane; civilians pull left
            return "adjacent lane / pull to the left shoulder" if num_lanes > 1 else "left shoulder"
        else:
            return "adjacent lane / pull to the right shoulder" if num_lanes > 1 else "right shoulder"

    def _make_advisory(
        self,
        vehicle_ids: List[str],
        text: str,
        lane: int,
        severity: str,
        t: float,
    ) -> Optional[GuidanceAdvisory]:
        """Create a GuidanceAdvisory if not suppressed by the deduplication window.

        One key is generated per *individual* vehicle so that different vehicles
        with the same instruction are each deduplicated independently.
        """
        to_send: List[str] = []
        for vid in vehicle_ids:
            key = _AdvisoryKey(vehicle_id=vid, text_template=text)
            last = self._last_issued.get(key, -math.inf)
            if (t - last) >= _DEDUP_WINDOW_S:
                to_send.append(vid)
                self._last_issued[key] = float(t)

        if not to_send:
            return None

        record = AdvisoryRecord(
            t=float(t),
            vehicle_ids=list(to_send),
            text=text,
            lane=lane,
            severity=severity,
        )
        self.advisory_feed.append(record)

        return GuidanceAdvisory(
            target_vehicle_ids=to_send,
            text=text,
            lane=lane,
            severity=severity,
            ts=float(t),
            sender=self.id,
            recipient="*",
        )
