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
    "Normal traffic": {"inject_emergency": False, "inject_fake": False},
    "Valid emergency": {"inject_emergency": True, "inject_fake": False},
    "Spoofed request": {"inject_emergency": False, "inject_fake": True},
    "Mixed": {"inject_emergency": True, "inject_fake": True},
}

INCIDENT_TYPES = ["trauma", "cardiac", "stroke", "general"]
DEMAND_LEVELS = ["low", "med", "high"]
ATTACK_TYPES = [
    "bad_signature",
    "replay",
    "teleport_spoofed_gps",
    "overspeed",
    "unknown_vehicle",
]


def _build_valid_request(engine: ClearPathEngine, amb_id: str) -> Optional[PreemptionRequest]:
    vehicle = engine.sim.vehicles.get(amb_id)
    if vehicle is None:
        return None
    x, y = engine.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
    nonce = str(uuid.uuid4())
    tick = float(engine.current_tick)
    token = issue_token(amb_id, nonce, tick, engine.config.hmac_secret)
    bearing = engine.sim.network.edge_bearing(*vehicle.edge)
    return PreemptionRequest(
        vehicle_id=amb_id,
        token=token,
        nonce=nonce,
        incident_loc=(x, y),
        severity="CRITICAL",
        telemetry=Telemetry(
            x=x,
            y=y,
            speed_mps=vehicle.speed,
            accel_mps2=0.0,
            heading_deg=bearing,
            edge_id=f"{vehicle.edge[0]}_{vehicle.edge[1]}",
            lane=vehicle.lane,
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


def dispatch_emergency_handler() -> None:
    engine = st.session_state.engine
    if engine is None:
        return
    amb_ids = list(engine._active_ambulances.keys())
    if not amb_ids:
        new_id = engine.sim.spawn_ambulance("j_0_0", "j_5_5")
        req = _build_valid_request(engine, new_id)
    else:
        req = _build_valid_request(engine, amb_ids[0])

    if req:
        result = engine.submit_emergency_request(req, "trauma", ground_truth_valid=True)
        st.session_state.last_verdict = result
        st.session_state.last_verdict_atk = None
        st.session_state.incident_locs[req.vehicle_id] = req.incident_loc


def render_console_page() -> None:
    """Render the full interactive simulation console."""
    _init_console_state()

    st.markdown("## Simulation Control Console")
    st.markdown(
        "Execute discrete-time traffic simulations, trigger authenticated preemption requests, test adversarial attack vectors, and inspect distributed agent coordination."
    )

    # ── Sidebar Controls ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Simulation Controls")
        scenario_name = st.selectbox("Scenario Preset", list(SCENARIOS.keys()), index=1)
        seed = st.number_input("Random Seed", min_value=0, max_value=9999, value=42, step=1)
        demand_level = st.selectbox("Traffic Demand", DEMAND_LEVELS, index=1)
        incident_type = st.selectbox("Incident Severity", INCIDENT_TYPES, index=0)
        policy_choice = st.selectbox(
            "Junction Agent Policy",
            ["Rule-based (Heuristics)", "RL (Trained Q-Net)"],
            index=0,
        )
        junction_policy = "rl" if "RL" in policy_choice else "rule"
        preemption_on = st.toggle("ClearPath Preemption", value=True)

        st.markdown("---")
        st.markdown("**Execution State**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Play" if not st.session_state.running else "Running...", key="btn_play", type="primary"):
                st.session_state.running = True
            if st.button("Step", key="btn_step"):
                if st.session_state.engine:
                    st.session_state.engine.step()
        with c2:
            if st.button("Pause", key="btn_pause"):
                st.session_state.running = False
            if st.button("Reset", key="btn_reset"):
                st.session_state.show_reset_dialog = True

        st.markdown("---")
        st.markdown("**Corridor Interventions**")
        if st.button("Dispatch Emergency", key="btn_dispatch_emg", type="primary"):
            st.session_state.show_dispatch_dialog = True

        st.markdown("---")
        st.markdown("**Adversarial Security Test**")
        attack_type = st.selectbox(
            "Attack Vector",
            ATTACK_TYPES,
            format_func=lambda x: x.replace("_", " ").title(),
        )
        if st.button("Fire Spoofed Attack", key="btn_fire_attack"):
            eng = _get_engine(seed, demand_level, junction_policy, preemption_on)
            fake_req = _build_fake_request(eng, attack_type)
            result = eng.submit_emergency_request(fake_req, "general", ground_truth_valid=False)
            st.session_state.last_verdict = result
            st.session_state.last_verdict_atk = attack_type

        st.markdown("---")
        if st.button("Run 3-Way Policy Evaluation", key="btn_cmp_eval"):
            with st.spinner("Running 3-Way Benchmark: Baseline vs Rules vs RL (300 ticks each)..."):
                cfg_cmp = load_config(seed=int(seed), window_s=25, queue_flush_threshold=12, alpha=0.7, max_ticks=900)
                # Baseline
                b_eng = ClearPathEngine(cfg_cmp, preemption_enabled=False, demand_level=demand_level)
                for t in range(300):
                    b_eng.step()
                    if t == 10:
                        b_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                base_m = b_eng.metrics.summary()

                # Rules
                r_eng = ClearPathEngine(cfg_cmp, preemption_enabled=True, demand_level=demand_level, baseline=b_eng.metrics, junction_policy="rule")
                for t in range(300):
                    r_eng.step()
                    if t == 10:
                        amb = r_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                        req = _build_valid_request(r_eng, amb)
                        if req:
                            r_eng.submit_emergency_request(req, incident_type, ground_truth_valid=True)
                rule_m = r_eng.metrics.summary()

                # RL
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

    # ── Handle Dialogs ──────────────────────────────────────────────────────────
    if st.session_state.get("show_reset_dialog"):
        show_reset_confirmation(reset_engine_state)
        st.session_state.show_reset_dialog = False

    if st.session_state.get("show_dispatch_dialog"):
        show_dispatch_confirmation(
            vehicle_id="AMB_001",
            hospital_name="St. Jude Trauma Center",
            incident_type=incident_type,
            on_confirm=dispatch_emergency_handler,
        )
        st.session_state.show_dispatch_dialog = False

    engine = _get_engine(seed, demand_level, junction_policy, preemption_on)

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

    # ── KPI Row ────────────────────────────────────────────────────────────────
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
        render_big_numeral("Cross Delay (avg)", f"{cross_delay:.1f}", "s", "Side street impact", cross_delay <= 15.0)
    with k3:
        render_big_numeral("Attack Defense", f"{atk_rate * 100:.0f}", "%", "Zero leakage", True)
    with k4:
        render_big_numeral("False Rejections", f"{fp_rate * 100:.1f}", "%", "0 legitimate blocked", fp_rate == 0.0)
    with k5:
        render_big_numeral("Ambulance Stops", str(stops), "", "0 stops = green wave", stops == 0)

    # ── 2-Column Responsive Layout: Map (60%) vs Inspector Tabs (40%) ───────────
    c_map, c_diag = st.columns([6, 4])

    with c_map:
        st.markdown('<div class="cp-card">', unsafe_allow_html=True)
        st.markdown("### Microscopic Traffic Grid & Active Route")

        # Accessible Signal Legend
        st.markdown(
            """
            <div style="display:flex; gap:12px; font-size:0.75rem; margin-bottom:8px; flex-wrap:wrap;">
                <span><span style="color:#2F9E55; font-weight:700;">G</span> Green</span>
                <span><span style="color:#C99A1B; font-weight:700;">Y</span> Yellow</span>
                <span><span style="color:#D6453A; font-weight:700;">R</span> Red</span>
                <span><span style="color:var(--cp-accent); font-weight:700;">&bull;</span> Ambulance</span>
                <span><span style="font-weight:700;">+</span> Hospital</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        fig_grid = build_grid_figure(
            snap=snap,
            engine=engine,
            incident_locs=st.session_state.incident_locs,
            dark_mode=st.session_state.get("dark_mode", False),
        )
        st.plotly_chart(fig_grid, use_container_width=True, config={"displayModeBar": False})

        st.caption(
            f"Tick: {snap['tick']} | Vehicles: {len(snap['vehicles'])} | Active Ambulances: {len(engine._active_ambulances)} | Signals: 36 (6x6 Grid)"
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c_diag:
        st.markdown('<div class="cp-card">', unsafe_allow_html=True)
        tab_sec, tab_guide, tab_bus, tab_disp, tab_metrics = st.tabs(
            ["Security", "Guidance", "Agent Bus", "Hospital Triage", "Metrics & Policy"]
        )

        with tab_sec:
            st.markdown("#### Security Gateway Decision")
            verdict = st.session_state.get("last_verdict")
            if verdict:
                auth = verdict.get("auth")
                allowed = verdict.get("authenticated", False)
                reasons = getattr(auth, "reasons", []) if auth else []
                risk = getattr(auth, "risk_score", 0.0) if auth else 0.0
                atk_lbl = st.session_state.get("last_verdict_atk") or "Legitimate"

                status_color = "var(--cp-signal-green)" if allowed else "var(--cp-signal-red)"
                status_text = "ALLOWED - VALID HMAC SIGNATURE" if allowed else "BLOCKED - ATTACK REJECTED"
                reasons_text = ", ".join(reasons) if reasons else "None (Verified)"

                st.markdown(
                    f"""
                    <div style="border:1px solid {status_color}; padding:12px; border-radius:4px; margin-bottom:12px;">
                        <div style="font-weight:700; color:{status_color}; font-size:0.95rem;">{status_text}</div>
                        <div style="font-size:0.8rem; margin-top:4px;">Vector: <b>{atk_lbl.replace('_', ' ').title()}</b> | Risk Score: <b>{risk:.2f}</b></div>
                        <div style="font-size:0.75rem; color:var(--cp-muted);">Reason Codes: {reasons_text}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.caption("Awaiting preemption authentication requests.")

            st.markdown("#### Audit Trail (Last 20)")
            audit = engine.security.audit_trail[-20:]
            if audit:
                audit_rows = []
                for entry in reversed(audit):
                    allowed = entry.get("allowed", False)
                    audit_rows.append({
                        "t (s)": f"{entry.get('ts', 0):.1f}",
                        "Vehicle": entry.get("vehicle_id", "")[:14],
                        "Verdict": "ALLOW" if allowed else "BLOCK",
                        "Risk": f"{entry.get('risk_score', 0):.2f}",
                        "Reasons": ", ".join(entry.get("reasons", [])) or "None",
                    })
                st.dataframe(pd.DataFrame(audit_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No security verification events recorded yet.")

            rc = dict(engine.security.reason_counts)
            if rc:
                st.markdown("#### Attack Block Reasons")
                fig_rc = build_reason_figure(rc, dark_mode=st.session_state.get("dark_mode", False))
                st.plotly_chart(fig_rc, use_container_width=True, config={"displayModeBar": False})

        with tab_guide:
            st.markdown("#### Driver Advisory Feed")
            advisories = list(engine.guidance.advisory_feed)[-15:]
            if advisories:
                for rec in reversed(advisories):
                    sev = getattr(rec, "severity", "INFO")
                    sev_col = "var(--cp-signal-red)" if sev == "CRITICAL" else ("var(--cp-signal-yellow)" if sev == "WARN" else "var(--cp-signal-green)")
                    st.markdown(
                        f"""
                        <div style="border-bottom:1px solid var(--cp-rule); padding:8px 0; font-size:0.82rem;">
                            <span style="color:{sev_col}; font-weight:700;">[{sev}]</span> <b>t={rec.t:.0f}s:</b> {rec.text}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No active guidance advisories. Dispatch an emergency vehicle to observe route clearing.")

            st.markdown("#### Dynamic VMS Signs")
            vms = snap.get("vms_board", {})
            if vms:
                for jid, msg in vms.items():
                    st.markdown(f"**[{jid}]**: `{msg}`")
            else:
                st.caption("Corridor normal. Speed limit 50 km/h. All signals cycling autonomously.")

        with tab_bus:
            st.markdown("#### Message Bus Feed (Last 25)")
            bus_msgs = engine.bus.message_log[-25:]
            if bus_msgs:
                feed = []
                for m in reversed(bus_msgs):
                    feed.append({
                        "t (s)": f"{getattr(m, 'ts', 0):.0f}",
                        "Type": getattr(m, "type", type(m).__name__),
                        "Sender": str(getattr(m, "sender", ""))[:14],
                        "Recipient": str(getattr(m, "recipient", ""))[:14],
                    })
                st.dataframe(pd.DataFrame(feed), use_container_width=True, hide_index=True)
            else:
                st.caption("Message bus initialized. Start simulation to observe inter-agent messages.")

            st.markdown("#### Junction Controllers")
            jstates = []
            for jid, jagent in list(engine.junctions.items())[:12]:
                jstates.append({
                    "Junction": jid,
                    "Signal": snap["signals"].get(jid, "-"),
                    "Phase": jagent.state.value,
                    "Vehicle": getattr(jagent, "_vehicle_id", None) or "None",
                })
            st.dataframe(pd.DataFrame(jstates), use_container_width=True, hide_index=True)

        with tab_disp:
            st.markdown("#### Hospital Capacity & Triage Table")
            hosps = []
            for h_id, hosp in engine.sim.network.hospitals.items():
                beds = sum(hosp.get("available_beds_by_unit", {}).values())
                hosps.append({
                    "Hospital ID": h_id,
                    "Name": hosp.get("name", ""),
                    "Beds": beds,
                    "Wait (min)": hosp.get("avg_wait_time_min", 0),
                    "Specialties": ", ".join(hosp.get("specialties", [])),
                })
            st.dataframe(pd.DataFrame(hosps), use_container_width=True, hide_index=True)

        with tab_metrics:
            st.markdown("#### Live Network Telemetry")
            fig_tel = build_telemetry_figure(history, dark_mode=st.session_state.get("dark_mode", False))
            st.plotly_chart(fig_tel, use_container_width=True, config={"displayModeBar": False})

            cmp = st.session_state.get("comparison_result")
            if cmp:
                st.markdown("#### 3-Way Policy Evaluation")
                fig_cmp = build_comparison_figure(cmp, dark_mode=st.session_state.get("dark_mode", False))
                st.plotly_chart(fig_cmp, use_container_width=True, config={"displayModeBar": False})

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__" or True:
    render_console_page()

