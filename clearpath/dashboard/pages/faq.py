"""Frequently Asked Questions Page for ClearPath Multi-Agent Preemption Prototype.

Provides 10 expandable real technical answers addressing security, algorithms,
junction actuation, civilian guidance, and simulation mechanics.
"""

from __future__ import annotations

import streamlit as st

FAQ_DATA = [
    {
        "question": "What is ClearPath-lite, and what core problem does it solve?",
        "answer": (
            "ClearPath is an open-source multi-agent emergency preemption platform designed to coordinate traffic signals ahead of verified emergency vehicles. Traditional emergency vehicle preemption (EVP) systems rely on unauthenticated optical strobes or sirens, which are prone to tampering, single-point failures, and severe side-street congestion. ClearPath integrates HMAC cryptographic verification, density-aware hospital dispatching, and distributed junction negotiation to eliminate ambulance stops while maintaining cross-traffic throughput."
        ),
    },
    {
        "question": "How does the Security Gateway Agent verify emergency preemption tokens?",
        "answer": (
            "Every preemption request contains a signature token: `<vehicle_id>.<nonce>.<tick>.<hmac_sha256>`. The Security Gateway Agent validates: (1) Cryptographic validity via constant-time HMAC-SHA256 verification using a pre-shared secret key; (2) Replay protection via a sliding-window nonce cache that rejects seen UUIDs; (3) Timestamp expiration where abs(current_tick - token_tick) <= 60s; (4) Kinematic speed plausibility ensuring reported velocity <= 35 m/s; and (5) Geometric coordinate continuity ensuring reported coordinates are reachable from previous positions."
        ),
    },
    {
        "question": "Why does ClearPath use HMAC-SHA256 rather than JSON Web Tokens (JWT)?",
        "answer": (
            "ClearPath avoids JWT to eliminate unnecessary complexity and vulnerability surface in safety-critical vehicle-to-infrastructure (V2I) communication. HMAC-SHA256 tokens are under 100 bytes (minimizing RF packet fragmentation on DSRC / C-V2X channels), require zero external library dependencies, execute in constant time, and eliminate standard JWT vulnerabilities such as header algorithm substitution ('none' algorithm attacks) and complex JSON deserialization overhead."
        ),
    },
    {
        "question": "How does the Dispatcher Agent score hospitals and compute corridor routes?",
        "answer": (
            "The Dispatcher calculates a composite score for each available trauma center:\n\n"
            "Score(H) = alpha * (TravelTime(H) / max_time) + (1 - alpha) * (1 - Beds(H) / max_beds)\n\n"
            "With alpha = 0.70 by default, prioritizing transit time while ensuring the receiving facility possesses adequate emergency capacity. Corridor paths are planned using density-aware Dijkstra / A* routing that applies an empirical BPR delay penalty based on real-time link vehicle counts."
        ),
    },
    {
        "question": "How do Junction Controllers guarantee zero conflicting green phases?",
        "answer": (
            "Junction agents operate a deterministic finite state machine (NORMAL -> PRE_CLEAR -> HOLD_GREEN -> RECOVERY). Conflicting approaches are forced into standard yellow change intervals followed by all-red clearance before any corridor approach receives green. In both rule-based and reinforcement learning policies, safety action masking forbids any action that would actuate conflicting greens concurrently."
        ),
    },
    {
        "question": "How does the system prevent side-street traffic starvation after an ambulance passes?",
        "answer": (
            "Immediately upon ambulance departure (signaled by a PassedNotice message), the junction transitions into a 31-second adaptive RECOVERY phase. During recovery, accumulated cross-traffic queues receive prioritized green phases before standard cyclic scheduling resumes, restoring network throughput to over 107% of uncoordinated baseline levels within 60 seconds."
        ),
    },
    {
        "question": "How does the Guidance Agent assist civilian drivers during preemption?",
        "answer": (
            "The Guidance Agent continuously scans 150 meters ahead of active ambulances. It issues directional lane-clearing advisories ('Clear lane: move right', 'Pull over and stop') directly to affected vehicles, causing civilian cars to decelerate and yield according to the Intelligent Driver Model (IDM), and updates Dynamic Variable Message Signs (VMS) on corridor approaches."
        ),
    },
    {
        "question": "What happens if an emergency vehicle deviates from its planned corridor route?",
        "answer": (
            "Telemetry messages broadcast vehicle coordinates every tick. If an ambulance deviates from its expected route, the Dispatcher Agent detects the deviation, broadcasts RevokeCorridor notices to downstream junctions to release locked signals back to autonomous operation, and initiates a fresh reservation handshake along the updated trajectory."
        ),
    },
    {
        "question": "How is deterministic simulation repeatability guaranteed?",
        "answer": (
            "ClearPath uses seeded pseudo-random number generators (`random.Random(seed)` and `numpy.random.default_rng(seed)`) for vehicle Poisson arrivals, origin-destination sampling, and driver kinematic heterogeneity. Identical random seeds produce bit-exact simulation runs across operating systems."
        ),
    },
    {
        "question": "What are the primary limitations of the current simulation model?",
        "answer": (
            "ClearPath-lite is a research prototype. Current limitations include: (1) 1D lane coordinates without lateral steering or physical shoulder pull-over physics; (2) In-process asynchronous message bus without real-world RF packet drop or mTLS encryption; and (3) Symmetric HMAC pre-shared keys rather than decentralized Public Key Infrastructure (PKI) with certificate revocation."
        ),
    },
]


def render_faq_page() -> None:
    """Render expandable FAQ page."""
    st.markdown("## Frequently Asked Questions")
    st.markdown(
        "Technical explanations regarding system architecture, cryptographic security, signal actuation, and simulation design."
    )

    for item in FAQ_DATA:
        with st.expander(item["question"], expanded=False):
            st.write(item["answer"])


if __name__ == "__main__" or True:
    render_faq_page()

