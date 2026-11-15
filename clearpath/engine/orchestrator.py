"""Simulation orchestrator coordinating world simulation and multi-agent tick loop."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from clearpath.agents.dispatcher import DispatcherAgent
from clearpath.agents.junction import JunctionAgent
from clearpath.agents.security import SecurityAgent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import PreemptionRequest
from clearpath.config import SimConfig, load_config
from clearpath.sim.simulator import Simulator


class Orchestrator:
    """Coordinates simulation ticks, message bus delivery, and agent execution.

    Wires the preemption path end to end: a ``PreemptionRequest`` is verified by
    :class:`SecurityAgent`, the verdict is handed to :class:`DispatcherAgent`,
    and the accepted request produces a ``RoutePlan`` plus one ``EtaNotice`` per
    junction, computed against the simulator's live ``WorldView``.
    """

    def __init__(
        self, config: Optional[SimConfig] = None, bus: Optional[MessageBus] = None
    ) -> None:
        """Initialize orchestrator engine and the security/dispatch agents."""
        self.config = config or load_config()
        self.bus = bus or MessageBus(seed=self.config.seed)
        self.sim = Simulator(self.config)
        self.logger = logging.getLogger("clearpath.engine.Orchestrator")
        self.current_tick: int = 0

        # Tokens carry simulation seconds, so the security clock follows the tick
        # counter rather than wall time.
        self.security = SecurityAgent(
            "security", self.bus, self.config, self.sim.network.graph,
            clock=lambda: float(self.sim.current_tick),
        )
        self.dispatcher = DispatcherAgent(
            "dispatcher", self.bus, self.config, self.sim.network,
            clock=lambda: float(self.sim.current_tick),
        )
        # One junction agent per intersection; the simulator is handed over only
        # for its actuator methods (set/clear signal override).
        self.junctions: Dict[str, JunctionAgent] = {
            node: JunctionAgent(
                node, self.bus, self.config, self.sim.network, self.sim
            )
            for node in self.sim.network.graph.nodes
        }

    def step(self) -> None:
        """Advance one full tick: deliver messages, step agents, step simulator."""
        self.current_tick += 1
        self.bus.step(self.current_tick)
        world_view = self.sim.get_world_view()
        self.dispatcher.step(world_view, self.current_tick)
        for junction in self.junctions.values():
            junction.step(world_view, self.current_tick)
        self.sim.step()

    def handle_preemption_request(
        self, request: PreemptionRequest, incident_type: str = "general"
    ) -> Dict[str, Any]:
        """Authenticate a request, then dispatch it against the live world view.

        Args:
            request: Preemption request carrying a signed token and telemetry.
            incident_type: One of ``trauma``, ``cardiac``, ``stroke``, ``general``.

        Returns:
            ``{"authenticated", "auth", "dispatch"}`` where ``dispatch`` is the
            dispatcher result dict, or None when verification failed.
        """
        request.ts = float(self.sim.current_tick)
        auth = self.security.authenticate(request)
        self.bus.publish(auth)
        # Same-tick handoff so the corridor is planned in this tick; the bus copy
        # reaches every other subscriber on the next delivery.
        self.dispatcher.on_message(auth)

        if not auth.is_authenticated:
            self.logger.info(
                "Rejected preemption for %s: %s", request.vehicle_id, auth.security_log
            )
            return {"authenticated": False, "auth": auth, "dispatch": None}

        dispatch = self.dispatcher.dispatch(
            request.vehicle_id, request.incident_loc, incident_type,
            self.sim.get_world_view(),
        )
        self.logger.info(
            "Dispatched %s: %s", request.vehicle_id, auth.security_log
        )
        return {"authenticated": True, "auth": auth, "dispatch": dispatch}
