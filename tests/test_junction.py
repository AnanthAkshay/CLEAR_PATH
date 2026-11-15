"""Unit tests for JunctionAgent preemption (step 5a)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from typing import Any, Dict, List, Optional, Tuple

from clearpath.agents.junction import JunctionAgent, JunctionState
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    EtaNotice, GreenWavePrepare, PassedNotice, RecoveryDone, RecoveryStarted,
    ReserveAck, ReserveCorridor, ReserveNack, RevokePreemption, RoutePlan,
)
from clearpath.config import SimConfig, load_config
from clearpath.sim.network import RoadNetwork
from clearpath.sim.signals import SignalController
from clearpath.sim.simulator import Simulator

NODE = "j_1_1"
NS_APPROACH = ("j_0_1", "j_1_1")
EW_APPROACH = ("j_1_0", "j_1_1")


class _Actuator:
    """Actuator double recording calls and driving a real SignalController."""

    def __init__(self, config: SimConfig, node: str = NODE) -> None:
        self.controller = SignalController(node, config)
        self.calls: List[Tuple[float, str, str]] = []
        self.offsets: List[float] = []
        self.now = 0.0

    def set_signal_override(self, junction_id: str, phase: Any, reason: str = "") -> None:
        self.calls.append((self.now, "set", str(getattr(phase, "value", phase))))
        self.controller.set_phase_override(phase, reason=reason, t=self.now)

    def clear_signal_override(self, junction_id: str) -> None:
        self.calls.append((self.now, "clear", ""))
        self.controller.clear_override()

    def advance(self, now: float) -> None:
        self.now = now
        self.controller.step(1.0)

    def set_signal_offset(self, junction_id: str, offset_s: float) -> None:
        self.offsets.append(offset_s)
        self.controller.offset_s = offset_s

    def state(self, approach: Tuple[str, str]) -> str:
        return self.controller.state_for_approach(approach)

    def is_green(self, approach: Tuple[str, str]) -> bool:
        return self.controller.state_for_approach(approach) == "G"


def _agent(
    config: SimConfig, actuator: _Actuator, node: str = NODE, bus: Optional[MessageBus] = None
) -> JunctionAgent:
    """Build a junction agent, sharing ``bus`` and ``network`` when supplied."""
    return JunctionAgent(
        node, bus or MessageBus(seed=config.seed), config,
        getattr(actuator, "network", None) or RoadNetwork(config), actuator,
    )


def _eta(
    approach_edge: str,
    eta_t: float,
    node: str = NODE,
    exit_edge: str = "j_1_1_j_1_2",
    vehicle_id: str = "AMB_1",
) -> EtaNotice:
    return EtaNotice(
        junction_id=node, vehicle_id=vehicle_id, eta_t=eta_t,
        approach_edge=approach_edge, exit_edge=exit_edge,
        ts=0.0, sender="dispatcher", recipient=node,
    )


def _beat(agent: JunctionAgent, t: float) -> None:
    """Deliver an unrelated message so the bus is not silent this tick."""
    agent.on_message(
        GreenWavePrepare(
            from_junction_id="j_0_0", to_junction_id=agent.id, vehicle_id="OTHER",
            expected_arrival_t=0.0, ts=float(t), sender="j_0_0", recipient=agent.id,
        )
    )


def _passed(t: float) -> PassedNotice:
    return PassedNotice(
        junction_id=NODE, vehicle_id="AMB_1", t=t, ts=t, sender=NODE, recipient="*"
    )


@dataclass
class _Snap:
    """Vehicle snapshot stand-in."""

    id: str
    edge: Tuple[str, str]
    offset_m: float
    speed_mps: float


@dataclass
class _View:
    """Perception stand-in exposing only the fields the junction reads."""

    queues: Dict[Tuple[str, str], int] = field(default_factory=dict)
    signals: Dict[str, str] = field(default_factory=dict)
    vehicles: List[_Snap] = field(default_factory=list)
    densities: Dict[Tuple[str, str], float] = field(default_factory=dict)


def _view(
    queue: int = 0,
    signal: str = "NS_GREEN",
    vehicles: Optional[List[_Snap]] = None,
    densities: Optional[Dict[Tuple[str, str], float]] = None,
) -> _View:
    """Build a view whose cross approach (``NS``) holds ``queue`` stopped cars."""
    return _View(
        queues={("j_0_1", NODE): queue} if queue else {},
        signals={NODE: signal},
        vehicles=vehicles or [],
        densities=densities or {},
    )


def _chain(
    nodes: List[str], config: SimConfig, bus: MessageBus, network: RoadNetwork
) -> Dict[str, JunctionAgent]:
    """Build one junction agent per node, all sharing a bus and road graph."""
    agents: Dict[str, JunctionAgent] = {}
    for node in nodes:
        actuator = _Actuator(config, node)
        actuator.network = network
        agents[node] = JunctionAgent(node, bus, config, network, actuator)
    return agents


def _messages(agent: JunctionAgent, kind: Any) -> List[Any]:
    """Return the messages of ``kind`` the agent's bus has seen."""
    return [m for m in agent.bus.message_log if isinstance(m, kind)]


