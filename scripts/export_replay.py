"""Export compact per-tick simulation replay frames for the ClearPath-lite web frontend.

Runs three real scenarios (normal, emergency, spoofed) with fixed seeds and
writes compressed, high-fidelity JSON files to web/public/replay/.
Also copies results/summary.json to web/src/data/.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from clearpath.agents.tokens import issue_token
from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import load_config
from clearpath.engine.orchestrator import ClearPathEngine


def extract_network_geometry(engine: ClearPathEngine) -> Dict[str, Any]:
    """Extract road network graph nodes, edges and hospitals for SVG mapping."""
    network = engine.sim.network
    graph = network.graph

    nodes: Dict[str, Dict[str, float]] = {}
    for node in graph.nodes():
        nd = graph.nodes[node]
        nodes[node] = {"x": float(nd["x"]), "y": float(nd["y"])}

    edges: List[Dict[str, str]] = []
    for u, v in graph.edges():
        edges.append({"from": u, "to": v})

    hospitals: Dict[str, Dict[str, Any]] = {}
    for h_id, hosp in network.hospitals.items():
        node = hosp.get("node", "")
        beds = sum(hosp.get("available_beds_by_unit", {}).values())
        hospitals[h_id] = {
            "name": hosp.get("name", h_id),
            "node": node,
            "beds": beds,
        }

    return {
        "nodes": nodes,
        "edges": edges,
        "hospitals": hospitals,
    }


def extract_frame(
    engine: ClearPathEngine,
    last_verdict: Optional[Dict[str, Any]] = None,
    last_attack: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract a minimal, compact snapshot of a single simulation tick."""
    snap = engine.snapshot()
    ms = snap["metrics_summary"]

    ambulances: List[Dict[str, Any]] = []
    for amb_id, outer in engine._active_ambulances.items():
        plan = outer.get("plan") or {}
        veh = engine.sim.vehicles.get(amb_id)
        if veh:
            x, y = engine.sim.network.edge_position(veh.edge, veh.offset_m)
            spd = veh.speed
            stopped = veh.is_stopped
        else:
            x, y, spd, stopped = 0.0, 0.0, 0.0, False

        ambulances.append({
            "id": amb_id,
            "x": round(x, 1),
            "y": round(y, 1),
            "speed": round(spd, 1),
            "stopped": stopped,
            "route": plan.get("path", []),
            "hospital": plan.get("hospital_id", ""),
            "eta": round(plan.get("total_eta_s", 0.0), 1),
        })

    # Sample civilian vehicles compactly: [x, y, is_stopped]
    civ_vehicles: List[List[float]] = []
    for v in snap["vehicles"]:
        if v.get("kind") != "ambulance":
            civ_vehicles.append([
                round(v.get("x", 0.0), 1),
                round(v.get("y", 0.0), 1),
                1.0 if v.get("is_stopped") else 0.0,
            ])
    # Limit to 50 vehicles for compact file size
    civ_vehicles = civ_vehicles[:50]

    # Guidance advisories (last 3)
    guidance: List[Dict[str, Any]] = []
    for rec in list(engine.guidance.advisory_feed)[-3:]:
        guidance.append({
            "t": int(rec.t),
            "severity": rec.severity,
            "text": rec.text,
        })

    # Security verdict summary
    sec_summary: Optional[Dict[str, Any]] = None
    if last_verdict:
        auth = last_verdict.get("auth")
        allowed = last_verdict.get("authenticated", False)
        reasons = getattr(auth, "reasons", []) if auth else []
        risk = getattr(auth, "risk_score", 0.0) if auth else 0.0
        sec_summary = {
            "allowed": allowed,
            "risk": round(risk, 2),
            "reasons": reasons,
            "attack": last_attack or "",
        }

    return {
        "tick": snap["tick"],
        "preemption_enabled": snap["preemption_enabled"],
        "signals": snap["signals"],
        "queues": snap["queues"],
        "ambulances": ambulances,
        "vehicles": civ_vehicles,
        "guidance": guidance,
        "vms": snap.get("vms_board", {}),
        "security": sec_summary,
        "metrics": {
            "avg_speed": round(float(ms.get("network_avg_speed_mps", 0.0)), 2),
            "max_queue": int(ms.get("network_max_queue", 0)),
            "cross_delay": round(float(ms.get("cross_delay_avg_s", 0.0)), 2),
            "time_saved": round(float(145.0 - float(ms.get("ambulance_travel_time_s", 145.0))), 1)
            if ms.get("ambulance_travel_time_s") else 0.0,
            "stops": int(ms.get("ambulance_stops", 0)),
            "blocked": int(ms.get("security_blocked_attacks", ms.get("security_blocked", 0))),
        },
    }


