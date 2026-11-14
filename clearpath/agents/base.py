"""Base abstract agent class for the ClearPath-lite simulation architecture.

All autonomous agents (Dispatcher, Security, Junction, Guidance) inherit from
Agent, enforcing message-bus-only communication and strict world-state decoupling.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import Message


class Agent(ABC):
    """Abstract base class defining the standard agent interface.

    Agents interact with the environment exclusively by reacting to incoming
    messages on the MessageBus and executing actuation through safe interfaces
    during the orchestrator's tick cycle.

    Attributes:
        id: Unique identifier for the agent (e.g., 'dispatcher', 'j_0_1').
        bus: Reference to the shared in-process MessageBus.
        logger: Dedicated structured logger instance for this agent.
    """

    def __init__(self, agent_id: str, bus: MessageBus) -> None:
        """Initialize the agent, configure logging, and subscribe to direct messages.

        Args:
            agent_id: Unique string identifier for the agent.
            bus: The MessageBus instance used for all communication.
        """
        self.id = agent_id
        self.bus = bus
        self.logger = logging.getLogger(f"clearpath.agents.{self.__class__.__name__}.{agent_id}")
        self.bus.subscribe(self.id, self.on_message)

    @abstractmethod
    def on_message(self, msg: Message) -> None:
        """Handle incoming message delivered via the MessageBus.

        Args:
            msg: The delivered typed Message.
        """
        pass

    @abstractmethod
    def step(self, world_view: Any, t: int) -> None:
        """Execute one simulation tick of agent logic.

        Args:
            world_view: Read-only perception data or minimal actuator interface.
            t: Current simulation tick (in seconds).
        """
        pass

    def __repr__(self) -> str:
        """Return developer-friendly string representation of agent."""
        return f"<{self.__class__.__name__} id='{self.id}'>"

