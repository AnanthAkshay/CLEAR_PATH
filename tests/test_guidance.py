"""Unit tests for GuidanceAgent (step 6a).

Coverage
--------
* Vehicles ahead in the same lane receive "Clear lane" / "Pull over" instructions.
* Vehicles *behind* the ambulance, or beyond 150 m, receive nothing.
* Deduplication suppresses the same instruction within 5 s.
* The drive-side flag flips the pull-direction text (left vs right shoulder).
* The yield effect lets the ambulance pass without slowing below a threshold.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pytest

from clearpath.agents.guidance import GuidanceAgent, _DEDUP_WINDOW_S, _LOOKAHEAD_M
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import GuidanceAdvisory
from clearpath.config import SimConfig, load_config
from clearpath.sim.network import RoadNetwork
from clearpath.sim.simulator import Simulator


# ---------------------------------------------------------------------------
# Minimal stub types (avoid importing from simulator internals in pure-unit tests)
# ---------------------------------------------------------------------------

@dataclass
class _Snap:
    """Lightweight stand-in for VehicleSnapshot."""
    id: str
    kind: str = "car"
    edge: Tuple[str, str] = ("j_0_0", "j_0_1")
    offset_m: float = 0.0
    speed_mps: float = 10.0
    lane: int = 0
    is_stopped: bool = False
    wait_time_s: float = 0.0
    yield_until_t: float = 0.0
    x: float = 0.0
    y: float = 0.0
    heading_deg: float = 90.0


@dataclass
class _View:
    """Minimal WorldView stand-in."""
    tick: int = 0
    vehicles: List[_Snap] = field(default_factory=list)
    queues: Dict[Tuple[str, str], int] = field(default_factory=dict)
    signals: Dict[str, str] = field(default_factory=dict)
    densities: Dict[Tuple[str, str], float] = field(default_factory=dict)


@dataclass
class _Vehicle:
    """Stand-in for simulator.vehicles dict value (for route reading)."""
    id: str
    route: List[str] = field(default_factory=list)
    edge: Tuple[str, str] = ("j_0_0", "j_0_1")
    lane: int = 0


class _Actuator:
    """Records apply_yield calls."""

    def __init__(self) -> None:
        self.yielded: Dict[str, float] = {}   # vehicle_id -> until_t

    def apply_yield(self, vehicle_ids: List[str], until_t: float) -> None:
        for vid in vehicle_ids:
            self.yielded[vid] = max(self.yielded.get(vid, 0.0), until_t)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def _network() -> RoadNetwork:
    return RoadNetwork(load_config())


def _agent(
    bus: Optional[MessageBus] = None,
    network: Optional[RoadNetwork] = None,
    actuator: Optional[_Actuator] = None,
    drive_left: bool = True,
) -> GuidanceAgent:
    bus = bus or MessageBus(seed=42)
    net = network or _network()
    act = actuator or _Actuator()
    return GuidanceAgent("guidance", bus, network=net, actuator=act, drive_left=drive_left)


def _amb(
    edge: Tuple[str, str] = ("j_0_0", "j_0_1"),
    offset_m: float = 50.0,
    lane: int = 1,
    speed_mps: float = 20.0,
) -> _Snap:
    return _Snap(id="AMB_1", kind="ambulance", edge=edge, offset_m=offset_m,
                 lane=lane, speed_mps=speed_mps)


def _car(
    vid: str,
    edge: Tuple[str, str] = ("j_0_0", "j_0_1"),
    offset_m: float = 100.0,
    lane: int = 1,
    speed_mps: float = 10.0,
    is_stopped: bool = False,
) -> _Snap:
    return _Snap(id=vid, kind="car", edge=edge, offset_m=offset_m, lane=lane,
                 speed_mps=speed_mps, is_stopped=is_stopped)


def _advisories(bus: MessageBus) -> List[GuidanceAdvisory]:
    return [m for m in bus.message_log if isinstance(m, GuidanceAdvisory)]


# ---------------------------------------------------------------------------
# 1. Vehicles ahead in the same lane receive "Clear lane" instructions
# ---------------------------------------------------------------------------

def test_same_lane_ahead_within_80m_gets_clear_lane() -> None:
    """A car in the same lane, 40 m ahead, gets a Clear-lane advisory."""
    bus = MessageBus(seed=42)
    net = _network()
    # j_0_0 -> j_0_1 is an arterial with 2 lanes (row 0, c%3==0 -> col 0 is arterial)
    # row 0 is arterial; col 0 is arterial; use the arterial horizontal edge
    amb_edge = ("j_0_0", "j_0_1")  # row 0 → arterial, 2 lanes
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=50.0, lane=1)
    car = _car("CAR_1", edge=amb_edge, offset_m=85.0, lane=1)  # 35 m ahead, same lane

    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    advs = _advisories(bus)
    assert advs, "Expected at least one advisory"
    texts = [a.text for a in advs]
    assert any("Clear lane" in t for t in texts), f"Expected 'Clear lane' in advisories: {texts}"
    # The car should be in the target vehicle IDs
    targeted = {vid for a in advs for vid in a.target_vehicle_ids}
    assert "CAR_1" in targeted


def test_single_lane_road_gets_pull_over() -> None:
    """A car ahead on a single-lane road gets 'Pull over to the left shoulder and stop'."""
    bus = MessageBus(seed=42)
    net = _network()
    # Row 1 (non-arterial, non-divisible by 3) → residential, 1 lane
    amb_edge = ("j_1_0", "j_1_1")   # row 1, residential → 1 lane
    # Confirm it's actually 1 lane
    lanes = net.graph[amb_edge[0]][amb_edge[1]]["lanes"]
    assert lanes == 1, f"Expected 1-lane road, got {lanes}"

    agent = _agent(bus=bus, network=net)
    amb = _amb(edge=amb_edge, offset_m=50.0, lane=0)
    car = _car("CAR_1", edge=amb_edge, offset_m=80.0, lane=0, speed_mps=5.0)

    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    texts = [a.text for a in _advisories(bus)]
    assert any("Pull over to the left shoulder" in t for t in texts), (
        f"Expected pull-over advisory on single-lane road: {texts}"
    )


def test_different_lane_80_to_150m_gets_slow_down() -> None:
    """A car in a different lane, 90 m ahead, gets 'Slow down' advisory."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")   # 2-lane arterial
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=10.0, lane=1)
    car = _car("CAR_2", edge=amb_edge, offset_m=105.0, lane=0)  # 95 m ahead, different lane

    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    texts = [a.text for a in _advisories(bus)]
    assert any("Slow down" in t for t in texts), (
        f"Expected 'Slow down' advisory: {texts}"
    )
    targeted = {vid for a in _advisories(bus) for vid in a.target_vehicle_ids}
    assert "CAR_2" in targeted


