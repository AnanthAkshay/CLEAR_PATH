"""Road network representation using NetworkX directed multigraphs.

Constructs an N x M urban grid where each road segment is represented as two
directed edges with lane counts, speed limits, lengths, free-flow transit times,
and compass bearings. Annotates hospital facility nodes from data/hospitals.json.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from clearpath.config import SimConfig


def edge_bearing(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate compass bearing in degrees [0, 360) from (x1, y1) to (x2, y2).

    Convention:
        0 deg   = North (+y)
        90 deg  = East  (+x)
        180 deg = South (-y)
        270 deg = West  (-x)
    """
    dx = x2 - x1
    dy = y2 - y1
    bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
    return round(bearing, 2)


class RoadNetwork:
    """Urban grid network topology, edge attributes, and geometric query helpers."""

    def __init__(self, config: SimConfig, hospitals_path: Optional[Path | str] = None) -> None:
        """Initialize road network topology from simulation configuration.

        Args:
            config: Simulation parameters including grid rows, cols, block length.
            hospitals_path: Optional path to hospitals.json file.
        """
        self.config = config
        self.graph = nx.DiGraph()
        self.hospitals: Dict[str, Dict[str, Any]] = {}
        self.hospital_nodes: Set[str] = set()
        self.boundary_nodes: List[str] = []

        if hospitals_path is None:
            hospitals_path = Path(__file__).resolve().parent.parent / "data" / "hospitals.json"
        self._load_hospitals(Path(hospitals_path))
        self._build_grid()

    def _load_hospitals(self, path: Path) -> None:
        """Load hospital definitions from JSON if present."""
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for hosp in data:
                    self.hospitals[hosp["id"]] = hosp
                    self.hospital_nodes.add(hosp["node_id"])

    def _build_grid(self) -> None:
        """Construct the N x M Manhattan grid graph with dual directed edges."""
        rows = self.config.grid_rows
        cols = self.config.grid_cols
        block_len = self.config.block_length_m

        # Add nodes
        for r in range(rows):
            for c in range(cols):
                node_id = f"j_{r}_{c}"
                x = float(c * block_len)
                y = float(r * block_len)
                is_boundary = (r == 0 or r == rows - 1 or c == 0 or c == cols - 1)
                is_hosp = node_id in self.hospital_nodes

                self.graph.add_node(
                    node_id,
                    r=r,
                    c=c,
                    x=x,
                    y=y,
                    is_boundary=is_boundary,
                    is_hospital=is_hosp,
                )
                if is_boundary:
                    self.boundary_nodes.append(node_id)

        # Add horizontal edges (East-West)
        for r in range(rows):
            is_arterial = (r % 3 == 0)
            road_class = "arterial" if is_arterial else "residential"
            lanes = 2 if is_arterial else 1
            speed_limit = self.config.arterial_mps if is_arterial else self.config.residential_mps
            free_flow_time = block_len / speed_limit

            for c in range(cols - 1):
                u = f"j_{r}_{c}"
                v = f"j_{r}_{c+1}"
                u_x, u_y = self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]
                v_x, v_y = self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]

                # u -> v (Eastbound, bearing = 90 deg)
                self.graph.add_edge(
                    u,
                    v,
                    length_m=block_len,
                    speed_limit_mps=speed_limit,
                    road_class=road_class,
                    lanes=lanes,
                    bearing_deg=edge_bearing(u_x, u_y, v_x, v_y),
                    free_flow_time_s=free_flow_time,
                    corridor=f"row_{r}",
                )
                # v -> u (Westbound, bearing = 270 deg)
                self.graph.add_edge(
                    v,
                    u,
                    length_m=block_len,
                    speed_limit_mps=speed_limit,
                    road_class=road_class,
                    lanes=lanes,
                    bearing_deg=edge_bearing(v_x, v_y, u_x, u_y),
                    free_flow_time_s=free_flow_time,
                    corridor=f"row_{r}",
                )

        # Add vertical edges (North-South)
        for c in range(cols):
            is_arterial = (c % 3 == 0)
            road_class = "arterial" if is_arterial else "residential"
            lanes = 2 if is_arterial else 1
            speed_limit = self.config.arterial_mps if is_arterial else self.config.residential_mps
            free_flow_time = block_len / speed_limit

            for r in range(rows - 1):
                u = f"j_{r}_{c}"
                v = f"j_{r+1}_{c}"
                u_x, u_y = self.graph.nodes[u]["x"], self.graph.nodes[u]["y"]
                v_x, v_y = self.graph.nodes[v]["x"], self.graph.nodes[v]["y"]

                # u -> v (Northbound, bearing = 0 deg)
                self.graph.add_edge(
                    u,
                    v,
                    length_m=block_len,
                    speed_limit_mps=speed_limit,
                    road_class=road_class,
                    lanes=lanes,
                    bearing_deg=edge_bearing(u_x, u_y, v_x, v_y),
                    free_flow_time_s=free_flow_time,
                    corridor=f"col_{c}",
                )
                # v -> u (Southbound, bearing = 180 deg)
                self.graph.add_edge(
                    v,
                    u,
                    length_m=block_len,
                    speed_limit_mps=speed_limit,
                    road_class=road_class,
                    lanes=lanes,
                    bearing_deg=edge_bearing(v_x, v_y, u_x, u_y),
                    free_flow_time_s=free_flow_time,
                    corridor=f"col_{c}",
                )

    def edge_bearing(self, u: str, v: str) -> float:
        """Return the compass bearing in degrees from node u to node v."""
        if self.graph.has_edge(u, v):
            return float(self.graph[u][v]["bearing_deg"])
        u_node = self.graph.nodes[u]
        v_node = self.graph.nodes[v]
        return edge_bearing(u_node["x"], u_node["y"], v_node["x"], v_node["y"])

    def nearest_node(self, x: float, y: float) -> str:
        """Find the junction node closest to the given (x, y) coordinates."""
        best_node = ""
        min_dist_sq = float("inf")
        for node, data in self.graph.nodes(data=True):
            dx = data["x"] - x
            dy = data["y"] - y
            dist_sq = dx * dx + dy * dy
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                best_node = node
        return best_node

    def edge_position(self, edge: Tuple[str, str], offset_m: float) -> Tuple[float, float]:
        """Interpolate (x, y) position on an edge given offset distance from start node."""
        u, v = edge
        u_data = self.graph.nodes[u]
        v_data = self.graph.nodes[v]
        length = self.graph[u][v]["length_m"]

        ratio = 0.0 if length <= 0.0 else max(0.0, min(1.0, offset_m / length))
        x = u_data["x"] + ratio * (v_data["x"] - u_data["x"])
        y = u_data["y"] + ratio * (v_data["y"] - u_data["y"])
        return round(x, 2), round(y, 2)

    def neighbors(self, node: str) -> List[str]:
        """Return all downstream adjacent junction node identifiers."""
        return list(self.graph.successors(node))

    def approach_edges(self, node: str) -> List[Tuple[str, str]]:
        """Return all inbound edges leading into the given junction node."""
        return [(u, node) for u in self.graph.predecessors(node)]

    def turn_type(self, in_edge: Tuple[str, str], out_edge: Tuple[str, str]) -> str:
        """Classify maneuver from in_edge to out_edge as 'straight', 'left', or 'right'.

        Args:
            in_edge: Approaching edge (u, v).
            out_edge: Departing edge (v, w).

        Returns:
            One of 'straight', 'left', 'right'.
        """
        u, v = in_edge
        v_out, w = out_edge
        if v != v_out:
            raise ValueError(f"Disconnected edges: {in_edge} does not connect to {out_edge}")

        b_in = self.edge_bearing(u, v)
        b_out = self.edge_bearing(v, w)

        # Delta heading in [-180, 180)
        delta = (b_out - b_in + 180.0) % 360.0 - 180.0

        if abs(delta) <= 45.0:
            return "straight"
        elif delta > 45.0:
            return "right"
        else:
            return "left"
