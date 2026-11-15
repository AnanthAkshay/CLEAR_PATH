"""Print the dispatcher's ranked hospitals for three incident types."""

from __future__ import annotations

from clearpath.agents.dispatcher import DispatcherAgent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import AuthResult
from clearpath.config import load_config
from clearpath.sim.network import RoadNetwork
from clearpath.sim.simulator import WorldView

INCIDENTS = (
    ("trauma", (950.0, 50.0)),
    ("cardiac", (950.0, 950.0)),
    ("stroke", (50.0, 50.0)),
)


def main() -> None:
    """Dispatch one ambulance for each incident type and print the scores."""
    config = load_config()
    network = RoadNetwork(config)
    dispatcher = DispatcherAgent("dispatcher", MessageBus(seed=7), config, network)
    dispatcher.on_message(AuthResult(vehicle_id="AMB_1", is_authenticated=True))
    world = WorldView(tick=0, vehicles=[], queues={}, signals={}, densities={})

    for incident_type, location in INCIDENTS:
        result = dispatcher.dispatch("AMB_1", location, incident_type, world)
        print(
            f"\n{incident_type.upper()} incident at {location} "
            f"-> {result['origin']} (degraded={result['degraded']})"
        )
        for rank, entry in enumerate(result["ranked"], start=1):
            print(
                f"  {rank}. {entry['hospital_id']:<15} score={entry['score']:>6.3f} "
                f"(t={entry['travel_ratio']:.2f} w={entry['wait_ratio']:.2f}) "
                f"travel={entry['travel_time_s']:>6.1f}s "
                f"wait={entry['hospital_wait_s']:>6.0f}s beds={entry['beds']}"
            )
        print(
            f"  chosen={result['hospital_id']} "
            f"total_eta={result['total_eta_s']:.1f}s "
            f"junctions={len(result['path'])} "
            f"alternatives={len(result['alternatives'])}"
        )


if __name__ == "__main__":
    main()