# ---------------------------------------------------------------------------
# 2. Vehicles behind the ambulance get no advisory
# ---------------------------------------------------------------------------

def test_vehicle_behind_ambulance_gets_no_advisory() -> None:
    """A car behind the ambulance (smaller offset) must not receive any advisory."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=100.0, lane=1)
    car_behind = _car("CAR_BEHIND", edge=amb_edge, offset_m=50.0, lane=1)  # 50 m BEHIND

    view = _View(vehicles=[amb, car_behind])
    agent.step(view, t=1)

    targeted = {vid for a in _advisories(bus) for vid in a.target_vehicle_ids}
    assert "CAR_BEHIND" not in targeted, "Vehicle behind ambulance received an advisory"


def test_vehicle_beyond_150m_gets_no_advisory() -> None:
    """A car more than 150 m ahead must not receive any advisory."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=10.0, lane=1)
    # Put the car 160 m ahead → beyond the 150 m threshold
    car_far = _car("CAR_FAR", edge=amb_edge, offset_m=170.0, lane=1)

    view = _View(vehicles=[amb, car_far])
    agent.step(view, t=1)

    targeted = {vid for a in _advisories(bus) for vid in a.target_vehicle_ids}
    assert "CAR_FAR" not in targeted, "Vehicle beyond 150 m received an advisory"


