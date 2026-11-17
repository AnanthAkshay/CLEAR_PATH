"""Plotly chart and grid figure builders for ClearPath dashboard.

Strict editorial design:
- Transparent paper & plot backgrounds
- Hairline axes and grid lines
- Signals paired with accessible G / Y / R text annotations
- Zero drop shadows, zero gradients
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from clearpath.config import SimConfig
from clearpath.dashboard.theme import TOKENS
from clearpath.engine.orchestrator import ClearPathEngine

SIGNAL_PHASE_LABELS = {
    "NS_GREEN": "G (North-South)",
    "NS_YELLOW": "Y (North-South)",
    "EW_GREEN": "G (East-West)",
    "EW_YELLOW": "Y (East-West)",
    "ALL_RED_TO_EW": "R (All-Red)",
    "ALL_RED_TO_NS": "R (All-Red)",
}

SIGNAL_COLORS = {
    "NS_GREEN": "#2F9E55",
    "NS_YELLOW": "#C99A1B",
    "EW_GREEN": "#2F9E55",
    "EW_YELLOW": "#C99A1B",
    "ALL_RED_TO_EW": "#D6453A",
    "ALL_RED_TO_NS": "#D6453A",
}


def _inner_plan(outer: Dict[str, Any]) -> Dict[str, Any]:
    return outer.get("plan") or {}


def build_grid_figure(
    snap: Dict[str, Any],
    engine: ClearPathEngine,
    incident_locs: Dict[str, Any],
    dark_mode: bool = False,
) -> go.Figure:
    """Build the road grid map with signal states, route corridor, and vehicles."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    network = engine.sim.network
    graph = network.graph
    cfg = engine.config

    fig = go.Figure()

    # 1. Road lines (hairline)
    ex, ey = [], []
    for u, v in graph.edges():
        ux = graph.nodes[u]["x"]
        uy = graph.nodes[u]["y"]
        vx = graph.nodes[v]["x"]
        vy = graph.nodes[v]["y"]
        ex += [ux, vx, None]
        ey += [uy, vy, None]

    fig.add_trace(
        go.Scatter(
            x=ex,
            y=ey,
            mode="lines",
            line=dict(color=t["road_color"], width=1.5),
            name="Road Network",
            hoverinfo="none",
        )
    )

    # 2. Preempted corridor route polyline
    for amb_id, outer in engine._active_ambulances.items():
        inner = _inner_plan(outer)
        path = inner.get("path", [])
        if len(path) >= 2:
            rx = [graph.nodes[n]["x"] for n in path if n in graph.nodes]
            ry = [graph.nodes[n]["y"] for n in path if n in graph.nodes]
            fig.add_trace(
                go.Scatter(
                    x=rx,
                    y=ry,
                    mode="lines",
                    line=dict(color=t["accent"], width=4),
                    name=f"Corridor ({amb_id})",
                    hoverinfo="none",
                )
            )

    # 3. Junction nodes & preemption rings
    jx, jy, jcolor, jhover, jtext = [], [], [], [], []
    ring_x, ring_y = [], []

    for node in graph.nodes():
        nd = graph.nodes[node]
        x, y = float(nd["x"]), float(nd["y"])
        phase = snap["signals"].get(node, "NS_GREEN")
        col = SIGNAL_COLORS.get(phase, "#2F9E55")

        jagent = engine.junctions.get(node)
        jstate = jagent.state.value if jagent else "NORMAL"

        if jstate in ("PRE_CLEAR", "HOLD_GREEN", "RECOVERY"):
            ring_x.append(x)
            ring_y.append(y)

        short_phase = "G" if "GREEN" in phase else ("Y" if "YELLOW" in phase else "R")

        jx.append(x)
        jy.append(y)
        jcolor.append(col)
        jtext.append(short_phase)
        jhover.append(
            f"<b>Junction {node}</b><br>"
            f"Signal: <b>{SIGNAL_PHASE_LABELS.get(phase, phase)}</b><br>"
            f"Corridor Phase: <b>{jstate}</b>"
        )

    # Preemption rings
    if ring_x:
        fig.add_trace(
            go.Scatter(
                x=ring_x,
                y=ring_y,
                mode="markers",
                marker=dict(
                    size=26,
                    color="rgba(0,0,0,0)",
                    line=dict(color=t["signal_yellow"], width=1.5),
                ),
                name="Preemption Ring",
                hoverinfo="none",
            )
        )

    # Junction markers with G/Y/R text for accessibility
    fig.add_trace(
        go.Scatter(
            x=jx,
            y=jy,
            mode="markers+text",
            marker=dict(
                size=15,
                color=jcolor,
                line=dict(color=t["surface"], width=1),
            ),
            text=jtext,
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=8, family="IBM Plex Mono"),
            name="Signals (G/Y/R)",
            customdata=jhover,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )

    # 4. Civilian vehicles
    car_x, car_y, car_c, car_h = [], [], [], []
    amb_x, amb_y, amb_h = [], [], []

    for v in snap["vehicles"]:
        x, y = v.get("x", 0.0), v.get("y", 0.0)
        kind = v.get("kind", "car")
        spd = v.get("speed_mps", 0.0)
        stopped = v.get("is_stopped", False)
        wt = v.get("wait_time_s", 0.0)

        if kind == "ambulance":
            amb_x.append(x)
            amb_y.append(y)
            amb_h.append(
                f"<b>Ambulance {v['id']}</b><br>"
                f"Speed: {spd:.1f} m/s ({spd * 3.6:.0f} km/h)<br>"
                f"Status: {'Stopped' if stopped else 'En Route'}"
            )
        else:
            if stopped:
                col = t["signal_red"]
            else:
                ratio = min(spd / max(cfg.arterial_mps, 1.0), 1.0)
                col = t["signal_green"] if ratio > 0.5 else t["signal_yellow"]
            car_x.append(x)
            car_y.append(y)
            car_c.append(col)
            car_h.append(
                f"<b>Vehicle {v['id']}</b><br>"
                f"Speed: {spd:.1f} m/s<br>"
                f"Wait: {wt:.0f} s"
            )

    if car_x:
        fig.add_trace(
            go.Scatter(
                x=car_x,
                y=car_y,
                mode="markers",
                marker=dict(
                    size=5,
                    color=car_c,
                    line=dict(color="rgba(0,0,0,0.2)", width=0.5),
                ),
                name="Vehicles",
                text=car_h,
                hovertemplate="%{text}<extra></extra>",
            )
        )

    # Ambulance marker
    if amb_x:
        fig.add_trace(
            go.Scatter(
                x=amb_x,
                y=amb_y,
                mode="markers+text",
                marker=dict(
                    size=20,
                    color=t["accent"],
                    symbol="star",
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                text=["AMB"] * len(amb_x),
                textposition="top center",
                textfont=dict(size=10, family="IBM Plex Mono", color=t["accent"]),
                name="Ambulance",
                customdata=amb_h,
                hovertemplate="%{customdata}<extra></extra>",
            )
        )

    # 5. Hospitals
    for h_id, hosp in network.hospitals.items():
        hnode = hosp.get("node", "")
        if hnode and hnode in graph.nodes:
            hx = float(graph.nodes[hnode]["x"])
            hy = float(graph.nodes[hnode]["y"])
            beds = sum(hosp.get("available_beds_by_unit", {}).values())
            fig.add_trace(
                go.Scatter(
                    x=[hx],
                    y=[hy],
                    mode="markers+text",
                    marker=dict(
                        size=16,
                        color=t["ink"],
                        symbol="cross",
                        line=dict(color=t["surface"], width=1.5),
                    ),
                    text=[f"{hosp.get('name', '')[:10]} ({beds}b)"],
                    textposition="top right",
                    textfont=dict(size=9, color=t["ink"], family="Public Sans"),
                    name=f"Hospital: {hosp.get('name', '')[:12]}",
                    hovertemplate=(
                        f"<b>{hosp.get('name', '')}</b><br>"
                        f"Available Beds: <b>{beds}</b><br>"
                        f"Node: {hnode}<extra></extra>"
                    ),
                )
            )

    # 6. Incident markers
    for amb_id, loc in incident_locs.items():
        if loc:
            fig.add_trace(
                go.Scatter(
                    x=[loc[0]],
                    y=[loc[1]],
                    mode="markers+text",
                    marker=dict(
                        size=14,
                        color=t["signal_red"],
                        symbol="x",
                        line=dict(color=t["surface"], width=1.5),
                    ),
                    text=["INCIDENT"],
                    textposition="bottom center",
                    textfont=dict(size=9, color=t["signal_red"], family="IBM Plex Mono"),
                    name=f"Incident ({amb_id})",
                    hovertemplate=f"<b>Incident Location</b><br>Vehicle: {amb_id}<extra></extra>",
                )
            )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=4, r=4, t=12, b=4),
        height=500,
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor="x",
            scaleratio=1,
        ),
    )

    return fig


