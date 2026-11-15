"""Tests for the ClearPath-lite DispatcherAgent."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from clearpath.agents.dispatcher import DispatcherAgent
from clearpath.bus.message_bus import MessageBus
from clearpath.bus.messages import AuthResult, EtaNotice, RevokePreemption, RoutePlan
from clearpath.config import load_config
from clearpath.sim.network import RoadNetwork
from clearpath.sim.simulator import VehicleSnapshot, WorldView


def _hospital(
    hospital_id: str, node: str, units: Dict[str, int], wait_min: float,
    specialties: List[str],
) -> Dict[str, Any]:
    """Build one hospitals.json entry."""
    return {
        "id": hospital_id,
        "name": hospital_id,
        "node": node,
        "total_beds": sum(units.values()),
        "available_beds_by_unit": units,
        "specialties": specialties,
        "avg_wait_time_min": wait_min,
    }


def _world() -> WorldView:
    """An empty but valid perception state (no congestion, no queues)."""
    return WorldView(tick=0, vehicles=[], queues={}, signals={}, densities={})


def _snapshot(vehicle_id: str, edge: Any, offset_m: float) -> VehicleSnapshot:
    """A vehicle sitting part-way along ``edge``."""
    return VehicleSnapshot(
        id=vehicle_id,
        kind="ambulance",
        edge=edge,
        offset_m=offset_m,
        speed_mps=10.0,
        lane=0,
        x=0.0,
        y=0.0,
        heading_deg=90.0,
        is_stopped=False,
        wait_time_s=0.0,
        yield_until_t=0.0,
    )


def _dispatcher(
    tmp_path: Any, hospitals: List[Dict[str, Any]], alpha: float = 0.7,
    clock: Any = None,
) -> DispatcherAgent:
    """Build an authenticated dispatcher over a 3x5 grid with custom hospitals."""
    path = tmp_path / "hospitals.json"
    path.write_text(json.dumps(hospitals), encoding="utf-8")
    config = load_config(alpha=alpha, grid_rows=3, grid_cols=5)
    agent = DispatcherAgent(
        "dispatcher", MessageBus(seed=3), config,
        RoadNetwork(config, hospitals_path=path),
        clock=clock or (lambda: 0.0),
    )
    agent.on_message(AuthResult(vehicle_id="AMB_1", is_authenticated=True))
    return agent


def test_picks_farther_hospital_when_nearest_lacks_capacity(tmp_path: Any) -> None:
    """The adjacent hospital has no free trauma bed, so the 3-block-away one wins."""
    hospitals = [
        _hospital("HOSP_NEAR", "j_0_1", {"trauma": 0, "general": 10}, 5.0, ["trauma"]),
        _hospital("HOSP_FAR", "j_0_4", {"trauma": 3, "general": 2}, 10.0, ["trauma"]),
    ]
    agent = _dispatcher(tmp_path, hospitals)

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    assert result["dispatched"] is True
    assert result["hospital_id"] == "HOSP_FAR"
    assert [entry["hospital_id"] for entry in result["ranked"]] == ["HOSP_FAR"]
    assert result["degraded"] is False


def test_alpha_flips_the_choice(tmp_path: Any) -> None:
    """Pure travel weighting takes the near hospital; pure wait weighting the far one."""
    hospitals = [
        _hospital("HOSP_NEAR", "j_0_1", {"trauma": 2}, 60.0, ["trauma"]),
        _hospital("HOSP_FAR", "j_0_2", {"trauma": 2}, 0.0, ["trauma"]),
    ]
    travel_first = _dispatcher(tmp_path, hospitals, alpha=1.0)
    wait_first = _dispatcher(tmp_path, hospitals, alpha=0.0)

    quick = travel_first.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())
    quiet = wait_first.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    assert quick["hospital_id"] == "HOSP_NEAR"
    assert quiet["hospital_id"] == "HOSP_FAR"

    # Both criteria are fractions of fixed references, not of the candidate set.
    near, far = quick["ranked"]
    assert near["travel_ratio"] < far["travel_ratio"]
    assert near["wait_ratio"] > far["wait_ratio"]
    # alpha=1.0 scores on travel alone; alpha=0.0 on wait alone.
    assert near["score"] == near["travel_ratio"]
    assert quiet["ranked"][0]["score"] == quiet["ranked"][0]["wait_ratio"]


def test_hospital_on_incident_node_still_notifies_the_junction(tmp_path: Any) -> None:
    """A zero-length corridor publishes a terminus notice instead of silence."""
    hospitals = [_hospital("HOSP_HERE", "j_0_0", {"trauma": 3}, 5.0, ["trauma"])]
    agent = _dispatcher(tmp_path, hospitals)

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    assert result["path"] == ["j_0_0"]
    assert result["total_eta_s"] == 0.0

    notices = [msg for msg in agent.bus.message_log if isinstance(msg, EtaNotice)]
    assert len(notices) == 1
    assert notices[0].junction_id == "j_0_0"
    assert notices[0].recipient == "j_0_0"
    assert notices[0].eta_t == 0.0
    assert notices[0].approach_edge == ""
    assert notices[0].exit_edge == ""
    assert notices[0].vehicle_id == "AMB_1"

    plans = [msg for msg in agent.bus.message_log if isinstance(msg, RoutePlan)]
    assert len(plans) == 1
    assert plans[0].path_nodes == ["j_0_0"]
    assert plans[0].eta_by_junction == {"j_0_0": 0.0}


def test_score_ignores_unrelated_candidates(tmp_path: Any) -> None:
    """An unrelated third hospital must not change anyone else's score."""
    base = [
        _hospital("HOSP_A", "j_0_1", {"trauma": 2}, 1.67, ["trauma"]),
        _hospital("HOSP_B", "j_0_2", {"trauma": 2}, 0.83, ["trauma"]),
    ]
    extra = _hospital("HOSP_C", "j_0_4", {"trauma": 9}, 0.0, ["trauma"])

    alone = _dispatcher(tmp_path, base).dispatch("AMB_1", (0.0, 0.0), "trauma", _world())
    crowded = _dispatcher(tmp_path, base + [extra]).dispatch(
        "AMB_1", (0.0, 0.0), "trauma", _world()
    )

    assert alone["hospital_id"] == "HOSP_A"
    assert crowded["hospital_id"] == "HOSP_A"

    alone_scores = {entry["hospital_id"]: entry["score"] for entry in alone["ranked"]}
    crowded_scores = {entry["hospital_id"]: entry["score"] for entry in crowded["ranked"]}
    assert alone_scores["HOSP_A"] == crowded_scores["HOSP_A"]
    assert alone_scores["HOSP_B"] == crowded_scores["HOSP_B"]


