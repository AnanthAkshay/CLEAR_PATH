"""DispatcherAgent: hospital selection, corridor routing and ETA scheduling."""

from __future__ import annotations

import math
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx

from clearpath.agents.base import Agent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    AuthResult, EtaNotice, Message, RevokePreemption, RoutePlan,
)
from clearpath.config import SimConfig
from clearpath.sim.network import RoadNetwork

_ALTERNATIVES = 3
_CONGESTION_RATIO = 1.25
_REROUTE_EVERY_TICKS = 5


class DispatcherAgent(Agent):
    """Picks a destination hospital and builds the preemption ETA corridor.

    Routing runs on the live ``WorldView``. Every edge is costed in seconds as
    ``t_edge = length / max(v_min, v_limit * (1 - density_factor)) + queue_delay``
    where ``queue_delay = queue_len * avg_headway`` and
    ``avg_headway = (vehicle_length + gap) / effective_speed``. Paths are solved
    with A* using a Euclidean-distance-over-max-speed heuristic, which stays
    admissible because no edge can be traversed faster than ``ambulance_max_mps``.

    Hospitals are ranked by ``score = alpha * (travel / reference_travel_s) +
    (1 - alpha) * (wait / reference_wait_s)``. Both criteria are expressed as
    fractions of fixed reference values, so a hospital's score depends only on
    itself and the references — never on which other candidates happen to
    qualify. Raw seconds stay on every ranked entry.

    The ETA walk uses ``min(ambulance_max_mps * 0.8, limit * 1.3)`` per edge, which
    is the speed the corridor is expected to sustain once preemption is granted.
    """

    def __init__(
        self, agent_id: str, bus: MessageBus, config: SimConfig,
        network: RoadNetwork, clock: Any = time.monotonic,
    ) -> None:
        """Initialize the dispatcher with config, the road network and a clock.

        The clock supplies the publish time for re-plans, which have no world view
        to take a tick from; it must return simulation seconds, not wall time.
        """
        super().__init__(agent_id, bus)
        self.config = config
        self.network = network
        self.clock = clock
        self._auth: Dict[str, AuthResult] = {}
        self._plans: Dict[str, Dict[str, Any]] = {}
        self._cached_weights_tick: Optional[int] = None
        self._cached_weights: Dict[Tuple[str, str], float] = {}
        self._static_edge_params: Dict[Tuple[str, str], Tuple[float, float, float, float]] = {}
        if hasattr(self.network, "graph"):
            for u, v, data in self.network.graph.edges(data=True):
                length = float(data["length_m"])
                limit = float(data["speed_limit_mps"])
                spacing = self.config.vehicle_length_m + self.config.avg_gap_m
                jam_per_km = int(data.get("lanes", 1)) * 1000.0 / spacing
                self._static_edge_params[(u, v)] = (length, limit, spacing, jam_per_km)

    def on_message(self, msg: Message) -> None:
        """Record authentication verdicts; a revocation withdraws authorization."""
        if isinstance(msg, AuthResult):
            if msg.is_authenticated:
                self._auth[msg.vehicle_id] = msg
            else:
                self._auth.pop(msg.vehicle_id, None)
        elif isinstance(msg, RevokePreemption):
            self._auth.pop(msg.vehicle_id, None)

    def step(self, world_view: Any, t: int) -> None:
        """Periodically re-plan active corridors whose predicted cost degraded."""
        if t % _REROUTE_EVERY_TICKS != 0:
            return
        for vehicle_id in list(self._plans):
            self.reroute_if_congested(vehicle_id, world_view)

    # ------------------------------------------------------------------
    # Public planning API
    # ------------------------------------------------------------------

    def dispatch(
        self,
        vehicle_id: str,
        incident_loc: Tuple[float, float],
        incident_type: str,
        world_view: Any,
        target_hospital_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rank hospitals for an incident and publish the chosen corridor plan.
        
        If target_hospital_id is provided, routes directly to that hospital facility.
        """
        origin = self.network.nearest_node(float(incident_loc[0]), float(incident_loc[1]))
        result: Dict[str, Any] = {
            "vehicle_id": vehicle_id,
            "origin": origin,
            "incident_type": incident_type,
            "ranked": [],
            "degraded": False,
            "dispatched": False,
        }

        if vehicle_id not in self._auth:
            result["reason"] = "no authenticated AuthResult for vehicle"
            return result

        weights = self._weights(world_view)
        ranked, degraded = self._rank(origin, incident_type, weights)
        result["ranked"] = ranked
        result["degraded"] = degraded

        best = None
        if target_hospital_id:
            # Match user-selected target hospital
            for cand in ranked:
                if cand["hospital_id"] == target_hospital_id or cand.get("node") == target_hospital_id:
                    best = cand
                    break
            if best is None:
                # Direct route even if specialty filter didn't match
                hosp = self.network.hospitals.get(target_hospital_id)
                if hosp:
                    node = self._hospital_node(hosp)
                    path = self._shortest(origin, node, weights)
                    if path:
                        travel = self._travel_time(path, weights)
                        wait_s = float(hosp.get("avg_wait_time_min", 0.0)) * 60.0
                        beds = sum(int(c) for c in hosp.get("available_beds_by_unit", {}).values())
                        best = {
                            "hospital_id": hosp["id"],
                            "name": hosp.get("name", ""),
                            "node": node,
                            "beds": beds,
                            "travel_time_s": round(travel, 2),
                            "hospital_wait_s": round(wait_s, 2),
                            "relaxed": True,
                            "path": path,
                        }
        elif ranked:
            best = ranked[0]

        if best is None:
            result["reason"] = "no reachable hospital with available capacity"
            return result

        eta, total = self._schedule(best["path"])
        plan = {
            "vehicle_id": vehicle_id,
            "origin": origin,
            "node": best["node"],
            "hospital_id": best["hospital_id"],
            "incident_type": incident_type,
            "path": best["path"],
            "eta_by_junction": eta,
            "total_eta_s": total,
            "cost": best["travel_time_s"],
            "weights": weights,
            "approach_edge": None,
            "position": None,
        }
        self._plans[vehicle_id] = plan

        now = float(world_view.tick)
        self._publish(plan, now)

        result.update(
            {
                "dispatched": True,
                "hospital_id": best["hospital_id"],
                "path": best["path"],
                "eta_by_junction": eta,
                "total_eta_s": total,
                "alternatives": self._alternatives(origin, best["node"], weights),
                "reason": "ok",
            }
        )
        return result

    def replan(
        self, vehicle_id: str, blocked_nodes: Iterable[str], world_view: Any = None
    ) -> Optional[Dict[str, Any]]:
        """Re-route from the vehicle's current position around rejected junctions.

        The start node and remaining head is derived from the vehicle's live edge
        and offset (via ``world_view``, or the last observed position), so a
        mid-route re-plan never re-announces junctions already cleared and its
        ETAs are measured from now rather than from the original origin.
        """
        plan = self._plans.get(vehicle_id)
        if plan is None:
            return None

        start, approach, head_s = self._resolve_from(plan, world_view)
        path = self._shortest(start, plan["node"], plan["weights"], set(blocked_nodes))
        if path is None:
            return None

        eta, total = self._schedule(path, head_s)
        plan.update(
            {
                "path": path,
                "eta_by_junction": eta,
                "total_eta_s": total,
                "cost": self._travel_time(path, plan["weights"]) + head_s,
                "approach_edge": approach,
            }
        )
        if plan["vehicle_id"] in self._auth:
            self._publish(plan, self.clock())
        return plan

    def reroute_if_congested(self, vehicle_id: str, world_view: Any) -> bool:
        """Re-plan when the live cost of the active corridor exceeds it by over 25% or traffic makes an alternative path faster."""
        plan = self._plans.get(vehicle_id)
        if plan is None:
            return False

        weights = self._weights(world_view)
        start, approach, head_s = self._resolve_from(plan, world_view)
        path = self._shortest(start, plan["node"], weights)
        if path is None:
            return False

        cost = self._travel_time(path, weights) + head_s

        # Evaluate cost of staying on current remaining path under live traffic
        curr_path = plan.get("path", [])
        curr_rem: List[str] = []
        if start in curr_path:
            idx = curr_path.index(start)
            curr_rem = list(curr_path[idx:])

        curr_cost = (self._travel_time(curr_rem, weights) + head_s) if len(curr_rem) >= 2 else cost
        path_diverges = bool(curr_rem and path != curr_rem)

        # Trigger re-plan if:
        # 1. Total cost exceeds original plan cost by 25%, OR
        # 2. Current path ahead is congested (>15% slower than alternative) and a better route exists
        is_congested = (cost > plan["cost"] * _CONGESTION_RATIO) or (path_diverges and curr_cost > cost * 1.15)
        if not is_congested:
            return False

        eta, total = self._schedule(path, head_s)
        plan.update(
            {
                "path": path,
                "weights": weights,
                "cost": cost,
                "eta_by_junction": eta,
                "total_eta_s": total,
                "approach_edge": approach,
            }
        )
        if plan["vehicle_id"] in self._auth:
            self._publish(plan, float(world_view.tick))
        return True

    def _publish(self, plan: Dict[str, Any], now: float) -> None:
        """Publish the plan's RoutePlan and one EtaNotice per downstream junction.

        Junctions without an approach edge are skipped, because there is no turn
        for them to serve -- except on a single-node corridor, where the origin is
        also the destination. That node gets one terminus notice with an empty
        approach and exit and ``eta_t = now``, so it learns a vehicle terminates
        there rather than hearing nothing at all.
        """
        path = plan["path"]
        eta = plan["eta_by_junction"]
        self.bus.publish(
            RoutePlan(
                vehicle_id=plan["vehicle_id"],
                hospital_id=plan["hospital_id"],
                path_nodes=list(path),
                eta_by_junction=dict(eta),
                total_eta_s=plan["total_eta_s"],
                ts=now,
                sender=self.id,
                recipient="*",
            )
        )
        terminus = len(path) == 1
        for i, node in enumerate(path):
            if i == 0:
                approach = plan.get("approach_edge")
            else:
                approach = f"{path[i - 1]}_{node}"
            if not approach and not terminus:
                continue
            exit_edge = f"{node}_{path[i + 1]}" if i + 1 < len(path) else ""
            self.bus.publish(
                EtaNotice(
                    junction_id=node,
                    vehicle_id=plan["vehicle_id"],
                    eta_t=now + eta[node],
                    approach_edge=approach or "",
                    exit_edge=exit_edge,
                    ts=now,
                    sender=self.id,
                    recipient=node,
                )
            )

    # ------------------------------------------------------------------
    # Cost model
    # ------------------------------------------------------------------

    def _edge_cost(self, edge: Tuple[str, str], world_view: Any) -> float:
        """Return the traversal cost of ``edge`` in seconds.

        ``t_edge = length / max(v_min, v_limit * (1 - density_factor)) + queue_delay``
        where ``queue_delay = queue_len * avg_headway``,
        ``avg_headway = (vehicle_length + gap) / effective_speed``, and
        ``density_factor = vehicles_per_km / jam_density`` with
        ``jam_density = lanes * 1000 / (vehicle_length + gap)``. The world view
        reports densities in vehicles per kilometre, so they are divided by the
        lane capacity before entering the 0..1 density factor.

        Args:
            edge: Directed edge ``(u, v)``.
            world_view: Live perception state carrying ``densities`` and ``queues``.

        Returns:
            Edge cost in seconds.
        """
        params = self._static_edge_params.get(edge)
        if params is not None:
            length, limit, spacing, jam_per_km = params
        else:
            u, v = edge
            data = self.network.graph[u][v]
            length = float(data["length_m"])
            limit = float(data["speed_limit_mps"])
            spacing = self.config.vehicle_length_m + self.config.avg_gap_m
            jam_per_km = int(data.get("lanes", 1)) * 1000.0 / spacing

        densities = getattr(world_view, "densities", {}) or {}
        queues = getattr(world_view, "queues", {}) or {}
        density = min(1.0, max(0.0, float(densities.get(edge, 0.0))) / jam_per_km)
        effective = max(self.config.min_speed_mps, limit * (1.0 - density))
        headway = spacing / effective
        queue_len = int(queues.get(edge, 0))

        # Physical civilian car count on this road segment
        density_val = float(densities.get(edge, 0.0))
        car_count = max(0, int(round(density_val * (length / 1000.0))))

        # Realistic emergency vehicle traffic delay:
        # 1. Base travel time at effective flow speed
        # 2. Civilian vehicle friction: each car in the ambulance's corridor adds yield/clearing friction
        # 3. Intersection queue delay: each queued car at the downstream signal adds red-queue clearing time
        traffic_friction = car_count * 3.5
        queue_delay = queue_len * max(headway, 3.5)
        return (length / effective) + traffic_friction + queue_delay

    def _weights(self, world_view: Any) -> Dict[Tuple[str, str], float]:
        """Cost every edge of the network for the current world view (cached per tick)."""
        tick = getattr(world_view, "tick", None)
        if tick is not None and self._cached_weights_tick == tick:
            return self._cached_weights

        edge_iter = self._static_edge_params.keys() if self._static_edge_params else self.network.graph.edges()
        weights = {
            edge: self._edge_cost(edge, world_view)
            for edge in edge_iter
        }
        if tick is not None:
            self._cached_weights_tick = tick
            self._cached_weights = weights
        return weights

    def _heuristic(self, u: str, v: str) -> float:
        """Euclidean distance over max speed: admissible lower bound on cost."""
        a = self.network.graph.nodes[u]
        b = self.network.graph.nodes[v]
        return math.hypot(b["x"] - a["x"], b["y"] - a["y"]) / self.config.ambulance_max_mps

    def _shortest(
        self, origin: str, target: str, weights: Dict[Tuple[str, str], float],
        blocked: Optional[Set[str]] = None,
    ) -> Optional[List[str]]:
        """A* shortest path, optionally avoiding a set of blocked junctions."""
        graph = self.network.graph
        if blocked:
            graph = nx.restricted_view(graph, list(blocked), [])
        try:
            return nx.astar_path(
                graph, origin, target,
                heuristic=self._heuristic,
                weight=lambda u, v, d: weights[(u, v)],
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def _travel_time(self, path: Sequence[str], weights: Dict[Tuple[str, str], float]) -> float:
        """Sum the cost model over a path."""
        return sum(weights[(u, v)] for u, v in zip(path, path[1:]))

    def _alternatives(
        self, origin: str, target: str, weights: Dict[Tuple[str, str], float]
    ) -> List[List[str]]:
        """Up to three loop-free candidate paths (Yen) for reservation fallback."""
        paths: List[List[str]] = []
        try:
            for path in nx.shortest_simple_paths(
                self.network.graph, origin, target,
                weight=lambda u, v, d: weights[(u, v)],
            ):
                paths.append(path)
                if len(paths) >= _ALTERNATIVES:
                    break
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
        return paths

    def _current_position(
        self, vehicle_id: str, world_view: Any, plan: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Return the vehicle's edge and offset, refreshing it from the world view."""
        if world_view is not None:
            for snapshot in world_view.vehicles:
                if snapshot.id == vehicle_id:
                    plan["position"] = {
                        "edge": (snapshot.edge[0], snapshot.edge[1]),
                        "offset_m": float(snapshot.offset_m),
                    }
                    return plan["position"]
        return plan.get("position")

    def _remaining_leg_s(self, edge: Tuple[str, str], offset_m: float) -> float:
        """Seconds left on the vehicle's current edge from its offset to the node."""
        data = self.network.graph[edge[0]][edge[1]]
        speed = min(
            self.config.ambulance_max_mps * 0.8,
            float(data["speed_limit_mps"]) * 1.3,
        )
        remaining = max(0.0, float(data["length_m"]) - offset_m)
        return remaining / max(speed, self.config.min_speed_mps)

    def _resolve_from(
        self, plan: Dict[str, Any], world_view: Any
    ) -> Tuple[str, Optional[str], float]:
        """Return (start node, approach edge, head seconds) for a mid-route re-plan."""
        position = self._current_position(plan["vehicle_id"], world_view, plan)
        if position is None or not self.network.graph.has_edge(*position["edge"]):
            return plan["origin"], None, 0.0

        edge = position["edge"]
        return edge[1], f"{edge[0]}_{edge[1]}", self._remaining_leg_s(
            edge, position["offset_m"]
        )

    def _schedule(
        self, path: Sequence[str], head_s: float = 0.0
    ) -> Tuple[Dict[str, float], float]:
        """Walk the path accumulating preemption-aware travel time per junction.

        ``head_s`` is the time already needed to finish the vehicle's current edge,
        so the first junction in ``path`` is reached at ``head_s`` rather than 0.
        """
        eta: Dict[str, float] = {path[0]: head_s}
        elapsed = head_s
        for u, v in zip(path, path[1:]):
            data = self.network.graph[u][v]
            speed = min(
                self.config.ambulance_max_mps * 0.8,
                float(data["speed_limit_mps"]) * 1.3,
            )
            elapsed += float(data["length_m"]) / max(speed, self.config.min_speed_mps)
            eta[v] = elapsed
        return eta, elapsed

    # ------------------------------------------------------------------
    # Hospital ranking
    # ------------------------------------------------------------------

    def _rank(
        self, origin: str, incident_type: str, weights: Dict[Tuple[str, str], float]
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Rank hospitals by score, relaxing the specialty filter if none qualify."""
        ranked = self._candidates(origin, incident_type, weights, relaxed=False)
        degraded = False
        if not ranked:
            degraded = True
            ranked = self._candidates(origin, incident_type, weights, relaxed=True)

        self._apply_scores(ranked)
        ranked.sort(key=lambda entry: (entry["score"], entry["hospital_id"]))
        return ranked, degraded

    def _candidates(
        self, origin: str, incident_type: str,
        weights: Dict[Tuple[str, str], float], relaxed: bool,
    ) -> List[Dict[str, Any]]:
        """Return every hospital that can take this incident under a filter."""
        return [
            entry
            for entry in (
                self._score(hosp, origin, incident_type, weights, relaxed)
                for hosp in self.network.hospitals.values()
            )
            if entry is not None
        ]

    def _apply_scores(self, entries: List[Dict[str, Any]]) -> None:
        """Express both criteria against fixed references, then weight them.

        ``score = alpha * (travel / reference_travel_s) + (1 - alpha) * (wait /
        reference_wait_s)``. Because the divisors are fixed configuration values
        rather than the min/max of the current candidate set, a hospital's score
        is unaffected by unrelated hospitals appearing or disappearing, and scores
        stay comparable between incidents. They are cost-like (lower is better)
        and deliberately not clamped to 0..1; raw seconds stay on the entry.
        """
        travel_ref = max(self.config.reference_travel_s, 1e-6)
        wait_ref = max(self.config.reference_wait_s, 1e-6)

        for entry in entries:
            travel_ratio = entry["travel_time_s"] / travel_ref
            wait_ratio = entry["hospital_wait_s"] / wait_ref
            entry["travel_ratio"] = round(travel_ratio, 4)
            entry["wait_ratio"] = round(wait_ratio, 4)
            entry["score"] = round(
                self.config.alpha * travel_ratio
                + (1.0 - self.config.alpha) * wait_ratio,
                4,
            )

    def _score(
        self, hospital: Dict[str, Any], origin: str, incident_type: str,
        weights: Dict[Tuple[str, str], float], relaxed: bool,
    ) -> Optional[Dict[str, Any]]:
        """Build a candidate entry, or return None when it cannot take this incident."""
        units = hospital.get("available_beds_by_unit", {})
        specialties = [s.lower() for s in hospital.get("specialties", [])]

        if relaxed:
            beds = sum(int(count) for count in units.values())
        else:
            if incident_type.lower() not in specialties:
                return None
            beds = int(units.get(incident_type.lower(), 0))
        if beds <= 0:
            return None

        node = self._hospital_node(hospital)
        path = self._shortest(origin, node, weights)
        if path is None:
            return None

        travel = self._travel_time(path, weights)
        wait_s = float(hospital.get("avg_wait_time_min", 0.0)) * 60.0
        return {
            "hospital_id": hospital["id"],
            "name": hospital.get("name", ""),
            "node": node,
            "beds": beds,
            "travel_time_s": round(travel, 2),
            "hospital_wait_s": round(wait_s, 2),
            "relaxed": relaxed,
            "path": path,
        }

    def _hospital_node(self, hospital: Dict[str, Any]) -> str:
        """Return the grid node of a hospital entry."""
        return str(hospital["node"])
