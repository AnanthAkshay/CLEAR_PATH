"""Simulation Console Page for ClearPath Multi-Agent Preemption Prototype.

Features interactive scenario selection, stepping controls, confirmation dialogs,
microscopic road grid canvas, security authentication gate, guidance feed,
live telemetry timeseries, and 3-way policy comparison.

Uses st.fragment for performant, localized updates without full-page re-renders.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from clearpath.agents.tokens import issue_token
from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import SimConfig, load_config
from clearpath.engine.orchestrator import ClearPathEngine

from clearpath.dashboard.charts import (
    build_comparison_figure,
    build_grid_figure,
    build_reason_figure,
    build_telemetry_figure,
)
from clearpath.dashboard.components import (
    render_big_numeral,
    show_dispatch_confirmation,
    show_reset_confirmation,
)

SCENARIOS = {
    "Valid emergency": {"inject_emergency": True, "inject_fake": False},
    "Normal traffic": {"inject_emergency": False, "inject_fake": False},
    "Spoofed request": {"inject_emergency": False, "inject_fake": True},
    "Mixed traffic": {"inject_emergency": True, "inject_fake": True},
}

INCIDENT_TYPES = ["cardiac", "trauma", "stroke", "general"]
DEMAND_LEVELS = ["low", "med", "high"]
ATTACK_TYPES = [
    "bad_signature",
    "replay",
    "teleport_spoofed_gps",
    "overspeed",
    "unknown_vehicle",
]

from clearpath.dashboard.locations import (
    GRID_NODES,
    get_edge_label,
    get_location_cross,
    get_location_display,
    get_location_name,
)

HOSPITAL_OPTIONS = {
    "auto": "Auto-Select (AI Triage Score)",
    "HOSP_CENTRAL": "Central Memorial Hospital (South Plaza)",
    "HOSP_RIVERSIDE": "Riverside Urgent Care (Midtown Plaza)",
    "HOSP_WEST": "Westside Community Clinic (Westside Hilltop)",
    "HOSP_NORTH": "North General Hospital (Northview Heights)",
}


def get_node_label(node: str) -> str:
    return get_location_display(node)


def _build_valid_request(
    engine: ClearPathEngine,
    amb_id: str,
    origin_node: str = "j_0_0",
) -> Optional[PreemptionRequest]:
    vehicle = engine.sim.vehicles.get(amb_id)
    if vehicle is not None:
        x, y = engine.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
        bearing = engine.sim.network.edge_bearing(*vehicle.edge)
        edge_id = f"{vehicle.edge[0]}_{vehicle.edge[1]}"
        speed = vehicle.speed
        lane = vehicle.lane
    else:
        graph = engine.sim.network.graph
        if origin_node in graph.nodes:
            nd = graph.nodes[origin_node]
            x, y = float(nd["x"]), float(nd["y"])
        else:
            x, y = 0.0, 0.0
        successors = list(graph.successors(origin_node))
        next_node = successors[0] if successors else origin_node
        bearing = engine.sim.network.edge_bearing(origin_node, next_node) if graph.has_edge(origin_node, next_node) else 0.0
        edge_id = f"{origin_node}_{next_node}"
        speed = 10.0
        lane = 0

    nonce = str(uuid.uuid4())
    tick = float(engine.current_tick)
    token = issue_token(amb_id, nonce, tick, engine.config.hmac_secret)
    return PreemptionRequest(
        vehicle_id=amb_id,
        token=token,
        nonce=nonce,
        incident_loc=(x, y),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=x,
            y=y,
            speed_mps=speed,
            accel_mps2=0.0,
            heading_deg=bearing,
            edge_id=edge_id,
            lane=lane,
            vehicle_id=amb_id,
        ),
        sender="console",
    )


def _build_fake_request(engine: ClearPathEngine, attack_type: str) -> PreemptionRequest:
    cfg = engine.config
    graph = engine.sim.network.graph
    nodes = list(graph.nodes())

    import random
    rng = random.Random(99)
    n1 = rng.choice(nodes)
    neighbours = list(graph.successors(n1))
    n2 = neighbours[0] if neighbours else n1

    n1d = graph.nodes[n1]
    bx, by = float(n1d["x"]), float(n1d["y"])
    tick = float(engine.current_tick)
    vid = "FAKE_AMB_001"
    nonce = str(uuid.uuid4())

    if attack_type == "bad_signature":
        token = f"{vid}.{nonce}.{tick}.INVALIDSIG"
    elif attack_type == "replay":
        old_nonce = "replay-known-nonce"
        token = issue_token(vid, old_nonce, 0.0, cfg.hmac_secret)
        engine.security._nonces[old_nonce] = float(engine.current_tick)
        nonce = old_nonce
    elif attack_type == "teleport_spoofed_gps":
        bx += 5000.0
        by += 5000.0
        token = issue_token(vid, nonce, tick, cfg.hmac_secret)
    elif attack_type == "overspeed":
        token = issue_token(vid, nonce, tick, cfg.hmac_secret)
    elif attack_type == "unknown_vehicle":
        vid = "UNKNOWN_VEH_XYZ"
        token = issue_token(vid, nonce, tick, "wrong-secret-key")
    else:
        token = "INVALID"

    speed = cfg.ambulance_max_mps * 3.0 if attack_type == "overspeed" else 10.0
    bearing = (
        engine.sim.network.edge_bearing(n1, n2)
        if graph.has_edge(n1, n2)
        else 90.0
    )

    return PreemptionRequest(
        vehicle_id=vid,
        token=token,
        nonce=nonce,
        incident_loc=(bx, by),
        severity="HIGH",
        telemetry=Telemetry(
            x=bx,
            y=by,
            speed_mps=speed,
            accel_mps2=0.0,
            heading_deg=bearing,
            edge_id=f"{n1}_{n2}",
            lane=0,
            vehicle_id=vid,
        ),
        sender="console_fake",
    )


def _init_console_state() -> None:
    defaults = {
        "engine": None,
        "running": False,
        "snapshot_history": [],
        "last_verdict": None,
        "last_verdict_atk": None,
        "comparison_result": None,
        "incident_locs": {},
        "show_reset_dialog": False,
        "show_dispatch_dialog": False,
        "selected_origin": "j_0_0",
        "selected_hospital": "auto",
        "incident_type": "cardiac",
        "selected_signal_node": "j_2_2",
        "signal_override_feedback": None,
        "selected_jam_edge": ("j_1_1", "j_1_2"),
        "traffic_jam_feedback": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _get_engine(seed: int, demand: str, policy: str, preemption: bool) -> ClearPathEngine:
    if st.session_state.engine is None:
        cfg = load_config(seed=seed, window_s=25, queue_flush_threshold=12, alpha=0.7, max_ticks=900)
        st.session_state.engine = ClearPathEngine(
            cfg,
            preemption_enabled=preemption,
            demand_level=demand,
            junction_policy=policy,
        )
    return st.session_state.engine


def reset_engine_state() -> None:
    st.session_state.engine = None
    st.session_state.snapshot_history = []
    st.session_state.last_verdict = None
    st.session_state.last_verdict_atk = None
    st.session_state.incident_locs = {}
    st.session_state.running = False
    st.session_state.signal_override_feedback = None
    st.session_state.traffic_jam_feedback = None


def dispatch_emergency_handler() -> None:
    engine = st.session_state.engine
    if engine is None:
        return
    origin_node = st.session_state.get("selected_origin", "j_0_0")
    target_hosp = st.session_state.get("selected_hospital", "auto")
    target_hosp_id = None if target_hosp == "auto" else target_hosp
    inc_type = st.session_state.get("incident_type", "cardiac")

    new_id = f"AMB_{len(engine.sim.ambulance_history) + 1}"
    req = _build_valid_request(engine, new_id, origin_node=origin_node)

    if req:
        result = engine.submit_emergency_request(
            req,
            inc_type,
            ground_truth_valid=True,
            target_hospital_id=target_hosp_id,
        )
        st.session_state.last_verdict = result
        st.session_state.last_verdict_atk = None
        st.session_state.incident_locs[req.vehicle_id] = req.incident_loc


def render_console_page() -> None:
    """Render the full interactive simulation console."""
    _init_console_state()

    # Console Header
    st.markdown(
        """
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin-bottom:16px;">
            <div>
                <h1 style="margin:0; font-size:1.8rem;">Traffic Operations & Preemption Console</h1>
                <p style="color:var(--cp-ink-secondary); margin:4px 0 0 0; font-size:0.95rem;">
                    Mission control interface for real-time microscopic grid simulation, HMAC verification, and corridor actuation.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sidebar Configuration ──────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🚨 Emergency Dispatch Setup")
        sel_origin = st.selectbox(
            "Incident Origin (Location)",
            GRID_NODES,
            index=GRID_NODES.index(st.session_state.selected_origin) if st.session_state.selected_origin in GRID_NODES else 0,
            format_func=get_node_label,
            help="Choose the intersection where the emergency occurred.",
        )
        st.session_state.selected_origin = sel_origin

        sel_hosp = st.selectbox(
            "Destination Hospital",
            list(HOSPITAL_OPTIONS.keys()),
            index=list(HOSPITAL_OPTIONS.keys()).index(st.session_state.selected_hospital) if st.session_state.selected_hospital in HOSPITAL_OPTIONS else 0,
            format_func=lambda x: HOSPITAL_OPTIONS[x],
            help="Select the target hospital or let the AI Dispatcher rank automatically.",
        )
        st.session_state.selected_hospital = sel_hosp

        incident_type = st.selectbox("Incident Severity", INCIDENT_TYPES, index=0)
        st.session_state.incident_type = incident_type

        st.markdown("---")
        st.markdown("### Grid Parameters")
        scenario_name = st.selectbox("Scenario Preset", list(SCENARIOS.keys()), index=0)
        seed = st.number_input("Random Seed", min_value=0, max_value=9999, value=42, step=1)
        demand_level = st.selectbox("Traffic Demand", DEMAND_LEVELS, index=1)
        policy_choice = st.selectbox(
            "Junction Agent Policy",
            ["Rule-based (Heuristics)", "RL (Trained Q-Net)"],
            index=0,
        )
        junction_policy = "rl" if "RL" in policy_choice else "rule"
        preemption_on = st.toggle("ClearPath Preemption", value=True)

        st.markdown("---")
        st.markdown("### Security Vector Injection")
        attack_type = st.selectbox(
            "Attack Vector",
            ATTACK_TYPES,
            format_func=lambda x: x.replace("_", " ").title(),
        )
        if st.button("Inject Spoofed Attack", key="btn_fire_attack"):
            eng = _get_engine(seed, demand_level, junction_policy, preemption_on)
            fake_req = _build_fake_request(eng, attack_type)
            result = eng.submit_emergency_request(fake_req, "general", ground_truth_valid=False)
            st.session_state.last_verdict = result
            st.session_state.last_verdict_atk = attack_type

        st.markdown("---")
        if st.button("Run 3-Way Policy Evaluation", key="btn_cmp_eval"):
            with st.spinner("Executing 3-Way Benchmark (Baseline vs Rules vs RL)..."):
                cfg_cmp = load_config(seed=int(seed), window_s=25, queue_flush_threshold=12, alpha=0.7, max_ticks=900)
                b_eng = ClearPathEngine(cfg_cmp, preemption_enabled=False, demand_level=demand_level)
                for t in range(300):
                    b_eng.step()
                    if t == 10:
                        b_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                base_m = b_eng.metrics.summary()

                r_eng = ClearPathEngine(cfg_cmp, preemption_enabled=True, demand_level=demand_level, baseline=b_eng.metrics, junction_policy="rule")
                for t in range(300):
                    r_eng.step()
                    if t == 10:
                        amb = r_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                        req = _build_valid_request(r_eng, amb)
                        if req:
                            r_eng.submit_emergency_request(req, incident_type, ground_truth_valid=True)
                rule_m = r_eng.metrics.summary()

                rl_eng = ClearPathEngine(cfg_cmp, preemption_enabled=True, demand_level=demand_level, baseline=b_eng.metrics, junction_policy="rl")
                for t in range(300):
                    rl_eng.step()
                    if t == 10:
                        amb = rl_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                        req = _build_valid_request(rl_eng, amb)
                        if req:
                            rl_eng.submit_emergency_request(req, incident_type, ground_truth_valid=True)
                rl_m = rl_eng.metrics.summary()

                st.session_state.comparison_result = {
                    "baseline": base_m,
                    "rule": rule_m,
                    "rl": rl_m,
                }

    # ── Handle Confirmation Dialogs ────────────────────────────────────────────
    if st.session_state.get("show_reset_dialog"):
        show_reset_confirmation(reset_engine_state)
        st.session_state.show_reset_dialog = False

    if st.session_state.get("show_dispatch_dialog"):
        hosp_disp = HOSPITAL_OPTIONS.get(st.session_state.selected_hospital, "Central Memorial Hospital")
        show_dispatch_confirmation(
            vehicle_id="AMB_001",
            hospital_name=hosp_disp,
            incident_type=st.session_state.incident_type,
            on_confirm=dispatch_emergency_handler,
            incident_origin=get_node_label(st.session_state.selected_origin),
        )
        st.session_state.show_dispatch_dialog = False

    engine = _get_engine(seed, demand_level, junction_policy, preemption_on)

    # ── Tactical Control Bar ───────────────────────────────────────────────────
    ctrl1, ctrl2, ctrl3, ctrl4, ctrl5, ctrl6 = st.columns([1.2, 1, 1, 1, 1.8, 1])
    with ctrl1:
        if not st.session_state.running:
            if st.button("▶ Run Live", key="bar_play", type="primary", width="stretch"):
                st.session_state.running = True
                st.rerun()
        else:
            if st.button("⏸ Pause", key="bar_pause", width="stretch"):
                st.session_state.running = False
                st.rerun()
    with ctrl2:
        if st.button("⏭ +1s Step", key="bar_step", width="stretch"):
            engine.step()
            st.rerun()
    with ctrl3:
        if st.button("⏩ +5s Step", key="bar_step5", width="stretch"):
            for _ in range(5):
                engine.step()
            st.rerun()
    with ctrl4:
        if st.button("🔄 Reset", key="bar_reset", width="stretch"):
            st.session_state.show_reset_dialog = True
            st.rerun()
    with ctrl5:
        if st.button("🚨 Dispatch Code-3", key="bar_dispatch", type="primary", width="stretch"):
            st.session_state.show_dispatch_dialog = True
            st.rerun()
    with ctrl6:
        tick_val = engine.current_tick
        st.markdown(
            f"""
            <div style="background:var(--cp-surface); border:1px solid var(--cp-rule); border-radius:var(--cp-radius-sm); padding:6px 12px; text-align:center; height:42px; display:flex; align-items:center; justify-content:center;">
                <span class="cp-mono" style="font-weight:700; color:var(--cp-accent-hover); font-size:1rem;">T={tick_val}s</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Simulation Fragment (Localized Auto-Reruns while Playing) ─────────────────
    render_simulation_fragment(engine, preemption_on)


@st.fragment(run_every=0.35 if st.session_state.get("running") else None)
def render_simulation_fragment(engine: ClearPathEngine, preemption_on: bool) -> None:
    """Performant localized fragment for discrete simulation stepping."""
    if st.session_state.get("running"):
        engine.step()

    snap = engine.snapshot()
    ms = snap.get("metrics_summary", {})

    st.session_state.snapshot_history.append(snap)
    if len(st.session_state.snapshot_history) > 300:
        st.session_state.snapshot_history = st.session_state.snapshot_history[-300:]

    history = st.session_state.snapshot_history

    # ── High-Density KPI Strip ─────────────────────────────────────────────────
    amb_time = ms.get("ambulance_travel_time_s")
    cross_delay = ms.get("cross_delay_avg_s", 0.0)
    atk_rate = ms.get("security_attack_block_rate", ms.get("security_block_rate", 1.0))
    fp_rate = ms.get("security_false_positive_rate", 0.0)
    stops = ms.get("ambulance_stops", 0)

    amb_str = f"{amb_time:.0f}" if amb_time else "Ready"
    amb_unit = "s" if amb_time else ""

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        render_big_numeral("Ambulance Transit", amb_str, amb_unit, f"Tick {snap['tick']}", True)
    with k2:
        render_big_numeral("Cross Delay", f"{cross_delay:.1f}", "s", "Side Street Queue", cross_delay <= 15.0)
    with k3:
        render_big_numeral("Defense Rate", f"{atk_rate * 100:.0f}", "%", "Zero Leakage", True)
    with k4:
        render_big_numeral("False Positive", f"{fp_rate * 100:.1f}", "%", "0 Legitimate Blocked", fp_rate == 0.0)
    with k5:
        render_big_numeral("Ambulance Stops", str(stops), "/ run", "Green Wave Lock", stops == 0)

    # ── 2-Column Responsive Layout: Map (60%) vs Inspector Tabs (40%) ───────────
    c_map, c_diag = st.columns([6, 4])

    with c_map:
        st.markdown(
            """
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div style="font-family:var(--cp-font-heading); font-weight:700; font-size:1.05rem; color:var(--cp-ink);">
                    Microscopic Road Grid & Corridor Tracking
                </div>
                <div style="display:flex; gap:10px; font-size:0.75rem;">
                    <span><span style="color:#10B981; font-weight:700;">●</span> Green</span>
                    <span><span style="color:#F59E0B; font-weight:700;">●</span> Yellow</span>
                    <span><span style="color:#EF4444; font-weight:700;">●</span> Red</span>
                    <span><span style="color:#EF4444; font-weight:700;">◆</span> Ambulance</span>
                    <span><span style="color:#38BDF8; font-weight:700;">✚</span> Hospital</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        fig_grid = build_grid_figure(
            snap=snap,
            engine=engine,
            incident_locs=st.session_state.incident_locs,
            dark_mode=st.session_state.get("dark_mode", True),
        )
        st.plotly_chart(fig_grid, width="stretch", config={"displayModeBar": False})

        st.caption(
            f"Active Vehicles: {len(snap['vehicles'])} | Ambulances: {len(engine._active_ambulances)} | Controlled Intersections: 36 | Tick: {snap['tick']}s"
        )

    with c_diag:
        tab_sec, tab_traffic, tab_sig, tab_guide, tab_bus, tab_disp, tab_metrics = st.tabs(
            ["🛡 Security", "🚗 Traffic & Routing", "🚦 Signal Controls", "🧭 Guidance", "⚡ Agent Bus", "🏥 Hospitals", "📊 Analytics"]
        )

        with tab_sec:
            st.markdown("##### Security Gateway Verification")
            verdict = st.session_state.get("last_verdict")
            if verdict:
                auth = verdict.get("auth")
                allowed = verdict.get("authenticated", False)
                reasons = getattr(auth, "reasons", []) if auth else []
                risk = getattr(auth, "risk_score", 0.0) if auth else 0.0
                atk_lbl = st.session_state.get("last_verdict_atk") or "Legitimate"

                status_color = "var(--cp-signal-green)" if allowed else "var(--cp-emergency)"
                status_bg = "rgba(16, 185, 129, 0.1)" if allowed else "rgba(239, 68, 68, 0.1)"
                status_text = "VERIFIED - VALID HMAC SIGNATURE" if allowed else "REJECTED - SPOOFED ATTACK DEFENDED"
                reasons_text = ", ".join(reasons) if reasons else "None (Passed All Checks)"

                st.markdown(
                    f"""
                    <div style="border:1px solid {status_color}; background:{status_bg}; padding:14px; border-radius:var(--cp-radius); margin-bottom:12px;">
                        <div style="font-weight:700; color:{status_color}; font-size:0.95rem;">{status_text}</div>
                        <div style="font-size:0.82rem; margin-top:4px; color:var(--cp-ink);">Vector: <b>{atk_lbl.replace('_', ' ').title()}</b> | Risk Score: <b>{risk:.2f}</b></div>
                        <div style="font-size:0.76rem; color:var(--cp-ink-secondary); margin-top:2px;">Reason Codes: {reasons_text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Security gateway active. Awaiting preemption authentication requests.")

            st.markdown("##### Cryptographic Audit Trail")
            audit = engine.security.audit_trail[-15:]
            if audit:
                audit_rows = []
                for entry in reversed(audit):
                    allowed = entry.get("allowed", False)
                    audit_rows.append({
                        "Tick": f"{entry.get('ts', 0):.0f}s",
                        "Vehicle ID": entry.get("vehicle_id", "")[:14],
                        "Verdict": "ALLOW" if allowed else "BLOCK",
                        "Risk": f"{entry.get('risk_score', 0):.2f}",
                        "Reasons": ", ".join(entry.get("reasons", [])) or "Clean",
                    })
                st.dataframe(pd.DataFrame(audit_rows), width="stretch", hide_index=True)

            rc = dict(engine.security.reason_counts)
            if rc:
                st.markdown("##### Attack Rejection Vectors")
                fig_rc = build_reason_figure(rc, dark_mode=st.session_state.get("dark_mode", True))
                st.plotly_chart(fig_rc, width="stretch", config={"displayModeBar": False})

        with tab_traffic:
            st.markdown("##### 🚗 Live Traffic Analysis & Congestion Rerouting")
            st.caption(
                "ClearPath's Dispatcher Agent actively monitors microscopic civilian vehicle density and signal queues. "
                "The edge traversal cost model dynamically factors in civilian friction and red-light queues to reroute emergency vehicles around bottlenecks."
            )

            densities = snap.get("densities", {})
            queues = snap.get("queues", {})
            active_cars = [v for v in snap.get("vehicles", []) if v.get("kind") == "car"]
            congested_edges = [
                k for k, d in densities.items()
                if float(d) >= 20.0 or int(queues.get(k, 0)) >= 2
            ]

            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                st.metric("Civilian Cars", len(active_cars))
            with t_col2:
                st.metric("Bottlenecks", len(congested_edges))
            with t_col3:
                st.metric("Rerouting Engine", "Active (A* + Live Cost)")

            st.markdown("---")
            st.markdown("###### 🚨 Interactive Bottleneck Injector")
            st.caption("Inject or clear traffic jams on any corridor to test real-time emergency vehicle rerouting.")

            graph = engine.sim.network.graph
            all_edges = sorted(list(graph.edges()), key=lambda e: (e[0], e[1]))

            def format_edge_opt(edge: tuple[str, str]) -> str:
                u, v = edge
                rclass = graph[u][v].get("road_class", "residential").title() if graph.has_edge(u, v) else "Road"
                return f"{get_edge_label(u, v)} [{rclass}]"

            jam_edge_idx = 0
            if st.session_state.selected_jam_edge in all_edges:
                jam_edge_idx = all_edges.index(st.session_state.selected_jam_edge)

            sel_jam_edge = st.selectbox(
                "Select Road Corridor to Congest / Clear",
                all_edges,
                index=jam_edge_idx,
                format_func=format_edge_opt,
                key="jam_edge_select",
            )
            st.session_state.selected_jam_edge = sel_jam_edge

            j_col1, j_col2 = st.columns(2)
            with j_col1:
                if st.button("🚨 Inject Jam (8 Cars)", key="btn_inject_jam", type="primary", width="stretch"):
                    u_jam, v_jam = sel_jam_edge
                    created = engine.inject_traffic_jam(u_jam, v_jam, num_vehicles=8)
                    st.session_state.traffic_jam_feedback = (
                        f"🚨 Injected {len(created)} civilian vehicles onto {get_edge_label(u_jam, v_jam)}. "
                        "Corridor is now jammed in RED! Dispatcher Agent is evaluating detours."
                    )
                    st.rerun()
            with j_col2:
                if st.button("🔄 Clear Traffic Jams", key="btn_clear_jam", width="stretch"):
                    cleared = engine.clear_traffic_jams()
                    st.session_state.traffic_jam_feedback = f"✅ Cleared {cleared} civilian bottleneck vehicles. Network flow restored."
                    st.rerun()

            if st.session_state.get("traffic_jam_feedback"):
                st.info(st.session_state.traffic_jam_feedback)

            st.markdown("---")
            st.markdown("###### 🚑 Active Ambulance Route Traffic Breakdown")
            if engine._active_ambulances:
                for amb_id, outer in engine._active_ambulances.items():
                    plan = outer.get("plan", {})
                    path = plan.get("path", [])
                    if len(path) >= 2:
                        route_legs = []
                        total_route_delay = 0.0
                        for i in range(len(path) - 1):
                            u, v = path[i], path[i + 1]
                            ekey = f"{u}_{v}"
                            length = graph[u][v].get("length_m", 200.0) if graph.has_edge(u, v) else 200.0
                            d_val = float(densities.get(ekey, 0.0))
                            cars_on_leg = max(0, int(round(d_val * (length / 1000.0))))
                            q_on_leg = int(queues.get(ekey, 0))
                            delay = cars_on_leg * 3.5 + q_on_leg * 4.0
                            total_route_delay += delay

                            status_str = "🟢 Clear Flow"
                            if cars_on_leg >= 5 or q_on_leg >= 3:
                                status_str = "🔴 JAMMED"
                            elif cars_on_leg >= 2 or q_on_leg >= 1:
                                status_str = "🟡 Moderate"

                            route_legs.append({
                                "Leg Corridor": get_edge_label(u, v),
                                "Civilian Cars": cars_on_leg,
                                "Signal Queue": q_on_leg,
                                "Traffic Delay": f"+{delay:.1f}s",
                                "Flow Status": status_str,
                            })
                        st.dataframe(pd.DataFrame(route_legs), width="stretch", hide_index=True)
                        if total_route_delay > 0:
                            st.caption(f"Total Traffic Delay on Planned Corridor: **+{total_route_delay:.1f}s** (Dispatcher dynamically detours when alternative is >= 15% faster)")
                        else:
                            st.caption("✨ Corridor is 100% free flow. Green wave preemption active.")
            else:
                st.caption("No emergency vehicle currently dispatched. Click '🚨 Dispatch Code-3' to see live route traffic telemetry.")

            st.markdown("---")
            st.markdown("###### 🌐 Top Congested City Corridors")
            corridor_rows = []
            wv_dens = engine.sim.get_world_view().densities
            wv_q = engine.sim.get_world_view().queues
            for (u, v), d_val in sorted(wv_dens.items(), key=lambda item: float(item[1]), reverse=True):
                q = int(wv_q.get((u, v), 0))
                if float(d_val) > 0 or q > 0:
                    length = graph[u][v].get("length_m", 200.0) if graph.has_edge(u, v) else 200.0
                    cars = max(0, int(round(float(d_val) * (length / 1000.0))))
                    corridor_rows.append({
                        "Corridor": get_edge_label(u, v),
                        "Civilian Cars": cars,
                        "Density": f"{float(d_val):.0f} veh/km",
                        "Queue": q,
                        "Ambulance Friction": f"+{cars * 3.5 + q * 4.0:.1f}s",
                    })
                    if len(corridor_rows) >= 8:
                        break
            if corridor_rows:
                st.dataframe(pd.DataFrame(corridor_rows), width="stretch", hide_index=True)
            else:
                st.caption("All city corridors currently operating at zero congestion.")

        with tab_sig:
            st.markdown("##### Manual Intersection Signal Controller")
            st.caption("Inspect and manually force signal phases across any of the 36 urban intersections.")

            sig_node = st.selectbox(
                "Select Intersection to Control",
                GRID_NODES,
                index=GRID_NODES.index(st.session_state.selected_signal_node) if st.session_state.selected_signal_node in GRID_NODES else 14,
                format_func=get_node_label,
                key="sig_ctrl_select",
            )
            st.session_state.selected_signal_node = sig_node

            curr_ctrl = engine.sim.signals.get(sig_node)
            curr_phase = curr_ctrl.current_phase().value if curr_ctrl else "NS_GREEN"
            is_overridden = curr_ctrl.is_preempted if curr_ctrl else False
            phase_time = curr_ctrl.time_in_phase() if curr_ctrl else 0.0

            p_color = "#10B981" if "GREEN" in curr_phase else ("#F59E0B" if "YELLOW" in curr_phase else "#EF4444")
            mode_text = "MANUAL OVERRIDE ACTIVE" if is_overridden else "AUTONOMOUS FIXED CYCLE"
            mode_color = "var(--cp-emergency)" if is_overridden else "var(--cp-signal-green)"

            loc_n = get_location_name(sig_node)
            loc_c = get_location_cross(sig_node)

            st.markdown(
                f"""
                <div style="background:var(--cp-surface); border:1px solid var(--cp-rule); border-radius:var(--cp-radius); padding:12px 16px; margin-bottom:12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-size:0.75rem; color:var(--cp-muted); text-transform:uppercase; font-weight:700;">Target Intersection</span>
                            <div style="font-family:var(--cp-font-heading); font-size:1.1rem; font-weight:700; color:var(--cp-ink);">{loc_n}</div>
                            <div style="font-size:0.8rem; color:var(--cp-ink-secondary);">{loc_c}</div>
                        </div>
                        <div style="text-align:right;">
                            <span style="font-size:0.75rem; color:var(--cp-muted); text-transform:uppercase; font-weight:700;">Active Phase</span>
                            <div style="font-family:var(--cp-font-mono); font-size:1rem; font-weight:700; color:{p_color};">● {curr_phase} ({phase_time:.1f}s)</div>
                        </div>
                    </div>
                    <div style="margin-top:8px; font-size:0.78rem; color:{mode_color}; font-weight:600;">
                        Operational Mode: {mode_text}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if st.session_state.get("signal_override_feedback"):
                st.success(st.session_state.signal_override_feedback)

            st.markdown("###### Instant Phase Actuation")
            btn_r1c1, btn_r1c2 = st.columns(2)
            with btn_r1c1:
                if st.button("🟢 Force NS Green", key="btn_sig_ns", width="stretch"):
                    engine.sim.force_signal_phase(sig_node, "NS_GREEN", reason="manual_operator")
                    st.session_state.signal_override_feedback = f"{loc_n} ({loc_c}) forced to NS_GREEN (Preempted)."
                    st.rerun()
            with btn_r1c2:
                if st.button("🟢 Force EW Green", key="btn_sig_ew", width="stretch"):
                    engine.sim.force_signal_phase(sig_node, "EW_GREEN", reason="manual_operator")
                    st.session_state.signal_override_feedback = f"{loc_n} ({loc_c}) forced to EW_GREEN (Preempted)."
                    st.rerun()

            btn_r2c1, btn_r2c2 = st.columns(2)
            with btn_r2c1:
                if st.button("🟡 Force Yellow", key="btn_sig_y", width="stretch"):
                    engine.sim.force_signal_phase(sig_node, "NS_YELLOW", reason="manual_operator")
                    st.session_state.signal_override_feedback = f"{loc_n} ({loc_c}) forced to Yellow clearance."
                    st.rerun()
            with btn_r2c2:
                if st.button("🔴 Force All-Red", key="btn_sig_r", width="stretch"):
                    engine.sim.force_signal_phase(sig_node, "ALL_RED_TO_EW", reason="manual_operator")
                    st.session_state.signal_override_feedback = f"{loc_n} ({loc_c}) forced to All-Red clearance."
                    st.rerun()

            if st.button("🔄 Clear Override (Resume Auto Cycle)", key="btn_sig_clear", type="primary", width="stretch"):
                engine.sim.clear_signal_override(sig_node)
                st.session_state.signal_override_feedback = f"{loc_n} ({loc_c}) override cleared. Restored normal fixed cycle."
                st.rerun()

            st.markdown("###### All-Intersections Live Grid State")
            sig_rows = []
            for n in GRID_NODES:
                c = engine.sim.signals.get(n)
                if c:
                    sig_rows.append({
                        "Intersection": get_location_name(n),
                        "Street Crossing": get_location_cross(n),
                        "Phase": c.current_phase().value,
                        "Elapsed": f"{c.time_in_phase():.1f}s",
                        "Mode": "MANUAL" if c.is_preempted else "Auto",
                    })
            st.dataframe(pd.DataFrame(sig_rows), width="stretch", hide_index=True, height=200)

        with tab_guide:
            st.markdown("##### Real-Time Driver Guidance Feed")
            advisories = list(engine.guidance.advisory_feed)[-12:]
            if advisories:
                for rec in reversed(advisories):
                    sev = getattr(rec, "severity", "INFO")
                    sev_col = "var(--cp-emergency)" if sev == "CRITICAL" else ("var(--cp-signal-yellow)" if sev == "WARN" else "var(--cp-signal-green)")
                    st.markdown(
                        f"""
                        <div style="border-bottom:1px solid var(--cp-rule-subtle); padding:8px 0; font-size:0.84rem;">
                            <span style="color:{sev_col}; font-weight:700; font-family:var(--cp-font-mono);">[{sev}]</span> <b>t={rec.t:.0f}s:</b> {rec.text}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Corridor clear. No active lane-clearing advisories.")

            st.markdown("##### Dynamic VMS Signs")
            vms = snap.get("vms_board", {})
            if vms:
                for jid, msg in vms.items():
                    st.markdown(f"**[{jid}]**: `{msg}`")
            else:
                st.caption("Variable Message Signs cycling standard speed limits.")

        with tab_bus:
            st.markdown("##### Inter-Agent Bus Activity")
            bus_msgs = engine.bus.message_log[-20:]
            if bus_msgs:
                feed = []
                for m in reversed(bus_msgs):
                    feed.append({
                        "t": f"{getattr(m, 'ts', 0):.0f}s",
                        "Type": getattr(m, "type", type(m).__name__),
                        "From": str(getattr(m, "sender", ""))[:12],
                        "To": str(getattr(m, "recipient", ""))[:12],
                    })
                st.dataframe(pd.DataFrame(feed), width="stretch", hide_index=True)
            else:
                st.caption("Message bus initialized and ready.")

        with tab_disp:
            st.markdown("##### Regional Hospital Triage Capacities")
            hosps = []
            for h_id, hosp in engine.sim.network.hospitals.items():
                beds = sum(hosp.get("available_beds_by_unit", {}).values())
                hosps.append({
                    "Facility": hosp.get("name", h_id),
                    "Beds Available": beds,
                    "Wait (min)": hosp.get("avg_wait_time_min", 0),
                    "Specialties": ", ".join(hosp.get("specialties", [])),
                })
            st.dataframe(pd.DataFrame(hosps), width="stretch", hide_index=True)

        with tab_metrics:
            st.markdown("##### Live Velocity Telemetry")
            fig_tel = build_telemetry_figure(history, dark_mode=st.session_state.get("dark_mode", True))
            st.plotly_chart(fig_tel, width="stretch", config={"displayModeBar": False})

            cmp = st.session_state.get("comparison_result")
            if cmp:
                st.markdown("##### 3-Way Policy Benchmark")
                fig_cmp = build_comparison_figure(cmp, dark_mode=st.session_state.get("dark_mode", True))
                st.plotly_chart(fig_cmp, width="stretch", config={"displayModeBar": False})


if __name__ == "__main__" or True:
    render_console_page()
