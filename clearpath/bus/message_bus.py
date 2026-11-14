"""In-process asynchronous message bus for multi-agent simulation.

Enforces latency, deterministic packet dropping, topic-based broadcasting,
and structured logging of all inter-agent communications.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable, DefaultDict, Dict, List, Optional, Set, Tuple

import numpy as np

from clearpath.bus.messages import Message


class MessageBus:
    """Central deterministic message exchange coordinating agent communication.

    Attributes:
        latency_ticks: Number of ticks required for message transit (default 1).
        drop_probability: Probability in [0.0, 1.0] that a published message is dropped.
        current_tick: Current simulation tick counter.
        message_log: Historical record of all published messages (including dropped).
    """

    def __init__(
        self,
        latency_ticks: int = 1,
        drop_probability: float = 0.0,
        seed: Optional[int] = 42,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        """Initialize the MessageBus with latency, fault parameters, and RNG.

        Args:
            latency_ticks: Transmission delay in simulation seconds/ticks.
            drop_probability: Probability of packet drop for fault injection.
            seed: Seed used if a custom RNG is not supplied.
            rng: Explicit numpy Generator for deterministic random draws.
        """
        self.latency_ticks = max(0, latency_ticks)
        self.drop_probability = max(0.0, min(1.0, drop_probability))
        self.current_tick: int = 0
        self.message_log: List[Message] = []
        self.dropped_messages: List[Message] = []

        if rng is not None:
            self._rng = rng
        elif seed is not None:
            self._rng = np.random.default_rng(seed)
        else:
            self._rng = np.random.default_rng()

        self._logger = logging.getLogger("clearpath.bus.MessageBus")

        # Handlers keyed by agent_id
        self._handlers: Dict[str, Callable[[Message], None]] = {}
        # Topic subscriptions: topic -> set of agent_ids
        self._topic_subscribers: DefaultDict[str, Set[str]] = defaultdict(set)

        # Delivery queue of tuples: (delivery_tick, sequence_order, message)
        self._seq_counter: int = 0
        self._delivery_queue: List[Tuple[int, int, Message]] = []

    def subscribe(
        self,
        agent_id: str,
        handler: Callable[[Message], None],
        topics: Optional[List[str]] = None,
    ) -> None:
        """Register an agent's message handler for direct and topic-based delivery.

        Args:
            agent_id: Unique identifier of the subscribing agent.
            handler: Callable invoked with arriving Message objects.
            topics: Optional list of additional broadcast topics to subscribe to.
        """
        self._handlers[agent_id] = handler
        # Always register agent for universal broadcast channels
        self._topic_subscribers["*"].add(agent_id)
        self._topic_subscribers["BROADCAST"].add(agent_id)

        if topics:
            for topic in topics:
                self._topic_subscribers[topic].add(agent_id)

        self._logger.debug(
            "Agent '%s' subscribed with topics: %s",
            agent_id,
            topics if topics else "[]",
        )

    def unsubscribe(self, agent_id: str) -> None:
        """Unregister an agent from all direct and topic queues.

        Args:
            agent_id: Unique identifier of the agent to unregister.
        """
        self._handlers.pop(agent_id, None)
        for subscribers in self._topic_subscribers.values():
            subscribers.discard(agent_id)
        self._logger.debug("Agent '%s' unsubscribed", agent_id)

    def publish(self, msg: Message) -> bool:
        """Publish a message onto the bus.

        Checks drop probability and enqueues the message for future delivery
        based on configured latency.

        Args:
            msg: The typed Message object to transmit.

        Returns:
            True if the message was enqueued, False if dropped due to fault injection.
        """
        self.message_log.append(msg)

        # Check for packet drop
        if self.drop_probability > 0.0 and self._rng.random() < self.drop_probability:
            self.dropped_messages.append(msg)
            self._logger.warning(
                "Message dropped (fault injection): type=%s sender=%s recipient=%s id=%s",
                msg.type,
                msg.sender,
                msg.recipient,
                msg.id,
            )
            return False

        delivery_tick = self.current_tick + self.latency_ticks
        self._seq_counter += 1
        self._delivery_queue.append((delivery_tick, self._seq_counter, msg))

        self._logger.debug(
            "Enqueued message: type=%s sender=%s recipient=%s scheduled_tick=%d",
            msg.type,
            msg.sender,
            msg.recipient,
            delivery_tick,
        )
        return True

    def broadcast(self, topic: str, msg: Message) -> bool:
        """Broadcast a message to all subscribers of a specific topic or wildcard.

        Args:
            topic: Destination broadcast topic (e.g. '*' or 'alerts').
            msg: The typed Message object to broadcast.

        Returns:
            True if enqueued, False if dropped.
        """
        msg.recipient = topic
        return self.publish(msg)

    def step(self, current_tick: Optional[int] = None) -> List[Message]:
        """Advance time or flush pending queue for current tick, dispatching due messages.

        Args:
            current_tick: Optional explicit tick to set. If omitted, advances by 1.

        Returns:
            List of messages delivered during this tick.
        """
        if current_tick is not None:
            self.current_tick = current_tick
        else:
            self.current_tick += 1

        # Partition delivery queue into ready and remaining
        ready_entries: List[Tuple[int, int, Message]] = []
        remaining_entries: List[Tuple[int, int, Message]] = []

        for entry in self._delivery_queue:
            delivery_tick, _, _ = entry
            if delivery_tick <= self.current_tick:
                ready_entries.append(entry)
            else:
                remaining_entries.append(entry)

        # Sort ready entries deterministically by (delivery_tick, sequence_order)
        ready_entries.sort(key=lambda e: (e[0], e[1]))
        self._delivery_queue = remaining_entries

        delivered: List[Message] = []
        for _, _, msg in ready_entries:
            self._dispatch(msg)
            delivered.append(msg)

        return delivered

    def _dispatch(self, msg: Message) -> None:
        """Route a ready message to designated recipient or broadcast subscribers."""
        recipient = msg.recipient

        # Direct unicast delivery
        if recipient in self._handlers:
            try:
                self._handlers[recipient](msg)
            except Exception as e:
                self._logger.exception(
                    "Error delivering message %s to %s: %s", msg.id, recipient, e
                )
            return

        # Topic broadcast delivery
        if recipient in self._topic_subscribers:
            recipients = list(self._topic_subscribers[recipient])
            for agent_id in recipients:
                handler = self._handlers.get(agent_id)
                if handler:
                    try:
                        handler(msg)
                    except Exception as e:
                        self._logger.exception(
                            "Error delivering broadcast %s to %s: %s", msg.id, agent_id, e
                        )
            return

        self._logger.debug(
            "Undeliverable message (no handler/topic for '%s'): id=%s type=%s",
            recipient,
            msg.id,
            msg.type,
        )

    def reset(self) -> None:
        """Clear all active message queues and delivery state."""
        self.current_tick = 0
        self._seq_counter = 0
        self._delivery_queue.clear()
        self.message_log.clear()
        self.dropped_messages.clear()

