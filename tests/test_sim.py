"""Unit tests for the ClearPath-lite simulation engine.

Covers:
1. Determinism (identical state after 300 ticks given identical seed).
2. Vehicle non-overlap invariant (bumper-to-bumper gap >= 0 on all lanes).
3. Signal safety invariant (no conflicting green phases at any intersection).
4. Ambulance congested delay (no preemption transit time > free flow).
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pytest

from clearpath.config import load_config
from clearpath.sim.network import RoadNetwork
from clearpath.sim.signals import SignalController, SignalPhase
from clearpath.sim.simulator import Simulator


def test_network_topology_and_helpers() -> None:
    """Verify grid construction, edge attributes, bearings, and turn classifications."""
    config = load_config(grid_rows=4, grid_cols=4, block_length_m=200.0)
    net = RoadNetwork(config)

    # 4x4 grid = 16 nodes
    assert len(net.graph.nodes) == 16
    # Each interior road segment has 2 directed edges: 2 * (4*3 + 4*3) = 48 directed edges
    assert len(net.graph.edges) == 48

    # Edge bearing checks
    assert net.edge_bearing("j_0_0", "j_0_1") == 90.0  # Eastbound
    assert net.edge_bearing("j_0_1", "j_0_0") == 270.0  # Westbound
    assert net.edge_bearing("j_0_0", "j_1_0") == 0.0  # Northbound
    assert net.edge_bearing("j_1_0", "j_0_0") == 180.0  # Southbound

    # Interpolation
    pos_start = net.edge_position(("j_0_0", "j_0_1"), 0.0)
    assert pos_start == (0.0, 0.0)
    pos_mid = net.edge_position(("j_0_0", "j_0_1"), 100.0)
    assert pos_mid == (100.0, 0.0)
    pos_end = net.edge_position(("j_0_0", "j_0_1"), 200.0)
    assert pos_end == (200.0, 0.0)

    # Turn types
    # Straight: coming East into j_1_1, continuing East
    assert net.turn_type(("j_1_0", "j_1_1"), ("j_1_1", "j_1_2")) == "straight"
    # Left turn: coming East into j_1_1, turning North (bearing 90 to 0)
    assert net.turn_type(("j_1_0", "j_1_1"), ("j_1_1", "j_2_1")) == "left"
    # Right turn: coming East into j_1_1, turning South (bearing 90 to 180)
    assert net.turn_type(("j_1_0", "j_1_1"), ("j_1_1", "j_0_1")) == "right"


def test_signals_never_conflicting_greens() -> None:
    """At no point in time should an intersection display Green to both NS and EW."""
    config = load_config(cycle_s=60, green_s=26, yellow_s=3, all_red_s=1)
    controller = SignalController("j_2_2", config)

    ns_edge = ("j_1_2", "j_2_2")
    ew_edge = ("j_2_1", "j_2_2")

    for _ in range(300):
        s_ns = controller.state_for_approach(ns_edge)
        s_ew = controller.state_for_approach(ew_edge)

        # Neither can both be green
        assert not (s_ns == "G" and s_ew == "G")
        # During yellow, conflicting movement must be red
        if s_ns == "Y":
            assert s_ew == "R"
        if s_ew == "Y":
            assert s_ns == "R"

        controller.step(1.0)


def test_signal_preemption_safe_clearance() -> None:
    """Preemption override while cross-street is green must transition through yellow and red."""
    config = load_config(cycle_s=60, green_s=26, yellow_s=3, all_red_s=1)
    controller = SignalController("j_2_2", config, offset_s=32.0)  # Starts in EW_GREEN

    ns_edge = ("j_1_2", "j_2_2")
    ew_edge = ("j_2_1", "j_2_2")

    assert controller.state_for_approach(ew_edge) == "G"
    assert controller.state_for_approach(ns_edge) == "R"

    # Request NS green override
    controller.set_phase_override("NS", reason="emergency_approach", t=0.0)

    # Immediately after override, EW must NOT instantly turn red without yellow
    assert controller.state_for_approach(ew_edge) == "Y"
    assert controller.state_for_approach(ns_edge) == "R"

    # Step through yellow clearance (3 seconds)
    controller.step(1.0)
    assert controller.state_for_approach(ew_edge) == "Y"
    controller.step(1.0)
    assert controller.state_for_approach(ew_edge) == "Y"
    controller.step(1.0)

    # Now in all-red clearance (1 second)
    assert controller.state_for_approach(ew_edge) == "R"
    assert controller.state_for_approach(ns_edge) == "R"

    # Step past all-red -> now NS is Green!
    controller.step(1.0)
    assert controller.state_for_approach(ns_edge) == "G"
    assert controller.state_for_approach(ew_edge) == "R"


def test_simulation_determinism() -> None:
    """Two simulations initialized with the same seed must produce identical states after 300 ticks."""
    config1 = load_config(seed=1234, max_ticks=300)
    sim1 = Simulator(config1, demand_level="med")

    config2 = load_config(seed=1234, max_ticks=300)
    sim2 = Simulator(config2, demand_level="med")

    for _ in range(300):
        sim1.step()
        sim2.step()

    assert sim1.current_tick == sim2.current_tick == 300
    assert sim1.completed_vehicles == sim2.completed_vehicles
    assert len(sim1.vehicles) == len(sim2.vehicles)

    v1_keys = sorted(sim1.vehicles.keys())
    v2_keys = sorted(sim2.vehicles.keys())
    assert v1_keys == v2_keys

    for k in v1_keys:
        v1 = sim1.vehicles[k]
        v2 = sim2.vehicles[k]
        assert v1.edge == v2.edge
        assert v1.lane == v2.lane
        assert pytest.approx(v1.offset_m, abs=1e-3) == v2.offset_m
        assert pytest.approx(v1.speed, abs=1e-3) == v2.speed
        assert v1.is_stopped == v2.is_stopped


def test_no_vehicles_overlap() -> None:
    """No two vehicles traveling on the same edge and lane may ever overlap."""
    config = load_config(seed=42, max_ticks=300)
    sim = Simulator(config, demand_level="high")

    for _ in range(300):
        sim.step()

        # Group by edge and lane
        lane_map: dict[tuple[tuple[str, str], int], list] = {}
        for veh in sim.vehicles.values():
            key = (veh.edge, veh.lane)
            lane_map.setdefault(key, []).append(veh)

        for (edge, lane), vehs in lane_map.items():
            if len(vehs) < 2:
                continue
            # Sort by offset descending (front to back)
            vehs.sort(key=lambda v: v.offset_m, reverse=True)
            for i in range(len(vehs) - 1):
                leader = vehs[i]
                follower = vehs[i + 1]
                # Bumper of follower must not penetrate leader rear bumper
                gap = leader.offset_m - follower.offset_m - leader.length_m
                assert gap >= -1e-2, (
                    f"Overlap detected at tick {sim.current_tick} on edge {edge} lane {lane}: "
                    f"leader {leader.id} offset={leader.offset_m:.2f}, "
                    f"follower {follower.id} offset={follower.offset_m:.2f}, gap={gap:.2f}"
                )


def test_ambulance_congested_vs_free_flow() -> None:
    """An ambulance on a congested grid with NO preemption takes strictly longer than free-flow time."""
    config = load_config(seed=42, max_ticks=400)
    sim = Simulator(config, demand_level="high")

    # Warm up grid for 60 ticks so queues accumulate
    for _ in range(60):
        sim.step()

    # Route: traversals across 4 blocks from j_0_0 to j_0_4
    route = ["j_0_0", "j_0_1", "j_0_2", "j_0_3", "j_0_4"]
    total_dist_m = 4 * config.block_length_m
    free_flow_time_s = total_dist_m / config.ambulance_max_mps

    amb_id = sim.spawn_ambulance("j_0_0", "j_0_4", route=route)
    start_tick = sim.current_tick

    # Run without preemption until ambulance arrives
    arrived = False
    arrival_tick = start_tick
    for _ in range(300):
        sim.step()
        if amb_id not in sim.vehicles:
            arrived = True
            arrival_tick = sim.current_tick
            break

    assert arrived, "Ambulance should reach destination within 300 ticks"
    actual_transit_time = arrival_tick - start_tick

    # Transit time through traffic signals and civilian traffic must be strictly greater than free flow
    assert actual_transit_time > free_flow_time_s, (
        f"Expected congested time ({actual_transit_time}s) > free-flow ({free_flow_time_s}s)"
    )

