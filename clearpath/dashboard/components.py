"""Reusable UI components for ClearPath Streamlit Dashboard.

Includes header, hero cards, dual progress bars, KPI metrics, security badges,
guidance feeds, and legend chips.
"""

from __future__ import annotations

import textwrap
from typing import Any, Dict, List, Optional
import streamlit as st


def render_header(
    running: bool,
    preemption_enabled: bool,
    tick: int,
    scenario_name: str,
    alerts_count: int = 0,
) -> None:
    """Render the dashboard top bar with status pills and alerts."""
    run_status_dot = "🟢" if running else "⏸️"
    run_status_text = "Running" if running else "Paused"

    mode_text = "ClearPath Active" if preemption_enabled else "Baseline Standard"
    mode_bg = "#DDEFD9" if preemption_enabled else "#FBD9E3"
    mode_color = "#1E6B15" if preemption_enabled else "#A81D43"

    alert_chip = (
        f'<span class="cp-badge-pill" style="background:#FBD9E3; color:#A81D43;">'
        f'🛡️ {alerts_count} Attacks Blocked</span>'
        if alerts_count > 0
        else '<span class="cp-badge-pill" style="background:#D9ECF8; color:#155D8A;">🛡️ 0 Security Alerts</span>'
    )

    html = textwrap.dedent(f"""
    <div class="cp-header-bar">
        <div class="cp-brand">
            <div class="cp-logo-icon">CP</div>
            <div>
                <h1 class="cp-title">ClearPath</h1>
                <div style="font-size:0.82rem; font-weight:600; color:var(--cp-ink-muted);">
                    Intelligent Emergency Corridor Preemption • Tick {tick}
                </div>
            </div>
        </div>
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span class="cp-badge-pill" style="background:var(--cp-surface); border:1px solid var(--cp-border); color:var(--cp-ink);">
                {run_status_dot} {run_status_text}
            </span>
            <span class="cp-badge-pill" style="background:{mode_bg}; color:{mode_color};">
                {mode_text}
            </span>
            <span class="cp-badge-pill" style="background:var(--cp-surface); border:1px solid var(--cp-border); color:var(--cp-ink);">
                Scenario: <b>{scenario_name}</b>
            </span>
            {alert_chip}
        </div>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_hero(
    time_saved_s: Optional[float],
    improvement_pct: Optional[float],
    baseline_time_s: Optional[float],
    clearpath_time_s: Optional[float],
) -> None:
    """Render the Big-Number Hero card with time saved and dual baseline vs ClearPath progress bars."""
    if time_saved_s is not None and time_saved_s > 0:
        val_str = f"{time_saved_s:.0f}"
        chip_html = (
            f'<div class="cp-hero-chip">▲ {improvement_pct:.1f}% faster than baseline</div>'
            if improvement_pct
            else ""
        )
    else:
        val_str = "0"
        chip_html = '<div class="cp-hero-chip" style="background:#E3F4DF; color:#2F5733;">Corridor Ready</div>'

    # Dual progress bar calculation
    b_val = baseline_time_s if (baseline_time_s and baseline_time_s > 0) else 145.0
    c_val = clearpath_time_s if (clearpath_time_s and clearpath_time_s > 0) else (b_val - (time_saved_s or 0))
    max_val = max(b_val, c_val, 1.0)
    b_pct = min(100.0, max(5.0, (b_val / max_val) * 100.0))
    c_pct = min(100.0, max(5.0, (c_val / max_val) * 100.0))

    html = textwrap.dedent(f"""
    <div class="cp-hero-savings">
        <div>
            <div class="cp-hero-label">
                <span>⚡ AMBULANCE TIME SAVED</span>
            </div>
            <div class="cp-hero-number-wrap">
                <span class="cp-hero-number">{val_str}</span>
                <span class="cp-hero-unit">seconds</span>
                {chip_html}
            </div>
        </div>
        <div class="cp-dual-bar">
            <div class="cp-dual-bar-row">
                <span>ClearPath Preemption Transit: <b>{c_val:.0f}s</b></span>
                <span style="color:var(--cp-accent); font-weight:700;">-{(b_val - c_val):.0f}s</span>
            </div>
            <div class="cp-progress-track">
                <div class="cp-progress-fill" style="width:{c_pct:.1f}%; background:var(--cp-accent);"></div>
            </div>
            <div class="cp-dual-bar-row">
                <span>Uncoordinated Baseline Transit: <b>{b_val:.0f}s</b></span>
                <span>100%</span>
            </div>
            <div class="cp-progress-track">
                <div class="cp-progress-fill" style="width:{b_pct:.1f}%; background:#A0AEC0;"></div>
            </div>
        </div>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_active_emergency_card(
    incident_type: str,
    hospital_name: str,
    eta_s: float,
    reserved_count: int,
    amb_id: str = "AMB_001",
    is_active: bool = True,
) -> None:
    """Render the pale green Active Emergency highlight card."""
    status_label = "ACTIVE DISPATCH" if is_active else "STANDBY"
    pulse_dot = "🔴" if is_active else "🟢"
    html = textwrap.dedent(f"""
    <div class="cp-active-emergency-card">
        <div>
            <div class="cp-emg-header">
                <div class="cp-emg-title">
                    <span>🚨 Active Emergency</span>
                </div>
                <span class="cp-badge-pill" style="background:#FFFFFF; color:#1E6B15; font-size:0.75rem;">
                    {pulse_dot} {status_label}
                </span>
            </div>
            <div style="font-size:0.85rem; color:#2A4E2F; font-weight:600; margin-bottom:12px;">
                Vehicle: <b>{amb_id}</b> • Protocol: Mutual-Auth Preemption
            </div>
            <div class="cp-emg-grid">
                <div class="cp-emg-item">
                    <div class="cp-emg-item-lbl">Incident Severity</div>
                    <div class="cp-emg-item-val">{incident_type.upper()}</div>
                </div>
                <div class="cp-emg-item">
                    <div class="cp-emg-item-lbl">Destination</div>
                    <div class="cp-emg-item-val">{hospital_name}</div>
                </div>
                <div class="cp-emg-item">
                    <div class="cp-emg-item-lbl">Corridor ETA</div>
                    <div class="cp-emg-item-val">{eta_s:.0f} sec</div>
                </div>
                <div class="cp-emg-item">
                    <div class="cp-emg-item-lbl">Reserved Waves</div>
                    <div class="cp-emg-item-val">{reserved_count} Junctions</div>
                </div>
            </div>
        </div>
        <div style="font-size:0.75rem; color:#2F5733; margin-top:10px;">
            ✓ Dual-direction hold-green locked • Cross-traffic queue-flush active
        </div>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def _single_kpi_card(
    label: str,
    tag: str,
    tag_bg: str,
    tag_ink: str,
    val: str,
    unit: str,
    subtext: str,
    bar_w: float,
    bar_color: str,
) -> str:
    return (
        f'<div class="cp-kpi-card">'
        f'<div class="cp-kpi-top">'
        f'<span class="cp-kpi-label">{label}</span>'
        f'<span class="cp-badge-pill" style="background:{tag_bg}; color:{tag_ink}; font-size:0.7rem; padding:2px 8px;">{tag}</span>'
        f'</div>'
        f'<div class="cp-kpi-val">{val}<span style="font-size:0.9rem; font-weight:600; color:var(--cp-ink-muted);">{unit}</span></div>'
        f'<div style="font-size:0.75rem; color:var(--cp-ink-muted);">{subtext}</div>'
        f'<div class="cp-kpi-bar">'
        f'<div class="cp-kpi-bar-fill" style="width:{bar_w:.0f}%; background:{bar_color};"></div>'
        f'</div>'
        f'</div>'
    )


def render_kpi_row(
    cross_delay_s: float,
    attack_block_rate: float,
    fp_rate: float,
    avg_queue: float,
    amb_stops: int,
    blocked_count: int = 0,
    fp_count: int = 0,
) -> None:
    """Render the 5 responsive KPI cards with thin indicator bars."""
    delay_bar_w = min(100.0, (cross_delay_s / 25.0) * 100.0)
    atk_bar_w = min(100.0, attack_block_rate * 100.0)
    fp_bar_w = min(100.0, fp_rate * 100.0)
    queue_bar_w = min(100.0, (avg_queue / 20.0) * 100.0)
    stops_bar_w = 100.0 if amb_stops == 0 else max(10.0, 100.0 - amb_stops * 25.0)

    cards = [
        _single_kpi_card("Cross-Traffic Delay", "avg", "#DDEFD9", "#1E6B15", f"{cross_delay_s:.1f}", "s", "Side street impact", delay_bar_w, "var(--cp-signal-green)"),
        _single_kpi_card("Attack Block Rate", "security", "#FBD9E3", "#A81D43", f"{attack_block_rate * 100:.0f}", "%", f"{blocked_count} defended", atk_bar_w, "var(--cp-accent)"),
        _single_kpi_card("False Positive", "legit", "#D9ECF8", "#155D8A", f"{fp_rate * 100:.1f}", "%", f"{fp_count} legit blocked", fp_bar_w, "var(--cp-info-blue)"),
        _single_kpi_card("Corridor Queue", "flush", "#FBEBC8", "#87560B", f"{avg_queue:.0f}", "veh", "Max queue on route", queue_bar_w, "var(--cp-signal-yellow)"),
        _single_kpi_card("Ambulance Stops", "stops", "#DDEFD9", "#1E6B15", f"{amb_stops}", "/corridor", "0 stops = continuous wave", stops_bar_w, "var(--cp-accent)"),
    ]
    html = f'<div class="cp-kpi-grid">{"".join(cards)}</div>'
    st.markdown(html, unsafe_allow_html=True)


def render_map_legend() -> None:
    """Render the pastel chips legend row for the road grid."""
    html = textwrap.dedent("""
    <div class="cp-legend-bar">
        <span class="cp-legend-chip" style="background:#DDEFD9; color:#1E6B15;">
            <span class="cp-dot" style="background:#3FB950;"></span> Green (G)
        </span>
        <span class="cp-legend-chip" style="background:#FBEBC8; color:#87560B;">
            <span class="cp-dot" style="background:#D29922;"></span> Yellow (Y)
        </span>
        <span class="cp-legend-chip" style="background:#FBD9E3; color:#A81D43;">
            <span class="cp-dot" style="background:#F85149;"></span> Red (R)
        </span>
        <span class="cp-legend-chip" style="background:#FBEBC8; color:#87560B;">
            <span class="cp-dot" style="background:#F28C28;"></span> Ambulance 🚑
        </span>
        <span class="cp-legend-chip" style="background:#D9ECF8; color:#155D8A;">
            <span class="cp-dot" style="background:#2B7DE9;"></span> Hospital 🏥
        </span>
        <span class="cp-legend-chip" style="background:#DDEFD9; color:#1E6B15;">
            <span class="cp-dot" style="background:#3FB950; border:2px solid #D29922;"></span> Preempted Ring
        </span>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_security_verdict_card(
    verdict: Optional[Dict[str, Any]],
    last_verdict_atk: Optional[str] = None,
) -> None:
    """Render large ALLOWED / BLOCKED banner chip and risk analysis."""
    if not verdict:
        html = textwrap.dedent("""
        <div class="cp-sec-banner" style="background:var(--cp-surface-muted); border:1px solid var(--cp-border); color:var(--cp-ink-muted);">
            <div style="font-weight:700; font-size:0.9rem;">🛡️ Security Sentinel Idle</div>
            <div style="font-size:0.8rem;">Awaiting preemption requests for HMAC token verification.</div>
        </div>
        """)
        st.markdown(html, unsafe_allow_html=True)
        return

    auth = verdict.get("auth")
    allowed = verdict.get("authenticated", False)
    reasons = getattr(auth, "reasons", []) if auth else []
    risk = getattr(auth, "risk_score", 0.0) if auth else 0.0
    atk_lbl = (last_verdict_atk or "").replace("_", " ").title()

    banner_class = "cp-sec-banner-allow" if allowed else "cp-sec-banner-block"
    icon = "✅" if allowed else "🚫"
    status_text = "ALLOWED — VALID TOKEN" if allowed else "BLOCKED — ATTACK DEFENDED"

    reasons_chips = "".join(
        f'<span class="cp-badge-pill" style="background:rgba(0,0,0,0.1); margin-right:4px;">{r}</span>'
        for r in reasons
    ) or '<span class="cp-badge-pill" style="background:rgba(0,0,0,0.1);">None (Verified)</span>'

    attack_info = f'<div style="font-size:0.8rem; margin-top:4px;">Attack Vector: <b>{atk_lbl}</b></div>' if atk_lbl else ""

    html = textwrap.dedent(f"""
    <div class="cp-sec-banner {banner_class}">
        <div>
            <div style="font-size:1.15rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                <span>{icon}</span> <span>{status_text}</span>
            </div>
            {attack_info}
        </div>
        <div style="text-align:right;">
            <div style="font-size:0.8rem; font-weight:700;">Risk Score: <b>{risk:.2f} / 1.00</b></div>
            <div style="margin-top:6px;">{reasons_chips}</div>
        </div>
    </div>
    """)
    st.markdown(html, unsafe_allow_html=True)


def render_guidance_card(
    advisories: List[Any],
    vms_board: Dict[str, str],
) -> None:
    """Render advisories and VMS board in clean rounded containers."""
    st.markdown("#### 💬 Citizen Guidance & Driver Advisories")
    if advisories:
        for rec in reversed(advisories[-6:]):
            sev = getattr(rec, "severity", "INFO")
            chip_bg = "#FBD9E3" if sev == "CRITICAL" else ("#FBEBC8" if sev == "WARN" else "#DDEFD9")
            chip_ink = "#A81D43" if sev == "CRITICAL" else ("#87560B" if sev == "WARN" else "#1E6B15")
            vids = ", ".join(getattr(rec, "vehicle_ids", [])[:3])
            item_html = textwrap.dedent(f"""
            <div class="cp-advisory-item">
                <span class="cp-badge-pill" style="background:{chip_bg}; color:{chip_ink}; font-size:0.72rem;">
                    {sev}
                </span>
                <div style="flex:1;">
                    <div style="font-weight:700; color:var(--cp-ink);">{rec.text}</div>
                    <div style="font-size:0.75rem; color:var(--cp-ink-muted);">Target: {vids or 'All corridor drivers'} • t={rec.t:.0f}s</div>
                </div>
            </div>
            """)
            st.markdown(item_html, unsafe_allow_html=True)
    else:
        st.caption("No active guidance advisories yet. Trigger an emergency request to dispatch route guidance.")

    vms_entries = "".join(f"<div><b>[{jid}]</b>: {msg}</div>" for jid, msg in vms_board.items())
    if not vms_board:
        vms_entries = "<div>CORRIDOR NORMAL — SPEED LIMIT 50 KM/H — ALL SIGNALS CYCLING</div>"

    vms_html = textwrap.dedent(f"""
    <div class="cp-vms-panel">
        <div class="cp-vms-header">📡 Dynamic VMS Variable Message Signs</div>
        <div style="font-size:0.85rem; line-height:1.5;">
            {vms_entries}
        </div>
    </div>
    """)
    st.markdown(vms_html, unsafe_allow_html=True)
