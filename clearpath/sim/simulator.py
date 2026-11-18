"""Deterministic tick-based grid simulator engine (1 tick = 1 second).

Maintains vehicle kinematics, signal phase updates, queue estimations,
and decoupled actuator endpoints for multi-agent controllers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from clearpath.config import SimConfig
from clearpath.sim.network import RoadNetwork
from clearpath.sim.signals import SignalController, SignalPhase
from clearpath.sim.traffic_gen import TrafficGenerator
from clearpath.sim.vehicles import Vehicle


@dataclass(frozen=True)
class VehicleSnapshot:
    """Read-only telemetry snapshot of an individual vehicle."""

    id: str
    kind: str
    edge: Tuple[str, str]
    offset_m: float
    speed_mps: float
    lane: int
    x: float
    y: float
    heading_deg: float
    is_stopped: bool
    wait_time_s: float
    yield_until_t: float


@dataclass(frozen=True)
class WorldView:
    """Immutable perception state provided to agents during orchestrator step."""

    tick: int
    vehicles: List[VehicleSnapshot]
    queues: Dict[Tuple[str, str], int]
    signals: Dict[str, str]
    densities: Dict[Tuple[str, str], float]


class Simulator:
    """Central deterministic traffic simulator enforcing 1 tick = 1 second."""

    def __init__(
        self,
        config: SimConfig,
        rng: Optional[np.random.Generator] = None,
        demand_level: str = "med",
    ) -> None:
        """Initialize simulation environment with network, signals, and traffic generator."""
        self.config = config
        self.rng = rng or np.random.default_rng(config.seed)
        self.current_tick: int = 0

        self.network = RoadNetwork(config)

        # Initialize signal controllers with staggered offsets across grid
        self.signals: Dict[str, SignalController] = {}
        for node in self.network.graph.nodes:
            node_data = self.network.graph.nodes[node]
            r, c = node_data["r"], node_data["c"]
            offset = float((r * 7 + c * 11) % self.config.cycle_s)
            self.signals[node] = SignalController(node, self.config, offset_s=offset)

        self.traffic_gen = TrafficGenerator(
            config,
            self.network,
            demand_level=demand_level,
            rng=self.rng,
        )

        self.vehicles: Dict[str, Vehicle] = {}
        self.completed_vehicles: int = 0
        self.total_wait_time_s: float = 0.0
        self.ambulance_history: List[Dict[str, Any]] = []

    def spawn_ambulance(
        self,
        origin_node: str,
        destination_node: str,
        route: Optional[List[str]] = None,
    ) -> str:
        """Inject an emergency ambulance onto the network.

        Args:
            origin_node: Starting junction node ID.
            destination_node: Destination hospital or junction node ID.
            route: Explicit sequence of nodes. If omitted, computes shortest path.

        Returns:
            The generated ambulance vehicle ID.
        """
        if route is None:
            route = nx.shortest_path(
                self.network.graph,
                origin_node,
                destination_node,
                weight="free_flow_time_s",
            )

        if len(route) < 2:
            raise ValueError(f"Route must contain at least 2 nodes: {route}")

        first_edge = (route[0], route[1])
        edge_data = self.network.graph[route[0]][route[1]]
        lanes = edge_data.get("lanes", 1)
        ambulance_id = f"AMB_{len(self.ambulance_history) + 1}"

        placed_lane = 0
        candidate_lanes = [1, 0] if lanes > 1 else [0]
        for l_idx in candidate_lanes:
            min_headway = min(
                (v.offset_m for v in self.vehicles.values() if v.edge == first_edge and v.lane == l_idx),
                default=float("inf"),
            )
            if min_headway >= (self.config.vehicle_length_m + 5.0):
                placed_lane = l_idx
                break

        amb = Vehicle(
            id=ambulance_id,
            kind="ambulance",
            edge=first_edge,
            offset_m=0.0,
            speed=self.config.ambulance_max_mps * 0.5,
            lane=placed_lane,
            route=route[2:],
            is_stopped=False,
            wait_time=0.0,
            length_m=self.config.vehicle_length_m,
            max_speed=self.config.ambulance_max_mps,
            max_accel=self.config.ambulance_max_accel,
        )

        self.vehicles[ambulance_id] = amb
        return ambulance_id

    # -------------------------------------------------------------------------
    # Actuator Interface
    # -------------------------------------------------------------------------

    def force_signal_phase(
        self,
        junction_id: str,
        phase: SignalPhase | str,
        reason: str = "manual_operator_override",
    ) -> None:
        """Actuator: Directly force a specific signal phase (instantaneous override)."""
        if junction_id in self.signals:
            self.signals[junction_id].force_phase(phase, reason=reason)

    def set_signal_override(
        self,
        junction_id: str,
        phase: SignalPhase | str,
        reason: str = "emergency_preemption",
    ) -> None:
        """Actuator: Request preemption override at the designated junction."""
        if junction_id in self.signals:
            self.signals[junction_id].set_phase_override(
                phase,
                reason=reason,
                t=float(self.current_tick),
            )

    def clear_signal_override(self, junction_id: str) -> None:
        """Actuator: Release preemption lock at designated junction."""
        if junction_id in self.signals:
            self.signals[junction_id].clear_override()

    def apply_yield(self, vehicle_ids: List[str], until_t: float) -> None:
        """Actuator: Instruct vehicles to yield to passing emergency corridor."""
        for v_id in vehicle_ids:
            if v_id in self.vehicles:
                veh = self.vehicles[v_id]
                veh.yield_until_t = max(veh.yield_until_t, until_t)

    def inject_traffic_jam(self, u: str, v: str, num_vehicles: int = 8) -> List[str]:
        """Inject a bumper-to-bumper civilian traffic jam along a road segment."""
        edge = (u, v)
        if not self.network.graph.has_edge(u, v):
            return []

        edge_data = self.network.graph[u][v]
        length = float(edge_data.get("length_m", 200.0))
        lanes = int(edge_data.get("lanes", 1))

        created_ids = []
        spacing = length / max(1, num_vehicles + 1)

        for i in range(num_vehicles):
            veh_id = f"jam_car_{u}_{v}_{self.current_tick}_{i}"
            offset = max(2.0, min(length - 5.0, (i + 1) * spacing))
            lane = i % lanes
            veh = Vehicle(
                id=veh_id,
                kind="car",
                edge=edge,
                offset_m=offset,
                speed=1.0,
                lane=lane,
                route=[],
                is_stopped=True,
                wait_time=30.0,
                length_m=4.5,
                max_speed=float(edge_data.get("speed_limit_mps", 15.6)),
                max_accel=2.0,
            )
            self.vehicles[veh_id] = veh
            created_ids.append(veh_id)

        return created_ids

    def clear_traffic_jams(self, u: Optional[str] = None, v: Optional[str] = None) -> int:
        """Clear injected or all civilian traffic on a road or network-wide."""
        to_remove = []
        for veh_id, veh in self.vehicles.items():
            if veh.kind != "car":
                continue
            if u is not None and v is not None:
                if veh.edge == (u, v):
                    to_remove.append(veh_id)
            elif veh_id.startswith("jam_car_"):
                to_remove.append(veh_id)
        for vid in to_remove:
            self.vehicles.pop(vid, None)
        return len(to_remove)


    # -------------------------------------------------------------------------
    # Simulation Step Logic
    # -------------------------------------------------------------------------

    def step(self) -> None:
        """Advance the simulation world by 1 tick (1 simulated second)."""
        self.current_tick += 1
        dt = float(self.config.tick_seconds)

        # 1. Advance signal controllers
        for controller in self.signals.values():
            controller.step(dt)

        # 2. Spawn traffic arrivals
        new_vehicles = self.traffic_gen.generate_step(
            self.current_tick,
            list(self.vehicles.values()),
        )
        for v in new_vehicles:
            self.vehicles[v.id] = v

        # 3. Organize vehicles by edge and lane
        lane_map: Dict[Tuple[Tuple[str, str], int], List[Vehicle]] = defaultdict(list)
        for v in self.vehicles.values():
            lane_map[(v.edge, v.lane)].append(v)

        for v_list in lane_map.values():
            v_list.sort(key=lambda veh: veh.offset_m, reverse=True)

        # Handle yielding lane changes for civilian cars on 2-lane roads
        for v in list(self.vehicles.values()):
            if v.kind == "car" and v.yield_until_t > self.current_tick:
                edge_data = self.network.graph[v.edge[0]][v.edge[1]]
                if edge_data.get("lanes", 1) > 1 and v.lane == 1:
                    target_lane = 0
                    cars_in_target = lane_map[(v.edge, target_lane)]
                    can_merge = True
                    for other in cars_in_target:
                        if other.offset_m >= v.offset_m:
                            gap = other.offset_m - v.offset_m - other.length_m
                        else:
                            gap = v.offset_m - other.offset_m - v.length_m
                        if gap < 6.0:
                            can_merge = False
                            break
                    if can_merge:
                        lane_map[(v.edge, v.lane)].remove(v)
                        v.lane = target_lane
                        lane_map[(v.edge, target_lane)].append(v)
                        lane_map[(v.edge, target_lane)].sort(
                            key=lambda veh: veh.offset_m, reverse=True
                        )

        # 4. Compute car-following updates per lane
        for (edge, lane), v_list in lane_map.items():
            u, v = edge
            edge_data = self.network.graph[u][v]
            edge_len = float(edge_data["length_m"])
            speed_limit = float(edge_data["speed_limit_mps"])
            signal = self.signals[v]
            approach_signal = signal.state_for_approach(edge)
            max_offset_on_edge = edge_len - 0.5

            for i, veh in enumerate(v_list):
                leader = v_list[i - 1] if i > 0 else None

                # Determine desired speed v0
                if veh.is_ambulance:
                    if leader is not None and (leader.offset_m - veh.offset_m - leader.length_m) < 20.0:
                        v0 = veh.crawl_speed_mps
                    else:
                        v0 = veh.max_speed
                else:
                    if veh.yield_until_t > self.current_tick:
                        v0 = speed_limit * 0.5
                    else:
                        v0 = speed_limit

                # Check if leader vehicle can enter downstream intersection
                stop_line_dist: Optional[float] = None
                if leader is None:
                    can_enter = False
                    if approach_signal == "G" or (veh.is_ambulance and signal.is_preempted):
                        # Signal allows passing; check if downstream edge has space
                        if len(veh.route) > 0:
                            next_node = veh.route[0]
                            next_edge = (v, next_node)
                            next_lanes = self.network.graph[v][next_node].get("lanes", 1)
                            target_lane = min(veh.lane, next_lanes - 1)
                            downstream_list = lane_map.get((next_edge, target_lane))
                            min_downstream = (
                                downstream_list[-1].offset_m if downstream_list else float("inf")
                            )
                            if min_downstream >= (veh.length_m + 3.0):
                                can_enter = True
                        else:
                            can_enter = True  # Reached final destination

                    if not can_enter:
                        stop_line_dist = max_offset_on_edge

                accel = veh.compute_idm_accel(v0, leader, stop_line_dist, dt)
                v_tentative = max(0.0, veh.speed + accel * dt)
                dist_want = v_tentative * dt

                # Enforce strict non-overlap bound
                if leader is not None:
                    gap = leader.offset_m - veh.offset_m - leader.length_m
                    max_move = max(0.0, gap - 1.0)
                    dist_actual = min(dist_want, max_move)
                else:
                    gap_to_stop = max_offset_on_edge - veh.offset_m
                    if stop_line_dist is not None:
                        dist_actual = min(dist_want, max(0.0, gap_to_stop))
                    else:
                        # Clear to enter intersection, but bounded by edge length
                        dist_actual = min(dist_want, max(0.0, edge_len - veh.offset_m + 0.1))

                veh.speed = dist_actual / dt if dt > 0 else 0.0
                veh.offset_m += dist_actual

                veh.is_stopped = (veh.speed < 0.1)
                if veh.is_stopped:
                    veh.wait_time += dt
                    self.total_wait_time_s += dt

        # 5. Process intersection transitions for vehicles reaching the end of their edge
        finished_vehicles: List[str] = []
        for veh in list(self.vehicles.values()):
            u, v = veh.edge
            edge_len = float(self.network.graph[u][v]["length_m"])

            if veh.offset_m >= (edge_len - 0.6):
                signal = self.signals[v]
                signal_state = signal.state_for_approach(veh.edge)
                can_cross = (signal_state == "G") or (veh.is_ambulance and signal.is_preempted)

                if can_cross:
                    if len(veh.route) > 0:
                        next_node = veh.route[0]
                        next_edge = (v, next_node)
                        next_edge_lanes = self.network.graph[v][next_node].get("lanes", 1)
                        next_lane = min(veh.lane, next_edge_lanes - 1)

                        target_lane_veh = [
                            ov for ov in self.vehicles.values()
                            if ov.edge == next_edge and ov.lane == next_lane
                        ]
                        min_offset = min((ov.offset_m for ov in target_lane_veh), default=float("inf"))

                        if min_offset >= (veh.length_m + 3.0):
                            veh.offset_m = 0.0
                            veh.edge = next_edge
                            veh.lane = next_lane
                            veh.route = veh.route[1:]
                            veh.is_stopped = False
                        else:
                            veh.offset_m = edge_len - 0.5
                            veh.speed = 0.0
                            veh.is_stopped = True
                    else:
                        finished_vehicles.append(veh.id)
                else:
                    veh.offset_m = edge_len - 0.5
                    veh.speed = 0.0
                    veh.is_stopped = True

        for v_id in finished_vehicles:
            del self.vehicles[v_id]
            self.completed_vehicles += 1

        # 6. Record ambulance history
        for veh in self.vehicles.values():
            if veh.is_ambulance:
                x, y = self.network.edge_position(veh.edge, veh.offset_m)
                self.ambulance_history.append(
                    {
                        "vehicle_id": veh.id,
                        "tick": self.current_tick,
                        "x": x,
                        "y": y,
                        "speed_mps": veh.speed,
                        "edge": veh.edge,
                        "offset_m": veh.offset_m,
                    }
                )

    # -------------------------------------------------------------------------
    # World View Perception
    # -------------------------------------------------------------------------

    def get_world_view(self) -> WorldView:
        """Synthesize an immutable, read-only perception snapshot of the environment."""
        snapshots: List[VehicleSnapshot] = []
        edge_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        queues: Dict[Tuple[str, str], int] = defaultdict(int)

        for veh in self.vehicles.values():
            edge_counts[veh.edge] += 1
            u, v = veh.edge
            edge_len = self.network._edge_lengths.get(veh.edge, 200.0)
            x, y = self.network.edge_position(veh.edge, veh.offset_m)
            b_deg = self.network._edge_bearings.get(veh.edge, 0.0)

            # Queue condition: speed < 1.0 m/s within 60 m of stop line
            dist_to_stop = edge_len - veh.offset_m
            if veh.speed < 1.0 and dist_to_stop <= 60.0:
                queues[veh.edge] += 1

            snapshots.append(
                VehicleSnapshot(
                    id=veh.id,
                    kind=veh.kind,
                    edge=veh.edge,
                    offset_m=round(veh.offset_m, 2),
                    speed_mps=round(veh.speed, 2),
                    lane=veh.lane,
                    x=x,
                    y=y,
                    heading_deg=b_deg,
                    is_stopped=veh.is_stopped,
                    wait_time_s=veh.wait_time,
                    yield_until_t=veh.yield_until_t,
                )
            )

        densities: Dict[Tuple[str, str], float] = {}
        for u, v, data in self.network.graph.edges(data=True):
            edge = (u, v)
            count = edge_counts.get(edge, 0)
            len_km = data["length_m"] / 1000.0
            densities[edge] = round(count / max(0.01, len_km), 2)

        signals_map = {node: ctrl.current_phase().value for node, ctrl in self.signals.items()}

        return WorldView(
            tick=self.current_tick,
            vehicles=snapshots,
            queues=dict(queues),
            signals=signals_map,
            densities=densities,
        )