def _plan(path: List[str]) -> RoutePlan:
    return RoutePlan(
        vehicle_id="AMB_1", hospital_id="HOSP_RIVERSIDE", path_nodes=list(path),
        eta_by_junction={node: 10.0 * i for i, node in enumerate(path)},
        total_eta_s=10.0 * (len(path) - 1), ts=0.0,
        sender="dispatcher", recipient="*",
    )


def test_approach_turns_green_at_the_announced_eta() -> None:
    """The green is requested 5 s out and is up by the announced arrival."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 20.0))

    green_at: Optional[int] = None
    for t in range(1, 26):
        _beat(agent, t)
        agent.step(None, t)
        actuator.advance(float(t))
        if t < 15:
            assert actuator.calls == [], "override requested before the 5 s lead window"
        if t == 14:
            assert actuator.is_green(EW_APPROACH) is False
        if green_at is None and actuator.is_green(EW_APPROACH):
            green_at = t

    assert green_at is not None and green_at <= 20
    assert actuator.calls[0][1:] == ("set", "EW")
    assert agent.state is JunctionState.HOLD_GREEN


def test_no_conflicting_greens_at_any_tick() -> None:
    """Yellow and all-red keep the cross street red through the whole preemption."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 20.0))

    conflicts = 0
    for t in range(1, 31):
        agent.step(None, t)
        actuator.advance(float(t))
        if actuator.is_green(NS_APPROACH) and actuator.is_green(EW_APPROACH):
            conflicts += 1
        if t == 22:
            agent.on_message(_passed(22.0))

    for t in range(31, 90):
        agent.step(_view(), t)
        actuator.advance(float(t))
        if actuator.is_green(NS_APPROACH) and actuator.is_green(EW_APPROACH):
            conflicts += 1

    assert conflicts == 0
    assert [call[1] for call in actuator.calls] == ["set", "set", "clear"]
    assert agent.state is JunctionState.NORMAL
    assert agent.event_log[-1]["reason"] == "recovery complete"
    assert [m for m in _messages(agent, RecoveryDone)]


