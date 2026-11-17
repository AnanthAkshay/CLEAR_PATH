"""How It Works Page for ClearPath Multi-Agent Preemption Prototype.

Explains system architecture, agent roles (Dispatcher, Security, Junction, Guidance),
state machine transitions, and preemption negotiation protocols.
"""

from __future__ import annotations

import streamlit as st
from clearpath.dashboard.components import (
    render_agent_row,
    render_preemption_timeline,
)


def render_how_it_works_page() -> None:
    """Render editorial How It Works architectural breakdown."""
    st.markdown("## System Architecture & Multi-Agent Protocol")
    st.markdown(
        """
        ClearPath operates as a decentralized multi-agent system where four specialized agents collaborate over an asynchronous in-memory publish-subscribe message bus. 
        Each agent maintains independent internal state, evaluates deterministic rules, and enforces strict fail-safe invariants without centralized single points of failure.
        """
    )

    # ── Numbered Agent Rows ─────────────────────────────────────────────────────
    st.markdown("### The Four Specialized Agents")
    render_agent_row(
        num="01",
        name="Dispatcher Agent",
        role="Triage & Corridor Routing",
        algorithm_summary="Evaluates hospital capability scores, executes density-aware Dijkstra / A* route planning, and generates arrival ETA schedules per junction.",
        status="Core Routing",
    )
    render_agent_row(
        num="02",
        name="Security Gateway Agent",
        role="Cryptographic & Kinematic Defense",
        algorithm_summary="Verifies HMAC-SHA256 signature tokens, maintains sliding nonce cache against replay attacks, and validates vehicle kinematic speed and position continuity.",
        status="Zero-Trust Gate",
    )
    render_agent_row(
        num="03",
        name="Junction Controller Agent",
        role="Distributed Signal Actuation",
        algorithm_summary="Executes finite state machine transitions (Pre-Clear, Hold Green, Recovery, Fail-Safe), guarantees zero conflicting green phases, and flushes cross-traffic queues.",
        status="Intersection Actuator",
    )
    render_agent_row(
        num="04",
        name="Guidance Advisory Agent",
        role="Civilian Driver Cooperation",
        algorithm_summary="Scans 150m ahead of emergency vehicles, issues directional lane-clearing advisories to civilian drivers, and broadcasts corridor status to variable message signs.",
        status="Driver Cooperation",
    )

    # ── Preemption Flow Timeline ────────────────────────────────────────────────
    st.markdown("### Corridor Reservation Handshake")
    st.caption("Standard sequence for corridor preemption negotiation and signal locking.")
    render_preemption_timeline()

    # ── Junction Finite State Machine ───────────────────────────────────────────
    st.markdown("### Junction Finite State Machine")
    st.markdown(
        """
        Every signalized intersection runs an autonomous state machine with deterministic transitions:
        - **NORMAL:** Autonomous fixed-time or actuated signal cycling (North-South Green vs. East-West Green).
        - **PRE_CLEAR:** Pre-emption wave preparation. Downstream queues are cleared with brief green flushes; conflicting approaches transition through yellow clearance intervals.
        - **HOLD_GREEN:** Corridor approach locked in green state for approaching ambulance; conflicting approaches held in all-red state.
        - **RECOVERY:** Compensated green allocation for starved side-street traffic immediately after ambulance passes.
        - **FAIL_SAFE:** Automatic timeout recovery returning signals to standard cycling if communication drops.
        """
    )

    # ── Mathematical Formulations ───────────────────────────────────────────────
    st.markdown("### Hospital Triage & Route Cost Formulas")
    st.markdown(
        """
        **Hospital Scoring Function:**
        $$\\text{Score}(H) = \\alpha \\cdot \\frac{\\text{TravelTime}(H)}{\\max(\\text{TravelTimes})} + (1 - \\alpha) \\cdot \\left(1 - \\frac{\\text{Beds}(H)}{\\max(\\text{Beds})}\\right)$$
        Where $\\alpha = 0.70$ balances rapid transport time against receiving facility bed availability.

        **Density-Aware Edge Cost:**
        $$\\text{Cost}(e) = \\frac{\\text{Length}(e)}{\\text{FreeFlowSpeed}(e)} \\cdot \\left(1 + 0.15 \\cdot \\left(\\frac{N_e}{C_e}\\right)^4\\right)$$
        Where $N_e$ is current link vehicle count and $C_e$ is edge design capacity.
        """
    )


if __name__ == "__main__" or True:
    render_how_it_works_page()