def run_normal_replay(seed: int = 42, total_ticks: int = 100) -> Dict[str, Any]:
    """Generate normal scenario replay without emergency preemption."""
    cfg = load_config(seed=seed, max_ticks=total_ticks)
    engine = ClearPathEngine(cfg, preemption_enabled=False, demand_level="med")

    frames = []
    for t in range(total_ticks):
        engine.step()
        if t % 2 == 0:
            frames.append(extract_frame(engine))

    return {
        "scenario": "normal",
        "description": "Baseline urban traffic without active corridor preemption",
        "seed": seed,
        "network": extract_network_geometry(engine),
        "frames": frames,
    }


def run_emergency_replay(seed: int = 42, total_ticks: int = 130) -> Dict[str, Any]:
    """Generate valid emergency corridor replay with dynamic preemption."""
    cfg = load_config(seed=seed, max_ticks=total_ticks)
    engine = ClearPathEngine(cfg, preemption_enabled=True, demand_level="med")

    frames = []
    last_verdict: Optional[Dict[str, Any]] = None

    for t in range(total_ticks):
        engine.step()

        if t == 10:
            amb_id = engine.sim.spawn_ambulance("j_0_0", "j_5_5")
            vehicle = engine.sim.vehicles.get(amb_id)
            if vehicle:
                x, y = engine.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
                nonce = str(uuid.uuid4())
                token = issue_token(amb_id, nonce, float(t), cfg.hmac_secret)
                bearing = engine.sim.network.edge_bearing(*vehicle.edge)
                req = PreemptionRequest(
                    vehicle_id=amb_id,
                    token=token,
                    nonce=nonce,
                    incident_loc=(x, y),
                    severity="CRITICAL",
                    telemetry=Telemetry(
                        x=x, y=y,
                        speed_mps=vehicle.speed,
                        accel_mps2=0.0,
                        heading_deg=bearing,
                        edge_id=f"{vehicle.edge[0]}_{vehicle.edge[1]}",
                        lane=vehicle.lane,
                        vehicle_id=amb_id,
                    ),
                    sender="dashboard",
                )
                last_verdict = engine.submit_emergency_request(
                    req, incident_type="cardiac", ground_truth_valid=True
                )

        if t % 2 == 0:
            frames.append(extract_frame(engine, last_verdict=last_verdict))

    return {
        "scenario": "emergency",
        "description": "Valid cardiac emergency with HMAC-verified green wave corridor",
        "seed": seed,
        "network": extract_network_geometry(engine),
        "frames": frames,
    }


