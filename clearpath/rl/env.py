"""Gym-style Reinforcement Learning environment wrapping the ClearPath Simulator.

Features:
- Configured for a small 3x3 urban grid (9 junctions).
- Per-junction observation vector:
    1. queue_N: queue on incoming North approach (0 if boundary)
    2. queue_S: queue on incoming South approach (0 if boundary)
    3. queue_E: queue on incoming East approach (0 if boundary)
    4. queue_W: queue on incoming West approach (0 if boundary)
    5. max_wait_time: longest waiting time of any vehicle at this junction
    6. ambulance_dist: distance to approaching ambulance (0 if none)
    7. ambulance_eta: ETA of approaching ambulance (0 if none)
    8. phase_is_ns: 1.0 if NS axis has green or yellow, 0.0 otherwise
    9. phase_is_ew: 1.0 if EW axis has green or yellow, 0.0 otherwise
    10. phase_is_clearance: 1.0 if in yellow or all-red clearance interval
    11. elapsed_phase_time: seconds elapsed in current phase
- Actions per junction:
    0: hold (maintain current phase)
    1: switch (initiate transition to cross phase)
    2: extend (extend current green phase)
    3: preempt-green (request preemption green for approaching ambulance)
- Action masking via safety state machine:
    Invalid unsafe actions (e.g. switching mid-clearance, extending past max hold,
    preempting without ambulance) are strictly masked out.
- Reward:
    R = -(w1 * ambulance_delay) - (w2 * total_queue) + (w3 * preemption_success_bonus)
        - (w4 * safety_violation_penalty)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from clearpath.config import SimConfig
from clearpath.sim.network import RoadNetwork
from clearpath.sim.signals import SignalController, SignalPhase
from clearpath.sim.simulator import Simulator


# ─────────────────────────────────────────────────────────────────────────────
# Minimal Gym-compatible Space Interfaces (zero external dependencies)
# ─────────────────────────────────────────────────────────────────────────────

class Discrete:
    """Discrete action space [0, n - 1]."""

    def __init__(self, n: int, seed: Optional[int] = None) -> None:
        self.n = int(n)
        self._rng = np.random.default_rng(seed)

    def sample(self, mask: Optional[np.ndarray] = None) -> int:
        if mask is not None:
            valid = np.flatnonzero(mask)
            if len(valid) > 0:
                return int(self._rng.choice(valid))
        return int(self._rng.integers(0, self.n))

    def contains(self, x: Any) -> bool:
        return isinstance(x, (int, np.integer)) and 0 <= x < self.n

    def __repr__(self) -> str:
        return f"Discrete({self.n})"


class Box:
    """Continuous bounded or unbounded observation space."""

    def __init__(
        self,
        low: Union[float, np.ndarray],
        high: Union[float, np.ndarray],
        shape: Tuple[int, ...],
        dtype: type = np.float32,
        seed: Optional[int] = None,
    ) -> None:
        self.shape = shape
        self.dtype = dtype
        self.low = np.full(shape, low, dtype=dtype) if np.isscalar(low) else np.asarray(low, dtype=dtype)
        self.high = np.full(shape, high, dtype=dtype) if np.isscalar(high) else np.asarray(high, dtype=dtype)
        self._rng = np.random.default_rng(seed)

    def sample(self) -> np.ndarray:
        return self._rng.uniform(self.low, self.high).astype(self.dtype)

    def contains(self, x: Any) -> bool:
        arr = np.asarray(x)
        return arr.shape == self.shape and np.all(arr >= self.low) and np.all(arr <= self.high)

    def __repr__(self) -> str:
        return f"Box(shape={self.shape}, dtype={self.dtype})"


# ─────────────────────────────────────────────────────────────────────────────
# Actions enumeration & constants
# ─────────────────────────────────────────────────────────────────────────────

ACTION_HOLD = 0
ACTION_SWITCH = 1
ACTION_EXTEND = 2
ACTION_PREEMPT_GREEN = 3
NUM_ACTIONS = 4
OBS_DIM = 11


# ─────────────────────────────────────────────────────────────────────────────
# ClearPathGridEnv
# ─────────────────────────────────────────────────────────────────────────────

class ClearPathGridEnv:
    """Gym-style Multi-Junction Environment wrapping the Simulator on a 3x3 grid."""

    def __init__(
        self,
        config: Optional[SimConfig] = None,
        demand_level: str = "med",
        max_ticks: int = 200,
        ambulance_spawn_tick: int = 15,
        ambulance_origin: str = "j_0_0",
        ambulance_destination: str = "j_2_2",
        w1: float = 5.0,     # ambulance delay weight
        w2: float = 0.05,    # queue weight
        w3: float = 20.0,    # preemption success bonus
        w4: float = 10.0,    # safety violation penalty
        seed: int = 42,
    ) -> None:
        self.base_seed = seed
        self.demand_level = demand_level
        self.max_ticks = max_ticks
        self.ambulance_spawn_tick = ambulance_spawn_tick
        self.ambulance_origin = ambulance_origin
        self.ambulance_destination = ambulance_destination
        self.w1 = w1
        self.w2 = w2
        self.w3 = w3
        self.w4 = w4

        # Configure 3x3 grid
        if config is None:
            self.config = SimConfig(
                grid_rows=3,
                grid_cols=3,
                block_length_m=200.0,
                max_ticks=max_ticks,
                seed=seed,
            )
        else:
            self.config = config

        self.nodes = [f"j_{r}_{c}" for r in range(self.config.grid_rows) for c in range(self.config.grid_cols)]
        self.num_junctions = len(self.nodes)

        # Standard spaces
        self.action_space = Discrete(NUM_ACTIONS, seed=seed)
        self.observation_space = Box(low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32, seed=seed)

        self.sim: Optional[Simulator] = None
        self.ambulance_id: Optional[str] = None
        self.ambulance_passed_junctions: set[str] = set()
        self.current_tick: int = 0
        self._episode_rng = np.random.default_rng(seed)

    # ─────────────────────────────────────────────────────────────────────────
    # Environment Reset
    # ─────────────────────────────────────────────────────────────────────────

    def reset(self, seed: Optional[int] = None) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Reset the simulation environment to the initial state."""
        if seed is not None:
            self.base_seed = seed
            self._episode_rng = np.random.default_rng(seed)

        # Create fresh simulator
        cfg = SimConfig(
            grid_rows=self.config.grid_rows,
            grid_cols=self.config.grid_cols,
            block_length_m=self.config.block_length_m,
            max_ticks=self.max_ticks,
            seed=int(self._episode_rng.integers(0, 1000000)),
        )
        self.sim = Simulator(cfg, demand_level=self.demand_level)
        self.current_tick = 0
        self.ambulance_id = None
        self.ambulance_passed_junctions = set()

        obs = self._get_all_observations()
        info = {
            "tick": self.current_tick,
            "action_masks": self.action_masks(),
        }
        return obs, info

    # ─────────────────────────────────────────────────────────────────────────
    # Action Masking (Safety State Machine)
    # ─────────────────────────────────────────────────────────────────────────

    def action_mask(self, junction_id: str) -> np.ndarray:
        """Compute boolean validity mask [hold, switch, extend, preempt] for a junction.

        Strictly enforces clearance intervals and bounds:
        - When in yellow or all-red clearance: only HOLD is valid.
        - When in green:
            * SWITCH is valid only if min_green elapsed or emergency override.
            * EXTEND is valid if elapsed < max_preemption_hold_s.
            * PREEMPT_GREEN is valid only if an ambulance is approaching.
            * HOLD is valid if elapsed < max_preemption_hold_s.
        """
        assert self.sim is not None, "Call reset() before action_mask()"
        controller = self.sim.signals.get(junction_id)
        if controller is None:
            return np.array([True, False, False, False], dtype=bool)

        mask = np.zeros(NUM_ACTIONS, dtype=bool)
        phase = controller.phase
        elapsed = controller.time_in_phase_s

        is_clearance = phase in (
            SignalPhase.NS_YELLOW,
            SignalPhase.EW_YELLOW,
            SignalPhase.ALL_RED_TO_EW,
            SignalPhase.ALL_RED_TO_NS,
        )

        if is_clearance:
            # Must finish clearance; only HOLD is safe
            mask[ACTION_HOLD] = True
            return mask

        # We are in green (NS_GREEN or EW_GREEN)
        max_hold = float(self.config.max_preemption_hold_s)
        min_green = float(self.config.min_green_for_cross_s)

        # Check if an ambulance is approaching this junction
        amb_info = self._get_ambulance_info(junction_id)
        has_approaching_amb = amb_info is not None and amb_info["eta"] <= float(self.config.window_s)
        emergency_override = amb_info is not None and amb_info["eta"] <= 10.0

        # Action 0: HOLD
        if elapsed < max_hold:
            mask[ACTION_HOLD] = True
        else:
            mask[ACTION_HOLD] = False  # Must switch if max hold reached

        # Action 1: SWITCH
        if elapsed >= min_green or emergency_override:
            mask[ACTION_SWITCH] = True
        else:
            mask[ACTION_SWITCH] = False

        # Action 2: EXTEND
        if elapsed < max_hold:
            mask[ACTION_EXTEND] = True
        else:
            mask[ACTION_EXTEND] = False

        # Action 3: PREEMPT_GREEN
        if has_approaching_amb:
            mask[ACTION_PREEMPT_GREEN] = True
        else:
            mask[ACTION_PREEMPT_GREEN] = False

        # Fallback: at least one action must always be valid
        if not np.any(mask):
            mask[ACTION_HOLD] = True

        return mask

    def action_masks(self) -> Dict[str, np.ndarray]:
        """Return action masks for all junctions."""
        return {node: self.action_mask(node) for node in self.nodes}

    # ─────────────────────────────────────────────────────────────────────────
    # Environment Step
    # ─────────────────────────────────────────────────────────────────────────

    def step(
        self,
        actions: Union[Dict[str, int], List[int], np.ndarray],
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, float], bool, bool, Dict[str, Any]]:
        """Advance the environment by 1 tick given actions for junctions."""
        assert self.sim is not None, "Call reset() before step()"
        self.current_tick += 1
        t = float(self.current_tick)

        # Normalize actions to dict
        act_dict: Dict[str, int] = {}
        if isinstance(actions, dict):
            act_dict = actions
        else:
            act_list = list(actions)
            for idx, node in enumerate(self.nodes):
                act_dict[node] = int(act_list[idx]) if idx < len(act_list) else ACTION_HOLD

        # Check action masks and apply safety interventions
        safety_violations: Dict[str, int] = {node: 0 for node in self.nodes}
        current_masks = self.action_masks()

        for node in self.nodes:
            raw_act = act_dict.get(node, ACTION_HOLD)
            mask = current_masks[node]
            controller = self.sim.signals[node]

            # Intercept invalid unsafe action
            if not mask[raw_act]:
                safety_violations[node] = 1
                safe_act = ACTION_HOLD
            else:
                safe_act = raw_act

            # Apply safe actuation to signal controller
            self._apply_action(node, safe_act, controller, t)

        # Spawn ambulance if scheduled
        if self.current_tick == self.ambulance_spawn_tick and self.ambulance_id is None:
            self.ambulance_id = self.sim.spawn_ambulance(
                self.ambulance_origin,
                self.ambulance_destination,
            )

        # Advance simulator physics by 1 tick
        self.sim.step()
        world_view = self.sim.get_world_view()

        # Compute rewards and metrics
        rewards = self._compute_rewards(safety_violations, world_view)

        # Observations for next state
        next_obs = self._get_all_observations()

        # Termination conditions
        terminated = False
        ambulance_finished = False
        if self.ambulance_id is not None:
            # Check if ambulance finished route
            amb_veh = self.sim.vehicles.get(self.ambulance_id)
            if amb_veh is None and self.current_tick > self.ambulance_spawn_tick:
                ambulance_finished = True

        truncated = self.current_tick >= self.max_ticks
        if ambulance_finished and self.current_tick >= (self.ambulance_spawn_tick + 60):
            terminated = True

        info = {
            "tick": self.current_tick,
            "action_masks": self.action_masks(),
            "safety_violations": sum(safety_violations.values()),
            "ambulance_active": self.ambulance_id in self.sim.vehicles,
            "ambulance_completed": ambulance_finished,
            "total_network_queue": sum(world_view.queues.values()),
        }

        return next_obs, rewards, terminated, truncated, info

    # ─────────────────────────────────────────────────────────────────────────
    # Actuation Helper
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_action(
        self,
        junction_id: str,
        action: int,
        controller: SignalController,
        t: float,
    ) -> None:
        """Translate action into safe SignalController override."""
        phase = controller.phase
        is_ns_green = phase == SignalPhase.NS_GREEN
        is_ew_green = phase == SignalPhase.EW_GREEN

        if action == ACTION_HOLD:
            # If in override, maintain it; otherwise regular cycle continues
            pass

        elif action == ACTION_SWITCH:
            # Transition to cross axis
            target_phase = "EW" if is_ns_green else "NS"
            self.sim.set_signal_override(junction_id, target_phase, reason="rl_switch")

        elif action == ACTION_EXTEND:
            # Extend current green axis
            current_axis = "NS" if is_ns_green else "EW"
            self.sim.set_signal_override(junction_id, current_axis, reason="rl_extend")

        elif action == ACTION_PREEMPT_GREEN:
            # Preempt green for approaching ambulance
            amb_info = self._get_ambulance_info(junction_id)
            if amb_info is not None:
                approach_axis = amb_info["axis"]
                self.sim.set_signal_override(junction_id, approach_axis, reason="rl_preempt")

    # ─────────────────────────────────────────────────────────────────────────
    # Observations Helper
    # ─────────────────────────────────────────────────────────────────────────

    def _get_all_observations(self) -> Dict[str, np.ndarray]:
        """Compute the per-junction observation vector for all junctions."""
        world_view = self.sim.get_world_view()
        return {node: self._get_junction_obs(node, world_view) for node in self.nodes}

    def _get_junction_obs(self, junction_id: str, world_view: Any) -> np.ndarray:
        """Compute the 11-dim observation vector for a single junction.

        Dimensions:
        [0..3] Incoming queues: North, South, East, West
        [4] Longest waiting time among vehicles on incoming approaches
        [5] Distance to approaching ambulance (0.0 if none)
        [6] ETA to approaching ambulance (0.0 if none)
        [7] Phase is NS (1.0 or 0.0)
        [8] Phase is EW (1.0 or 0.0)
        [9] Phase is clearance interval (1.0 or 0.0)
        [10] Elapsed seconds in current phase
        """
        controller = self.sim.signals[junction_id]
        parts = junction_id.split("_")
        r, c = int(parts[1]), int(parts[2])

        # Incoming approach edges:
        # From North (r+1 -> r), South (r-1 -> r), East (c+1 -> c), West (c-1 -> c)
        north_edge = (f"j_{r+1}_{c}", junction_id) if r < self.config.grid_rows - 1 else None
        south_edge = (f"j_{r-1}_{c}", junction_id) if r > 0 else None
        east_edge  = (f"j_{r}_{c+1}", junction_id) if c < self.config.grid_cols - 1 else None
        west_edge  = (f"j_{r}_{c-1}", junction_id) if c > 0 else None

        q_north = float(world_view.queues.get(north_edge, 0)) if north_edge else 0.0
        q_south = float(world_view.queues.get(south_edge, 0)) if south_edge else 0.0
        q_east  = float(world_view.queues.get(east_edge, 0))  if east_edge else 0.0
        q_west  = float(world_view.queues.get(west_edge, 0))  if west_edge else 0.0

        # Longest wait time at incoming approaches
        incoming_edges = {north_edge, south_edge, east_edge, west_edge} - {None}
        max_wait = 0.0
        for veh in world_view.vehicles:
            if veh.edge in incoming_edges and veh.is_stopped:
                if veh.wait_time_s > max_wait:
                    max_wait = float(veh.wait_time_s)

        # Ambulance distance & ETA
        amb_info = self._get_ambulance_info(junction_id)
        amb_dist = float(amb_info["dist"]) if amb_info else 0.0
        amb_eta  = float(amb_info["eta"]) if amb_info else 0.0

        # Signal phase state
        phase = controller.phase
        phase_ns = 1.0 if phase in (SignalPhase.NS_GREEN, SignalPhase.NS_YELLOW) else 0.0
        phase_ew = 1.0 if phase in (SignalPhase.EW_GREEN, SignalPhase.EW_YELLOW) else 0.0
        phase_clearance = 1.0 if phase in (
            SignalPhase.NS_YELLOW,
            SignalPhase.EW_YELLOW,
            SignalPhase.ALL_RED_TO_EW,
            SignalPhase.ALL_RED_TO_NS,
        ) else 0.0
        elapsed = float(controller.time_in_phase_s)

        obs = np.array([
            q_north,
            q_south,
            q_east,
            q_west,
            max_wait,
            amb_dist,
            amb_eta,
            phase_ns,
            phase_ew,
            phase_clearance,
            elapsed,
        ], dtype=np.float32)

        return obs

    # ─────────────────────────────────────────────────────────────────────────
    # Ambulance Tracking
    # ─────────────────────────────────────────────────────────────────────────

    def _get_ambulance_info(self, junction_id: str) -> Optional[Dict[str, Any]]:
        """Return distance, ETA and entry axis for an ambulance approaching this junction."""
        if self.ambulance_id is None:
            return None
        amb = self.sim.vehicles.get(self.ambulance_id)
        if amb is None:
            return None

        # Build full route sequence: [curr_u, curr_v, ...route]
        full_route = [amb.edge[0], amb.edge[1]] + list(amb.route)
        if junction_id not in full_route:
            return None

        j_idx = full_route.index(junction_id)
        if j_idx == 0:
            # Ambulance already passed this junction
            return None

        # Previous node on route entering this junction
        prev_node = full_route[j_idx - 1]
        entry_edge = (prev_node, junction_id)

        # Determine if entry is North-South or East-West
        u_p = prev_node.split("_")
        v_p = junction_id.split("_")
        axis = "NS" if u_p[2] == v_p[2] else "EW"

        # Calculate distance along route to junction stopline
        graph = self.sim.network.graph
        dist = 0.0
        if amb.edge == entry_edge:
            edge_len = float(graph[amb.edge[0]][amb.edge[1]]["length_m"])
            dist = max(0.0, edge_len - amb.offset_m)
        elif full_route.index(amb.edge[0]) < j_idx:
            curr_edge_len = float(graph[amb.edge[0]][amb.edge[1]]["length_m"])
            dist += max(0.0, curr_edge_len - amb.offset_m)
            curr_v_idx = full_route.index(amb.edge[1])
            for i in range(curr_v_idx, j_idx):
                u, v = full_route[i], full_route[i + 1]
                dist += float(graph[u][v]["length_m"])
        else:
            return None

        speed = max(float(amb.speed), float(self.config.min_speed_mps))
        eta = dist / speed

        return {
            "dist": dist,
            "eta": eta,
            "axis": axis,
            "entry_edge": entry_edge,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Reward Calculation
    # ─────────────────────────────────────────────────────────────────────────

    def _compute_rewards(
        self,
        safety_violations: Dict[str, int],
        world_view: Any,
    ) -> Dict[str, float]:
        """Calculate per-junction reward R:

        R = -(w1 * ambulance_delay) - (w2 * total_queue) + (w3 * preemption_success_bonus)
            - (w4 * safety_violation_penalty)
        """
        rewards: Dict[str, float] = {}

        # Ambulance delay
        amb = self.sim.vehicles.get(self.ambulance_id) if self.ambulance_id else None

        for node in self.nodes:
            parts = node.split("_")
            r, c = int(parts[1]), int(parts[2])

            incoming_edges = [
                (f"j_{r+1}_{c}", node) if r < self.config.grid_rows - 1 else None,
                (f"j_{r-1}_{c}", node) if r > 0 else None,
                (f"j_{r}_{c+1}", node) if c < self.config.grid_cols - 1 else None,
                (f"j_{r}_{c-1}", node) if c > 0 else None,
            ]
            valid_edges = [e for e in incoming_edges if e is not None]

            # 1. Local queue at this junction
            node_queue = sum(world_view.queues.get(edge, 0) for edge in valid_edges)

            # 2. Local ambulance delay
            amb_delay = 0.0
            preempt_bonus = 0.0
            if amb is not None:
                # If ambulance is approaching or on approach to this node
                amb_info = self._get_ambulance_info(node)
                if amb_info is not None and amb_info["dist"] < 250.0:
                    if amb.is_stopped:
                        amb_delay = 1.0
                    else:
                        amb_delay = max(0.0, 1.0 - (amb.speed / self.config.ambulance_max_mps))

                    # Preemption success bonus if ambulance is passing freely through green
                    controller = self.sim.signals[node]
                    curr_axis = "NS" if controller.phase == SignalPhase.NS_GREEN else (
                        "EW" if controller.phase == SignalPhase.EW_GREEN else None
                    )
                    if amb_info["dist"] < 30.0 and curr_axis == amb_info["axis"] and not amb.is_stopped:
                        if node not in self.ambulance_passed_junctions:
                            preempt_bonus = 1.0
                            self.ambulance_passed_junctions.add(node)

            # 3. Safety penalty
            safety_pen = float(safety_violations.get(node, 0))

            # Combine reward
            r_val = (
                -(self.w1 * amb_delay)
                -(self.w2 * float(node_queue))
                +(self.w3 * preempt_bonus)
                -(self.w4 * safety_pen)
            )
            rewards[node] = float(r_val)

        return rewards

