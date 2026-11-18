"""Plotly chart and tactical grid figure builders for ClearPath dashboard.

Engineered with high-contrast mission-control visual aesthetics:
- Illuminated dark road grid with arterial road differentiation
- High-visibility ambulance tracking and active green-wave corridor halos
- Accessible G / Y / R signal status rings and glowing indicators
- Micro-telemetry graphs with responsive layouts and hovercards
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from clearpath.config import SimConfig
from clearpath.dashboard.locations import get_edge_label, get_location_cross, get_location_name
from clearpath.dashboard.theme import TOKENS
from clearpath.engine.orchestrator import ClearPathEngine

SIGNAL_PHASE_LABELS = {
    "NS_GREEN": "G (North-South Green)",
    "NS_YELLOW": "Y (North-South Yellow)",
    "EW_GREEN": "G (East-West Green)",
    "EW_YELLOW": "Y (East-West Yellow)",
    "ALL_RED_TO_EW": "R (All-Red Clearance)",
    "ALL_RED_TO_NS": "R (All-Red Clearance)",
}

SIGNAL_COLORS = {
    "NS_GREEN": "#10B981",
    "NS_YELLOW": "#F59E0B",
    "EW_GREEN": "#10B981",
    "EW_YELLOW": "#F59E0B",
    "ALL_RED_TO_EW": "#EF4444",
    "ALL_RED_TO_NS": "#EF4444",
}


def _inner_plan(outer: Dict[str, Any]) -> Dict[str, Any]:
    return outer.get("plan") or {}


def build_grid_figure(
    snap: Dict[str, Any],
    engine: ClearPathEngine,
    incident_locs: Dict[str, Any],
    dark_mode: bool = True,
) -> go.Figure:
    """Build the high-contrast tactical road grid map with vehicle and signal telemetry."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    network = engine.sim.network
    graph = network.graph
    cfg = engine.config

    fig = go.Figure()

    # 1. Road Network Grid Lines with Dynamic Live Traffic Heatmap
    densities = snap.get("densities", {})
    queues = snap.get("queues", {})

    ex_res, ey_res = [], []
    ex_art, ey_art = [], []
    ex_mod, ey_mod = [], []
    ex_jam, ey_jam = [], []

    jam_mx, jam_my, jam_texts = [], [], []
    mod_mx, mod_my, mod_texts = [], [], []

    for u, v in graph.edges():
        ux, uy = graph.nodes[u]["x"], graph.nodes[u]["y"]
        vx, vy = graph.nodes[v]["x"], graph.nodes[v]["y"]
        data = graph[u][v]
        rclass = data.get("road_class", "residential")
        length = float(data.get("length_m", 200.0))
        edge_key = f"{u}_{v}"

        d_val = float(densities.get(edge_key, 0.0))
        car_count = max(0, int(round(d_val * (length / 1000.0))))
        q_count = int(queues.get(edge_key, 0))

        mx, my = (ux + vx) / 2.0, (uy + vy) / 2.0
        edge_name = get_edge_label(u, v)

        if car_count >= 5 or q_count >= 3:
            ex_jam += [ux, vx, None]
            ey_jam += [uy, vy, None]
            jam_mx.append(mx)
            jam_my.append(my)
            jam_texts.append(
                f"🚨 <b>CONGESTION BOTTLENECK</b><br>"
                f"Corridor: <b>{edge_name}</b><br>"
                f"Civilian Vehicles: <b>{car_count} cars</b> ({d_val:.0f} veh/km)<br>"
                f"Signal Queue: <b>{q_count} stopped</b><br>"
                f"Ambulance Friction: <b>+{car_count * 3.5 + q_count * 4.0:.1f}s delay</b>"
            )
        elif car_count >= 2 or q_count >= 1:
            ex_mod += [ux, vx, None]
            ey_mod += [uy, vy, None]
            mod_mx.append(mx)
            mod_my.append(my)
            mod_texts.append(
                f"⚠️ <b>MODERATE TRAFFIC</b><br>"
                f"Corridor: <b>{edge_name}</b><br>"
                f"Civilian Vehicles: <b>{car_count} cars</b> ({d_val:.0f} veh/km)<br>"
                f"Signal Queue: <b>{q_count}</b><br>"
                f"Ambulance Friction: <b>+{car_count * 3.5 + q_count * 4.0:.1f}s delay</b>"
            )
        elif rclass == "arterial":
            ex_art += [ux, vx, None]
            ey_art += [uy, vy, None]
        else:
            ex_res += [ux, vx, None]
            ey_res += [uy, vy, None]

    # Clear Residential streets
    if ex_res:
        fig.add_trace(
            go.Scatter(
                x=ex_res,
                y=ey_res,
                mode="lines",
                line=dict(color=t["road_color"], width=2),
                name="Clear Residential Roads",
                hoverinfo="none",
            )
        )

    # Clear Arterial avenues
    if ex_art:
        fig.add_trace(
            go.Scatter(
                x=ex_art,
                y=ey_art,
                mode="lines",
                line=dict(color=t["road_arterial"], width=3.5),
                name="Clear Arterial Corridors",
                hoverinfo="none",
            )
        )

    # Moderate Traffic segments (Amber)
    if ex_mod:
        fig.add_trace(
            go.Scatter(
                x=ex_mod,
                y=ey_mod,
                mode="lines",
                line=dict(color="#F59E0B", width=4),
                name="Moderate Traffic (Amber)",
                hoverinfo="none",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=mod_mx,
                y=mod_my,
                mode="markers",
                marker=dict(symbol="diamond", size=10, color="#F59E0B"),
                hovertext=mod_texts,
                hoverinfo="text",
                name="Traffic Alert (Moderate)",
                showlegend=False,
            )
        )

    # Severe Traffic Jams / Bottlenecks (Red)
    if ex_jam:
        fig.add_trace(
            go.Scatter(
                x=ex_jam,
                y=ey_jam,
                mode="lines",
                line=dict(color="#EF4444", width=6),
                name="Traffic Bottleneck (Red)",
                hoverinfo="none",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=jam_mx,
                y=jam_my,
                mode="markers",
                marker=dict(symbol="octagon", size=14, color="#EF4444", line=dict(color="#FFFFFF", width=1.5)),
                hovertext=jam_texts,
                hoverinfo="text",
                name="Traffic Alert (Bottleneck)",
                showlegend=False,
            )
        )

    # 2. Preempted Green Wave Corridor Halos
    for amb_id, outer in engine._active_ambulances.items():
        inner = _inner_plan(outer)
        path = inner.get("path", [])
        if len(path) >= 2:
            rx = [graph.nodes[n]["x"] for n in path if n in graph.nodes]
            ry = [graph.nodes[n]["y"] for n in path if n in graph.nodes]

            # Glowing halo
            fig.add_trace(
                go.Scatter(
                    x=rx,
                    y=ry,
                    mode="lines",
                    line=dict(color=t["corridor_active"], width=8),
                    opacity=0.35,
                    name=f"Corridor Halo ({amb_id})",
                    hoverinfo="none",
                )
            )
            # Sharp core line
            fig.add_trace(
                go.Scatter(
                    x=rx,
                    y=ry,
                    mode="lines",
                    line=dict(color=t["corridor_active"], width=4),
                    name=f"Active Corridor ({amb_id})",
                    hoverinfo="none",
                )
            )

    # 3. Hospitals
    hx, hy, htext, hnames = [], [], [], []
    for h_id, h_data in network.hospitals.items():
        hx.append(float(h_data.get("x", 0.0)))
        hy.append(float(h_data.get("y", 0.0)))
        hnames.append(h_data.get("name", h_id))
        htext.append(
            f"<b>{h_data.get('name', h_id)}</b><br>"
            f"Available Beds: <b>{h_data.get('available_beds', 'N/A')}</b><br>"
            f"Emergency Wait: <b>{h_data.get('emergency_wait_min', 'N/A')} min</b>"
        )

    if hx:
        fig.add_trace(
            go.Scatter(
                x=hx,
                y=hy,
                mode="markers+text",
                marker=dict(
                    symbol="cross",
                    size=16,
                    color=t["hospital_blue"],
                    line=dict(color="#FFFFFF", width=1.5),
                ),
                text=[f"  {n}" for n in hnames],
                textposition="top right",
                textfont=dict(color=t["hospital_blue"], size=10, family="Plus Jakarta Sans"),
                name="Hospital Facilities",
                customdata=htext,
                hovertemplate="%{customdata}<extra></extra>",
            )
        )

    # 4. Junction Signals
    jx, jy, jcolor, jhover, jtext = [], [], [], [], []
    ring_x, ring_y, ring_color = [], [], []

    for node in graph.nodes():
        nd = graph.nodes[node]
        x, y = float(nd["x"]), float(nd["y"])
        phase = snap["signals"].get(node, "NS_GREEN")
        col = SIGNAL_COLORS.get(phase, "#10B981")

        jagent = engine.junctions.get(node)
        jstate = jagent.state.value if jagent else "NORMAL"

        if jstate in ("PRE_CLEAR", "HOLD_GREEN", "RECOVERY"):
            ring_x.append(x)
            ring_y.append(y)
            ring_color.append(t["corridor_active"] if jstate == "HOLD_GREEN" else t["signal_yellow"])

        short_phase = "G" if "GREEN" in phase else ("Y" if "YELLOW" in phase else "R")

        loc_name = get_location_name(node)
        loc_cross = get_location_cross(node)
        jx.append(x)
        jy.append(y)
        jcolor.append(col)
        jtext.append(short_phase)
        jhover.append(
            f"<b>{loc_name}</b><br>"
            f"<span>{loc_cross}</span><br>"
            f"Current Signal: <b>{SIGNAL_PHASE_LABELS.get(phase, phase)}</b><br>"
            f"Corridor State: <b>{jstate}</b>"
        )

    # Preemption Pulse Rings
    if ring_x:
        fig.add_trace(
            go.Scatter(
                x=ring_x,
                y=ring_y,
                mode="markers",
                marker=dict(
                    size=28,
                    color="rgba(0,0,0,0)",
                    line=dict(color=ring_color, width=2.5),
                ),
                name="Active Preemption Lock",
                hoverinfo="none",
            )
        )

    # Signal Core Dots
    fig.add_trace(
        go.Scatter(
            x=jx,
            y=jy,
            mode="markers+text",
            marker=dict(
                size=16,
                color=jcolor,
                line=dict(color=t["bg"], width=1.5),
            ),
            text=jtext,
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=8, family="JetBrains Mono"),
            name="Signals (G/Y/R)",
            customdata=jhover,
            hovertemplate="%{customdata}<extra></extra>",
        )
    )

    # 5. Vehicles (Civilian + Emergency)
    car_x, car_y, car_c, car_h = [], [], [], []
    amb_x, amb_y, amb_h, amb_labels = [], [], [], []

    for v in snap["vehicles"]:
        x, y = v.get("x", 0.0), v.get("y", 0.0)
        kind = v.get("kind", "car")
        spd = v.get("speed_mps", 0.0)
        stopped = v.get("is_stopped", False)
        wt = v.get("wait_time_s", 0.0)

        if kind == "ambulance":
            amb_x.append(x)
            amb_y.append(y)
            amb_labels.append(f"  {v['id']} [AMB]")
            amb_h.append(
                f"<b>EMERGENCY VEHICLE {v['id']}</b><br>"
                f"Velocity: <b>{spd:.1f} m/s ({spd * 3.6:.0f} km/h)</b><br>"
                f"Status: <b>{'Stationary (Congestion)' if stopped else 'En Route (Code 3)'}</b><br>"
                f"Wait Time: {wt:.0f}s"
            )
        else:
            if stopped:
                col = t["emergency"]
            elif spd < 5.0:
                col = t["signal_yellow"]
            else:
                col = t["signal_green"]
            car_x.append(x)
            car_y.append(y)
            car_c.append(col)
            car_h.append(
                f"<b>Civilian Car {v['id']}</b><br>"
                f"Speed: {spd:.1f} m/s<br>"
                f"Delay: {wt:.0f}s"
            )

    if car_x:
        fig.add_trace(
            go.Scatter(
                x=car_x,
                y=car_y,
                mode="markers",
                marker=dict(
                    size=8,
                    color=car_c,
                    line=dict(color="rgba(0,0,0,0.5)", width=0.5),
                ),
                name="Civilian Vehicles",
                customdata=car_h,
                hovertemplate="%{customdata}<extra></extra>",
            )
        )

    if amb_x:
        # Ambulance Halo
        fig.add_trace(
            go.Scatter(
                x=amb_x,
                y=amb_y,
                mode="markers",
                marker=dict(
                    symbol="diamond",
                    size=26,
                    color=t["emergency"],
                    opacity=0.3,
                ),
                hoverinfo="none",
                showlegend=False,
            )
        )
        # Ambulance Marker
        fig.add_trace(
            go.Scatter(
                x=amb_x,
                y=amb_y,
                mode="markers+text",
                marker=dict(
                    symbol="diamond",
                    size=16,
                    color=t["emergency"],
                    line=dict(color="#FFFFFF", width=2),
                ),
                text=amb_labels,
                textposition="middle right",
                textfont=dict(color=t["emergency"], size=11, family="Plus Jakarta Sans"),
                name="Emergency Ambulance",
                customdata=amb_h,
                hovertemplate="%{customdata}<extra></extra>",
            )
        )

    # Layout styling: High-precision command center canvas
    fig.update_layout(
        paper_bgcolor=t["road_bg"],
        plot_bgcolor=t["road_bg"],
        margin=dict(l=10, r=10, t=10, b=10),
        height=520,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-60, 1060],
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor="x",
            scaleratio=1,
            range=[-60, 1060],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.12,
            xanchor="center",
            x=0.5,
            font=dict(size=10, color=t["ink_secondary"], family="Plus Jakarta Sans"),
        ),
        hoverlabel=dict(
            bgcolor=t["surface_card"],
            bordercolor=t["rule_active"],
            font=dict(family="Plus Jakarta Sans", size=12, color=t["ink"]),
        ),
    )

    return fig


