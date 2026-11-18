"""Reusable UI components for ClearPath Streamlit Command Center.

Engineered for high-density, mission-critical operational intelligence:
- Live status indicators and telemetry badges
- High-contrast accessible G/Y/R signal indicators
- Interactive dialogs, site search, and streamlined consent
- Precision typography pairing: Plus Jakarta Sans + Inter + JetBrains Mono
"""

from __future__ import annotations

import datetime
import html
import os
import subprocess
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
import streamlit as st

from clearpath.dashboard.theme import TOKENS


def get_git_commit_date() -> str:
    """Return last git commit date, falling back to file mtime or today."""
    try:
        d = subprocess.check_output(
            ["git", "log", "-1", "--format=%cd", "--date=format:%Y-%m-%d"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if d:
            return d
    except Exception:
        pass
    try:
        mtime = os.path.getmtime(__file__)
        return datetime.date.fromtimestamp(mtime).isoformat()
    except Exception:
        return datetime.date.today().isoformat()


def render_sticky_header(current_page: str = "Home", dark_mode: bool = True) -> None:
    """Render top command bar with status dot, brand mark, page indicator, and actions."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    # Skip to Content Link (Accessibility)
    st.markdown(
        '<a href="#main-content" class="cp-skip-link">Skip to main content</a>',
        unsafe_allow_html=True,
    )

    # Scroll progress bar
    st.markdown('<div class="cp-scroll-progress"></div>', unsafe_allow_html=True)

    # Top sticky command header content
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown(
            f"""
            <div class="cp-brand-wrap">
                <div class="cp-brand-icon">CP</div>
                <div>
                    <a href="/" class="cp-brand-name">ClearPath</a>
                    <span class="cp-brand-badge" style="margin-left:8px;">PREEMPTION OS</span>
                    <span class="cp-brand-badge" style="color:var(--cp-accent-hover); font-weight:700; border-color:var(--cp-rule-active);">{current_page}</span>
                </div>
                <div class="cp-status-pill" style="margin-left:8px;">
                    <div class="cp-status-dot"></div>
                    <span>SIMULATOR ACTIVE</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with h_col2:
        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            theme_label = "☀ Light" if dark_mode else "🌙 Dark"
            if st.button(theme_label, key="header_theme_toggle", help="Toggle Light / Dark mode"):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.rerun()
        with btn_c2:
            op_label = "Operator ✓" if st.session_state.get("operator_authenticated") else "Sign In"
            if st.button(op_label, key="header_operator_signin", help="Operator Console Access"):
                st.session_state.show_operator_dialog = True
                st.rerun()

    # Anchor for Skip to Content
    st.markdown('<div id="main-content"></div>', unsafe_allow_html=True)


def render_cookie_banner() -> None:
    """Render sleek floating toast banner for privacy preferences."""
    if st.session_state.get("cookie_choice_made"):
        return

    with st.container():
        st.markdown(
            """
            <div class="cp-cookie-banner">
                <div style="font-weight:700; font-family:var(--cp-font-heading); margin-bottom:4px; color:var(--cp-ink);">
                    Interface Preferences & Local State
                </div>
                <div class="cp-cookie-text">
                    This simulation prototype preserves theme and scenario parameters purely in your browser session. No third-party tracking scripts or tracking cookies exist.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 3])
        with c1:
            if st.button("Accept", key="cookie_accept", type="primary"):
                st.session_state.cookie_consent = True
                st.session_state.cookie_choice_made = True
                st.rerun()
        with c2:
            if st.button("Decline", key="cookie_decline"):
                st.session_state.cookie_consent = False
                st.session_state.cookie_choice_made = True
                st.session_state.utm_params = {}
                st.rerun()


@st.dialog("Operator Console Authentication")
def show_operator_dialog() -> None:
    """Operator password dialog for elevated simulation overrides."""
    st.markdown(
        """
        **Urban Traffic Management Console**  
        *Demo authorization grants manual emergency preemption overrides and simulated corridor locks.*
        """
    )
    with st.form("operator_signin_form"):
        pwd = st.text_input(
            "Operator Passcode (Demo: clearpath2026)",
            type="password",
            help="Default research session passcode: clearpath2026",
        )
        submitted = st.form_submit_button("Authenticate Operator", type="primary")
        if submitted:
            if pwd.strip() in ("clearpath2026", "admin"):
                st.session_state.operator_authenticated = True
                st.session_state.show_operator_dialog = False
                st.success("Operator session authenticated. Preemption actuators unlocked.")
                st.rerun()
            else:
                st.error("Invalid passcode. Enter 'clearpath2026' for research prototype access.")


@st.dialog("Confirm Simulation Reset")
def show_reset_confirmation(on_confirm: Callable[[], None]) -> None:
    """Confirmation modal prior to resetting simulation state."""
    st.markdown(
        "Are you sure you want to re-initialize the simulation environment? All vehicle queues, active corridors, and bus messages will reset to tick 0."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset Grid", type="primary", key="dlg_confirm_reset"):
            on_confirm()
            st.rerun()
    with col2:
        if st.button("Cancel", key="dlg_cancel_reset"):
            st.rerun()


@st.dialog("Confirm Code-3 Preemption Dispatch")
def show_dispatch_confirmation(
    vehicle_id: str,
    hospital_name: str,
    incident_type: str,
    on_confirm: Callable[[], None],
    incident_origin: str = "j_0_0",
) -> None:
    """Confirmation modal prior to launching green-wave preemption."""
    st.markdown(
        f"""
        **Verify Emergency Preemption Parameters**
        - **Emergency Unit:** `{vehicle_id}`
        - **Incident Origin:** `{incident_origin}`
        - **Triage Level:** `{incident_type.upper()}`
        - **Destination Facility:** `{hospital_name}`
        - **Token Security:** `HMAC-SHA256 Nonce Verification`
        
        This issues priority reservations along the planned corridor, forcing intersecting approaches into clearance yellow before locking green phases.
        """
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Authorize Preemption", type="primary", key="dlg_confirm_dispatch"):
            on_confirm()
            st.rerun()
    with col2:
        if st.button("Cancel", key="dlg_cancel_dispatch"):
            st.rerun()


def render_big_numeral(
    label: str,
    value: str,
    unit: str = "",
    delta: str = "",
    delta_good: bool = True,
) -> None:
    """Modern command center metric card with micro-badges and JetBrains Mono numerals."""
    delta_bg = "rgba(16, 185, 129, 0.12)" if delta_good else "rgba(239, 68, 68, 0.12)"
    delta_color = "var(--cp-signal-green)" if delta_good else "var(--cp-emergency)"
    delta_border = "rgba(16, 185, 129, 0.25)" if delta_good else "rgba(239, 68, 68, 0.25)"

    delta_html = (
        f"""
        <div class="cp-metric-sub">
            <span style="background:{delta_bg}; color:{delta_color}; border:1px solid {delta_border}; padding:2px 8px; border-radius:4px;">
                {delta}
            </span>
        </div>
        """
        if delta
        else '<div class="cp-metric-sub">&nbsp;</div>'
    )
    st.markdown(
        f"""
        <div class="cp-metric-box">
            <div class="cp-metric-label">{label}</div>
            <div class="cp-metric-value">{value}<span style="font-size:1.1rem; color:var(--cp-muted); font-weight:500; margin-left:4px;">{unit}</span></div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_agent_row(
    num: str,
    name: str,
    role: str,
    algorithm_summary: str,
    status: str = "Active",
) -> None:
    """Structured architectural row for multi-agent system overview."""
    st.markdown(
        f"""
        <div style="background:var(--cp-surface); border:1px solid var(--cp-rule); border-radius:var(--cp-radius); padding:16px 20px; margin-bottom:12px; display:grid; grid-template-columns:40px 1fr auto; gap:16px; align-items:center;">
            <div style="font-family:var(--cp-font-mono); font-weight:800; font-size:1.2rem; color:var(--cp-accent-hover);">{num}</div>
            <div>
                <div style="font-family:var(--cp-font-heading); font-weight:700; font-size:1rem; color:var(--cp-ink);">
                    {name} <span style="font-weight:500; font-size:0.8rem; color:var(--cp-muted); margin-left:6px;">[{role}]</span>
                </div>
                <div style="font-size:0.85rem; color:var(--cp-ink-secondary); margin-top:3px; line-height:1.4;">{algorithm_summary}</div>
            </div>
            <div>
                <span class="cp-brand-badge" style="color:var(--cp-signal-green); border-color:rgba(16,185,129,0.3); background:rgba(16,185,129,0.08);">{status}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_preemption_timeline() -> None:
    """Interactive visual timeline detailing the end-to-end corridor lifecycle."""
    steps = [
        (
            "01 Cryptographic Signing",
            "Emergency vehicle generates a 128-bit cryptographic nonce, binds live GPS/speed/heading telemetry, and issues an HMAC-SHA256 authentication token.",
        ),
        (
            "02 Cyber-Physical Gate Verification",
            "Security Gateway Agent checks token signature, enforces nonce replay caches, checks time expiration (window <= 60s), and rejects impossible kinematics (> 35 m/s).",
        ),
        (
            "03 Dispatcher Facility Triage & Routing",
            "Dispatcher computes facility scores balancing travel time with trauma bed availability, running density-aware A* routing across grid links.",
        ),
        (
            "04 Inter-Junction Reservation Handshake",
            "Junction Controllers receive ETA schedules, evaluate cross-traffic queue depth, initiate mandatory yellow clearance, and return ReserveAck commitments.",
        ),
        (
            "05 Green-Wave Lock & Queue Flushing",
            "Downstream intersections flush standing queues prior to arrival, locking solid green corridor phases while the Guidance Agent issues driver yield advisories.",
        ),
        (
            "06 Balanced Post-Preemption Recovery",
            "Upon ambulance passage (PassedNotice), intersections execute fair recovery phases, allocating extended green splits to cross streets to restore equilibrium.",
        ),
    ]

    items_html = "".join(
        f"""
        <div style="position:relative; padding-left:32px; margin-bottom:20px; border-left:2px solid var(--cp-rule);">
            <div style="position:absolute; left:-7px; top:3px; width:12px; height:12px; border-radius:50%; background:var(--cp-accent-hover); box-shadow:0 0 8px var(--cp-accent-glow);"></div>
            <div style="font-family:var(--cp-font-heading); font-weight:700; font-size:0.98rem; color:var(--cp-ink);">{title}</div>
            <div style="font-size:0.86rem; color:var(--cp-ink-secondary); margin-top:4px; line-height:1.45;">{desc}</div>
        </div>
        """
        for title, desc in steps
    )

    st.markdown(f'<div style="margin:20px 0;">{items_html}</div>', unsafe_allow_html=True)


def render_skeleton(kind: str = "card") -> None:
    """Skeleton loader placeholder for asynchronous transitions."""
    height = "480px" if kind == "map" else ("220px" if kind == "table" else "120px")
    st.markdown(
        f'<div style="height:{height}; width:100%; background:var(--cp-surface); border:1px solid var(--cp-rule); border-radius:var(--cp-radius); animation:cp-pulse 1.8s infinite ease-in-out; margin-bottom:16px;"></div>',
        unsafe_allow_html=True,
    )


def render_site_search(
    docs_dict: Dict[str, str],
    faq_list: List[Dict[str, str]],
    results_dict: Dict[str, Any],
) -> None:
    """Search utility indexing documentation, FAQ, and scenario verification results."""
    query = st.text_input(
        "Search documentation, algorithms, and benchmark results",
        placeholder="Search keywords (e.g., HMAC, A*, starvation, recovery, replay, green wave)...",
        key="global_site_search",
    ).strip()

    if not query:
        return

    q_lower = query.lower()
    matches: List[Tuple[str, str, str]] = []

    for item in faq_list:
        q_text = item.get("question", "")
        a_text = item.get("answer", "")
        if q_lower in q_text.lower() or q_lower in a_text.lower():
            matches.append(("FAQ", q_text, a_text[:220] + "..."))

    for doc_name, doc_content in docs_dict.items():
        if q_lower in doc_name.lower() or q_lower in doc_content.lower():
            idx = doc_content.lower().find(q_lower)
            start = max(0, idx - 40)
            end = min(len(doc_content), idx + 140)
            matches.append((f"Docs: {doc_name}", f"Section in {doc_name}", "..." + doc_content[start:end].replace("\n", " ") + "..."))

    for chk in results_dict.get("checklist", []):
        c_title = chk.get("title", "")
        c_details = chk.get("details", "")
        if q_lower in c_title.lower() or q_lower in c_details.lower():
            matches.append(("Benchmark Results", c_title, c_details))

    st.markdown(f"**Found {len(matches)} matches for '{html.escape(query)}':**")
    for cat, title, snippet in matches[:8]:
        st.markdown(
            f"""
            <div class="cp-card" style="padding:14px 18px; margin-bottom:10px;">
                <div style="font-size:0.74rem; text-transform:uppercase; color:var(--cp-accent-hover); font-weight:700; font-family:var(--cp-font-mono);">{cat}</div>
                <div style="font-weight:700; font-size:1rem; margin:2px 0; color:var(--cp-ink);">{title}</div>
                <div style="font-size:0.85rem; color:var(--cp-ink-secondary); line-height:1.4;">{html.escape(snippet)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_floating_contact_button() -> None:
    """Floating action trigger pinned to bottom right."""
    st.markdown(
        '<a href="Contact" class="cp-floating-contact"><span>💬</span> Operator Support</a>',
        unsafe_allow_html=True,
    )


def render_footer(last_updated: Optional[str] = None) -> None:
    """Command center footer with version, open-source license, and back-to-top shortcut."""
    date_str = last_updated or get_git_commit_date()
    st.markdown(
        f"""
        <div class="cp-footer">
            <div>
                <b style="color:var(--cp-ink);">ClearPath Autonomous Preemption System</b> | Open Source (MIT License)<br>
                <span>Cyber-physical emergency traffic management and multi-agent coordination prototype.</span>
            </div>
            <div style="text-align:right;">
                <span>System Build: <b class="cp-mono" style="color:var(--cp-ink);">{date_str}</b></span><br>
                <a href="#main-content" style="font-weight:600; color:var(--cp-accent-hover);">Back to top ↑</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