def test_hold_never_exceeds_the_cap() -> None:
    """Without a PassedNotice the green is dropped at max_preemption_hold_s."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 10.0))

    set_t: Optional[int] = None
    recovery_t: Optional[int] = None
    t = 0
    while t < 120:
        t += 1
        _beat(agent, t)
        agent.step(None, t)
        actuator.advance(float(t))
        sets = [call for call in actuator.calls if call[1] == "set"]
        if set_t is None and sets:
            set_t = t
        if recovery_t is None and len(sets) >= 2:
            recovery_t = t
            break

    assert set_t == 5
    assert recovery_t is not None
    assert recovery_t - set_t == config.max_preemption_hold_s
    assert agent.state is JunctionState.RECOVERY
    assert agent.event_log[-1]["reason"] == "hold cap reached"

    # No second preemption is requested; the extra set is the compensating green.
    for _ in range(10):
        t += 1
        agent.step(None, t)
        actuator.advance(float(t))
    assert [call[1] for call in actuator.calls] == ["set", "set"]
    assert actuator.calls[1][2] == "NS"


def test_short_cross_queue_goes_straight_to_hold() -> None:
    """A queue within the flush threshold skips the pre-clear entirely."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 20.0))

    view = _view(queue=config.queue_flush_threshold)
    for t in range(1, 26):
        _beat(agent, t)
        agent.step(view, t)
        actuator.advance(float(t))

    assert [entry["new"] for entry in agent.event_log] == ["HOLD_GREEN"]
    assert agent.event_log[0]["t"] == 15.0
    assert agent.state is JunctionState.HOLD_GREEN


def test_long_cross_queue_pre_clears_before_the_normal_lead() -> None:
    """An over-threshold queue starts the transition at eta - window_s."""
    config = load_config()
    actuator = _Actuator(config)
    bus = MessageBus(seed=config.seed)
    agent = JunctionAgent(NODE, bus, config, RoadNetwork(config), actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 100.0))

    for t in range(1, 111):
        _beat(agent, t)
        agent.step(_view(queue=15), t)

    assert [entry["new"] for entry in agent.event_log] == ["PRE_CLEAR", "HOLD_GREEN"]
    assert agent.event_log[0]["t"] == 100.0 - config.window_s
    # The transition costs exactly the controller's yellow plus all-red.
    assert agent.event_log[1]["t"] == 100.0 - config.window_s + config.yellow_s + config.all_red_s
    assert agent.event_log[0]["t"] < 100.0 - 5.0
    assert [call[1] for call in actuator.calls] == ["set"]
    assert not [m for m in bus.message_log if isinstance(m, ReserveNack)]
    assert agent.state is JunctionState.HOLD_GREEN


def test_undrainable_cross_queue_is_nacked_with_earliest_time() -> None:
    """A queue that cannot clear inside the window is refused, not served late."""
    config = load_config()
    actuator = _Actuator(config)
    bus = MessageBus(seed=config.seed)
    agent = JunctionAgent(NODE, bus, config, RoadNetwork(config), actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 100.0))

    for t in range(1, 111):
        agent.step(_view(queue=40), t)

    nacks = [m for m in bus.message_log if isinstance(m, ReserveNack)]
    assert len(nacks) == 1
    assert nacks[0].vehicle_id == "AMB_1"
    assert nacks[0].recipient == "dispatcher"
    assert "earliest feasible" in nacks[0].reason
    assert agent.state is JunctionState.REJECTED
    assert actuator.calls == []


def test_min_green_delays_the_switch_until_the_cross_phase_is_served() -> None:
    """A freshly started cross green is not cut short by a distant ambulance."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 100.0))

    for t in range(1, 81):
        signal = "EW_GREEN" if t < 70 else "NS_GREEN"
        agent.step(_view(queue=15, signal=signal), t)

    assert agent.event_log[0]["new"] == "PRE_CLEAR"
    assert agent.event_log[0]["t"] == 70.0 + config.min_green_for_cross_s


def test_min_green_yields_to_an_ambulance_within_10_seconds() -> None:
    """A late notice switches immediately even though the cross green is young."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)

    for t in range(1, 50):
        agent.step(_view(signal="EW_GREEN"), t)
    agent.on_message(_eta("j_1_0_j_1_1", 60.0))

    requested: Optional[int] = None
    for t in range(50, 61):
        agent.step(_view(signal="NS_GREEN"), t)
        if requested is None and actuator.calls:
            requested = t

    # min_green would have held until 58, but the ambulance is 5 s away at 55.
    assert requested == 55
    assert requested < 50 + config.min_green_for_cross_s
    assert agent.event_log[0]["new"] == "HOLD_GREEN"