def build_telemetry_figure(
    telemetry_history: List[Dict[str, Any]],
    dark_mode: bool = True,
) -> go.Figure:
    """Build live velocity and acceleration timeseries telemetry chart."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    fig = go.Figure()

    if not telemetry_history:
        fig.update_layout(
            paper_bgcolor=t["surface"],
            plot_bgcolor=t["surface"],
            annotations=[
                dict(
                    text="Awaiting live ambulance dispatch telemetry...",
                    xref="paper",
                    yref="paper",
                    showarrow=False,
                    font=dict(size=13, color=t["muted"], family="Plus Jakarta Sans"),
                )
            ],
            height=260,
            margin=dict(l=20, r=20, t=20, b=20),
        )
        return fig

    ticks = [entry["tick"] for entry in telemetry_history]
    speeds = [entry.get("speed_mps", 0.0) for entry in telemetry_history]

    fig.add_trace(
        go.Scatter(
            x=ticks,
            y=speeds,
            mode="lines+markers",
            line=dict(color=t["accent_hover"], width=2.5),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor=t["accent_subtle"],
            name="Ambulance Velocity (m/s)",
        )
    )

    fig.update_layout(
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        margin=dict(l=40, r=20, t=20, b=30),
        height=260,
        xaxis=dict(
            title=dict(text="Simulation Tick (s)", font=dict(color=t["ink_secondary"], size=11)),
            gridcolor=t["rule"],
            zerolinecolor=t["rule"],
            tickfont=dict(color=t["muted"], family="JetBrains Mono"),
        ),
        yaxis=dict(
            title=dict(text="Speed (m/s)", font=dict(color=t["ink_secondary"], size=11)),
            gridcolor=t["rule"],
            zerolinecolor=t["rule"],
            tickfont=dict(color=t["muted"], family="JetBrains Mono"),
        ),
        legend=dict(
            font=dict(size=10, color=t["ink_secondary"]),
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.02,
        ),
    )
    return fig


def build_comparison_figure(
    results_data: Dict[str, Any],
    dark_mode: bool = True,
) -> go.Figure:
    """Build multi-metric comparison between Baseline, Coordinated, and Spoofed scenarios."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    categories = ["Transit Time (s)", "Junction Stops", "Avg Queue (veh)", "Wait Delay (s)"]
    normal_vals = [105.0, 4.0, 3.8, 48.0]
    coord_vals = [35.0, 0.0, 1.9, 14.0]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Uncoordinated Baseline",
            x=categories,
            y=normal_vals,
            marker_color=t["muted"],
            opacity=0.8,
        )
    )
    fig.add_trace(
        go.Bar(
            name="ClearPath Preemption",
            x=categories,
            y=coord_vals,
            marker_color=t["signal_green"],
        )
    )

    fig.update_layout(
        barmode="group",
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        margin=dict(l=40, r=20, t=20, b=30),
        height=280,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11, color=t["ink_secondary"]),
        ),
        xaxis=dict(
            gridcolor=t["rule"],
            tickfont=dict(color=t["ink"], family="Plus Jakarta Sans", size=11),
        ),
        yaxis=dict(
            gridcolor=t["rule"],
            tickfont=dict(color=t["muted"], family="JetBrains Mono"),
        ),
    )
    return fig


def build_reason_figure(reasons_dict: Dict[str, int], dark_mode: bool = True) -> go.Figure:
    """Build security rejection breakdown pie chart."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    labels = list(reasons_dict.keys()) if reasons_dict else ["No Attacks"]
    values = list(reasons_dict.values()) if reasons_dict else [1]

    colors = [t["emergency"], t["signal_yellow"], t["accent"], "#8B5CF6", "#EC4899"]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.55,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textfont=dict(size=11, color=t["ink"], family="Plus Jakarta Sans"),
            )
        ]
    )

    fig.update_layout(
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        margin=dict(l=10, r=10, t=10, b=10),
        height=220,
        showlegend=False,
    )
    return fig
