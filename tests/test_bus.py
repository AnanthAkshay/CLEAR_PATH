"""Unit tests for the ClearPath-lite MessageBus.

Covers message latency delivery order, topic and wildcard broadcasts,
drop probability determinism with fixed seeds, and structured logging.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np
import pytest

from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import (
    GuidanceAdvisory,
    Message,
    PreemptionRequest,
    RoutePlan,
    Telemetry,
)


def test_latency_delivery_order() -> None:
    """Messages published at tick t must arrive at tick t + latency_ticks in order."""
    bus = MessageBus(latency_ticks=1, drop_probability=0.0, seed=42)
    received_a: List[Message] = []
    received_b: List[Message] = []

    bus.subscribe("agent_a", lambda m: received_a.append(m))
    bus.subscribe("agent_b", lambda m: received_b.append(m))

    # At tick 0, publish two messages for agent_a and one for agent_b
    msg1 = Message(sender="sim", recipient="agent_a", ts=0.0)
    msg2 = Message(sender="sim", recipient="agent_b", ts=0.0)
    msg3 = Message(sender="sim", recipient="agent_a", ts=0.0)

    bus.publish(msg1)
    bus.publish(msg2)
    bus.publish(msg3)

    # Prior to step, nothing should be delivered
    assert len(received_a) == 0
    assert len(received_b) == 0

    # Advance to tick 1: all messages scheduled for tick 1 should be delivered in order
    delivered = bus.step(current_tick=1)
    assert len(delivered) == 3
    assert len(received_a) == 2
    assert received_a[0].id == msg1.id
    assert received_a[1].id == msg3.id
    assert len(received_b) == 1
    assert received_b[0].id == msg2.id

    # Test configurable higher latency (latency_ticks = 3)
    bus_high_latency = MessageBus(latency_ticks=3, drop_probability=0.0, seed=42)
    received_high: List[Message] = []
    bus_high_latency.subscribe("agent_x", lambda m: received_high.append(m))

    msg_delayed = Message(sender="sim", recipient="agent_x", ts=0.0)
    bus_high_latency.publish(msg_delayed)

    # Tick 1: not delivered
    bus_high_latency.step(current_tick=1)
    assert len(received_high) == 0

    # Tick 2: not delivered
    bus_high_latency.step(current_tick=2)
    assert len(received_high) == 0

    # Tick 3: delivered
    bus_high_latency.step(current_tick=3)
    assert len(received_high) == 1
    assert received_high[0].id == msg_delayed.id


def test_broadcast_delivery() -> None:
    """Verify universal wildcard broadcasting and selective topic subscriptions."""
    bus = MessageBus(latency_ticks=1, drop_probability=0.0, seed=42)
    received_a: List[Message] = []
    received_b: List[Message] = []
    received_c: List[Message] = []

    bus.subscribe("agent_a", lambda m: received_a.append(m), topics=["corridor_north"])
    bus.subscribe("agent_b", lambda m: received_b.append(m), topics=["corridor_north", "alerts"])
    bus.subscribe("agent_c", lambda m: received_c.append(m), topics=["corridor_south"])

    # 1. Direct message to agent_a
    direct_msg = Message(sender="dispatcher", recipient="agent_a")
    bus.publish(direct_msg)

    # 2. Universal broadcast
    broadcast_msg = Message(sender="security", recipient="*")
    bus.broadcast("*", broadcast_msg)

    # 3. Topic broadcast to 'corridor_north'
    topic_msg = Message(sender="junction_1", recipient="corridor_north")
    bus.broadcast("corridor_north", topic_msg)

    bus.step(1)

    # Agent A receives: direct, universal broadcast, corridor_north
    assert len(received_a) == 3
    assert {m.id for m in received_a} == {direct_msg.id, broadcast_msg.id, topic_msg.id}

    # Agent B receives: universal broadcast, corridor_north
    assert len(received_b) == 2
    assert {m.id for m in received_b} == {broadcast_msg.id, topic_msg.id}

    # Agent C receives: universal broadcast only
    assert len(received_c) == 1
    assert received_c[0].id == broadcast_msg.id


def test_drop_probability_determinism() -> None:
    """Identical seeds must yield identical packet drop and delivery sequences."""
    seed = 999
    drop_rate = 0.35
    num_messages = 50

    def run_simulation(s: int) -> tuple[List[str], List[str]]:
        rng = np.random.default_rng(s)
        bus = MessageBus(latency_ticks=1, drop_probability=drop_rate, rng=rng)
        delivered_ids: List[str] = []
        bus.subscribe("test_agent", lambda m: delivered_ids.append(m.id))

        for i in range(num_messages):
            bus.publish(
                Message(
                    id=f"msg_{i}",
                    sender="sender",
                    recipient="test_agent",
                    ts=float(i),
                )
            )

        bus.step(1)
        dropped_ids = [m.id for m in bus.dropped_messages]
        return delivered_ids, dropped_ids

    run1_delivered, run1_dropped = run_simulation(seed)
    run2_delivered, run2_dropped = run_simulation(seed)

    # Strict equality between independent runs with identical seed
    assert run1_delivered == run2_delivered
    assert run1_dropped == run2_dropped

    # Verify that drops actually occurred given non-zero drop probability
    assert len(run1_dropped) > 0
    assert len(run1_delivered) > 0
    assert len(run1_delivered) + len(run1_dropped) == num_messages

    # Verify deterministic 100% drop and 0% drop
    bus_zero = MessageBus(latency_ticks=1, drop_probability=0.0, seed=1)
    bus_zero.subscribe("agent", lambda m: None)
    bus_zero.publish(Message(recipient="agent"))
    assert len(bus_zero.dropped_messages) == 0

    bus_full = MessageBus(latency_ticks=1, drop_probability=1.0, seed=1)
    bus_full.subscribe("agent", lambda m: None)
    bus_full.publish(Message(recipient="agent"))
    assert len(bus_full.dropped_messages) == 1


def test_logging_and_message_log(caplog: pytest.LogCaptureFixture) -> None:
    """Verify that message history is logged in message_log and standard logging captures events."""
    bus = MessageBus(latency_ticks=1, drop_probability=0.5, seed=42)

    received: List[Message] = []
    bus.subscribe("agent_log", lambda m: received.append(m))

    telemetry = Telemetry(
        x=100.0,
        y=200.0,
        speed_mps=15.0,
        accel_mps2=1.2,
        heading_deg=90.0,
        edge_id="e_0_1",
        lane=1,
        vehicle_id="AMB_01",
    )
    req = PreemptionRequest(
        sender="AMB_01",
        recipient="agent_log",
        vehicle_id="AMB_01",
        token="valid-token",
        telemetry=telemetry,
        severity="CRITICAL",
    )

    with caplog.at_level(logging.DEBUG):
        bus.publish(req)

    # Full message log must contain the message regardless of delivery/drop
    assert len(bus.message_log) == 1
    assert bus.message_log[0].id == req.id
    assert bus.message_log[0].type == "PreemptionRequest"

    # Verify logger caught structured events
    log_records = [rec for rec in caplog.records if "clearpath.bus.MessageBus" in rec.name]
    assert len(log_records) > 0
    assert any("PreemptionRequest" in rec.message for rec in log_records)


def test_typed_messages_instantiation() -> None:
    """Verify default initialization and polymorphism across all defined message types."""
    req = PreemptionRequest()
    assert req.type == "PreemptionRequest"
    assert req.id is not None

    plan = RoutePlan(vehicle_id="AMB_1", hospital_id="H1", path_nodes=["j0", "j1"])
    assert plan.type == "RoutePlan"
    assert plan.path_nodes == ["j0", "j1"]

    adv = GuidanceAdvisory(target_vehicle_ids=["CIV_1", "CIV_2"], text="Move right", lane=1)
    assert adv.type == "GuidanceAdvisory"
    assert adv.text == "Move right"