def test_wait_no_longer_dominates_travel(tmp_path: Any) -> None:
    """The on-site hospital beats a 4-block-away one despite its longer ER wait."""
    hospitals = [
        _hospital("HOSP_HERE", "j_0_0", {"trauma": 4}, 20.0, ["trauma"]),
        _hospital("HOSP_AWAY", "j_0_4", {"trauma": 4}, 12.0, ["trauma"]),
    ]
    agent = _dispatcher(tmp_path, hospitals)

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    assert result["hospital_id"] == "HOSP_HERE"
    here, away = result["ranked"]
    assert here["travel_time_s"] < away["travel_time_s"]
    assert here["hospital_wait_s"] > away["hospital_wait_s"]
    assert here["score"] < away["score"]


def test_eta_schedule_is_strictly_increasing(tmp_path: Any) -> None:
    """Arrival times must increase monotonically along the chosen path."""
    hospitals = [_hospital("HOSP_FAR", "j_0_4", {"trauma": 5}, 10.0, ["trauma"])]
    agent = _dispatcher(tmp_path, hospitals)

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())
    path = result["path"]
    etas = [result["eta_by_junction"][node] for node in path]

    assert etas[0] == 0.0
    assert all(later > earlier for earlier, later in zip(etas, etas[1:]))
    assert result["total_eta_s"] == etas[-1]