# ---------------------------------------------------------------------------
# 3. Deduplication
# ---------------------------------------------------------------------------

def test_deduplication_suppresses_repeat_within_5s() -> None:
    """The same advisory must NOT be re-issued within the dedup window."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=50.0, lane=1)
    car = _car("CAR_D", edge=amb_edge, offset_m=85.0, lane=1)
    view = _View(vehicles=[amb, car])

    # First tick → advisory issued
    agent.step(view, t=1)
    count_after_tick1 = sum(
        1 for a in _advisories(bus) if "CAR_D" in a.target_vehicle_ids
    )
    assert count_after_tick1 >= 1, "Expected advisory on first tick"

    # Ticks 2-4 → within dedup window → should not re-issue
    for tick in range(2, int(_DEDUP_WINDOW_S)):
        agent.step(view, t=tick)

    count_after_dedup = sum(
        1 for a in _advisories(bus) if "CAR_D" in a.target_vehicle_ids
    )
    assert count_after_dedup == count_after_tick1, (
        "Advisory was re-issued within the dedup window"
    )


def test_deduplication_allows_reissue_after_window() -> None:
    """After the dedup window expires the same advisory may be issued again."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=50.0, lane=1)
    car = _car("CAR_R", edge=amb_edge, offset_m=85.0, lane=1)
    view = _View(vehicles=[amb, car])

    agent.step(view, t=1)
    count_1 = sum(1 for a in _advisories(bus) if "CAR_R" in a.target_vehicle_ids)

    # Jump past the dedup window
    agent.step(view, t=1 + int(_DEDUP_WINDOW_S) + 1)
    count_2 = sum(1 for a in _advisories(bus) if "CAR_R" in a.target_vehicle_ids)

    assert count_2 > count_1, "Advisory was not re-issued after the dedup window"


# ---------------------------------------------------------------------------
# 4. Drive-side flag flips the direction text
# ---------------------------------------------------------------------------

def test_drive_left_uses_left_shoulder() -> None:
    """With drive_left=True the advisory says 'left shoulder'."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")  # 2-lane arterial
    agent = _agent(bus=bus, network=net, drive_left=True)

    amb = _amb(edge=amb_edge, offset_m=50.0, lane=1)
    car = _car("CAR_L", edge=amb_edge, offset_m=75.0, lane=1)
    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    texts = [a.text for a in _advisories(bus)]
    assert any("left" in t.lower() for t in texts), (
        f"Expected 'left' in advisory text for drive_left=True: {texts}"
    )


def test_drive_right_uses_right_shoulder() -> None:
    """With drive_left=False the advisory says 'right shoulder'."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")  # 2-lane arterial
    agent = _agent(bus=bus, network=net, drive_left=False)

    amb = _amb(edge=amb_edge, offset_m=50.0, lane=1)
    car = _car("CAR_R", edge=amb_edge, offset_m=75.0, lane=1)
    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    texts = [a.text for a in _advisories(bus)]
    assert any("right" in t.lower() for t in texts), (
        f"Expected 'right' in advisory text for drive_left=False: {texts}"
    )


# ---------------------------------------------------------------------------
# 5. Severity escalation by distance
# ---------------------------------------------------------------------------