def build_telemetry_figure(
    history: List[Dict[str, Any]],
    dark_mode: bool = False,
) -> go.Figure:
    """Build telemetry timeseries figure for speed, queue, and cross-traffic delay."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    ticks = [h["tick"] for h in history]
    ms_hist = [h["metrics_summary"] for h in history]

    speeds = [
        m.get("network_avg_speed_mps", m.get("network_avg_speed", 0))
        for m in ms_hist
    ]
    queues = [m.get("network_max_queue", 0) for m in ms_hist]
    delays = [m.get("cross_delay_avg_s", 0.0) for m in ms_hist]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=[
            "Network Average Speed (m/s)",
            "Max Approach Queue Length",
            "Cross-Traffic Delay (s)",
        ],
        vertical_spacing=0.10,
    )

    fig.add_trace(
        go.Scatter(
            x=ticks,
            y=speeds,
            name="Speed",
            mode="lines",
            line=dict(color=t["signal_green"], width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=ticks,
            y=queues,
            name="Queue",
            mode="lines",
            line=dict(color=t["signal_yellow"], width=1.5),
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=ticks,
            y=delays,
            name="Delay",
            mode="lines",
            line=dict(color=t["signal_red"], width=1.5),
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["muted"], size=11, family="Public Sans"),
        height=380,
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
    )

    for i in range(1, 4):
        fig.update_xaxes(gridcolor=t["rule"], row=i, col=1)
        fig.update_yaxes(gridcolor=t["rule"], row=i, col=1)

    return fig


def build_reason_figure(
    reason_counts: Dict[str, int],
    dark_mode: bool = False,
) -> go.Figure:
    """Build horizontal bar chart for security block reasons."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    labels = [k.replace("_", " ").title() for k in reason_counts.keys()]
    values = list(reason_counts.values())

    fig = go.Figure(
        go.Bar(
            y=labels,
            x=values,
            orientation="h",
            marker=dict(
                color=t["signal_red"],
            ),
            text=values,
            textposition="outside",
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["muted"], size=11, family="Public Sans"),
        height=180,
        margin=dict(l=10, r=20, t=10, b=10),
        xaxis=dict(showgrid=True, gridcolor=t["rule"]),
        yaxis=dict(showgrid=False),
    )
    return fig


def build_comparison_figure(
    comparison_result: Dict[str, Any],
    dark_mode: bool = False,
) -> go.Figure:
    """Build 3-way policy comparison bar chart: Baseline vs Rule-based vs RL Policy."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    bm = comparison_result.get("baseline", {})
    rm = comparison_result.get("rule", comparison_result.get("clearpath", {}))
    rlm = comparison_result.get("rl", {})

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

    bars = [
        go.Bar(
            name="Baseline",
            x=labels,
            y=base_vals,
            marker_color=t["muted"],
        ),
        go.Bar(
            name="Rule-based (Waves)",
            x=labels,
            y=rule_vals,
            marker_color=t["accent"],
        ),
    ]
    if rl_vals:
        bars.append(
            go.Bar(
                name="RL Policy (Safety Masked)",
                x=labels,
                y=rl_vals,
                marker_color=t["signal_green"],
            )
        )

    fig = go.Figure(data=bars)
    fig.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["ink"], size=11, family="Public Sans"),
        height=320,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(l=10, r=10, t=30, b=20),
        xaxis=dict(tickangle=-25, gridcolor=t["rule"]),
        yaxis=dict(gridcolor=t["rule"]),
    )
    return fig