def test_four_junction_corridor_all_ack() -> None:
    """The first junction seeds the chain and every junction ackknowledges."""
    config = load_config()
    network = RoadNetwork(config)
    bus = MessageBus(seed=config.seed)
    path = ["j_0_0", "j_0_1", "j_0_2", "j_0_3", "j_0_4"]
    junctions = _chain(path[1:], config, bus, network)

    bus.publish(_plan(path))
    for tick in range(1, 7):
        bus.step(tick)

    acks = {m.junction_id for m in bus.message_log if isinstance(m, ReserveAck)}
    assert acks == set(path[1:])
    assert not [m for m in bus.message_log if isinstance(m, ReserveNack)]
    assert all(junction._tentative.get("AMB_1") for junction in junctions.values())

    # Each hop forwards only the chain that is still ahead of it.
    sent = [
        (m.sender, m.corridor_nodes)
        for m in bus.message_log if isinstance(m, ReserveCorridor)
    ]
    assert sent == [
        ("j_0_1", ["j_0_2", "j_0_3", "j_0_4"]),
        ("j_0_2", ["j_0_3", "j_0_4"]),
        ("j_0_3", ["j_0_4"]),
    ]


def test_nack_from_third_junction_releases_upstream_tentative_holds() -> None:
    """A refusal propagates back and every junction on the way drops its hold."""
    config = load_config()
    network = RoadNetwork(config)
    bus = MessageBus(seed=config.seed)
    path = ["j_0_0", "j_0_1", "j_0_2", "j_0_3", "j_0_4"]
    junctions = _chain(path[1:], config, bus, network)

    bus.publish(_plan(path))
    for tick in range(1, 7):
        bus.step(tick)
    assert junctions["j_0_1"]._tentative.get("AMB_1")

    # Junction 3 refuses the arrival it was asked to reserve.
    bus.publish(
        ReserveNack(
            junction_id="j_0_3", vehicle_id="AMB_1",
            reason="cross queue 40 needs 45.0s", ts=6.0,
            sender="j_0_3", recipient="j_0_2",
        )
    )
    for tick in range(7, 10):
        bus.step(tick)

    assert "AMB_1" not in junctions["j_0_2"]._tentative
    assert "AMB_1" not in junctions["j_0_1"]._tentative
    propagated = [
        m for m in bus.message_log
        if isinstance(m, ReserveNack) and m.recipient == "dispatcher"
    ]
    assert propagated and "downstream refused" in propagated[0].reason


def test_missing_ack_times_out_as_a_nack() -> None:
    """A junction that hears no Ack acts on the timeout as a refusal."""
    config = load_config()
    network = RoadNetwork(config)
    bus = MessageBus(seed=config.seed)
    junction = _chain(["j_0_1"], config, bus, network)["j_0_1"]

    bus.publish(_plan(["j_0_0", "j_0_1", "j_0_2", "j_0_3"]))
    bus.step(1)

    assert junction._pending_downstream is not None
    assert junction._pending_downstream[0] == "AMB_1"

    for t in range(1, config.negotiation_timeout_ticks + 2):
        junction.step(_view(), t)

    nacks = [m for m in bus.message_log if isinstance(m, ReserveNack)]
    assert len(nacks) == 1
    assert nacks[0].recipient == "dispatcher"
    assert nacks[0].reason == "negotiation timeout"
    assert "AMB_1" not in junction._tentative
    assert junction._pending_downstream is None