def test_refuses_to_dispatch_without_authentication(tmp_path: Any) -> None:
    """Without a recorded AuthResult the dispatcher publishes nothing."""
    hospitals = [_hospital("HOSP_FAR", "j_0_4", {"trauma": 5}, 10.0, ["trauma"])]
    path = tmp_path / "hospitals.json"
    path.write_text(json.dumps(hospitals), encoding="utf-8")
    config = load_config(grid_rows=3, grid_cols=5)
    bus = MessageBus(seed=3)
    agent = DispatcherAgent(
        "dispatcher", bus, config, RoadNetwork(config, hospitals_path=path)
    )

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    assert result["dispatched"] is False
    assert result["ranked"] == []
    assert not any(isinstance(msg, RoutePlan) for msg in bus.message_log)


def test_replan_avoids_blocked_node(tmp_path: Any) -> None:
    """A junction rejection moves the path and re-publishes it to the corridors."""
    hospitals = [_hospital("HOSP_FAR", "j_0_4", {"trauma": 5}, 10.0, ["trauma"])]
    agent = _dispatcher(tmp_path, hospitals)

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())
    assert "j_0_2" in result["path"]

    plan = agent.replan("AMB_1", ["j_0_2"])

    assert plan is not None
    assert "j_0_2" not in plan["path"]
    assert plan["path"][0] == "j_0_0"
    assert plan["path"][-1] == "j_0_4"

    plans = [msg for msg in agent.bus.message_log if isinstance(msg, RoutePlan)]
    assert len(plans) == 2
    assert plans[-1].path_nodes == plan["path"]
    assert plans[-1].eta_by_junction == plan["eta_by_junction"]

    junctions = [
        msg.junction_id for msg in agent.bus.message_log if isinstance(msg, EtaNotice)
    ]
    assert junctions == result["path"][1:] + plan["path"][1:]

    # A revoked vehicle keeps its updated state but publishes nothing further.
    agent.on_message(RevokePreemption(vehicle_id="AMB_1", reason="SPEED_LIMIT"))
    assert agent.replan("AMB_1", ["j_0_1"]) is not None
    assert len([msg for msg in agent.bus.message_log if isinstance(msg, RoutePlan)]) == 2


def test_replan_publishes_current_tick_not_dispatch_tick(tmp_path: Any) -> None:
    """A late re-plan must announce arrivals from now, not from the original tick."""
    now = [0.0]
    hospitals = [_hospital("HOSP_FAR", "j_0_4", {"trauma": 5}, 10.0, ["trauma"])]
    agent = _dispatcher(tmp_path, hospitals, clock=lambda: now[0])
    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    now[0] = 120.0
    plan = agent.replan("AMB_1", ["j_0_2"])
    assert plan is not None

    plans = [msg for msg in agent.bus.message_log if isinstance(msg, RoutePlan)]
    assert plans[-1].ts == 120.0

    notices = [msg for msg in agent.bus.message_log if isinstance(msg, EtaNotice)]
    replan_notices = notices[len(result["path"]) - 1:]
    assert len(replan_notices) == len(plan["path"]) - 1
    assert all(notice.ts == 120.0 for notice in replan_notices)
    assert replan_notices[0].eta_t == 120.0 + plan["eta_by_junction"][plan["path"][1]]
    assert replan_notices[0].eta_t > 120.0


