"""ClearPath-lite Streamlit Dashboard.

Imports ClearPathEngine directly and drives the simulation tick-by-tick with
Plotly visualisations, a live message-bus feed, security audit log, dispatcher
hospital ranking, guidance advisories, metrics charts, and a side-by-side
baseline comparison.

Run with:
    streamlit run clearpath/dashboard/app.py
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── ensure the project root is on sys.path ────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# ── ClearPath imports ─────────────────────────────────────────────────────────
from clearpath.agents.tokens import issue_token
from clearpath.bus.messages import PreemptionRequest, Telemetry
from clearpath.config import SimConfig, load_config
from clearpath.engine.orchestrator import ClearPathEngine

# ─────────────────────────────────────────────────────────────────────────────
# Page config  (must be the FIRST Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClearPath-lite Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Dark-theme CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] { background:#0e1117; color:#fafafa; }
    [data-testid="stSidebar"]          { background:#161b22; }
    .kpi-card {
        background:#1c2333; border:1px solid #30363d; border-radius:10px;
        padding:16px 20px; text-align:center; margin-bottom:8px;
    }
    .kpi-label { font-size:.78rem; color:#8b949e; text-transform:uppercase; letter-spacing:.06em; }
    .kpi-value { font-size:1.9rem; font-weight:700; color:#e6edf3; margin:4px 0; }
    .kpi-delta-good { font-size:.85rem; color:#3fb950; }
    .kpi-delta-bad  { font-size:.85rem; color:#f85149; }
    .kpi-delta-neu  { font-size:.85rem; color:#8b949e; }
    .verdict-allow { background:#196b2e; border-radius:8px; padding:12px; margin:8px 0; }
    .verdict-block { background:#6e1c1c; border-radius:8px; padding:12px; margin:8px 0; }
    #MainMenu, footer { visibility:hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
SCENARIOS = {
    "Normal traffic":   {"inject_emergency": False, "inject_fake": False},
    "Valid emergency":  {"inject_emergency": True,  "inject_fake": False},
    "Spoofed request":  {"inject_emergency": False, "inject_fake": True},
    "Mixed":            {"inject_emergency": True,  "inject_fake": True},
}

INCIDENT_TYPES = ["trauma", "cardiac", "stroke", "general"]
DEMAND_LEVELS  = ["low", "med", "high"]
ATTACK_TYPES   = [
    "bad_signature",
    "replay",
    "teleport_spoofed_gps",
    "overspeed",
    "unknown_vehicle",
]

SIGNAL_COLORS = {
    "NS_GREEN":       "#2ea043",
    "NS_YELLOW":      "#d29922",
    "EW_GREEN":       "#2ea043",
    "EW_YELLOW":      "#d29922",
    "ALL_RED_TO_EW":  "#f85149",
    "ALL_RED_TO_NS":  "#f85149",
}

AGENT_MSG_COLORS = {
    "security":   "#f85149",
    "dispatcher": "#388bfd",
    "guidance":   "#3fb950",
    "junction":   "#a371f7",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a valid PreemptionRequest for a live ambulance
# ─────────────────────────────────────────────────────────────────────────────
def _build_valid_request(engine: ClearPathEngine, amb_id: str) -> Optional[PreemptionRequest]:
    vehicle = engine.sim.vehicles.get(amb_id)
    if vehicle is None:
        return None
    x, y    = engine.sim.network.edge_position(vehicle.edge, vehicle.offset_m)
    nonce   = str(uuid.uuid4())
    tick    = float(engine.current_tick)
    token   = issue_token(amb_id, nonce, tick, engine.config.hmac_secret)
    bearing = engine.sim.network.edge_bearing(*vehicle.edge)
    return PreemptionRequest(
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


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a deliberately malformed request
# ─────────────────────────────────────────────────────────────────────────────
def _build_fake_request(engine: ClearPathEngine, attack_type: str) -> PreemptionRequest:
    cfg   = engine.config
    graph = engine.sim.network.graph
    nodes = list(graph.nodes())

    import random
    rng = random.Random(99)
    n1  = rng.choice(nodes)
    neighbours = list(graph.successors(n1))
    n2  = neighbours[0] if neighbours else n1

    n1d  = graph.nodes[n1]
    bx, by = float(n1d["x"]), float(n1d["y"])
    tick   = float(engine.current_tick)
    vid    = "FAKE_AMB_001"
    nonce  = str(uuid.uuid4())

    if attack_type == "bad_signature":
        token = f"{vid}.{nonce}.{tick}.INVALIDSIG"

    elif attack_type == "replay":
        # Use a nonce that the security agent has already seen (tick=0 token)
        old_nonce = "replay-known-nonce"
        token     = issue_token(vid, old_nonce, 0.0, cfg.hmac_secret)
        # Pre-inject the nonce into the security agent's seen set so it triggers
        engine.security._nonces[old_nonce] = float(engine.current_tick)
        nonce = old_nonce

    elif attack_type == "teleport_spoofed_gps":
        bx   += 5000.0        # 5 km jump
        by   += 5000.0
        token = issue_token(vid, nonce, tick, cfg.hmac_secret)

    elif attack_type == "overspeed":
        token = issue_token(vid, nonce, tick, cfg.hmac_secret)

    elif attack_type == "unknown_vehicle":
        vid   = "UNKNOWN_VEH_XYZ"
        token = issue_token(vid, nonce, tick, "wrong-secret-key")

    else:
        token = "INVALID"

    speed   = cfg.ambulance_max_mps * 3.0 if attack_type == "overspeed" else 10.0
    bearing = (engine.sim.network.edge_bearing(n1, n2)
               if graph.has_edge(n1, n2) else 90.0)

    return PreemptionRequest(
        vehicle_id=vid,
        token=token,
        nonce=nonce,
        incident_loc=(bx, by),
        severity="HIGH",
        telemetry=Telemetry(
            x=bx, y=by,
            speed_mps=speed,
            accel_mps2=0.0,
            heading_deg=bearing,
            edge_id=f"{n1}_{n2}",
            lane=0,
            vehicle_id=vid,
        ),
        sender="dashboard_fake",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helper: safely unwrap the nested active-ambulance plan
#
#  engine._active_ambulances[vid] == {"plan": <dispatch_dict>, "start_tick": int}
#  <dispatch_dict> has: vehicle_id, path, hospital_id, eta_by_junction, ...
# ─────────────────────────────────────────────────────────────────────────────
def _inner_plan(outer: Dict[str, Any]) -> Dict[str, Any]:
    """Return the inner dispatch dict from an _active_ambulances entry."""
    return outer.get("plan") or {}


# ─────────────────────────────────────────────────────────────────────────────
# Session-state initialisation
# ─────────────────────────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "engine":           None,
        "running":          False,
        "snapshot_history": [],
        "last_verdict":     None,
        "last_verdict_atk": None,
        "comparison_result": None,
        "pending_emergency": False,
        "pending_fake":      False,
        "incident_locs":    {},   # amb_id -> (x, y) stored when request is sent
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚑 ClearPath-lite")
    st.markdown("---")

    scenario_name = st.selectbox("Scenario", list(SCENARIOS.keys()), index=1)
    seed          = st.number_input("Random seed", min_value=0, max_value=9999,
                                    value=42, step=1)
    demand_level  = st.selectbox("Traffic demand", DEMAND_LEVELS, index=1)
    incident_type = st.selectbox("Incident type", INCIDENT_TYPES, index=0)

    st.markdown("---")
    st.markdown("**Preemption parameters**")
    preemption_window = st.slider("Preemption window (s)", 10, 60, 25, 5)
    queue_flush_thr   = st.slider("Queue-flush threshold", 4, 24, 12, 1)
    alpha             = st.slider("Dispatcher α (travel weight)", 0.0, 1.0, 0.7, 0.05)
    sim_speed         = st.slider("Sim speed (ticks/refresh)", 1, 20, 3, 1)

    st.markdown("---")
    clearpath_on = st.toggle("ClearPath ON/OFF", value=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        start_btn = st.button("▶ Start", use_container_width=True, type="primary")
        step_btn  = st.button("⏭ Step",  use_container_width=True)
    with c2:
        pause_btn = st.button("⏸ Pause",  use_container_width=True)
        reset_btn = st.button("🔄 Reset", use_container_width=True)

    st.markdown("---")
    st.markdown("**Emergency controls**")
    send_emg_btn  = st.button("🚨 Send emergency request", use_container_width=True,
                               type="primary")
    send_fake_btn = st.button("💀 Inject FAKE request",    use_container_width=True)

    st.markdown("---")
    st.markdown("**Fake-request panel**")
    attack_type     = st.selectbox("Attack type", ATTACK_TYPES,
                                   format_func=lambda x: x.replace("_", " ").title())
    fire_attack_btn = st.button("🔥 Fire attack & show verdict",
                                use_container_width=True)

    st.markdown("---")
    compare_btn = st.button("⚖️ Run side-by-side comparison",
                            use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# Config / engine helpers
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
    if st.session_state.engine is None or rebuild:
        st.session_state.engine          = ClearPathEngine(cfg, preemption_enabled=clearpath_on,
                                                           demand_level=demand_level)
        st.session_state.snapshot_history = []
        st.session_state.last_verdict     = None
        st.session_state.comparison_result = None
        st.session_state.incident_locs    = {}
    return st.session_state.engine


# ── Button handlers ───────────────────────────────────────────────────────────
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
# Side-by-side comparison (headless, no rerun needed)
# ─────────────────────────────────────────────────────────────────────────────
if compare_btn:
    with st.spinner("Running Baseline + ClearPath headless (300 ticks each)…"):
        TICKS   = 300
        cfg_cmp = _make_config(int(seed), preemption_window, queue_flush_thr, alpha)

        # --- Baseline ---
        base_eng = ClearPathEngine(cfg_cmp, preemption_enabled=False,
                                   demand_level=demand_level)
        base_amb = None
        for t in range(TICKS):
            base_eng.step()
            if t == 10:
                base_amb = base_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
        base_m = base_eng.metrics.summary()

        # --- ClearPath ---
        cp_eng = ClearPathEngine(cfg_cmp, preemption_enabled=True,
                                 demand_level=demand_level,
                                 baseline=base_eng.metrics)
        cp_amb = None
        for t in range(TICKS):
            cp_eng.step()
            if t == 10:
                cp_amb = cp_eng.sim.spawn_ambulance("j_0_0", "j_5_5")
                req = _build_valid_request(cp_eng, cp_amb)
                if req:
                    cp_eng.submit_emergency_request(
                        req, incident_type, ground_truth_valid=True
                    )
        cp_m = cp_eng.metrics.summary()

        st.session_state.comparison_result = {"baseline": base_m, "clearpath": cp_m}


# ─────────────────────────────────────────────────────────────────────────────
# Get / build engine and advance simulation
# ─────────────────────────────────────────────────────────────────────────────
engine: ClearPathEngine = _ensure_engine()

if st.session_state.running:
    for _ in range(sim_speed):
        engine.step()

    # ── Fire pending valid emergency ──────────────────────────────────────
    if st.session_state.pending_emergency:
        amb_ids = list(engine._active_ambulances.keys())
        if not amb_ids:
            new_id = engine.sim.spawn_ambulance("j_0_0", "j_5_5")
            req    = _build_valid_request(engine, new_id)
        else:
            req = _build_valid_request(engine, amb_ids[0])

        if req:
            result = engine.submit_emergency_request(
                req, incident_type, ground_truth_valid=True
            )
            st.session_state.last_verdict     = result
            st.session_state.last_verdict_atk = None
            # store incident location for grid marker
            st.session_state.incident_locs[req.vehicle_id] = req.incident_loc
        st.session_state.pending_emergency = False

    # ── Fire pending fake request ─────────────────────────────────────────
    if st.session_state.pending_fake:
        fake_req = _build_fake_request(engine, attack_type)
        result   = engine.submit_emergency_request(fake_req, "general",
                                                   ground_truth_valid=False)
        st.session_state.last_verdict     = result
        st.session_state.last_verdict_atk = attack_type
        st.session_state.pending_fake     = False

elif step_btn:
    engine.step()

# Single-shot fire attack (regardless of run state)
if fire_attack_btn:
    fake_req = _build_fake_request(engine, attack_type)
    result   = engine.submit_emergency_request(fake_req, "general",
                                               ground_truth_valid=False)
    st.session_state.last_verdict     = result
    st.session_state.last_verdict_atk = attack_type

# Take snapshot
snap: Dict[str, Any] = engine.snapshot()
ms:   Dict[str, Any] = snap["metrics_summary"]

# Rolling snapshot history (capped at 600)
st.session_state.snapshot_history.append(snap)
if len(st.session_state.snapshot_history) > 600:
    st.session_state.snapshot_history = st.session_state.snapshot_history[-600:]
history: List[Dict] = st.session_state.snapshot_history


# ─────────────────────────────────────────────────────────────────────────────
# KPI cards
# ─────────────────────────────────────────────────────────────────────────────
def _kpi(label: str, value: str, delta: str = "", good: bool = True) -> str:
    dcls = ("kpi-delta-good" if good else "kpi-delta-bad") if delta else "kpi-delta-neu"
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="{dcls}">{delta}</div>'
        f"</div>"
    )


amb_time    = ms.get("ambulance_travel_time_s")
amb_stops   = ms.get("ambulance_stops", 0)
cross_delay = ms.get("cross_delay_avg_s", 0.0)
block_rate  = ms.get("security_block_rate", 0.0)
improvement = ms.get("ambulance_improvement_pct")

amb_val   = f"{amb_time:.0f}s" if amb_time else "—"
delta_str = f"▲ {improvement:+.1f}% vs baseline" if improvement else ""

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(
        _kpi("🚑 Ambulance transit", amb_val, delta_str, (improvement or 0) > 0),
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        _kpi("🚦 Cross-traffic delay", f"{cross_delay:.1f}s"),
        unsafe_allow_html=True,
    )
with k3:
    n_blocked = ms.get("security_blocked", 0)
    st.markdown(
        _kpi("🛡 Fake-request block rate", f"{block_rate*100:.0f}%",
             f"{n_blocked} blocked", True),
        unsafe_allow_html=True,
    )
with k4:
    st.markdown(
        _kpi("🛑 Ambulance stops", str(amb_stops), f"Tick {snap['tick']}", True),
        unsafe_allow_html=True,
    )

st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Plotly grid figure
# ─────────────────────────────────────────────────────────────────────────────
def _build_grid(snap: Dict, engine: ClearPathEngine) -> go.Figure:
    network = engine.sim.network
    graph   = network.graph
    cfg     = engine.config

    fig = go.Figure()
    fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        margin=dict(l=0, r=0, t=36, b=0),
        height=620,
        showlegend=True,
        legend=dict(bgcolor="#161b22", bordercolor="#30363d", borderwidth=1,
                    font=dict(color="#e6edf3", size=10), x=1.01, y=1),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   scaleanchor="x", scaleratio=1),
        title=dict(
            text=(f"Tick {snap['tick']}  |  "
                  f"{'🟢 ClearPath ON' if snap['preemption_enabled'] else '🔴 Baseline'}  |  "
                  f"Vehicles: {len(snap['vehicles'])}"),
            font=dict(color="#e6edf3", size=13), x=0.01,
        ),
    )

    # ── Road lines ──────────────────────────────────────────────────────────
    ex, ey = [], []
    for u, v in graph.edges():
        ux = graph.nodes[u]["x"]; uy = graph.nodes[u]["y"]
        vx = graph.nodes[v]["x"]; vy = graph.nodes[v]["y"]
        ex += [ux, vx, None]
        ey += [uy, vy, None]
    fig.add_trace(go.Scatter(
        x=ex, y=ey, mode="lines",
        line=dict(color="#21262d", width=2),
        name="Roads", hoverinfo="none",
    ))

    # ── Route corridor polyline ──────────────────────────────────────────────
    for amb_id, outer in engine._active_ambulances.items():
        inner = _inner_plan(outer)
        path  = inner.get("path", [])
        if len(path) >= 2:
            rx = [graph.nodes[n]["x"] for n in path if n in graph.nodes]
            ry = [graph.nodes[n]["y"] for n in path if n in graph.nodes]
            fig.add_trace(go.Scatter(
                x=rx, y=ry, mode="lines",
                line=dict(color="rgba(56,139,253,0.50)", width=10),
                name=f"Route ({amb_id})", hoverinfo="none",
            ))

    # ── Junction nodes ───────────────────────────────────────────────────────
    jx, jy, jcolor, jhover = [], [], [], []
    ring_x, ring_y = [], []

    for node in graph.nodes():
        nd    = graph.nodes[node]
        x, y  = float(nd["x"]), float(nd["y"])
        phase = snap["signals"].get(node, "NS_GREEN")
        col   = SIGNAL_COLORS.get(phase, "#2ea043")

        jagent  = engine.junctions.get(node)
        jstate  = jagent.state.value if jagent else "NORMAL"

        if jstate in ("PRE_CLEAR", "HOLD_GREEN", "RECOVERY"):
            ring_x.append(x); ring_y.append(y)

        jx.append(x); jy.append(y); jcolor.append(col)
        jhover.append(f"<b>{node}</b><br>Signal: {phase}<br>State: {jstate}")

    if ring_x:
        fig.add_trace(go.Scatter(
            x=ring_x, y=ring_y, mode="markers",
            marker=dict(size=30, color="rgba(0,0,0,0)",
                        line=dict(color="#d29922", width=3)),
            name="Preemption ring", hoverinfo="none",
        ))

    fig.add_trace(go.Scatter(
        x=jx, y=jy, mode="markers",
        marker=dict(size=14, color=jcolor,
                    line=dict(color="#30363d", width=1)),
        name="Junctions",
        text=jhover, hovertemplate="%{text}<extra></extra>",
    ))

    # ── Vehicles ─────────────────────────────────────────────────────────────
    car_x, car_y, car_c, car_h = [], [], [], []
    amb_x, amb_y, amb_h        = [], [], []

    for v in snap["vehicles"]:
        x, y     = v.get("x", 0.0), v.get("y", 0.0)
        kind     = v.get("kind", "car")
        spd      = v.get("speed_mps", 0.0)
        stopped  = v.get("is_stopped", False)
        wt       = v.get("wait_time_s", 0.0)

        if kind == "ambulance":
            amb_x.append(x); amb_y.append(y)
            amb_h.append(f"<b>🚑 {v['id']}</b><br>Speed: {spd:.1f} m/s<br>"
                         f"Stopped: {stopped}")
        else:
            if stopped:
                col = "#f85149"
            else:
                ratio = min(spd / max(cfg.arterial_mps, 1.0), 1.0)
                r = int(255 * (1 - ratio))
                g = int(200 * ratio)
                col = f"rgb({r},{g},50)"
            car_x.append(x); car_y.append(y)
            car_c.append(col)
            car_h.append(f"<b>{v['id']}</b><br>Speed: {spd:.1f} m/s<br>"
                         f"Wait: {wt:.0f}s")

    if car_x:
        fig.add_trace(go.Scatter(
            x=car_x, y=car_y, mode="markers",
            marker=dict(size=5, color=car_c,
                        line=dict(color="rgba(0,0,0,0.3)", width=0.5)),
            name="Civilian vehicles",
            text=car_h, hovertemplate="%{text}<extra></extra>",
        ))

    if amb_x:
        fig.add_trace(go.Scatter(
            x=amb_x, y=amb_y, mode="markers+text",
            marker=dict(size=22, color="#f78166", symbol="star",
                        line=dict(color="#ffffff", width=2)),
            text=["🚑"] * len(amb_x),
            textposition="top center",
            textfont=dict(size=14),
            name="Ambulance",
            customdata=amb_h,
            hovertemplate="%{customdata}<extra></extra>",
        ))

    # ── Hospitals ─────────────────────────────────────────────────────────────
    for h_id, hosp in network.hospitals.items():
        hnode = hosp.get("node", "")
        if hnode and hnode in graph.nodes:
            hx   = float(graph.nodes[hnode]["x"])
            hy   = float(graph.nodes[hnode]["y"])
            beds = sum(hosp.get("available_beds_by_unit", {}).values())
            fig.add_trace(go.Scatter(
                x=[hx], y=[hy], mode="markers+text",
                marker=dict(size=18, color="#f0883e", symbol="cross",
                            line=dict(color="#ffffff", width=2)),
                text=[f"🏥 {hosp.get('name','')[:12]}\n({beds}beds)"],
                textposition="top right",
                textfont=dict(size=8, color="#e6edf3"),
                name=f"Hospital: {hosp.get('name','')[:14]}",
                hovertemplate=(f"<b>{hosp.get('name','')}</b><br>"
                               f"Beds: {beds}<extra></extra>"),
            ))

    # ── Incident markers (stored when request was sent) ───────────────────────
    for amb_id, loc in st.session_state.incident_locs.items():
        if loc:
            fig.add_trace(go.Scatter(
                x=[loc[0]], y=[loc[1]], mode="markers",
                marker=dict(size=16, color="#f85149", symbol="x",
                            line=dict(color="#ffffff", width=2)),
                name=f"Incident ({amb_id})",
                hovertemplate=f"<b>Incident</b><br>{amb_id}<extra></extra>",
            ))

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Main layout: grid (left 3) + tabs (right 2)
# ─────────────────────────────────────────────────────────────────────────────
col_grid, col_tabs = st.columns([3, 2])

with col_grid:
    fig = _build_grid(snap, engine)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Right-column tabs
# ─────────────────────────────────────────────────────────────────────────────
with col_tabs:
    tab_agents, tab_sec, tab_disp, tab_guide, tab_metrics = st.tabs(
        ["🤖 Agents", "🔒 Security", "📡 Dispatcher", "💬 Guidance", "📈 Metrics"]
    )

    # ── Tab 1: Agents ─────────────────────────────────────────────────────────
    with tab_agents:
        st.markdown("#### Message-bus feed (last 30)")
        bus_msgs = engine.bus.message_log[-30:]
        feed_rows = []
        for msg in reversed(bus_msgs):
            mtype  = getattr(msg, "type", type(msg).__name__)
            sender = str(getattr(msg, "sender", ""))
            recip  = str(getattr(msg, "recipient", ""))
            ts     = getattr(msg, "ts", 0)
            feed_rows.append({
                "ts":   f"{ts:.0f}",
                "type": mtype,
                "from": sender[:18],
                "to":   recip[:18],
            })
        if feed_rows:
            st.dataframe(pd.DataFrame(feed_rows), use_container_width=True,
                         height=230, hide_index=True)
        else:
            st.caption("No messages yet — press ▶ Start.")

        st.markdown("#### Junction states")
        jstate_rows = []
        for jid, jagent in engine.junctions.items():
            phase  = snap["signals"].get(jid, "—")
            vid    = getattr(jagent, "_vehicle_id", None) or "—"
            jstate_rows.append({
                "Junction":    jid,
                "Signal":      phase,
                "Agent state": jagent.state.value,
                "Ambulance":   vid,
            })
        st.dataframe(pd.DataFrame(jstate_rows), use_container_width=True,
                     height=280, hide_index=True)

    # ── Tab 2: Security ───────────────────────────────────────────────────────
    with tab_sec:
        st.markdown("#### Audit log")
        audit = engine.security.audit_trail[-30:]
        if audit:
            rows = []
            for entry in reversed(audit):
                allowed = entry.get("allowed", False)
                rows.append({
                    "ts":      f"{entry.get('ts', 0):.1f}",
                    "vehicle": entry.get("vehicle_id", "")[:22],
                    "verdict": "ALLOW" if allowed else "BLOCK",
                    "risk":    f"{entry.get('risk_score', 0):.2f}",
                    "reasons": ", ".join(entry.get("reasons", [])) or "—",
                })
            df_audit = pd.DataFrame(rows)
            st.dataframe(df_audit, use_container_width=True,
                         height=200, hide_index=True)
        else:
            st.caption("No authentication events yet.")

        # Reason histogram
        rc = dict(engine.security.reason_counts)
        if rc:
            st.markdown("#### Block-reason histogram")
            fig_rc = go.Figure(go.Bar(
                x=list(rc.keys()), y=list(rc.values()),
                marker_color="#f85149",
                text=list(rc.values()), textposition="outside",
            ))
            fig_rc.update_layout(
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#e6edf3"), height=200,
                margin=dict(l=0, r=0, t=20, b=0),
                yaxis=dict(showgrid=True, gridcolor="#21262d"),
            )
            st.plotly_chart(fig_rc, use_container_width=True,
                            config={"displayModeBar": False})

        # Instant verdict banner
        verdict = st.session_state.last_verdict
        if verdict:
            auth    = verdict.get("auth")
            allowed = verdict.get("authenticated", False)
            reasons = getattr(auth, "reasons", []) if auth else []
            risk    = getattr(auth, "risk_score", 0.0) if auth else 0.0
            atk_lbl = (st.session_state.last_verdict_atk or "").replace("_", " ").title()
            cls  = "verdict-allow" if allowed else "verdict-block"
            icon = "✅" if allowed else "🚫"
            st.markdown(
                f'<div class="{cls}">'
                f'{icon} <b>{"ALLOWED" if allowed else "BLOCKED"}</b>'
                f'{"  |  Attack: " + atk_lbl if atk_lbl else ""}<br>'
                f'<small>Risk: {risk:.2f}  |  Reasons: {", ".join(reasons) or "none"}</small>'
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Tab 3: Dispatcher ─────────────────────────────────────────────────────
    with tab_disp:
        st.markdown("#### Hospital table")
        network = engine.sim.network
        hosp_rows = []
        for h_id, hosp in network.hospitals.items():
            beds = sum(hosp.get("available_beds_by_unit", {}).values())
            hosp_rows.append({
                "ID":          h_id,
                "Name":        hosp.get("name", ""),
                "Beds":        beds,
                "Wait (min)":  hosp.get("avg_wait_time_min", 0),
                "Specialties": ", ".join(hosp.get("specialties", [])),
            })
        st.dataframe(pd.DataFrame(hosp_rows), use_container_width=True,
                     height=200, hide_index=True)

        st.markdown("#### Active route ETA schedule")
        active_plans = engine._active_ambulances
        if active_plans:
            for amb_id, outer in active_plans.items():
                inner   = _inner_plan(outer)
                path    = inner.get("path", [])
                eta_map = inner.get("eta_by_junction", {})
                hospital_id = inner.get("hospital_id", "?")
                if path and eta_map:
                    eta_rows = [
                        {"Junction": n, "ETA (s)": f"{eta_map.get(n, 0):.1f}"}
                        for n in path if n in eta_map
                    ]
                    st.caption(f"**{amb_id}** → {hospital_id}  "
                               f"(total {inner.get('total_eta_s', 0):.0f}s)")
                    st.dataframe(pd.DataFrame(eta_rows), use_container_width=True,
                                 height=160, hide_index=True)
                else:
                    st.caption(f"{amb_id}: No route plan yet.")
        else:
            st.caption("No active ambulances. Send an emergency request first.")

    # ── Tab 4: Guidance ───────────────────────────────────────────────────────
    with tab_guide:
        st.markdown("#### Advisory feed")
        feed = list(engine.guidance.advisory_feed)[-30:]
        if feed:
            for rec in reversed(feed):
                sev  = rec.severity
                icon = {"CRITICAL": "🔴", "WARN": "🟡", "INFO": "🟢"}.get(sev, "⚪")
                vids = ", ".join(rec.vehicle_ids[:4])
                st.markdown(
                    f"{icon} **t={rec.t:.0f}** `[{sev}]` — {rec.text}  "
                    f"<small style='color:#8b949e'>{vids}</small>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No guidance advisories yet. Send an emergency request to trigger guidance.")

        st.markdown("#### VMS board")
        vms = snap.get("vms_board", {})
        if vms:
            for jid, msg in vms.items():
                st.info(f"**{jid}**: {msg}")
        else:
            st.caption("VMS board empty.")

    # ── Tab 5: Metrics ────────────────────────────────────────────────────────
    with tab_metrics:
        ticks   = [h["tick"] for h in history]
        ms_hist = [h["metrics_summary"] for h in history]

        speeds = [m.get("network_avg_speed_mps", m.get("network_avg_speed", 0)) for m in ms_hist]
        queues = [m.get("network_max_queue", 0)   for m in ms_hist]
        delays = [m.get("cross_delay_avg_s", 0.0) for m in ms_hist]

        fig_m = make_subplots(
            rows=3, cols=1, shared_xaxes=True,
            subplot_titles=["Avg speed (m/s)", "Max queue length", "Cross-traffic delay (s)"],
            vertical_spacing=0.08,
        )
        kw = dict(mode="lines", line=dict(width=1.5))
        fig_m.add_trace(go.Scatter(x=ticks, y=speeds, name="Speed",
                                   line=dict(color="#3fb950"), **kw), 1, 1)
        fig_m.add_trace(go.Scatter(x=ticks, y=queues, name="Queue",
                                   line=dict(color="#d29922"), **kw), 2, 1)
        fig_m.add_trace(go.Scatter(x=ticks, y=delays, name="Delay",
                                   line=dict(color="#f85149"), **kw), 3, 1)
        fig_m.update_layout(
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font=dict(color="#e6edf3", size=10),
            height=380, showlegend=False,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        for i in range(1, 4):
            fig_m.update_xaxes(gridcolor="#21262d", row=i, col=1)
            fig_m.update_yaxes(gridcolor="#21262d", row=i, col=1)
        st.plotly_chart(fig_m, use_container_width=True,
                        config={"displayModeBar": False})

        # ── Comparison bar chart ───────────────────────────────────────────
        cmp = st.session_state.comparison_result
        if cmp:
            bm, cm = cmp["baseline"], cmp["clearpath"]
            cmp_metrics = [
                ("Ambulance travel (s)",  "ambulance_travel_time_s"),
                ("Ambulance stops",       "ambulance_stops"),
                ("Cross-delay avg (s)",   "cross_delay_avg_s"),
                ("Security block rate",   "security_block_rate"),
                ("Avg speed (m/s)",       "network_avg_speed_mps"),
                ("Max queue",             "network_max_queue"),
            ]
            labels    = [m[0] for m in cmp_metrics]
            base_vals = [float(bm.get(m[1]) or 0) for m in cmp_metrics]
            cp_vals   = [float(cm.get(m[1]) or 0) for m in cmp_metrics]

            st.markdown("#### Baseline vs ClearPath comparison")
            fig_cmp = go.Figure(data=[
                go.Bar(name="Baseline",  x=labels, y=base_vals, marker_color="#8b949e"),
                go.Bar(name="ClearPath", x=labels, y=cp_vals,   marker_color="#388bfd"),
            ])
            fig_cmp.update_layout(
                barmode="group",
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                font=dict(color="#e6edf3", size=10),
                height=300,
                legend=dict(bgcolor="#161b22"),
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis=dict(tickangle=-30, gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d"),
            )
            st.plotly_chart(fig_cmp, use_container_width=True,
                            config={"displayModeBar": False})

            df_cmp = pd.DataFrame({
                "Metric":    labels,
                "Baseline":  [f"{v:.2f}" for v in base_vals],
                "ClearPath": [f"{v:.2f}" for v in cp_vals],
                "Δ":         [f"{(c-b):+.2f}" for b, c in zip(base_vals, cp_vals)],
            })
            st.dataframe(df_cmp, use_container_width=True, height=240, hide_index=True)
        else:
            st.caption("Click **⚖️ Run side-by-side comparison** in the sidebar to populate this chart.")


# ─────────────────────────────────────────────────────────────────────────────
# Status bar
# ─────────────────────────────────────────────────────────────────────────────
n_amb     = len(snap.get("active_ambulances", []))
n_blocked = len(snap.get("blocked_requests",  []))
mode_str  = "🟢 ClearPath ON" if snap["preemption_enabled"] else "🔴 Baseline"
run_str   = "▶ Running" if st.session_state.running else "⏸ Paused"

st.markdown(
    f"**Tick:** {snap['tick']}  |  **Vehicles:** {len(snap['vehicles'])}  |  "
    f"**Active ambulances:** {n_amb}  |  **Blocked requests:** {n_blocked}  |  "
    f"**Mode:** {mode_str}  |  {run_str}"
)

# ── Auto-refresh while running ────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(0.25)
    st.rerun()
