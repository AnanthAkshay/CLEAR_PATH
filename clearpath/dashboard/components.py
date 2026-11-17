"""Reusable UI components for ClearPath Streamlit Application.

Adheres strictly to editorial design guidelines:
- Zero emojis, zero drop shadows, zero gradients, zero glassmorphism
- Hairline borders (1px)
- Archivo headings, Public Sans body, IBM Plex Mono numerals
- Accessible G/Y/R signal indicators
- Interactive dialogs, search, skeletons, and cookie consent
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


def render_sticky_header(current_page: str = "Home", dark_mode: bool = False) -> None:
    """Render top sticky bar with skip-to-content, brand, theme switch, and operator sign-in."""
    mode = "dark" if dark_mode else "light"
    t = TOKENS[mode]

    # 1. Skip to Content Link (Feature 4, 12)
    st.markdown(
        '<a href="#main-content" class="cp-skip-link">Skip to main content</a>',
        unsafe_allow_html=True,
    )

    # 2. Scroll progress bar (Feature 8)
    st.markdown('<div class="cp-scroll-progress"></div>', unsafe_allow_html=True)

    # 3. Top sticky header content
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.markdown(
            f"""
            <div class="cp-brand-wrap">
                <a href="/" class="cp-brand-name">ClearPath</a>
                <span class="cp-brand-badge">Autonomous Corridor Preemption</span>
                <span class="cp-brand-badge" style="color:var(--cp-accent); font-weight:700;">{current_page}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with h_col2:
        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            theme_label = "Light" if dark_mode else "Dark"
            if st.button(theme_label, key="header_theme_toggle", help="Toggle Light / Dark mode"):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.rerun()
        with btn_c2:
            op_label = "Operator [Active]" if st.session_state.get("operator_authenticated") else "Sign in"
            if st.button(op_label, key="header_operator_signin", help="Demo Operator Access"):
                st.session_state.show_operator_dialog = True
                st.rerun()

    # Anchor for Skip to Content
    st.markdown('<div id="main-content"></div>', unsafe_allow_html=True)


