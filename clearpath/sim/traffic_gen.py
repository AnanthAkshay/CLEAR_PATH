"""Synthetic traffic generation module driven by deterministic Poisson processes.

Spawns civilian vehicles at network boundary intersections and plans origin-destination
routes across the urban grid.
"""

from __future__ import annotations

from typing import List, Optional

import networkx as nx
import numpy as np

from clearpath.config import SimConfig
from clearpath.sim.network import RoadNetwork
from clearpath.sim.vehicles import Vehicle


class TrafficGenerator:
    """Spawns vehicles deterministically at perimeter boundary junctions.

    Attributes:
        config: Simulation parameters.
        network: RoadNetwork topological reference.
        demand_level: Traffic demand scale ('low', 'med', 'high').
        rng: Deterministic numpy random generator.
    """

    DEMAND_RATES = {
        "low": 0.04,
        "med": 0.10,
        "high": 0.20,
    }

    def __init__(
        self,
        config: SimConfig,
        network: RoadNetwork,
        demand_level: str = "med",
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        """Initialize traffic generator with network and deterministic RNG."""
        self.config = config
        self.network = network
        self.demand_level = demand_level.lower()
        self.rng = rng or np.random.default_rng(config.seed)
        self._car_counter: int = 0
        self._rate_per_boundary: float = self.DEMAND_RATES.get(self.demand_level, 0.10)

    def set_demand_level(self, level: str) -> None:
        """Update traffic arrival demand intensity ('low', 'med', 'high')."""
        self.demand_level = level.lower()
        self._rate_per_boundary = self.DEMAND_RATES.get(self.demand_level, 0.10)

    def generate_step(self, current_tick: int, active_vehicles: List[Vehicle]) -> List[Vehicle]:
        """Generate new vehicles arriving during the current tick at boundary nodes.

        Args:
            current_tick: Current simulation tick.
            active_vehicles: List of all currently active vehicles in the simulator.

        Returns:
            List of newly spawned Vehicle instances ready to be injected.
        """
        spawned: List[Vehicle] = []
        boundary_nodes = self.network.boundary_nodes
        all_nodes = list(self.network.graph.nodes)

        # Build index of minimum offset per (edge, lane) to ensure headway on spawn
        min_offset_by_lane: dict[tuple[tuple[str, str], int], float] = {}
        for v in active_vehicles:
            key = (v.edge, v.lane)
            if key not in min_offset_by_lane or v.offset_m < min_offset_by_lane[key]:
                min_offset_by_lane[key] = v.offset_m

        for origin in boundary_nodes:
            # Poisson arrivals at this boundary node
            arrivals = int(self.rng.poisson(self._rate_per_boundary))
            if arrivals <= 0:
                continue

            for _ in range(arrivals):
                # Pick a random destination node distinct from origin
                dest = str(self.rng.choice(all_nodes))
                if dest == origin:
                    continue

                try:
                    path = nx.shortest_path(
                        self.network.graph,
                        origin,
                        dest,
                        weight="free_flow_time_s",
                    )
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue

                if len(path) < 2:
                    continue

                first_edge = (path[0], path[1])
                edge_data = self.network.graph[path[0]][path[1]]
                lanes = edge_data.get("lanes", 1)
                speed_limit = edge_data.get("speed_limit_mps", self.config.residential_mps)

                # Find a lane with sufficient headway at entrance (>= vehicle_length + 10m)
                safe_spawn_headway = self.config.vehicle_length_m + 10.0
                placed_lane: Optional[int] = None

                for lane_idx in range(lanes):
                    cur_min = min_offset_by_lane.get((first_edge, lane_idx), float("inf"))
                    if cur_min >= safe_spawn_headway:
                        placed_lane = lane_idx
                        # Reserve this spot so multiple cars don't spawn in same tick on same spot
                        min_offset_by_lane[(first_edge, lane_idx)] = 0.0
                        break

                if placed_lane is None:
                    # Entry point blocked, drop arrival to preserve safety invariant
                    continue

                self._car_counter += 1
                vehicle_id = f"car_{self._car_counter}"

                car = Vehicle(
                    id=vehicle_id,
                    kind="car",
                    edge=first_edge,
                    offset_m=0.0,
                    speed=speed_limit * 0.75,
                    lane=placed_lane,
                    route=path[2:],  # Nodes remaining after path[1]
                    is_stopped=False,
                    wait_time=0.0,
                    length_m=self.config.vehicle_length_m,
                    max_speed=speed_limit,
                    max_accel=2.5,
                )
                spawned.append(car)

        return spawned
