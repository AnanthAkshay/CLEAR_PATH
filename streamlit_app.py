"""ClearPath Streamlit Multipage Entry Point.

Central single-deployment entry point for Streamlit Community Cloud and local execution.
Implements multipage navigation via st.navigation / st.Page, global editorial styling,
session preference management, sticky header, cookie consent banner, and floating actions.

Run with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repository root is on sys.path
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from clearpath.dashboard.components import (
    render_cookie_banner,
    render_floating_contact_button,
    render_footer,
    render_sticky_header,
    show_operator_dialog,
)
from clearpath.dashboard.theme import get_theme_css

# ─────────────────────────────────────────────────────────────────────────────
# Page Configuration (Must be FIRST Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ClearPath | Autonomous Emergency Preemption",
    page_icon="CP",
    layout="wide",
    initial_sidebar_state="auto",
)

# ─────────────────────────────────────────────────────────────────────────────
# Session State Initialization & UTM Capture
# ─────────────────────────────────────────────────────────────────────────────
def _init_global_state() -> None:
    defaults = {
        "dark_mode": False,
        "cookie_choice_made": False,
        "cookie_consent": False,
        "operator_authenticated": False,
        "show_operator_dialog": False,
        "utm_params": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Capture UTM parameters via st.query_params (Feature 14)
    # Stored only if user has consented, or held tentatively until consent
    params = dict(st.query_params)
    utm_keys = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]
    found_utm = {k: params[k] for k in utm_keys if k in params}
    if found_utm and st.session_state.get("cookie_consent"):
        st.session_state.utm_params = found_utm


_init_global_state()

# ─────────────────────────────────────────────────────────────────────────────
# Inject Editorial Theme CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(get_theme_css(st.session_state.dark_mode), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Multipage Definition (st.navigation / st.Page)
# ─────────────────────────────────────────────────────────────────────────────
pages = [
    st.Page(
        "clearpath/dashboard/pages/home.py",
        title="Home",
        url_path="",
        default=True,
    ),
    st.Page(
        "clearpath/dashboard/pages/console.py",
        title="Console",
        url_path="console",
    ),
    st.Page(
        "clearpath/dashboard/pages/how_it_works.py",
        title="How It Works",
        url_path="how-it-works",
    ),
    st.Page(
        "clearpath/dashboard/pages/security.py",
        title="Security",
        url_path="security",
    ),
    st.Page(
        "clearpath/dashboard/pages/results.py",
        title="Results",
        url_path="results",
    ),
    st.Page(
        "clearpath/dashboard/pages/docs_page.py",
        title="Documentation",
        url_path="docs",
    ),
    st.Page(
        "clearpath/dashboard/pages/faq.py",
        title="FAQ",
        url_path="faq",
    ),
    st.Page(
        "clearpath/dashboard/pages/contact.py",
        title="Contact",
        url_path="contact",
    ),
    st.Page(
        "clearpath/dashboard/pages/privacy.py",
        title="Privacy",
        url_path="privacy",
    ),
    st.Page(
        "clearpath/dashboard/pages/terms.py",
        title="Terms",
        url_path="terms",
    ),
]

nav = st.navigation(pages, position="sidebar")

# ─────────────────────────────────────────────────────────────────────────────
# Global Shell Layout: Header, Cookie Banner, Page Runner, Floating Button, Footer
# ─────────────────────────────────────────────────────────────────────────────
current_title = nav.title if hasattr(nav, "title") else "ClearPath"

# 1. Sticky Header with Skip link & Theme Toggle
render_sticky_header(current_page=current_title, dark_mode=st.session_state.dark_mode)

# 2. Preferences & Cookie Notice
render_cookie_banner()

# 3. Operator Sign-In Modal Trigger
if st.session_state.get("show_operator_dialog"):
    show_operator_dialog()

# 4. Run Navigated Page
nav.run()

# 5. Floating Contact Button (Feature 20)
render_floating_contact_button()

# 6. Global Editorial Footer (Feature 4, 18)
render_footer()