def render_cookie_banner() -> None:
    """Render one-sentence privacy and preference banner (Feature 2)."""
    if st.session_state.get("cookie_choice_made"):
        return

    st.markdown(
        """
        <div class="cp-cookie-banner">
            <div class="cp-cookie-text">
                This prototype stores interface preferences (theme and navigation state) in session memory; no tracking or third-party cookies exist.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    b_col1, b_col2, _ = st.columns([1, 1, 3])
    with b_col1:
        if st.button("Accept preferences", key="cookie_accept", type="primary"):
            st.session_state.cookie_consent = True
            st.session_state.cookie_choice_made = True
            st.rerun()
    with b_col2:
        if st.button("Decline preferences", key="cookie_decline"):
            st.session_state.cookie_consent = False
            st.session_state.cookie_choice_made = True
            # Clear any captured UTM parameters if declined
            st.session_state.utm_params = {}
            st.rerun()


@st.dialog("Operator Sign-in (Simulation Access)")
def show_operator_dialog() -> None:
    """Password field with visibility toggle on clearly labelled demo form (Feature 13)."""
    st.markdown(
        """
        **Simulation Operator Console Access**  
        *Notice:* This demonstration sign-in grants simulated administrative privileges within this research prototype session. It is not connected to real emergency infrastructure.
        """
    )
    with st.form("operator_signin_form"):
        pwd = st.text_input(
            "Operator Password (Demo: clearpath2026)",
            type="password",
            help="Toggle the eye icon on the right to show or hide the password.",
        )
        submitted = st.form_submit_button("Authenticate Operator", type="primary")
        if submitted:
            if pwd.strip() == "clearpath2026" or pwd.strip() == "admin":
                st.session_state.operator_authenticated = True
                st.session_state.show_operator_dialog = False
                st.success("Operator session authenticated. Elevated preemption controls unlocked.")
                st.rerun()
            else:
                st.error("Invalid operator credential. Use demonstration password: clearpath2026")


@st.dialog("Confirm Simulation Reset")
def show_reset_confirmation(on_confirm: Callable[[], None]) -> None:
    """Confirmation dialog before resetting simulation state (Feature 17)."""
    st.markdown(
        "Are you sure you want to reset the simulation? All rolling snapshots, message bus logs, and active corridor plans will be reinitialized."
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm Reset", type="primary", key="dlg_confirm_reset"):
            on_confirm()
            st.rerun()
    with col2:
        if st.button("Cancel", key="dlg_cancel_reset"):
            st.rerun()


@st.dialog("Confirm Emergency Preemption Dispatch")
def show_dispatch_confirmation(
    vehicle_id: str,
    hospital_name: str,
    incident_type: str,
    on_confirm: Callable[[], None],
) -> None:
    """Confirmation dialog before dispatching emergency vehicle (Feature 17)."""
    st.markdown(
        f"""
        **Confirm Preemption Request Generation**
        - Vehicle ID: `{vehicle_id}`
        - Incident Classification: `{incident_type.upper()}`
        - Destination Target: `{hospital_name}`
        - Cryptographic Token: `HMAC-SHA256 Signed Nonce`
        
        This will initiate multi-junction corridor reservation and lock green phases along the planned route.
        """
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Dispatch Preemption", type="primary", key="dlg_confirm_dispatch"):
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
    """Editorial IBM Plex Mono metric box (Feature 6, Design Rules)."""
    delta_color = "var(--cp-signal-green)" if delta_good else "var(--cp-signal-red)"
    delta_html = (
        f'<div class="cp-metric-sub" style="color:{delta_color}; font-weight:600;">{delta}</div>'
        if delta
        else '<div class="cp-metric-sub">&nbsp;</div>'
    )
    st.markdown(
        f"""
        <div class="cp-metric-box">
            <div class="cp-metric-label">{label}</div>
            <div class="cp-metric-value">{value}<span style="font-size:1.1rem; color:var(--cp-muted); font-weight:400; margin-left:4px;">{unit}</span></div>
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
    """Numbered row for one of the four agents (Design Rules)."""
    st.markdown(
        f"""
        <div class="cp-agent-row">
            <div class="cp-agent-num">{num}</div>
            <div>
                <div class="cp-agent-name">{name} <span style="font-weight:400; font-size:0.8rem; color:var(--cp-muted); margin-left:6px;">[{role}]</span></div>
                <div class="cp-agent-desc">{algorithm_summary}</div>
            </div>
            <div>
                <span class="cp-brand-badge">{status}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_preemption_timeline() -> None:
    """Editorial vertical timeline for corridor preemption flow (Design Rules)."""
    steps = [
        (
            "01 Request Ingestion & Cryptographic Signing",
            "Emergency vehicle generates a unique 128-bit nonce, reads current telemetry (GPS, speed, heading), and issues an HMAC-SHA256 signature token using its pre-shared key.",
        ),
        (
            "02 Cyber-Physical Security Verification",
            "Security Agent verifies token validity against replay attacks, enforces cryptographic expiration (window <= 60s), checks kinematic speed limits (<= 35 m/s), and validates geographic coordinate continuity.",
        ),
        (
            "03 Dispatcher Triage & Dynamic Routing",
            "Dispatcher Agent calculates hospital suitability using weighted bed availability and specialized trauma care, executes density-aware Dijkstra / A* route planning, and generates arrival ETA schedules per junction.",
        ),
        (
            "04 Corridor Negotiation Handshake",
            "Dispatcher broadcasts ReserveCorridor requests. Each Junction Agent evaluates conflicting reservations, initiates yellow change intervals, and returns ReserveAck or ReserveNack with fallback.",
        ),
        (
            "05 Green-Wave Execution & Queue Flush",
            "Junction Controllers lock green signals for the corridor approach, trigger preemptive queue flushes on downstream links, and notify the Guidance Agent to broadcast civilian lane clearing.",
        ),
        (
            "06 Corridor Release & Balanced Recovery",
            "Ambulance broadcasts PassedNotice upon crossing the stop line. Junctions transition to a compensated recovery phase, prioritizing cross-traffic queues to prevent starvation.",
        ),
    ]

    items_html = "".join(
        f"""
        <div class="cp-timeline-step">
            <div class="cp-timeline-marker"></div>
            <div class="cp-timeline-title">{title}</div>
            <div class="cp-timeline-body">{desc}</div>
        </div>
        """
        for title, desc in steps
    )

    st.markdown(f'<div class="cp-timeline">{items_html}</div>', unsafe_allow_html=True)


def render_skeleton(kind: str = "card") -> None:
    """Skeleton loading placeholder with pulse disabled under prefers-reduced-motion (Feature 6)."""
    if kind == "map":
        height = "480px"
    elif kind == "table":
        height = "220px"
    elif kind == "kpi":
        height = "110px"
    else:
        height = "160px"

    st.markdown(
        f'<div class="cp-skeleton" style="height:{height}; width:100%; margin-bottom:16px;"></div>',
        unsafe_allow_html=True,
    )


def render_site_search(
    docs_dict: Dict[str, str],
    faq_list: List[Dict[str, str]],
    results_dict: Dict[str, Any],
) -> None:
    """Search box that filters docs, FAQ, and results with highlighted matches (Feature 3)."""
    query = st.text_input(
        "Search documentation, benchmarks, and FAQ",
        placeholder="Search keywords (e.g., HMAC, A*, starvation, recovery, replay)...",
        key="global_site_search",
    ).strip()

    if not query:
        return

    q_lower = query.lower()
    matches: List[Tuple[str, str, str]] = []

    # 1. Search FAQ
    for item in faq_list:
        q_text = item.get("question", "")
        a_text = item.get("answer", "")
        if q_lower in q_text.lower() or q_lower in a_text.lower():
            snippet = a_text[:240] + ("..." if len(a_text) > 240 else "")
            matches.append(("FAQ", q_text, snippet))

    # 2. Search Documentation
    for doc_name, doc_content in docs_dict.items():
        if q_lower in doc_name.lower() or q_lower in doc_content.lower():
            # Extract sentence with match
            idx = doc_content.lower().find(q_lower)
            start = max(0, idx - 60)
            end = min(len(doc_content), idx + 140)
            snippet = "..." + doc_content[start:end].replace("\n", " ") + "..."
            matches.append((f"Docs: {doc_name}", f"Section in {doc_name}", snippet))

    # 3. Search Results Checklist
    for chk in results_dict.get("checklist", []):
        c_title = chk.get("title", "")
        c_details = chk.get("details", "")
        if q_lower in c_title.lower() or q_lower in c_details.lower():
            matches.append(("Benchmark Results", c_title, c_details))

    st.markdown(f"**Found {len(matches)} matching results for '{html.escape(query)}':**")
    if matches:
        for cat, title, snippet in matches[:10]:
            # Highlight matching query text
            h_snippet = snippet
            try:
                # Case-insensitive replacement
                import re
                pattern = re.compile(re.escape(query), re.IGNORECASE)
                h_snippet = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", html.escape(snippet))
            except Exception:
                pass
            st.markdown(
                f"""
                <div class="cp-card" style="padding:12px 16px; margin-bottom:8px;">
                    <div style="font-size:0.75rem; text-transform:uppercase; color:var(--cp-accent); font-weight:700;">{cat}</div>
                    <div style="font-weight:700; font-size:0.95rem; margin:2px 0;">{title}</div>
                    <div style="font-size:0.82rem; color:var(--cp-muted); line-height:1.4;">{h_snippet}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("No matching content found. Try keywords like 'HMAC', 'ETA', 'Junction', 'Preemption', or 'Metrics'.")


def render_floating_contact_button() -> None:
    """Floating contact link fixed bottom-right via CSS, hidden in print (Feature 20)."""
    st.markdown(
        '<a href="Contact" class="cp-floating-contact">Contact Operator</a>',
        unsafe_allow_html=True,
    )


def render_footer(last_updated: Optional[str] = None) -> None:
    """Editorial footer with git commit date, back-to-top link, and license (Feature 4, 18)."""
    date_str = last_updated or get_git_commit_date()
    st.markdown(
        f"""
        <div class="cp-footer">
            <div>
                <b>ClearPath Autonomous Preemption System</b> | Open Source (MIT License)<br>
                <span>Research prototype for cyber-physical emergency traffic coordination. Not for safety-critical field operations.</span>
            </div>
            <div style="text-align:right;">
                <span>Last Updated: <b>{date_str}</b></span><br>
                <a href="#main-content" style="font-weight:600;">Back to top &uarr;</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
