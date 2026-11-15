"""JunctionAgent: per-intersection preemption, feasibility and green-wave negotiation.

Steps 5a-5c scope: reservation storage, the local feasibility check at
``eta - window_s``, pre-clear, the green hold and release, and sequential
corridor negotiation with live ETA handoff. Recovery, revocation, concurrency
and fail-safe are deliberately absent.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from clearpath.agents.base import Agent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    EtaNotice, GreenWavePrepare, Message, PassedNotice, RecoveryDone,
    RecoveryStarted, ReserveAck, ReserveCorridor, ReserveNack, RevokePreemption,
    RoutePlan,
)
from clearpath.config import SimConfig
from clearpath.sim.network import RoadNetwork

# Spec: the green is requested 5 s before the announced arrival and released 3 s
# after the vehicle crosses the stop line.
_HOLD_LEAD_S = 5.0
_HOLD_AFTER_PASS_S = 3.0
# Spec: a true emergency override may cut a phase that has not reached
# min_green_for_cross_s when the ambulance is closer than this.
_EMERGENCY_OVERRIDE_S = 10.0
# Ranking of the severity labels carried by ``PreemptionRequest``; an unknown or
# absent label counts as HIGH, which is that message's own default.
_SEVERITY_RANK = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}


class JunctionState(str, Enum):
    """Explicit per-junction lifecycle states."""

    NORMAL = "NORMAL"
    PRE_CLEAR = "PRE_CLEAR"
    HOLD_GREEN = "HOLD_GREEN"
    RECOVERY = "RECOVERY"
    REJECTED = "REJECTED"


class JunctionAgent(Agent):
    """Serves one approaching ambulance at a single intersection.

    Feasibility: at ``eta - window_s`` the junction sums the queues on its cross
    approaches. A queue at or below ``queue_flush_threshold`` takes the ordinary
    path (green at ``eta - 5 s``); a longer one must drain first, so the junction
    enters ``PRE_CLEAR`` and starts the transition as soon as
    ``min_green_for_cross_s`` allows, shortening the cross green through the
    actuator's own yellow and all-red. A queue that cannot drain inside the
    remaining window is answered with ``ReserveNack`` plus the earliest feasible
    time, and the junction moves to ``REJECTED``.

    Concurrency: a junction serves one ambulance at a time. When two notices
    overlap in time (their ETAs are closer than ``window_s``) the higher severity
    wins, and equal severities are broken by the earlier ETA; the loser is
    answered with ``ReserveNack``. A notice that arrives once a green is already
    in ``PRE_CLEAR`` or ``HOLD_GREEN`` never displaces it -- displacing an active
    hold needs a ``RevokePreemption``, not a rival notice.

    Fail-safe: while a reservation is held, ``bus_silence_timeout_ticks`` of
    silence releases the green through recovery instead of holding it forever.

    Negotiation: the first junction on a ``RoutePlan`` path seeds a
    ``ReserveCorridor`` carrying the remaining chain. Each junction answers its
    upstream with ``ReserveAck`` or ``ReserveNack`` and forwards the corridor
    downstream; a downstream ``ReserveNack`` travels back upstream and every
    junction it passes drops its tentative hold. A missing ``ReserveAck`` is
    treated as a ``ReserveNack`` after ``negotiation_timeout_ticks``. While a
    reservation is live the junction re-estimates the arrival from the
    ambulance's actual edge, offset and speed, and pushes the result downstream
    in ``GreenWavePrepare`` every tick.
    """

    def __init__(
        self,
        node_id: str,
        bus: MessageBus,
        config: SimConfig,
        network: RoadNetwork,
        actuators: Any,
    ) -> None:
        """Initialize the junction with no reservation, override or negotiation.

        Args:
            node_id: Junction identifier, matching the graph node (e.g. ``j_0_1``).
            bus: Shared message bus; the agent subscribes under ``node_id``.
            config: Simulation configuration (timings, threshold, hold cap).
            network: Road graph used to derive phases and cross-street speeds.
            actuators: Object exposing ``set_signal_override(junction_id, phase,
                reason)`` and ``clear_signal_override(junction_id)``.
        """
        super().__init__(node_id, bus)
        self.config = config
        self.network = network
        self.actuators = actuators
        self.state: JunctionState = JunctionState.NORMAL
        self.event_log: List[Dict[str, Any]] = []
        self._reservation: Optional[Dict[str, Any]] = None
        self._hold_started: Optional[float] = None
        self._release_at: Optional[float] = None
        self._pre_clear_until: Optional[float] = None
        self._phase_name: Optional[str] = None
        self._phase_since: float = 0.0
        self._last_message_t: float = 0.0
        # Negotiation state.
        self._paths: Dict[str, List[str]] = {}
        self._etas: Dict[str, Dict[str, float]] = {}
        self._tentative: Dict[str, bool] = {}
        self._upstream: Dict[str, str] = {}
        self._pending_downstream: Optional[Tuple[str, str, float]] = None
        # Recovery state.
        self._recovery_until: Optional[float] = None
        self._recovery_deadline: Optional[float] = None
        self._starved_phase: Optional[str] = None

    # ------------------------------------------------------------------
    # Bus
    # ------------------------------------------------------------------

    def on_message(self, msg: Message) -> None:
        """Route each message type to its handler."""
        self._last_message_t = float(getattr(msg, "ts", 0.0))
        if isinstance(msg, EtaNotice):
            if msg.junction_id == self.id:
                self._on_eta(msg)
        elif isinstance(msg, PassedNotice):
            if msg.junction_id == self.id:
                self._on_passed(msg)
        elif isinstance(msg, RoutePlan):
            self._on_plan(msg)
        elif isinstance(msg, ReserveCorridor):
            self._on_corridor(msg)
        elif isinstance(msg, ReserveAck):
            self._on_ack(msg)
        elif isinstance(msg, ReserveNack):
            self._on_nack(msg)
        elif isinstance(msg, GreenWavePrepare):
            self._on_prepare(msg)
        elif isinstance(msg, RevokePreemption):
            self._on_revoke(msg)

    def _on_eta(self, msg: EtaNotice) -> None:
        """Reserve this arrival, refusing it when a rival has the stronger claim."""
        phase = self._phase_for(msg.approach_edge)
        if phase is None:
            self.logger.warning(
                "Ignoring EtaNotice for %s: approach %r does not enter this junction",
                msg.vehicle_id, msg.approach_edge,
            )
            return
        candidate = {
            "vehicle_id": msg.vehicle_id,
            "eta_t": float(msg.eta_t),
            "approach_edge": msg.approach_edge,
            "exit_edge": msg.exit_edge,
            "phase": phase,
            "sender": msg.sender,
            "severity": getattr(msg, "severity", "HIGH"),
            "switch_at": None,
            "long": False,
            "queue": 0,
        }
        incumbent = self._reservation
        if incumbent is not None and incumbent["vehicle_id"] == candidate["vehicle_id"]:
            # A re-announced ETA for the vehicle already reserved replaces it.
            self._reservation = candidate
            return
        if incumbent is not None and self._overlaps(incumbent, candidate):
            committed = self.state in (JunctionState.PRE_CLEAR, JunctionState.HOLD_GREEN)
            if committed or not self._outranks(candidate, incumbent):
                self._reject(candidate, incumbent)
                return
            self._reject(incumbent, candidate)
        if self.state is JunctionState.REJECTED:
            self._transition(JunctionState.NORMAL, float(msg.ts), "new reservation")
        self._reservation = candidate

    def _overlaps(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """True when two arrivals compete for the same preemption window."""
        return abs(a["eta_t"] - b["eta_t"]) < float(self.config.window_s)

    def _outranks(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """True when ``a`` wins: higher severity first, then the earlier ETA."""
        rank_a = _SEVERITY_RANK.get(str(a["severity"]).upper(), _SEVERITY_RANK["HIGH"])
        rank_b = _SEVERITY_RANK.get(str(b["severity"]).upper(), _SEVERITY_RANK["HIGH"])
        if rank_a != rank_b:
            return rank_a > rank_b
        return (a["eta_t"], a["vehicle_id"]) < (b["eta_t"], b["vehicle_id"])

    def _reject(self, reservation: Dict[str, Any], winner: Dict[str, Any]) -> None:
        """Nack a reservation that lost the concurrency contest."""
        self.bus.publish(
            ReserveNack(
                junction_id=self.id, vehicle_id=reservation["vehicle_id"],
                reason=(
                    f"busy with {winner['vehicle_id']} "
                    f"({winner['severity']}, eta {winner['eta_t']:.0f}s)"
                ),
                ts=self._last_message_t, sender=self.id,
                recipient=reservation["sender"] or "dispatcher",
            )
        )

    def _on_passed(self, msg: PassedNotice) -> None:
        """Schedule the release of a green held for the reserved vehicle."""
        reservation = self._reservation
        if reservation is None or msg.vehicle_id != reservation["vehicle_id"]:
            return
        if self.state is not JunctionState.HOLD_GREEN or self._release_at is not None:
            return
        self._release_at = float(msg.t) + _HOLD_AFTER_PASS_S

    def _on_plan(self, msg: RoutePlan) -> None:
        """Learn the path, and seed the corridor if this is the first junction on it."""
        path = list(msg.path_nodes)
        self._paths[msg.vehicle_id] = path
        self._etas[msg.vehicle_id] = dict(msg.eta_by_junction)
        if len(path) < 3 or path[1] != self.id:
            return
        if self._pending_downstream is not None or self._tentative.get(msg.vehicle_id):
            return
        # The first junction commits too, and answers the dispatcher that asked.
        self._tentative[msg.vehicle_id] = True
        self._upstream[msg.vehicle_id] = msg.sender
        self.bus.publish(
            ReserveAck(
                junction_id=self.id, vehicle_id=msg.vehicle_id,
                reservation_id=msg.id, ts=msg.ts, sender=self.id, recipient=msg.sender,
            )
        )
        self._send_corridor(msg.vehicle_id, path[2:], float(msg.ts))

    def _on_corridor(self, msg: ReserveCorridor) -> None:
        """Acknowledge upstream, hold tentatively, and pass the chain down."""
        chain = list(msg.corridor_nodes)
        if chain and chain[0] == self.id:
            chain = chain[1:]
        self._tentative[msg.vehicle_id] = True
        self._upstream[msg.vehicle_id] = msg.sender
        self.bus.publish(
            ReserveAck(
                junction_id=self.id, vehicle_id=msg.vehicle_id,
                reservation_id=msg.id, ts=msg.ts, sender=self.id, recipient=msg.sender,
            )
        )
        if chain:
            self._send_corridor(msg.vehicle_id, chain, float(msg.ts))

    def _on_ack(self, msg: ReserveAck) -> None:
        """Clear the outstanding downstream wait for this vehicle."""
        pending = self._pending_downstream
        if pending is not None and pending[0] == msg.vehicle_id:
            self._pending_downstream = None

    def _on_nack(self, msg: ReserveNack) -> None:
        """Drop the tentative hold and carry the refusal back upstream."""
        self._pending_downstream = None
        self._tentative.pop(msg.vehicle_id, None)
        upstream = self._upstream.pop(msg.vehicle_id, "")
        if not upstream:
            return
        self.bus.publish(
            ReserveNack(
                junction_id=self.id, vehicle_id=msg.vehicle_id,
                reason=f"downstream refused: {msg.reason}", ts=msg.ts,
                sender=self.id, recipient=upstream,
            )
        )

    def _on_prepare(self, msg: GreenWavePrepare) -> None:
        """Adopt the arrival time an upstream junction estimates for us.

        The local re-estimate overwrites this on the next tick whenever the
        ambulance is visible from here; the notice is what keeps the arrival
        current while it is still upstream.
        """
        reservation = self._reservation
        if reservation is None or msg.to_junction_id != self.id:
            return
        if reservation["vehicle_id"] != msg.vehicle_id:
            return
        reservation["eta_t"] = float(msg.expected_arrival_t)

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def step(self, world_view: Any, t: int) -> None:
        """Refresh the ETA, police the negotiation, then plan, hold and release."""
        now = float(t)
        self._observe(world_view, now)
        self._refresh_and_prepare(world_view, now)
        self._check_negotiation_timeout(now)
        if self._fail_safe_due(now):
            self._enter_recovery(now, "fail-safe: bus silent")
        self._observe_pass(world_view, now)
        if self.state is JunctionState.NORMAL:
            self._plan_if_due(world_view, now)
            if self.state is JunctionState.NORMAL:
                self._switch_if_allowed(now)
        elif self.state in (JunctionState.PRE_CLEAR, JunctionState.HOLD_GREEN):
            self._advance_hold(now)
        elif self.state is JunctionState.RECOVERY:
            self._step_recovery(world_view, now)

    def _refresh_and_prepare(self, world_view: Any, now: float) -> None:
        """Re-estimate the arrival from live telemetry and tell the next junction."""
        reservation = self._reservation
        if reservation is None:
            return
        vehicle_id = reservation["vehicle_id"]
        eta = self._estimate_eta(world_view, vehicle_id, now)
        if eta is not None:
            reservation["eta_t"] = eta
            # The ordinary path tracks the live estimate; anything else would
            # freeze the switch on the first, least informed, guess.
            if reservation["switch_at"] is not None and not reservation["long"]:
                reservation["switch_at"] = eta - _HOLD_LEAD_S
        downstream = self._next_node(reservation["exit_edge"])
        if downstream is None:
            return
        self.bus.publish(
            GreenWavePrepare(
                from_junction_id=self.id, to_junction_id=downstream,
                vehicle_id=vehicle_id,
                expected_arrival_t=reservation["eta_t"] + self._edge_travel(self.id, downstream),
                ts=now, sender=self.id, recipient=downstream,
            )
        )

    def _check_negotiation_timeout(self, now: float) -> None:
        """Treat a missing downstream Ack as a Nack once the window expires."""
        pending = self._pending_downstream
        if pending is None:
            return
        vehicle_id, upstream, sent_at = pending
        if now - sent_at < self.config.negotiation_timeout_ticks:
            return
        self._pending_downstream = None
        self._tentative.pop(vehicle_id, None)
        upstream = self._upstream.pop(vehicle_id, upstream)
        if not upstream:
            return
        self.bus.publish(
            ReserveNack(
                junction_id=self.id, vehicle_id=vehicle_id, reason="negotiation timeout",
                ts=now, sender=self.id, recipient=upstream,
            )
        )

    def _send_corridor(self, vehicle_id: str, chain: List[str], now: float) -> None:
        """Forward the remaining chain to its first node and await its Ack."""
        downstream = chain[0]
        upstream = self._upstream.get(vehicle_id, "dispatcher")
        self._pending_downstream = (vehicle_id, upstream, now)
        self.bus.publish(
            ReserveCorridor(
                vehicle_id=vehicle_id, corridor_nodes=list(chain),
                eta_t=self._eta_of(vehicle_id, downstream, now),
                duration_s=float(self.config.window_s), ts=now,
                sender=self.id, recipient=downstream,
            )
        )

    # ------------------------------------------------------------------
    # Preemption
    # ------------------------------------------------------------------

    def _fail_safe_due(self, now: float) -> bool:
        """True when a live reservation has outlived the bus's silence budget."""
        if self._reservation is None:
            return False
        if self.state not in (JunctionState.PRE_CLEAR, JunctionState.HOLD_GREEN):
            return False
        return now - self._last_message_t > self.config.bus_silence_timeout_ticks

    def _plan_if_due(self, world_view: Any, now: float) -> None:
        """Run the local feasibility check once the planning time has arrived."""
        reservation = self._reservation
        if reservation is None or reservation["switch_at"] is not None:
            return
        if now < reservation["eta_t"] - self.config.window_s:
            return

        queue = self._cross_queue(world_view, reservation["phase"])
        reservation["queue"] = queue
        if queue <= self.config.queue_flush_threshold:
            reservation["switch_at"] = reservation["eta_t"] - _HOLD_LEAD_S
            return

        clear_s = self._clear_s(queue, reservation["phase"])
        usable_s = (reservation["eta_t"] - now) - self._transition_s()
        if clear_s > usable_s:
            self._nack(now, queue, clear_s)
            return
        reservation["switch_at"] = now
        reservation["long"] = True

    def _switch_if_allowed(self, now: float) -> None:
        """Request the green once it is due and the cross phase has had its minimum."""
        reservation = self._reservation
        if reservation is None or reservation["switch_at"] is None:
            return
        if now < reservation["switch_at"]:
            return
        if not self._emergency(now, reservation["eta_t"]):
            if now < self._min_green_end(reservation["phase"]):
                return
        self._request_green(now, reservation)

    def _request_green(self, now: float, reservation: Dict[str, Any]) -> None:
        """Hand the phase to the actuator, which runs its own yellow and all-red."""
        self.actuators.set_signal_override(
            self.id, reservation["phase"],
            reason=f"ambulance {reservation['vehicle_id']}",
        )
        self._hold_started = now
        self._release_at = None
        if reservation["long"]:
            self._pre_clear_until = now + self._transition_s()
            self._transition(
                JunctionState.PRE_CLEAR, now,
                f"cross queue {reservation['queue']} pre-clearing",
            )
        else:
            self._transition(
                JunctionState.HOLD_GREEN, now,
                f"green requested for {reservation['vehicle_id']}",
            )

    def _advance_hold(self, now: float) -> None:
        """Finish the pre-clear transition, then release on pass or at the cap."""
        if (
            self._hold_started is not None
            and now - self._hold_started >= self.config.max_preemption_hold_s
        ):
            self._enter_recovery(now, "hold cap reached")
            return
        if self.state is JunctionState.PRE_CLEAR:
            if self._pre_clear_until is not None and now >= self._pre_clear_until:
                self._pre_clear_until = None
                self._transition(JunctionState.HOLD_GREEN, now, "cross street cleared")
            return
        if self._release_at is not None and now >= self._release_at:
            self._enter_recovery(now, "cleared after pass")

    def _enter_recovery(self, now: float, reason: str) -> None:
        """Release the preemption green and compensate the starved cross street.

        The override moves to the cross phase, which forces the controller's own
        yellow and all-red first, so no green ever follows a green. The cross
        green is held for ``recovery_s`` plus the delay it suffered, with that
        extension capped at ``recovery_s`` so one long hold cannot starve it back.
        """
        reservation = self._reservation
        delay = 0.0 if self._hold_started is None else max(0.0, now - self._hold_started)
        if reservation is not None:
            self._starved_phase = "EW" if reservation["phase"] == "NS" else "NS"
        duration = float(self.config.recovery_s) + min(delay, float(self.config.recovery_s))

        self.actuators.set_signal_override(
            self.id, self._starved_phase or "NS", reason="recovery"
        )
        self._reservation = None
        self._hold_started = None
        self._release_at = None
        self._pre_clear_until = None
        self._recovery_until = now + duration
        self._recovery_deadline = now + duration + float(self.config.recovery_s)
        self.bus.publish(
            RecoveryStarted(
                junction_id=self.id, recovery_duration_s=duration,
                ts=now, sender=self.id, recipient="*",
            )
        )
        self._transition(JunctionState.RECOVERY, now, reason)

    def _step_recovery(self, world_view: Any, now: float) -> None:
        """Hold the compensating green, then hand control back to the normal cycle."""
        if self._recovery_until is not None and now < self._recovery_until:
            return
        if not self._cross_exits_have_room(world_view):
            if self._recovery_deadline is not None and now < self._recovery_deadline:
                return
        self.actuators.clear_signal_override(self.id)
        self._realign_offset(now)
        self._recovery_until = None
        self._recovery_deadline = None
        self.bus.publish(
            RecoveryDone(junction_id=self.id, ts=now, sender=self.id, recipient="*")
        )
        self._transition(JunctionState.NORMAL, now, "recovery complete")

    def _on_revoke(self, msg: RevokePreemption) -> None:
        """Abandon the hold for a revoked vehicle and recover the cross street."""
        reservation = self._reservation
        if reservation is None or msg.vehicle_id != reservation["vehicle_id"]:
            return
        if self.state not in (JunctionState.PRE_CLEAR, JunctionState.HOLD_GREEN):
            return
        self._tentative.pop(msg.vehicle_id, None)
        self._enter_recovery(float(msg.ts), "revoked")

    def _nack(self, now: float, queue: int, clear_s: float) -> None:
        """Refuse the arrival and report the earliest time the queue can clear."""
        reservation = self._reservation
        assert reservation is not None
        earliest = now + clear_s + self._transition_s()
        self.bus.publish(
            ReserveNack(
                junction_id=self.id, vehicle_id=reservation["vehicle_id"],
                reason=(
                    f"cross queue {queue} needs {clear_s:.1f}s; "
                    f"earliest feasible {earliest:.1f}s"
                ),
                ts=now, sender=self.id,
                recipient=reservation["sender"] or "dispatcher",
            )
        )
        self._reservation = None
        self._transition(JunctionState.REJECTED, now, f"infeasible: cross queue {queue}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _observe(self, world_view: Any, now: float) -> None:
        """Track when this junction's displayed phase last changed."""
        signals = getattr(world_view, "signals", None) or {}
        name = signals.get(self.id)
        if name is not None and name != self._phase_name:
            self._phase_name = name
            self._phase_since = now

    def _estimate_eta(self, world_view: Any, vehicle_id: str, now: float) -> Optional[float]:
        """Arrival estimate from the ambulance's live edge, offset and speed.

        Returns None when the vehicle is not visible or is no longer travelling
        towards this junction along the planned path, so the last estimate stands.
        """
        snapshot = self._snapshot(world_view, vehicle_id)
        path = self._paths.get(vehicle_id)
        if snapshot is None or not path or self.id not in path:
            return None
        u, v = snapshot.edge
        if u not in path or v not in path:
            return None
        target = path.index(self.id)
        idx = path.index(v)
        if idx < path.index(u) or idx > target:
            return None

        graph = self.network.graph
        ambulance = str(getattr(snapshot, "kind", "")) == "ambulance"
        speed = float(snapshot.speed_mps)
        seconds = self._leg_time(
            max(0.0, float(graph[u][v]["length_m"]) - float(snapshot.offset_m)),
            speed, ambulance,
        )
        for i in range(idx, target):
            a, b = path[i], path[i + 1]
            leg_speed = speed if i == idx else float(graph[a][b]["speed_limit_mps"])
            seconds += self._leg_time(float(graph[a][b]["length_m"]), leg_speed, ambulance)
        return now + seconds

    def _leg_time(self, distance: float, speed: float, accelerate: bool) -> float:
        """Seconds to cover ``distance`` starting at ``speed``.

        An ambulance is modelled with its configured acceleration up to its top
        speed, so an estimate taken while it is still pulling away does not
        announce an arrival later than the real one. Civilian traffic keeps its
        current speed, which is all this agent knows about it.
        """
        speed = max(speed, self.config.min_speed_mps)
        if not accelerate:
            return distance / speed
        accel = float(self.config.ambulance_max_accel)
        top = max(float(self.config.ambulance_max_mps), speed)
        if accel <= 0.0 or speed >= top:
            return distance / speed
        ramp = (top * top - speed * speed) / (2.0 * accel)
        if distance <= ramp:
            return (-speed + math.sqrt(speed * speed + 2.0 * accel * distance)) / accel
        return (top - speed) / accel + (distance - ramp) / top

    def _observe_pass(self, world_view: Any, now: float) -> None:
        """Publish the pass notice this junction is the authority for.

        Nothing else announces that an ambulance cleared a stop line, so the
        junction does it itself once the reserved vehicle appears on an edge
        leaving this node, and then holds its green for the usual 3 s.
        """
        reservation = self._reservation
        if reservation is None or self._release_at is not None:
            return
        if self.state not in (JunctionState.PRE_CLEAR, JunctionState.HOLD_GREEN):
            return
        snapshot = self._snapshot(world_view, reservation["vehicle_id"])
        if snapshot is None or snapshot.edge[0] != self.id:
            return
        notice = PassedNotice(
            junction_id=self.id, vehicle_id=reservation["vehicle_id"],
            t=now, ts=now, sender=self.id, recipient="*",
        )
        self.bus.publish(notice)
        self._on_passed(notice)

    def _edge_travel(self, a: str, b: str) -> float:
        """Free-flow seconds to traverse edge ``(a, b)``."""
        data = self.network.graph[a][b]
        return self._leg_time(
            float(data["length_m"]), float(data["speed_limit_mps"]), False
        )

    def _eta_of(self, vehicle_id: str, node: str, now: float) -> float:
        """Arrival time at ``node`` from the plan, measured from ``now``."""
        return now + float(self._etas.get(vehicle_id, {}).get(node, 0.0))

    def _snapshot(self, world_view: Any, vehicle_id: str) -> Any:
        """Return the vehicle's snapshot from the world view, if present."""
        for snapshot in getattr(world_view, "vehicles", None) or []:
            if snapshot.id == vehicle_id:
                return snapshot
        return None

    def _next_node(self, exit_edge: str) -> Optional[str]:
        """Return the junction this junction's exit edge leads to."""
        prefix = self.id + "_"
        if not exit_edge.startswith(prefix):
            return None
        return exit_edge[len(prefix):] or None

    def _cross_exits_have_room(self, world_view: Any) -> bool:
        """True when every starved-axis exit can absorb a flush (no spillback).

        Occupancy is the reported density times the edge length; capacity is the
        lane count times one space per vehicle, both from config, and the exit
        needs room for at least one more vehicle.
        """
        phase = self._starved_phase
        if phase is None:
            return True
        densities = getattr(world_view, "densities", None) or {}
        graph = self.network.graph
        spacing = self.config.vehicle_length_m + self.config.avg_gap_m
        for w in graph.successors(self.id):
            if self._phase_for(f"{self.id}_{w}") == phase:
                continue
            data = graph[self.id][w]
            length_km = float(data["length_m"]) / 1000.0
            occupied = float(densities.get((self.id, w), 0.0)) * length_km
            capacity = float(data["lanes"]) * length_km * 1000.0 / spacing
            if occupied + 1.0 > capacity:
                return False
        return True

    def _realign_offset(self, now: float) -> None:
        """Re-phase this junction's cycle onto the simulation clock.

        ``SignalController`` consumes its offset only at construction and the
        actuator surface exposes no offset call, so this does nothing unless the
        actuator provides ``set_signal_offset``.
        """
        setter = getattr(self.actuators, "set_signal_offset", None)
        if setter is not None:
            setter(self.id, now % float(self.config.cycle_s))

    def _cross_queue(self, world_view: Any, phase: str) -> int:
        """Count queued vehicles on the approaches the reservation does not use."""
        queues = getattr(world_view, "queues", None) or {}
        return sum(
            int(count)
            for (u, v), count in queues.items()
            if v == self.id and self._phase_for(f"{u}_{v}") != phase
        )

    def _clear_s(self, queue: int, phase: str) -> float:
        """Time for ``queue`` stopped vehicles to discharge at saturation headway.

        Headway is the space one vehicle occupies (its length plus the configured
        bumper gap) divided by the cross street's own speed limit, so neither
        term is an invented constant.
        """
        return queue * (self.config.vehicle_length_m + self.config.avg_gap_m) / self._cross_speed_mps(phase)

    def _cross_speed_mps(self, phase: str) -> float:
        """Slowest speed limit among the cross-street approaches."""
        graph = self.network.graph
        limits = [
            float(graph[u][self.id]["speed_limit_mps"])
            for u in graph.predecessors(self.id)
            if self._phase_for(f"{u}_{self.id}") != phase
        ]
        return min(limits) if limits else self.config.residential_mps

    def _transition_s(self) -> float:
        """Time the controller needs to move a phase across to the other one."""
        return float(self.config.yellow_s + self.config.all_red_s)

    def _emergency(self, now: float, eta_t: float) -> bool:
        """True when the ambulance is close enough to ignore the cross minimum green."""
        return eta_t - now <= _EMERGENCY_OVERRIDE_S

    def _min_green_end(self, phase: str) -> float:
        """Earliest moment the currently served cross phase may be cut.

        No constraint applies when the running axis is the one the ambulance
        needs, or during an all-red interval.
        """
        axis = (self._phase_name or "").split("_")[0]
        if axis in ("NS", "EW") and axis != phase:
            return self._phase_since + self.config.min_green_for_cross_s
        return 0.0

    def _transition(self, state: JunctionState, t: float, reason: str) -> None:
        """Record a state change in ``event_log`` and apply it."""
        self.event_log.append(
            {"t": t, "old": self.state.value, "new": state.value, "reason": reason}
        )
        self.state = state

    def _phase_for(self, edge_id: str) -> Optional[str]:
        """Return the phase (``NS`` or ``EW``) that serves an approach edge."""
        parts = edge_id.split("_")
        for i in range(1, len(parts)):
            u, v = "_".join(parts[:i]), "_".join(parts[i:])
            if v != self.id or not self.network.graph.has_edge(u, v):
                continue
            nodes = self.network.graph.nodes
            return "NS" if nodes[u]["c"] == nodes[v]["c"] else "EW"
        return None