def test_replan_solves_from_current_position(tmp_path: Any) -> None:
    """A mid-route re-plan starts where the vehicle is and skips cleared junctions."""
    now = [0.0]
    hospitals = [_hospital("HOSP_FAR", "j_0_4", {"trauma": 5}, 10.0, ["trauma"])]
    agent = _dispatcher(tmp_path, hospitals, clock=lambda: now[0])
    agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    now[0] = 120.0
    on_edge = WorldView(
        tick=120,
        vehicles=[_snapshot("AMB_1", ("j_0_1", "j_0_2"), 100.0)],
        queues={},
        signals={},
        densities={},
    )

    plan = agent.replan("AMB_1", [], world_view=on_edge)

    assert plan is not None
    assert plan["path"][0] == "j_0_2"
    assert "j_0_0" not in plan["path"]
    assert "j_0_1" not in plan["path"]
    # Half the 200 m edge at 13.36 m/s, not zero.
    assert plan["eta_by_junction"]["j_0_2"] > 0.0

    notices = [msg for msg in agent.bus.message_log if isinstance(msg, EtaNotice)]
    first = notices[-len(plan["path"])]
    assert first.junction_id == "j_0_2"
    assert first.approach_edge == "j_0_1_j_0_2"
    assert first.ts == 120.0
    assert first.eta_t == 120.0 + plan["eta_by_junction"]["j_0_2"]

    # Still approaching j_0_2, now with the rest of row 0 queued up.
    jammed = WorldView(
        tick=150,
        vehicles=[_snapshot("AMB_1", ("j_0_1", "j_0_2"), 100.0)],
        queues={("j_0_2", "j_0_3"): 25, ("j_0_3", "j_0_4"): 25},
        signals={},
        densities={},
    )
    assert agent.reroute_if_congested("AMB_1", jammed) is True

    plans = [msg for msg in agent.bus.message_log if isinstance(msg, RoutePlan)]
    assert plans[-1].path_nodes[0] == "j_0_2"
    # Reroute stamps from the live world view tick rather than the clock.
    assert plans[-1].ts == 150.0


def test_congestion_reroute_publishes_new_plan(tmp_path: Any) -> None:
    """A cost rise over 25% re-plans the corridor and announces the new path."""
    hospitals = [_hospital("HOSP_FAR", "j_0_4", {"trauma": 5}, 10.0, ["trauma"])]
    agent = _dispatcher(tmp_path, hospitals)
    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    congested = WorldView(
        tick=30,
        vehicles=[],
        queues={(f"j_0_{i}", f"j_0_{i + 1}"): 20 for i in range(4)},
        signals={},
        densities={},
    )

    assert agent.reroute_if_congested("AMB_1", congested) is True

    plans = [msg for msg in agent.bus.message_log if isinstance(msg, RoutePlan)]
    assert len(plans) == 2
    assert plans[-1].path_nodes != result["path"]
    assert any(node.startswith("j_1_") for node in plans[-1].path_nodes)
    assert plans[-1].ts == 30.0

    junctions = [
        msg.junction_id for msg in agent.bus.message_log if isinstance(msg, EtaNotice)
    ]
    assert len(junctions) == (len(result["path"]) - 1) + (len(plans[-1].path_nodes) - 1)


def test_degraded_fallback_relaxes_specialty_and_beds(tmp_path: Any) -> None:
    """With no strict match the dispatcher relaxes the filter and flags degraded."""
    hospitals = [
        # No trauma specialty at all, but cardiac beds are free.
        _hospital("HOSP_NO_TRAUMA", "j_0_1", {"cardiac": 2}, 5.0, ["cardiac"]),
        # Has the trauma specialty but no free trauma bed.
        _hospital("HOSP_TRAUMA_FULL", "j_0_3", {"trauma": 0, "general": 4}, 10.0, ["trauma"]),
    ]
    agent = _dispatcher(tmp_path, hospitals)

    result = agent.dispatch("AMB_1", (0.0, 0.0), "trauma", _world())

    assert result["dispatched"] is True
    assert result["degraded"] is True
    assert result["hospital_id"] == "HOSP_NO_TRAUMA"
    assert len(result["ranked"]) == 2
    assert all(entry["relaxed"] is True for entry in result["ranked"])
    assert all(entry["beds"] > 0 for entry in result["ranked"])
