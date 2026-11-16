"""ClearPathEngine: main event-loop orchestrator for the ClearPath simulation.

Wires up every component and drives the per-tick cycle in a fixed order:

  1. ``simulator.step()`` / ``get_world_view()``
  2. ``bus.step(t)`` – deliver pending messages
  3. Agent steps in priority order:
       Security (stream validation) →
       Dispatcher (reroute check) →
       JunctionAgents →
       GuidanceAgent
  4. Metrics collection
  5. ``snapshot()`` available for the dashboard / API

A run-mode flag ``preemption_enabled`` lets callers run the same seeded
scenario with and without corridor preemption so the two results can be
compared fairly.

Emergency requests
------------------
``submit_emergency_request(request)`` validates via SecurityAgent first.
Only authenticated requests spawn an ambulance, trigger corridor planning,
and start junction negotiation.  Spoofed requests have zero effect on any
signal and their block is counted in metrics.

Serialisable state
------------------
``snapshot()`` returns a plain dict (all values JSON-serialisable) holding
the current tick, vehicle positions, signal states, and metric summary.
It is used by both the FastAPI server and the Streamlit dashboard.

``reset(seed)`` tears everything down and re-initialises from scratch,
optionally with a different RNG seed, so the CLI scenario runner can keep
the same engine object across baseline / ClearPath runs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from clearpath.agents.dispatcher import DispatcherAgent
from clearpath.agents.guidance import GuidanceAgent
from clearpath.agents.junction import JunctionAgent
from clearpath.agents.security import SecurityAgent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    PreemptionRequest, RecoveryStarted, ReserveNack, RoutePlan,
)
from clearpath.config import SimConfig, load_config
from clearpath.engine.metrics import MetricsCollector
from clearpath.sim.simulator import Simulator

logger = logging.getLogger("clearpath.engine.ClearPathEngine")

# Message types counted as negotiation messages
_NEGOTIATION_TYPES = frozenset(
    {"ReserveCorridor", "ReserveAck", "ReserveNack", "EtaNotice", "GreenWavePrepare"}
)


# ─────────────────────────────────────────────────────────────────────────────
# Actuator Proxy
# ─────────────────────────────────────────────────────────────────────────────

class _ActuatorProxy:
    """Queues actuations from agents and applies them to the simulator when preemption is enabled."""

    def __init__(self, sim: Simulator, engine: ClearPathEngine) -> None:
        self.sim = sim
        self.engine = engine
        self.pending: List[Tuple[Any, ...]] = []

    def set_signal_override(self, junction_id: str, phase: Any, reason: str = "") -> None:
        if self.engine.preemption_enabled:
            self.pending.append(("set", junction_id, phase, reason))

    def clear_signal_override(self, junction_id: str) -> None:
        if self.engine.preemption_enabled:
            self.pending.append(("clear", junction_id))

    def apply_yield(self, vehicle_ids: List[str], until_t: float) -> None:
        if self.engine.preemption_enabled:
            self.pending.append(("yield", vehicle_ids, until_t))

    def apply(self) -> None:
        for item in self.pending:
            if item[0] == "set":
                self.sim.set_signal_override(item[1], item[2], reason=item[3])
            elif item[0] == "clear":
                self.sim.clear_signal_override(item[1])
            elif item[0] == "yield":
                self.sim.apply_yield(item[1], item[2])
        self.pending.clear()


# ─────────────────────────────────────────────────────────────────────────────
# ClearPathEngine
# ─────────────────────────────────────────────────────────────────────────────

class ClearPathEngine:
    """Full simulation engine: wires all components and drives the tick loop.

    Parameters
    ----------
    config : SimConfig | None
        Simulation configuration; ``load_config()`` defaults are used when None.
    preemption_enabled : bool
        When False the engine refuses *all* preemption requests so the same
        seeded run can be used as a no-preemption baseline.
    demand_level : str
        Traffic demand passed to the TrafficGenerator (``"low"``, ``"med"``,
        ``"high"``).
    baseline : MetricsCollector | None
        A previously-collected baseline ``MetricsCollector`` whose ambulance
        travel time is used to compute ``improvement_pct`` in the metrics.
    """

    def __init__(
        self,
        config: Optional[SimConfig] = None,
        preemption_enabled: bool = True,
        demand_level: str = "med",
        baseline: Optional[MetricsCollector] = None,
        junction_policy: str = "rule",
        rl_model: Optional[Any] = None,
    ) -> None:
        self.config = config or load_config()
        self.preemption_enabled = preemption_enabled
        self.demand_level = demand_level
        self.junction_policy = junction_policy
        self.rl_model = rl_model
        self.current_tick: int = 0

        self._build(baseline)

    # ─────────────────────────────────────────────────────────────────────────
    # Private construction / reset helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _build(self, baseline: Optional[MetricsCollector]) -> None:
        """(Re-)initialise all components from scratch."""
        cfg = self.config

        self.bus = MessageBus(seed=cfg.seed)
        self.sim = Simulator(cfg, demand_level=self.demand_level)

        clock = lambda: float(self.sim.current_tick)   # noqa: E731

        self.security = SecurityAgent(
            "security", self.bus, cfg,
            self.sim.network.graph,
            clock=clock,
        )
        self.dispatcher = DispatcherAgent(
            "dispatcher", self.bus, cfg,
            self.sim.network,
            clock=clock,
        )
        self.actuator = _ActuatorProxy(self.sim, self)
        self.junctions: Dict[str, JunctionAgent] = {
            node: JunctionAgent(
                node, self.bus, cfg, self.sim.network, self.actuator,
                policy=self.junction_policy, rl_model=self.rl_model,
            )
            for node in self.sim.network.graph.nodes
        }
        self.guidance = GuidanceAgent(
            "guidance", self.bus,
            network=self.sim.network,
            actuator=self.actuator,
            drive_left=True,  # India default
        )

        self.metrics = MetricsCollector(cfg, baseline=baseline)
        self._active_ambulances: Dict[str, Dict[str, Any]] = {}  # vehicle_id → plan info
        self._blocked_requests: List[Dict[str, Any]] = []

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def step(self) -> None:
        """Advance one full simulation tick in the mandated order.

        Order
        -----
        1. simulator.step() – vehicle kinematics, signals, spawning
        2. get_world_view() – immutable read-only snapshot
        3. bus.step(t)      – deliver pending messages to agents
        4. Agent steps:
             a. Security (stream validation of active ambulances)
             b. Dispatcher (congestion-triggered re-route check)
             c. JunctionAgents (ETA refresh, hold/release)
             d. GuidanceAgent  (lane advisories, yield orders)
        5. apply agent actuations to the simulator
        6. metrics.record()
        """
        self.current_tick += 1
        t = self.current_tick

        # 1. Advance physics
        self.sim.step()

        # 2. Snapshot world
        world_view = self.sim.get_world_view()

        # 3. Bus delivery
        self.bus.step(t)

        # 4a. Security: stream-validate every active ambulance
        for vid in list(self._active_ambulances):
            veh = self.sim.vehicles.get(vid)
            if veh is None:
                # Ambulance completed its run
                self._active_ambulances.pop(vid, None)
                continue
            # Build a lightweight telemetry object from live state
            x, y = self.sim.network.edge_position(veh.edge, veh.offset_m)
            bearing = self.sim.network.edge_bearing(*veh.edge)
            from clearpath.bus.messages import Telemetry
            telem = Telemetry(
                x=x, y=y,
                speed_mps=veh.speed,
                accel_mps2=0.0,
                heading_deg=bearing,
                edge_id=f"{veh.edge[0]}_{veh.edge[1]}",
                lane=veh.lane,
                vehicle_id=vid,
            )
            self.security.validate_stream(telem)

        # 4b. Dispatcher reroute check
        self.dispatcher.step(world_view, t)

        # 4c. Junction agents
        for junction in self.junctions.values():
            junction.step(world_view, t)

        # 4d. Guidance
        self.guidance.step(world_view, t)

        # 4e. Apply agent actuations to simulator
        self.actuator.apply()

        # 5. Metrics – scan newly published messages for negotiation / recovery
        self._process_new_messages()
        self.metrics.record(t, world_view, self.sim)

    def submit_emergency_request(
        self,
        request: PreemptionRequest,
        incident_type: str = "general",
        ground_truth_valid: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Authenticate then act on a preemption request.

        Parameters
        ----------
        request : PreemptionRequest
            Signed request from an ambulance unit.
        incident_type : str
            Hospital specialty selector (e.g. ``"trauma"``, ``"cardiac"``).
        ground_truth_valid : bool | None
            True when the scenario runner knows this is a genuine request;
            False when it is a known spoof.  Used only to update false-accept /
            false-reject counters.

        Returns
        -------
        dict
            ``{"authenticated": bool, "auth": AuthResult, "dispatch": dict | None}``
        """
        request.ts = float(self.sim.current_tick)

        # Always authenticate (counter tracks all attempts)
        auth = self.security.authenticate(request)
        self.bus.publish(auth)
        self.dispatcher.on_message(auth)

        # Record security metrics
        self.metrics.on_security_result(
            allowed=auth.is_authenticated,
            reasons=list(auth.reasons),
            ground_truth_valid=ground_truth_valid,
        )

        if not auth.is_authenticated:
            logger.info(
                "Rejected preemption for %s: %s", request.vehicle_id, auth.security_log
            )
            block = {
                "tick": self.current_tick,
                "vehicle_id": request.vehicle_id,
                "reasons": list(auth.reasons),
                "risk_score": auth.risk_score,
            }
            self._blocked_requests.append(block)
            return {"authenticated": False, "auth": auth, "dispatch": None}

        # Plan the corridor
        world_view = self.sim.get_world_view()
        dispatch = self.dispatcher.dispatch(request.vehicle_id, request.incident_loc, incident_type, world_view)

        if dispatch.get("dispatched"):
            path = dispatch["path"]
            vid = request.vehicle_id
            if vid not in self.sim.vehicles:
                try:
                    spawned_id = self.sim.spawn_ambulance(path[0], path[-1], route=list(path))
                    if spawned_id != vid:
                        amb = self.sim.vehicles.pop(spawned_id)
                        amb.id = vid
                        self.sim.vehicles[vid] = amb
                except Exception as exc:
                    logger.warning("Could not spawn ambulance: %s", exc)
            else:
                amb = self.sim.vehicles[vid]
                if len(path) >= 2 and (path[0], path[1]) == amb.edge:
                    amb.route = list(path[2:])
                elif len(path) >= 1 and path[0] == amb.edge[1]:
                    amb.route = list(path[1:])

            if self.preemption_enabled:
                self._active_ambulances[vid] = {
                    "plan": dispatch,
                    "start_tick": self.current_tick,
                }
                self.metrics.on_preemption_start(self.current_tick, world_view)
                logger.info("Dispatched %s → %s (preemption active)", vid, dispatch.get("hospital_id"))
            else:
                logger.info("Dispatched %s → %s (baseline run, no preemption)", vid, dispatch.get("hospital_id"))
        else:
            logger.warning("Dispatch failed for %s: %s", request.vehicle_id, dispatch.get("reason", "unknown"))

        return {"authenticated": True, "auth": auth, "dispatch": dispatch}

    def reset(self, seed: Optional[int] = None) -> None:
        """Tear down and rebuild the engine, optionally with a new RNG seed.

        This lets the scenario runner reuse the same engine object for the
        baseline and ClearPath runs without duplicating setup code.
        """
        if seed is not None:
            # Build a new config with the override seed (config is frozen)
            overrides: Dict[str, Any] = {}
            for f in self.config.__dataclass_fields__:  # type: ignore[attr-defined]
                overrides[f] = getattr(self.config, f)
            overrides["seed"] = seed
            self.config = SimConfig(**overrides)

        self.current_tick = 0
        self._active_ambulances = {}
        self._blocked_requests = []
        self._build(baseline=self.metrics.baseline)

    def snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serialisable state snapshot for the dashboard / API."""
        wv = self.sim.get_world_view()
        vehicles_data = [
            {
                "id": v.id,
                "kind": v.kind,
                "edge": list(v.edge),
                "offset_m": v.offset_m,
                "speed_mps": v.speed_mps,
                "lane": v.lane,
                "x": v.x,
                "y": v.y,
                "heading_deg": v.heading_deg,
                "is_stopped": v.is_stopped,
                "wait_time_s": v.wait_time_s,
            }
            for v in wv.vehicles
        ]
        signals_data = {
            node: ctrl.current_phase().value
            for node, ctrl in self.sim.signals.items()
        }
        return {
            "tick": self.current_tick,
            "preemption_enabled": self.preemption_enabled,
            "vehicles": vehicles_data,
            "signals": signals_data,
            "queues": {f"{u}_{v}": q for (u, v), q in wv.queues.items()},
            "densities": {f"{u}_{v}": d for (u, v), d in wv.densities.items()},
            "active_ambulances": list(self._active_ambulances.keys()),
            "blocked_requests": list(self._blocked_requests),
            "vms_board": dict(self.guidance.vms_board),
            "metrics_summary": self.metrics.summary(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Backward-compat shim (old Orchestrator interface still used by tests)
    # ─────────────────────────────────────────────────────────────────────────

    def handle_preemption_request(
        self, request: PreemptionRequest, incident_type: str = "general"
    ) -> Dict[str, Any]:
        """Alias for :meth:`submit_emergency_request` (old API)."""
        return self.submit_emergency_request(request, incident_type)

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _process_new_messages(self) -> None:
        """Scan recently published bus messages and update negotiation / recovery metrics."""
        # We track the index of the last-processed message to avoid double-counting.
        last_idx = getattr(self, "_last_msg_idx", 0)
        new_msgs = self.bus.message_log[last_idx:]
        self._last_msg_idx = len(self.bus.message_log)

        for msg in new_msgs:
            msg_type = getattr(msg, "type", type(msg).__name__)
            if msg_type in _NEGOTIATION_TYPES:
                self.metrics.on_negotiation_message(msg_type)
            if msg_type == "RecoveryStarted":
                jid = getattr(msg, "junction_id", "")
                dur = float(getattr(msg, "recovery_duration_s", 0.0))
                self.metrics.on_recovery(jid, dur)


# ─────────────────────────────────────────────────────────────────────────────
# Legacy Orchestrator alias (preserves import compatibility with existing tests)
# ─────────────────────────────────────────────────────────────────────────────

class Orchestrator(ClearPathEngine):
    """Backward-compatible alias for ClearPathEngine.

    The old ``Orchestrator`` class accepted ``(config, bus)`` and exposed
    ``handle_preemption_request``.  ``ClearPathEngine`` supersedes it; this
    subclass keeps the old constructor signature so pre-existing test code
    continues to import and use it without modification.
    """

    def __init__(
        self,
        config: Optional[SimConfig] = None,
        bus: Optional[MessageBus] = None,
        preemption_enabled: bool = True,
    ) -> None:
        # ClearPathEngine creates its own bus; if the caller supplied one we
        # swap it in after construction.
        super().__init__(config=config, preemption_enabled=preemption_enabled)
        if bus is not None:
            # Re-wire all agents to the caller-supplied bus
            self.bus = bus
            self._rewire_bus(bus)

    def _rewire_bus(self, bus: MessageBus) -> None:
        """Swap every agent's bus reference to the supplied one."""
        for agent in [self.security, self.dispatcher, self.guidance, *self.junctions.values()]:
            agent.bus = bus
            # Re-subscribe under the new bus
            bus.subscribe(agent.id, agent.on_message)