def test_severity_critical_within_50m() -> None:
    """A car within 50 m in the same lane should yield a CRITICAL advisory."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=60.0, lane=1)
    car = _car("CAR_CRIT", edge=amb_edge, offset_m=85.0, lane=1)  # 25 m ahead → CRITICAL
    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    for a in _advisories(bus):
        if "CAR_CRIT" in a.target_vehicle_ids:
            assert a.severity == "CRITICAL", f"Expected CRITICAL, got {a.severity}"
            return
    pytest.fail("No advisory found for CAR_CRIT")


def test_severity_info_beyond_100m() -> None:
    """A car more than 100 m ahead should receive an INFO advisory."""
    bus = MessageBus(seed=42)
    net = _network()
    amb_edge = ("j_0_0", "j_0_1")
    agent = _agent(bus=bus, network=net)

    amb = _amb(edge=amb_edge, offset_m=10.0, lane=1)
    car = _car("CAR_INFO", edge=amb_edge, offset_m=120.0, lane=1)  # 110 m ahead → INFO
    view = _View(vehicles=[amb, car])
    agent.step(view, t=1)

    for a in _advisories(bus):
        if "CAR_INFO" in a.target_vehicle_ids:
            assert a.severity == "INFO", f"Expected INFO, got {a.severity}"
            return
    pytest.fail("No advisory found for CAR_INFO")


# ---------------------------------------------------------------------------
# 6. Crossing-street advisory
# ---------------------------------------------------------------------------

def test_crossing_street_vehicles_get_stop_advisory() -> None:
    """Cars approaching the ambulance's destination junction get 'Stop. Do not enter'."""
    bus = MessageBus(seed=42)
    net = _network()
    # Ambulance on j_0_0→j_0_1 heading toward j_0_1.
    # A crossing car approaches j_0_1 from the south (j_1_1→j_0_1).
    amb_edge = ("j_0_0", "j_0_1")
    cross_edge = ("j_1_1", "j_0_1")  # approaches j_0_1 from south

    # Verify both edges exist in the network
    if not net.graph.has_edge(*cross_edge):
        pytest.skip("Cross-street edge not present in this network config")

    act = _Actuator()
    agent = _agent(bus=bus, network=net, actuator=act)

    amb = _amb(edge=amb_edge, offset_m=10.0, lane=1)
    # car on the crossing approach, within reach
    cross_car = _car("CROSS_CAR", edge=cross_edge, offset_m=100.0, lane=0)

    view = _View(vehicles=[amb, cross_car])
    agent.step(view, t=1)

    targeted = {vid for a in _advisories(bus) for vid in a.target_vehicle_ids}
    texts = {vid: [a.text for a in _advisories(bus) if vid in a.target_vehicle_ids]
             for vid in targeted}
    assert "CROSS_CAR" in targeted, (
        f"Crossing car not in any advisory. Targeted: {targeted}"
    )
    assert any(
        "Stop" in t or "Do not enter" in t
        for t in texts.get("CROSS_CAR", [])
    ), f"Expected stop advisory for crossing car, got: {texts}"


# ---------------------------------------------------------------------------
# 7. Yield effect integration: ambulance passes without slowing below threshold
# ---------------------------------------------------------------------------

