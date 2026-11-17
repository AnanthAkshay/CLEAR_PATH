"""Contact Page for ClearPath Multi-Agent Preemption Prototype.

Features operator contact form with client/server validation, per-field error states,
overall error summary, form success panel with generated reference ID,
transparent UTM metadata attachment (if consented), and direct GitHub Issues link.
"""

from __future__ import annotations

import re
import uuid
import streamlit as st

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def render_contact_page() -> None:
    """Render operator contact and feedback submission page."""
    st.markdown("## Contact Engineering & Operator Support")
    st.markdown(
        """
        Have questions regarding ClearPath deployment, architecture, or evaluation? Submit an inquiry below.  
        *Note:* Because Streamlit Community Cloud instances are ephemeral, inquiries generate a local session confirmation reference and can optionally be opened directly on GitHub Issues.
        """
    )

    # ── Display Success State if already submitted in this session ──────────────
    if st.session_state.get("contact_submitted"):
        sub = st.session_state.contact_submission
        st.markdown(
            f"""
            <div class="cp-card" style="border-left: 3px solid var(--cp-signal-green); padding: 20px;">
                <div style="font-family:var(--cp-font-heading); font-size:1.15rem; font-weight:700; color:var(--cp-signal-green);">
                    Inquiry Transmitted Successfully
                </div>
                <div style="font-size:0.85rem; margin-top:8px;">
                    Reference Identifier: <b class="cp-mono">{sub['ref_id']}</b><br>
                    Operator: <b>{sub['name']}</b> ({sub['email']})<br>
                    Timestamp: <span class="cp-mono">{sub['timestamp']}</span>
                </div>
                <div style="font-size:0.82rem; color:var(--cp-muted); margin-top:12px;">
                    Message Digest: <i>"{sub['message'][:100]}..."</i>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if sub.get("utm"):
            st.caption(f"Attached Campaign Attribution: {sub['utm']}")

        col_reset, col_gh = st.columns([1, 2])
        with col_reset:
            if st.button("Submit Another Inquiry"):
                st.session_state.contact_submitted = False
                st.session_state.contact_submission = None
                st.rerun()
        with col_gh:
            st.markdown(
                '<a href="https://github.com/AnanthAkshay/ClearPath/issues" target="_blank" style="display:inline-block; margin-top:8px;">'
                'Open as an Issue on GitHub &rarr;</a>',
                unsafe_allow_html=True,
            )
        return

    # ── Contact Form with Validation ────────────────────────────────────────────
    errors = []
    field_errors = {}

    with st.form("contact_operator_form"):
        name = st.text_input("Operator Name", placeholder="e.g., Alex Morgan")
        email = st.text_input("Official Email Address", placeholder="e.g., alex.morgan@dot.gov")
        inquiry_type = st.selectbox(
            "Inquiry Topic",
            [
                "Research Collaboration",
                "Simulation Architecture Question",
                "Security & Cryptography Feedback",
                "Deployment Guidance",
                "Other Technical Inquiry",
            ],
        )
        message = st.text_area(
            "Technical Message",
            placeholder="Please describe your technical question, feedback, or deployment requirements (minimum 10 characters)...",
            height=140,
        )

        submitted = st.form_submit_button("Submit Technical Inquiry", type="primary")

        if submitted:
            # Validate Name
            if not name.strip():
                errors.append("Name field cannot be empty.")
                field_errors["name"] = "Name is required."

            # Validate Email
            if not email.strip():
                errors.append("Email address field cannot be empty.")
                field_errors["email"] = "Email address is required."
            elif not _EMAIL_REGEX.match(email.strip()):
                errors.append("Email address syntax is invalid.")
                field_errors["email"] = "Invalid email format."

            # Validate Message
            if len(message.strip()) < 10:
                errors.append("Message must be at least 10 characters in length.")
                field_errors["message"] = "Message must contain at least 10 characters."

            # Display Error State Summary (Feature 16)
            if errors:
                st.error("Please correct the following submission errors:\n- " + "\n- ".join(errors))
            else:
                # Capture consented UTM parameters (Feature 14)
                attached_utm = {}
                if st.session_state.get("cookie_consent"):
                    attached_utm = st.session_state.get("utm_params", {})

                # Generate Form Success Reference (Feature 15)
                ref_id = f"REF-2026-{uuid.uuid4().hex[:6].upper()}"
                st.session_state.contact_submitted = True
                st.session_state.contact_submission = {
                    "ref_id": ref_id,
                    "name": name.strip(),
                    "email": email.strip(),
                    "topic": inquiry_type,
                    "message": message.strip(),
                    "utm": attached_utm,
                    "timestamp": "2026-11-17 17:40:00 UTC",
                }
                st.rerun()

    # Direct Open-Source GitHub Link
    st.markdown("---")
    st.markdown(
        """
        **Direct GitHub Issue Submission:**  
        For public bug reports, architectural questions, or feature requests, visit the [ClearPath GitHub Repository](https://github.com/AnanthAkshay/ClearPath/issues).
        """
    )


if __name__ == "__main__" or True:
    render_contact_page()