def test_eta_follows_a_lagging_ambulance() -> None:
    """Each tick re-estimates the arrival from the vehicle's own position and speed."""
    config = load_config()
    network = RoadNetwork(config)
    bus = MessageBus(seed=config.seed)
    junction = _chain(["j_0_1"], config, bus, network)["j_0_1"]

    bus.publish(_plan(["j_0_0", "j_0_1", "j_0_2"]))
    bus.step(1)
    junction.on_message(
        _eta("j_0_0_j_0_1", 30.0, node="j_0_1", exit_edge="j_0_1_j_0_2")
    )

    junction.step(_view(vehicles=[_Snap("AMB_1", ("j_0_0", "j_0_1"), 100.0, 10.0)]), 10)
    assert junction._reservation is not None
    assert junction._reservation["eta_t"] == 20.0

    junction.step(_view(vehicles=[_Snap("AMB_1", ("j_0_0", "j_0_1"), 150.0, 10.0)]), 12)
    assert junction._reservation["eta_t"] == 17.0

    prepares = [m for m in bus.message_log if isinstance(m, GreenWavePrepare)]
    assert len(prepares) == 2
    assert [p.to_junction_id for p in prepares] == ["j_0_2", "j_0_2"]
    assert prepares[1].expected_arrival_t < prepares[0].expected_arrival_t
    assert prepares[0].expected_arrival_t == pytest.approx(20.0 + 200.0 / 16.7)


def test_recovery_returns_to_normal_cycle_with_bounded_cross_delay() -> None:
    """Recovery serves the starved cross street, then rejoins the normal cycle."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 20.0))

    for t in range(1, 24):
        _beat(agent, t)
        agent.step(_view(), t)
        actuator.advance(float(t))
    agent.on_message(_passed(23.0))

    t = 23
    while agent.state is not JunctionState.RECOVERY and t < 40:
        t += 1
        agent.step(_view(), t)
        actuator.advance(float(t))

    assert agent.state is JunctionState.RECOVERY
    assert t == 26
    started = _messages(agent, RecoveryStarted)
    assert len(started) == 1
    duration = started[0].recovery_duration_s
    # Held green ran from 15 to 26, so the cross street gets 20 s plus 11 s of delay.
    assert duration == config.recovery_s + (26.0 - 15.0)
    assert config.recovery_s <= duration <= 2 * config.recovery_s

    for _ in range(6):
        t += 1
        agent.step(_view(), t)
        actuator.advance(float(t))
    assert actuator.is_green(NS_APPROACH) is True

    while agent.state is JunctionState.RECOVERY and t < 200:
        t += 1
        agent.step(_view(), t)
        actuator.advance(float(t))

    assert agent.state is JunctionState.NORMAL
    assert _messages(agent, RecoveryDone)
    assert actuator.offsets == [pytest.approx(26.0 + duration)]


def test_revocation_mid_hold_yields_yellow_then_all_red() -> None:
    """A revoked hold leaves through yellow and all-red, never green to green."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 20.0))

    t = 0
    while not actuator.is_green(EW_APPROACH) and t < 30:
        t += 1
        _beat(agent, t)
        agent.step(_view(), t)
        actuator.advance(float(t))
    assert agent.state is JunctionState.HOLD_GREEN

    agent.on_message(
        RevokePreemption(vehicle_id="AMB_1", reason="token revoked", ts=float(t))
    )
    assert agent.state is JunctionState.RECOVERY
    assert agent._reservation is None
    assert _messages(agent, RecoveryStarted)[-1].junction_id == NODE

    saw_yellow = False
    saw_all_red = False
    for _ in range(8):
        t += 1
        agent.step(_view(), t)
        actuator.advance(float(t))
        ns, ew = actuator.state(NS_APPROACH), actuator.state(EW_APPROACH)
        assert not (ns == "G" and ew == "G")
        saw_yellow = saw_yellow or "Y" in (ns, ew)
        saw_all_red = saw_all_red or (ns == "R" and ew == "R")

    assert saw_yellow is True
    assert saw_all_red is True
    assert actuator.is_green(NS_APPROACH) is True


