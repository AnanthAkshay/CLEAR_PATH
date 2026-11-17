"""ClearPath-lite Streamlit Dashboard.

Modern, responsive, accessible dashboard for real-time visualization of emergency
vehicle preemption, multi-agent corridor coordination, HMAC authentication,
and 3-way policy evaluation (Baseline vs Rule-Based Waves vs Trained RL).

Run with:
    streamlit run clearpath/dashboard/app.py
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Ensure project root is on sys.path ─────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import streamlit as st

# ── ClearPath modules ──────────────────────────────────────────────────────────
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
    render_active_emergency_card,
    render_guidance_card,
    render_header,
    render_hero,
    render_kpi_row,
    render_map_legend,
    render_security_verdict_card,
)
from clearpath.dashboard.theme import get_theme_css

# ─────────────────────────────────────────────────────────────────────────────
# Page configuration (MUST be the first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClearPath Emergency Preemption",
    page_icon="🚑",
    layout="wide",
    initial_sidebar_state="auto",
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────────────────────
# Request Helpers
# ─────────────────────────────────────────────────────────────────────────────
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
        sender="dashboard",
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
        sender="dashboard_fake",
    )


def _inner_plan(outer: Dict[str, Any]) -> Dict[str, Any]:
    return outer.get("plan") or {}


# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization
# ─────────────────────────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "engine": None,
        "running": False,
        "snapshot_history": [],
        "last_verdict": None,
        "last_verdict_atk": None,
        "comparison_result": None,
        "pending_emergency": False,
        "pending_fake": False,
        "incident_locs": {},
        "dark_mode": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar Controls
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🚑 ClearPath Control Center")
    st.markdown("---")

    col_theme1, col_theme2 = st.columns([3, 1])
    with col_theme1:
        st.markdown("**UI Theme**")
    with col_theme2:
        dark_toggle = st.toggle("Dark", value=st.session_state.dark_mode, label_visibility="collapsed")
        if dark_toggle != st.session_state.dark_mode:
            st.session_state.dark_mode = dark_toggle
            st.rerun()

    scenario_name = st.selectbox("Scenario", list(SCENARIOS.keys()), index=1)
    seed = st.number_input("Random seed", min_value=0, max_value=9999, value=42, step=1)
    demand_level = st.selectbox("Traffic demand", DEMAND_LEVELS, index=1)
    incident_type = st.selectbox("Incident type", INCIDENT_TYPES, index=0)

    st.markdown("---")
    st.markdown("**Preemption Parameters**")
    preemption_window = st.slider("Preemption window (s)", 10, 60, 25, 5)
    queue_flush_thr = st.slider("Queue-flush threshold", 4, 24, 12, 1)
    alpha = st.slider("Dispatcher α (travel weight)", 0.0, 1.0, 0.7, 0.05)
    sim_speed = st.slider("Sim speed (ticks/refresh)", 1, 20, 3, 1)

    st.markdown("---")
    clearpath_on = st.toggle("ClearPath Preemption ON", value=True)
    policy_choice = st.selectbox(
        "Junction Policy",
        ["Rule-based (Heuristics)", "RL (Trained Q-Net)"],
        index=0,
        help="Select JunctionAgent policy: rule-based corridor negotiation or trained RL policy",
    )
    junction_policy = "rl" if "RL" in policy_choice else "rule"

    st.markdown("---")
    st.markdown("**Simulation State**")
    c1, c2 = st.columns(2)
    with c1:
        start_btn = st.button("▶ Start", width="stretch", type="primary")
        step_btn = st.button("⏭ Step", width="stretch")
    with c2:
        pause_btn = st.button("⏸ Pause", width="stretch")
        reset_btn = st.button("🔄 Reset", width="stretch")

    st.markdown("---")
    st.markdown("**Corridor Actions**")
    send_emg_btn = st.button("🚨 Send Emergency Request", width="stretch", type="primary")
    send_fake_btn = st.button("💀 Inject Spoofed Request", width="stretch")

    st.markdown("---")
    st.markdown("**Security Testing**")
    attack_type = st.selectbox(
        "Attack vector",
        ATTACK_TYPES,
        format_func=lambda x: x.replace("_", " ").title(),
    )
    fire_attack_btn = st.button("🔥 Fire Attack & Verify", width="stretch")

    st.markdown("---")
    compare_btn = st.button("⚖️ Run 3-Way Policy Comparison", width="stretch")


# ── Inject Responsive CSS & Design Tokens ─────────────────────────────────────
st.markdown(get_theme_css(st.session_state.dark_mode), unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Engine Initializer & Lifecycle
# ─────────────────────────────────────────────────────────────────────────────
def _make_config(seed_val: int, win: int, q: int, a: float) -> SimConfig:
    return load_config(
        seed=int(seed_val),
        window_s=win,
        queue_flush_threshold=q,
        alpha=a,
        max_ticks=900,
    )


def _ensure_engine(rebuild: bool = False) -> ClearPathEngine:
    cfg = _make_config(int(seed), preemption_window, queue_flush_thr, alpha)
    current_pol = (
        getattr(st.session_state.engine, "junction_policy", None)
        if st.session_state.engine
        else None
    )
    if st.session_state.engine is None or rebuild or current_pol != junction_policy:
        st.session_state.engine = ClearPathEngine(
            cfg,
            preemption_enabled=clearpath_on,
            demand_level=demand_level,
            junction_policy=junction_policy,
        )
        st.session_state.snapshot_history = []
        st.session_state.last_verdict = None
        st.session_state.comparison_result = None
        st.session_state.incident_locs = {}
    return st.session_state.engine


# ── Mobile Quick Controls Card (Header Expander) ─────────────────────────────
with st.expander("⚡ Mobile Quick Controls & Action Bar", expanded=False):
    st.caption("Convenient control bar for touchscreens and mobile viewports.")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        if st.button("▶ Run", key="m_start", width="stretch"):
            _ensure_engine()
            st.session_state.running = True
    with m_col2:
        if st.button("⏸ Pause", key="m_pause", width="stretch"):
            st.session_state.running = False
    with m_col3:
        if st.button("⏭ Step", key="m_step", width="stretch"):
            _ensure_engine().step()
    with m_col4:
        if st.button("🔄 Reset", key="m_reset", width="stretch"):
            _ensure_engine(rebuild=True)
            st.session_state.running = False
            st.rerun()

    m_btn1, m_btn2 = st.columns(2)
    with m_btn1:
        if st.button("🚨 Dispatch Emergency", key="m_emg", width="stretch"):
            st.session_state.pending_emergency = True
    with m_btn2:
        if st.button("🔥 Inject Attack", key="m_atk", width="stretch"):
            st.session_state.pending_fake = True


# ── Button Handlers ───────────────────────────────────────────────────────────
if reset_btn:
    _ensure_engine(rebuild=True)
    st.session_state.running = False
    st.rerun()

if start_btn:
    _ensure_engine()
    st.session_state.running = True

if pause_btn:
    st.session_state.running = False

if send_emg_btn:
    st.session_state.pending_emergency = True

if send_fake_btn:
    st.session_state.pending_fake = True


# ─────────────────────────────────────────────────────────────────────────────
# 3-Way Policy Comparison Execution
# ─────────────────────────────────────────────────────────────────────────────
if compare_btn:
    with st.spinner("Executing 3-Way Comparison: Baseline vs Rules vs RL (300 ticks each)…"):
        TICKS = 300
        cfg_cmp = _make_config(int(seed), preemption_window, queue_flush_thr, alpha)

        # 1. Baseline (Preemption OFF)
        base_eng = ClearPathEngine(cfg_cmp, preemption_enabled=False, demand_level=demand_level)
        for t in range(TICKS):
            base_eng.step()
            if t == 10:
                base_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
        base_m = base_eng.metrics.summary()

        # 2. Rule-Based Preemption (Coordinated Waves)
        rule_eng = ClearPathEngine(
            cfg_cmp,
            preemption_enabled=True,
            demand_level=demand_level,
            baseline=base_eng.metrics,
            junction_policy="rule",
        )
        for t in range(TICKS):
            rule_eng.step()
            if t == 10:
                cp_amb = rule_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                req = _build_valid_request(rule_eng, cp_amb)
                if req:
                    rule_eng.submit_emergency_request(req, incident_type, ground_truth_valid=True)
        rule_m = rule_eng.metrics.summary()

        # 3. Trained RL Policy with Safety Action Masking
        rl_eng = ClearPathEngine(
            cfg_cmp,
            preemption_enabled=True,
            demand_level=demand_level,
            baseline=base_eng.metrics,
            junction_policy="rl",
        )
        for t in range(TICKS):
            rl_eng.step()
            if t == 10:
                rl_amb = rl_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                req = _build_valid_request(rl_eng, rl_amb)
                if req:
                    rl_eng.submit_emergency_request(req, incident_type, ground_truth_valid=True)
        rl_m = rl_eng.metrics.summary()

        st.session_state.comparison_result = {
            "baseline": base_m,
            "rule": rule_m,
            "rl": rl_m,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Advancing Simulation Engine
# ─────────────────────────────────────────────────────────────────────────────
engine: ClearPathEngine = _ensure_engine()

if st.session_state.running:
    for _ in range(sim_speed):
        engine.step()

    # Fire pending valid emergency
    if st.session_state.pending_emergency:
        amb_ids = list(engine._active_ambulances.keys())
        if not amb_ids:
            new_id = engine.sim.spawn_ambulance("j_0_0", "j_5_5")
            req = _build_valid_request(engine, new_id)
        else:
            req = _build_valid_request(engine, amb_ids[0])

        if req:
            result = engine.submit_emergency_request(req, incident_type, ground_truth_valid=True)
            st.session_state.last_verdict = result
            st.session_state.last_verdict_atk = None
            st.session_state.incident_locs[req.vehicle_id] = req.incident_loc
        st.session_state.pending_emergency = False

    # Fire pending fake request
    if st.session_state.pending_fake:
        fake_req = _build_fake_request(engine, attack_type)
        result = engine.submit_emergency_request(fake_req, "general", ground_truth_valid=False)
        st.session_state.last_verdict = result
        st.session_state.last_verdict_atk = attack_type
        st.session_state.pending_fake = False

elif step_btn:
    engine.step()

if fire_attack_btn:
    fake_req = _build_fake_request(engine, attack_type)
    result = engine.submit_emergency_request(fake_req, "general", ground_truth_valid=False)
    st.session_state.last_verdict = result
    st.session_state.last_verdict_atk = attack_type


# ── Take Engine Snapshot ───────────────────────────────────────────────────────
snap: Dict[str, Any] = engine.snapshot()
ms: Dict[str, Any] = snap["metrics_summary"]

st.session_state.snapshot_history.append(snap)
if len(st.session_state.snapshot_history) > 600:
    st.session_state.snapshot_history = st.session_state.snapshot_history[-600:]
history: List[Dict] = st.session_state.snapshot_history


# ─────────────────────────────────────────────────────────────────────────────
# 1. Header Bar
# ─────────────────────────────────────────────────────────────────────────────
alerts_count = ms.get("security_blocked_attacks", ms.get("security_blocked", 0))
render_header(
    running=st.session_state.running,
    preemption_enabled=snap["preemption_enabled"],
    tick=snap["tick"],
    scenario_name=scenario_name,
    alerts_count=alerts_count,
)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Hero Section (Big-Number Savings & Pale-Green Active Emergency Card)
# ─────────────────────────────────────────────────────────────────────────────
amb_time = ms.get("ambulance_travel_time_s")
improvement = ms.get("ambulance_improvement_pct")
baseline_time = 145.0  # reference baseline

# Calculate seconds saved
time_saved_s = (baseline_time - amb_time) if (amb_time and baseline_time > amb_time) else None

# Active emergency details
active_ambs = list(engine._active_ambulances.keys())
amb_id = active_ambs[0] if active_ambs else "AMB_001"
plan = _inner_plan(engine._active_ambulances.get(amb_id, {}))
eta_s = plan.get("total_eta_s", 78.0)
hospital_id = plan.get("hospital_id", "hosp_east")
hospital_obj = engine.sim.network.hospitals.get(hospital_id, {})
hospital_name = hospital_obj.get("name", "St. Jude Trauma Center")
reserved_count = len(plan.get("path", [])) or 5

c_hero_l, c_hero_r = st.columns([1.2, 1.0])
with c_hero_l:
    render_hero(
        time_saved_s=time_saved_s,
        improvement_pct=improvement,
        baseline_time_s=baseline_time,
        clearpath_time_s=amb_time,
    )
with c_hero_r:
    render_active_emergency_card(
        incident_type=incident_type,
        hospital_name=hospital_name,
        eta_s=eta_s,
        reserved_count=reserved_count,
        amb_id=amb_id,
        is_active=len(active_ambs) > 0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. 5 KPI Cards Row
# ─────────────────────────────────────────────────────────────────────────────
cross_delay = ms.get("cross_delay_avg_s", 0.0)
attack_block_rate = ms.get(
    "security_attack_block_rate", ms.get("security_block_rate", 1.0)
)
fp_rate = ms.get("security_false_positive_rate", 0.0)
avg_queue = ms.get("network_max_queue", 0)
amb_stops = ms.get("ambulance_stops", 0)
fp_count = ms.get("security_false_reject", 0)

render_kpi_row(
    cross_delay_s=cross_delay,
    attack_block_rate=attack_block_rate,
    fp_rate=fp_rate,
    avg_queue=float(avg_queue),
    amb_stops=amb_stops,
    blocked_count=alerts_count,
    fp_count=fp_count,
)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Main Responsive Section (Map Card ~2/3 + Diagnostic Tabs 1/3)
# ─────────────────────────────────────────────────────────────────────────────
col_map, col_diagnostics = st.columns([7, 5])

# ── Left Column: Road Network Map Card ────────────────────────────────────────
with col_map.container(border=True):
    st.markdown("### 🗺️ Microscopic Road Grid & Corridor Telemetry")
    render_map_legend()

    fig_map = build_grid_figure(
        snap=snap,
        engine=engine,
        incident_locs=st.session_state.incident_locs,
        dark_mode=st.session_state.dark_mode,
    )
    st.plotly_chart(fig_map, width="stretch", config={"displayModeBar": False})

    # Bottom status bar inside card
    n_amb = len(snap.get("active_ambulances", []))
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.78rem; color:var(--cp-ink-muted); padding-top:8px; border-top:1px solid var(--cp-border); flex-wrap:wrap; gap:8px;">
            <span>Sim Vehicles: <b>{len(snap['vehicles'])}</b></span>
            <span>Active Ambulances: <b>{n_amb}</b></span>
            <span>Junctions: <b>{len(engine.junctions)}</b></span>
            <span>Corridor Status: <b>{'🟢 Green Wave Active' if n_amb > 0 else '⚪ Standby'}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Right Column: Diagnostic & Inspector Tabs ─────────────────────────────────
with col_diagnostics.container(border=True):
    tab_agents, tab_sec, tab_disp, tab_guide, tab_metrics = st.tabs(
        ["🤖 Agents", "🔒 Security", "📡 Dispatcher", "💬 Guidance", "📈 Metrics"]
    )

    # ── Tab 1: Agents & Bus Feed ──────────────────────────────────────────────
    with tab_agents:
        st.markdown("#### Message-Bus Activity (Last 30)")
        bus_msgs = engine.bus.message_log[-30:]
        feed_rows = []
        for msg in reversed(bus_msgs):
            mtype = getattr(msg, "type", type(msg).__name__)
            sender = str(getattr(msg, "sender", ""))
            recip = str(getattr(msg, "recipient", ""))
            ts = getattr(msg, "ts", 0)
            feed_rows.append({
                "t (s)": f"{ts:.0f}",
                "Message Type": mtype,
                "Sender": sender[:16],
                "Recipient": recip[:16],
            })
        if feed_rows:
            st.dataframe(pd.DataFrame(feed_rows), width="stretch", height=230, hide_index=True)
        else:
            st.caption("No messages published yet — start the simulation to observe agent negotiation.")

        st.markdown("#### Junction Controller States")
        jstate_rows = []
        for jid, jagent in engine.junctions.items():
            phase = snap["signals"].get(jid, "—")
            vid = getattr(jagent, "_vehicle_id", None) or "—"
            jstate_rows.append({
                "Junction": jid,
                "Signal": phase,
                "Agent Phase": jagent.state.value,
                "Ambulance": vid,
            })
        st.dataframe(pd.DataFrame(jstate_rows), width="stretch", height=250, hide_index=True)

    # ── Tab 2: Security Sentinel ──────────────────────────────────────────────
    with tab_sec:
        st.markdown("#### Security Gateway Decision")
        render_security_verdict_card(
            st.session_state.last_verdict,
            st.session_state.last_verdict_atk,
        )

        st.markdown("#### Cryptographic Audit Log")
        audit = engine.security.audit_trail[-30:]
        if audit:
            rows = []
            for entry in reversed(audit):
                allowed = entry.get("allowed", False)
                rows.append({
                    "t (s)": f"{entry.get('ts', 0):.1f}",
                    "Vehicle": entry.get("vehicle_id", "")[:18],
                    "Verdict": "ALLOW" if allowed else "BLOCK",
                    "Risk": f"{entry.get('risk_score', 0):.2f}",
                    "Reasons": ", ".join(entry.get("reasons", [])) or "None",
                })
            df_audit = pd.DataFrame(rows)
            st.dataframe(df_audit, width="stretch", height=190, hide_index=True)
        else:
            st.caption("No authentication verification events yet.")

        # Block-reason histogram
        rc = dict(engine.security.reason_counts)
        if rc:
            st.markdown("#### Block-Reason Histogram")
            fig_rc = build_reason_figure(rc, dark_mode=st.session_state.dark_mode)
            st.plotly_chart(fig_rc, width="stretch", config={"displayModeBar": False})

    # ── Tab 3: Dispatcher & Hospital Triage ────────────────────────────────────
    with tab_disp:
        st.markdown("#### Hospital Capacity & Triage Ranking")
        network = engine.sim.network
        hosp_rows = []
        for h_id, hosp in network.hospitals.items():
            beds = sum(hosp.get("available_beds_by_unit", {}).values())
            hosp_rows.append({
                "ID": h_id,
                "Hospital Name": hosp.get("name", ""),
                "Beds": beds,
                "Wait (min)": hosp.get("avg_wait_time_min", 0),
                "Specialties": ", ".join(hosp.get("specialties", [])),
            })
        st.dataframe(pd.DataFrame(hosp_rows), width="stretch", height=200, hide_index=True)

        st.markdown("#### Active Route ETA Schedule")
        active_plans = engine._active_ambulances
        if active_plans:
            for amb_id_key, outer in active_plans.items():
                inner = _inner_plan(outer)
                path = inner.get("path", [])
                eta_map = inner.get("eta_by_junction", {})
                hosp_dest = inner.get("hospital_id", "?")
                if path and eta_map:
                    eta_rows = [
                        {"Junction": n, "ETA (s)": f"{eta_map.get(n, 0):.1f}"}
                        for n in path
                        if n in eta_map
                    ]
                    st.caption(f"**{amb_id_key}** → {hosp_dest} (Est. Travel: {inner.get('total_eta_s', 0):.0f}s)")
                    st.dataframe(pd.DataFrame(eta_rows), width="stretch", height=160, hide_index=True)
                else:
                    st.caption(f"{amb_id_key}: Calculating route…")
        else:
            st.caption("No active emergency routes. Dispatch an emergency to observe multi-junction scheduling.")

    # ── Tab 4: Citizen Guidance & VMS ─────────────────────────────────────────
    with tab_guide:
        render_guidance_card(
            advisories=list(engine.guidance.advisory_feed),
            vms_board=snap.get("vms_board", {}),
        )

    # ── Tab 5: Live Metrics & 3-Way Policy Comparison ──────────────────────────
    with tab_metrics:
        st.markdown("#### Live Telemetry Timeseries")
        fig_m = build_telemetry_figure(history, dark_mode=st.session_state.dark_mode)
        st.plotly_chart(fig_m, width="stretch", config={"displayModeBar": False})

        st.markdown("#### ⚖️ 3-Way Policy Evaluation: Baseline vs Rules vs RL")
        cmp = st.session_state.comparison_result
        if cmp:
            fig_cmp = build_comparison_figure(cmp, dark_mode=st.session_state.dark_mode)
            st.plotly_chart(fig_cmp, width="stretch", config={"displayModeBar": False})

            bm = cmp.get("baseline", {})
            rm = cmp.get("rule", cmp.get("clearpath", {}))
            rlm = cmp.get("rl", {})
            cmp_metrics = [
                ("Ambulance travel (s)", "ambulance_travel_time_s"),
                ("Ambulance stops", "ambulance_stops"),
                ("Cross-delay avg (s)", "cross_delay_avg_s"),
                ("Attack block rate", "security_attack_block_rate"),
                ("False-positive rate", "security_false_positive_rate"),
                ("Avg speed (m/s)", "network_avg_speed_mps"),
                ("Max queue", "network_max_queue"),
            ]
            labels = [m[0] for m in cmp_metrics]
            base_vals = [float(bm.get(m[1]) or 0) for m in cmp_metrics]
            rule_vals = [float(rm.get(m[1]) or 0) for m in cmp_metrics]
            rl_vals = [float(rlm.get(m[1]) or 0) for m in cmp_metrics] if rlm else []

            table_data = {
                "Metric": labels,
                "Baseline": [f"{v:.2f}" for v in base_vals],
                "Rule-based": [f"{v:.2f}" for v in rule_vals],
                "Rule Δ": [f"{(r - b):+.2f}" for b, r in zip(base_vals, rule_vals)],
            }
            if rl_vals:
                table_data["RL Policy"] = [f"{v:.2f}" for v in rl_vals]
                table_data["RL Δ"] = [f"{(rl - b):+.2f}" for b, rl in zip(base_vals, rl_vals)]

            st.dataframe(pd.DataFrame(table_data), width="stretch", height=240, hide_index=True)

            b_time = float(bm.get("ambulance_travel_time_s") or 0)
            r_time = float(rm.get("ambulance_travel_time_s") or 0)
            rl_time = float(rlm.get("ambulance_travel_time_s") or 0) if rlm else 0
            if r_time > 0 and rl_time > 0:
                st.info(
                    f"**Evaluation Summary**  \n"
                    f"• Baseline Transit: **{b_time:.1f}s**  \n"
                    f"• Rule-Based Preemption: **{r_time:.1f}s** ({((b_time - r_time) / b_time * 100.0) if b_time else 0:+.1f}% improvement)  \n"
                    f"• RL Policy Preemption: **{rl_time:.1f}s** ({((b_time - rl_time) / b_time * 100.0) if b_time else 0:+.1f}% improvement)  \n"
                    f"Both active policies enforce zero conflicting greens via junction action masking."
                )
        else:
            st.caption("Click **⚖️ Run 3-Way Policy Comparison** in the sidebar to run an automated 3-way evaluation benchmark.")


# ─────────────────────────────────────────────────────────────────────────────
# Auto-refresh loop while simulation is running
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(0.25)
    st.rerun()