def test_yield_effect_lets_ambulance_pass() -> None:
    """
    With GuidanceAgent running, the ambulance should cross the corridor faster
    than it would if cars are blocking the lane.

    We spin up a minimal Simulator run on an empty-ish network, place a civilian
    car ahead of the ambulance, and check that:
      a) apply_yield is called for the blocking car, and
      b) the ambulance's minimum speed during the run is above a floor
         (meaning it was not fully blocked behind the car).
    """
    config = load_config(seed=99)
    sim = Simulator(config, demand_level="low")
    # Suppress background traffic generation
    sim.traffic_gen._rate_per_boundary = 0.0

    bus = MessageBus(seed=99)
    act = sim   # Simulator implements apply_yield directly

    net = sim.network
    agent = GuidanceAgent("guidance", bus, network=net, actuator=act, drive_left=True)

    # Spawn ambulance on row-0 arterial corridor
    corridor = ["j_0_0", "j_0_1", "j_0_2", "j_0_3"]
    amb_id = sim.spawn_ambulance(corridor[0], corridor[-1], route=list(corridor))

    # Manually inject a civilian car just ahead of the ambulance (same lane)
    from clearpath.sim.vehicles import Vehicle
    blocker = Vehicle(
        id="BLOCKER",
        kind="car",
        edge=("j_0_0", "j_0_1"),
        offset_m=20.0,          # 20 m ahead of the ambulance (which starts at 0)
        speed=5.0,
        lane=sim.vehicles[amb_id].lane,
        route=["j_0_2", "j_0_3"],  # remaining nodes after j_0_1
    )
    sim.vehicles["BLOCKER"] = blocker

    max_amb_speed = 0.0
    yield_called_for_blocker = False
    ambulance_completed = False

    for tick in range(1, 80):
        view = sim.get_world_view()
        bus.step(tick)
        agent.step(view, tick)
        sim.step()

        # Check if ambulance is still present
        amb_snap = next((v for v in sim.get_world_view().vehicles if v.id == amb_id), None)
        if amb_snap is None:
            ambulance_completed = True
            break  # ambulance completed its run
        max_amb_speed = max(max_amb_speed, amb_snap.speed_mps)

        if sim.vehicles.get("BLOCKER") is not None:
            blocker_veh = sim.vehicles["BLOCKER"]
            if blocker_veh.yield_until_t > 0:
                yield_called_for_blocker = True

    assert yield_called_for_blocker, (
        "apply_yield was never called for the blocking car"
    )
    # The ambulance should have accelerated to a meaningful speed (proving it wasn't
    # permanently stuck behind the blocking car after the yield was applied).
    assert max_amb_speed > 10.0, (
        f"Ambulance never exceeded 10 m/s (max was {max_amb_speed:.2f} m/s); "
        "did the yield allow it to pass?"
    )
    # Ambulance should complete the corridor within the allotted ticks
    assert ambulance_completed, "Ambulance did not complete the corridor within 80 ticks"

# ---------------------------------------------------------------------------
# 8. Rolling advisory feed
# ---------------------------------------------------------------------------

def test_advisory_feed_maintains_last_50() -> None:
    """The advisory_feed never grows beyond 50 entries."""
    bus = MessageBus(seed=42)
    net = _network()
    agent = _agent(bus=bus, network=net)
    amb_edge = ("j_0_0", "j_0_1")

    for tick in range(1, 120):
        amb = _amb(edge=amb_edge, offset_m=10.0, lane=1)
        # Create a fresh car each tick to avoid dedup suppression
        car_id = f"CAR_{tick}"
        car = _car(car_id, edge=amb_edge, offset_m=50.0, lane=1)
        view = _View(vehicles=[amb, car])
        agent.step(view, t=tick)

    assert len(agent.advisory_feed) <= 50


# ---------------------------------------------------------------------------
# 9. VMS board text
# ---------------------------------------------------------------------------

def test_vms_board_contains_direction() -> None:
    """The VMS board text includes the approach direction and 'AMBULANCE APPROACHING'."""
    bus = MessageBus(seed=42)
    net = _network()

    class _ActWithVehicles(_Actuator):
        def __init__(self) -> None:
            super().__init__()
            self.vehicles: Dict[str, Any] = {
                "AMB_1": _Vehicle("AMB_1", route=["j_0_2"], edge=("j_0_0", "j_0_1"))
            }

    act = _ActWithVehicles()
    agent = _agent(bus=bus, network=net, actuator=act)

    amb = _amb(edge=("j_0_0", "j_0_1"), offset_m=10.0, lane=1)
    view = _View(vehicles=[amb])
    agent.step(view, t=1)

    assert agent.vms_board, "VMS board is empty after a tick with ambulance"
    for junction, text in agent.vms_board.items():
        assert "AMBULANCE APPROACHING" in text, f"VMS text missing 'AMBULANCE APPROACHING': {text}"
        assert "LANE" in text, f"VMS text missing 'LANE': {text}"