def test_overlapping_reservations_rank_by_severity_then_eta() -> None:
    """The stronger claim keeps the junction; the loser is nacked, never both served."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)

    ns_notice = _eta("j_0_1_j_1_1", 35.0, vehicle_id="AMB_1")
    agent.on_message(ns_notice)
    assert agent._reservation is not None
    assert agent._reservation["vehicle_id"] == "AMB_1"

    # Same severity, earlier ETA: the newcomer wins on the tie-break.
    agent.on_message(_eta("j_1_0_j_1_1", 30.0, vehicle_id="AMB_5"))
    assert agent._reservation["vehicle_id"] == "AMB_5"

    # Higher severity beats the earlier ETA.
    critical = _eta("j_1_0_j_1_1", 40.0, vehicle_id="AMB_2")
    critical.severity = "CRITICAL"
    agent.on_message(critical)
    assert agent._reservation["vehicle_id"] == "AMB_2"

    nacks = [m for m in agent.bus.message_log if isinstance(m, ReserveNack)]
    assert [(m.vehicle_id, m.reason.split()[2]) for m in nacks] == [
        ("AMB_1", "AMB_5"), ("AMB_5", "AMB_2"),
    ]

    conflicts = 0
    t = 0
    while t < 50:
        t += 1
        _beat(agent, t)
        agent.step(_view(), t)
        actuator.advance(float(t))
        if actuator.is_green(NS_APPROACH) and actuator.is_green(EW_APPROACH):
            conflicts += 1

    assert conflicts == 0
    assert actuator.is_green(EW_APPROACH) is True
    assert agent.state is JunctionState.HOLD_GREEN


# ---------------------------------------------------------------------------
# Headless corridor harness (step 5f)
# ---------------------------------------------------------------------------

CORRIDOR = [f"j_0_{c}" for c in range(5)]


class _QueuedActuator:
    """Collects actuator calls so the harness can apply them after the agent phase."""

    def __init__(self, sim: Simulator) -> None:
        self.sim = sim
        self.pending: List[Tuple[Any, ...]] = []

    def set_signal_override(self, junction_id: str, phase: Any, reason: str = "") -> None:
        self.pending.append(("set", junction_id, phase, reason))

    def clear_signal_override(self, junction_id: str) -> None:
        self.pending.append(("clear", junction_id))

    def apply(self) -> None:
        for call in self.pending:
            if call[0] == "set":
                self.sim.set_signal_override(call[1], call[2], reason=call[3])
            else:
                self.sim.clear_signal_override(call[1])
        self.pending.clear()


def _conflict(sim: Simulator, node: str) -> bool:
    """True when both approaches into ``node`` show green at the same time."""
    r, c = (int(part) for part in node.split("_")[1:])
    controller = sim.signals[node]
    ns = controller.state_for_approach((f"j_{r + 1}_{c}", node))
    ew = controller.state_for_approach((f"j_{r}_{c - 1}", node)) if c > 0 else "R"
    return ns == "G" and ew == "G"


def _dispatch(sim: Simulator, bus: MessageBus, ambulance: str) -> None:
    """Publish what the dispatcher publishes: the plan and one notice per junction."""
    eta = {node: float(i) * 200.0 / sim.config.arterial_mps for i, node in enumerate(CORRIDOR)}
    bus.publish(
        RoutePlan(
            vehicle_id=ambulance, hospital_id="HOSP_RIVERSIDE", path_nodes=list(CORRIDOR),
            eta_by_junction=eta, total_eta_s=eta[CORRIDOR[-1]], ts=0.0,
            sender="dispatcher", recipient="*",
        )
    )
    for i, node in enumerate(CORRIDOR[1:], start=1):
        bus.publish(
            EtaNotice(
                junction_id=node, vehicle_id=ambulance, eta_t=eta[node],
                approach_edge=f"{CORRIDOR[i - 1]}_{node}",
                exit_edge=f"{node}_{CORRIDOR[i + 1]}" if i + 1 < len(CORRIDOR) else "",
                ts=0.0, sender="dispatcher", recipient=node,
            )
        )


def _run_corridor(seed: int) -> Dict[str, Any]:
    """Drive one ambulance down the corridor; return a comparable trace."""
    config = load_config(seed=seed)
    sim = Simulator(config, demand_level="low")
    # An empty road, so the only thing that can stop the ambulance is a signal.
    sim.traffic_gen._rate_per_boundary = 0.0

    bus = MessageBus(seed=seed)
    actuator = _QueuedActuator(sim)
    junctions = {
        node: JunctionAgent(node, bus, config, sim.network, actuator) for node in CORRIDOR
    }
    ambulance = sim.spawn_ambulance(CORRIDOR[0], CORRIDOR[-1], route=list(CORRIDOR))
    _dispatch(sim, bus, ambulance)

    stops = 0
    conflicts = 0
    completed = False
    trace: List[Tuple[int, str, float]] = []
    for tick in range(1, 160):
        view = sim.get_world_view()
        bus.step(tick)                       # 1. bus delivery
        for junction in junctions.values():  # 2. agents step
            junction.step(view, tick)
        actuator.apply()                     # 3. actuations
        sim.step()

        conflicts += sum(1 for node in CORRIDOR[1:] if _conflict(sim, node))
        snapshot = next(
            (v for v in sim.get_world_view().vehicles if v.id == ambulance), None
        )
        if snapshot is None:
            completed = True
            break
        trace.append((tick, f"{snapshot.edge[0]}->{snapshot.edge[1]}", round(snapshot.speed_mps, 3)))
        if snapshot.is_stopped:
            stops += 1

    return {
        "stops": stops,
        "conflicts": conflicts,
        "completed": completed,
        "trace": trace,
        "events": {node: junction.event_log for node, junction in junctions.items()},
    }


def test_corridor_run_has_no_stops_and_no_conflicts() -> None:
    """A 5-junction preempted corridor carries the ambulance without stopping."""
    run = _run_corridor(7)

    assert run["stops"] == 0
    assert run["conflicts"] == 0
    assert run["completed"] is True, "the ambulance never finished the corridor"
    # It arrives on the final edge and is then removed at the destination.
    assert run["trace"][-1][1] == f"{CORRIDOR[-2]}->{CORRIDOR[-1]}"
    assert run["trace"][-1][0] > 20
    for entry in run["events"][CORRIDOR[1]]:
        assert "fail-safe" not in entry["reason"]


def test_corridor_run_is_deterministic_for_a_seed() -> None:
    """The same seed reproduces the run tick for tick."""
    first = _run_corridor(7)
    second = _run_corridor(7)

    assert first["stops"] == second["stops"]
    assert first["conflicts"] == second["conflicts"]
    assert first["trace"] == second["trace"]
    assert first["events"] == second["events"]


def test_fail_safe_releases_a_hold_when_the_bus_goes_silent() -> None:
    """A silent bus cannot keep a green reserved indefinitely."""
    config = load_config()
    actuator = _Actuator(config)
    agent = _agent(config, actuator)
    agent.on_message(_eta("j_1_0_j_1_1", 10.0))

    for t in range(1, 6):
        agent.step(_view(), t)
        actuator.advance(float(t))
    assert agent.state is JunctionState.HOLD_GREEN

    timeout = config.bus_silence_timeout_ticks
    for t in range(6, timeout + 2):
        agent.step(_view(), t)
        actuator.advance(float(t))

    assert agent.state is JunctionState.RECOVERY
    assert any("fail-safe" in entry["reason"] for entry in agent.event_log)
    assert agent._reservation is None

    t = timeout + 1
    while agent.state is JunctionState.RECOVERY and t < 200:
        t += 1
        agent.step(_view(), t)
        actuator.advance(float(t))

    assert agent.state is JunctionState.NORMAL
    assert _messages(agent, RecoveryDone)
