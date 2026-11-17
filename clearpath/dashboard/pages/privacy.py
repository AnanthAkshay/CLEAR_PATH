"""Privacy Policy Page for ClearPath Multi-Agent Preemption Prototype.

Explains data collection transparency, local session-only storage,
absence of third-party tracking, UTM parameter handling with explicit consent,
and research prototype boundaries.
"""

from __future__ import annotations

import streamlit as st


def render_privacy_page() -> None:
    """Render honest, transparent Privacy Policy."""
    st.markdown("## Privacy Policy & Data Handling")
    st.markdown("Last Updated: 2026-11-17 | Open Source MIT Project")
    st.markdown(
        """
        ### 1. Fundamental Principle: No Surveillance or Third-Party Tracking
        ClearPath is an open-source academic and engineering research prototype. 
        We do not deploy third-party analytics trackers, tracking beacons, advertising cookies, or telemetry spyware. All simulation processing occurs within the ephemeral container running this Streamlit application.

        ### 2. Session State & Preferences Storage
        When you interact with ClearPath:
        - **Interface Preferences:** Your selection of Light or Dark mode, active simulation parameters, and navigation tab selections are stored in volatile Streamlit session state (`st.session_state`).
        - **Session Ephemerality:** When you close your browser tab or your session expires, all session state variables are permanently erased from memory.
        - **Zero Persistent Tracking Cookies:** We do not write tracking cookies to your browser storage.

        ### 3. Campaign & Referral Tracking (UTM Parameters)
        If you arrive at ClearPath via a URL containing standard UTM parameters (e.g., `utm_source`, `utm_campaign`):
        - **Explicit Consent Requirement:** These parameters are captured into session state **only if** you click **"Accept preferences"** on the initial cookie/preferences banner.
        - **If You Decline:** If you click "Decline preferences" or do not accept, all UTM query parameters are discarded and never stored in session state.
        - **Purpose:** Consented UTM tags are attached solely to voluntary inquiry submissions on the Contact form to assist project maintainers in identifying research referral sources.

        ### 4. Contact Form Inquiries
        Information voluntarily submitted via the Contact form (name, email address, topic, technical inquiry message) is processed in session memory for confirmation receipt generation. Submissions are not sold, shared, or distributed.

        ### 5. Source Code & Auditability
        In accordance with the MIT License, the complete source code governing this application is publicly inspectable and auditable on GitHub.
        """
    )


if __name__ == "__main__" or True:
    render_privacy_page()