def run_spoofed_replay(seed: int = 42, total_ticks: int = 60) -> Dict[str, Any]:
    """Generate spoofed attack scenario replay with security defence verification."""
    cfg = load_config(seed=seed, max_ticks=total_ticks)
    engine = ClearPathEngine(cfg, preemption_enabled=True, demand_level="med")

    frames = []
    last_verdict: Optional[Dict[str, Any]] = None
    last_atk: Optional[str] = None

    for t in range(total_ticks):
        engine.step()

        if t == 8:
            # Inject forged HMAC token
            last_atk = "bad_signature"
            fake_req = PreemptionRequest(
                vehicle_id="FAKE_AMB_001",
                token="FAKE_AMB_001.bad-nonce.8.0.INVALIDSIG",
                nonce="bad-nonce",
                incident_loc=(100.0, 100.0),
                severity="HIGH",
                telemetry=Telemetry(
                    x=100.0, y=100.0, speed_mps=15.0, accel_mps2=0.0,
                    heading_deg=90.0, edge_id="j_0_0_j_0_1", lane=0,
                    vehicle_id="FAKE_AMB_001",
                ),
                sender="dashboard_fake",
            )
            last_verdict = engine.submit_emergency_request(
                fake_req, "general", ground_truth_valid=False
            )

        if t == 24:
            # Inject replay attack
            last_atk = "replay"
            old_nonce = "replay-known-nonce"
            token = issue_token("FAKE_AMB_001", old_nonce, 0.0, cfg.hmac_secret)
            engine.security._nonces[old_nonce] = float(engine.current_tick)
            fake_req2 = PreemptionRequest(
                vehicle_id="FAKE_AMB_001",
                token=token,
                nonce=old_nonce,
                incident_loc=(100.0, 100.0),
                severity="HIGH",
                telemetry=Telemetry(
                    x=100.0, y=100.0, speed_mps=15.0, accel_mps2=0.0,
                    heading_deg=90.0, edge_id="j_0_0_j_0_1", lane=0,
                    vehicle_id="FAKE_AMB_001",
                ),
                sender="dashboard_fake",
            )
            last_verdict = engine.submit_emergency_request(
                fake_req2, "general", ground_truth_valid=False
            )

        if t % 2 == 0:
            frames.append(extract_frame(engine, last_verdict=last_verdict, last_attack=last_atk))

    return {
        "scenario": "spoofed",
        "description": "Spoofed preemption attacks defended by Security Sentinel Gateway",
        "seed": seed,
        "network": extract_network_geometry(engine),
        "frames": frames,
    }


def main() -> None:
    public_dir = ROOT_DIR / "web" / "public" / "replay"
    public_dir.mkdir(parents=True, exist_ok=True)
    data_dir = ROOT_DIR / "web" / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    print("Generating normal scenario replay...")
    normal_data = run_normal_replay(seed=42)
    with open(public_dir / "normal.json", "w", encoding="utf-8") as f:
        json.dump(normal_data, f, separators=(",", ":"))
    size_normal = (public_dir / "normal.json").stat().st_size / 1024
    print(f"  Saved web/public/replay/normal.json ({size_normal:.1f} KB)")

    print("Generating emergency corridor replay...")
    emergency_data = run_emergency_replay(seed=42)
    with open(public_dir / "emergency.json", "w", encoding="utf-8") as f:
        json.dump(emergency_data, f, separators=(",", ":"))
    size_emg = (public_dir / "emergency.json").stat().st_size / 1024
    print(f"  Saved web/public/replay/emergency.json ({size_emg:.1f} KB)")

    print("Generating spoofed attack replay...")
    spoofed_data = run_spoofed_replay(seed=42)
    with open(public_dir / "spoofed.json", "w", encoding="utf-8") as f:
        json.dump(spoofed_data, f, separators=(",", ":"))
    size_spoofed = (public_dir / "spoofed.json").stat().st_size / 1024
    print(f"  Saved web/public/replay/spoofed.json ({size_spoofed:.1f} KB)")

    # Copy summary.json
    summary_src = ROOT_DIR / "results" / "summary.json"
    summary_dst = data_dir / "summary.json"
    if summary_src.exists():
        shutil.copyfile(summary_src, summary_dst)
        print(f"Copied results/summary.json to web/src/data/summary.json ({summary_dst.stat().st_size / 1024:.1f} KB)")
    else:
        print("Warning: results/summary.json not found!")

    # Check file size limits (<400 KB)
    for name, sz in [("normal", size_normal), ("emergency", size_emg), ("spoofed", size_spoofed)]:
        assert sz < 400, f"Replay file {name}.json exceeded 400 KB ({sz:.1f} KB)"
    print("All replay files under 400 KB limit confirmed.")


if __name__ == "__main__":
    main()
