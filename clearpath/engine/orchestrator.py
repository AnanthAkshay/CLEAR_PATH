"""Simulation orchestrator coordinating world simulation and multi-agent tick loop."""

from __future__ import annotations

import logging
from typing import Optional

from clearpath.bus.message_bus import MessageBus
from clearpath.config import SimConfig, load_config
from clearpath.sim.simulator import Simulator


class Orchestrator:
    """Coordinates simulation ticks, message bus delivery, and agent execution."""

    def __init__(
        self, config: Optional[SimConfig] = None, bus: Optional[MessageBus] = None
    ) -> None:
        """Initialize orchestrator engine."""
        self.config = config or load_config()
        self.bus = bus or MessageBus(seed=self.config.seed)
        self.sim = Simulator(self.config)
        self.logger = logging.getLogger("clearpath.engine.Orchestrator")
        self.current_tick: int = 0

    def step(self) -> None:
        """Advance one full tick: deliver messages, step agents, step simulator."""
        self.current_tick += 1
        self.bus.step(self.current_tick)
        self.sim.step()

