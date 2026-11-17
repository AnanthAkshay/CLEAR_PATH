"""Terms of Use Page for ClearPath Multi-Agent Preemption Prototype.

Accurate legal terms: simulation prototype boundaries, safety disclaimer,
MIT license terms, and limitation of liability.
"""

from __future__ import annotations

import streamlit as st


def render_terms_page() -> None:
    """Render Terms of Use and Prototype Safety Disclaimer."""
    st.markdown("## Terms of Use & Research Prototype Disclaimer")
    st.markdown("Last Updated: 2026-11-17 | Open Source MIT Project")
    st.markdown(
        """
        ### 1. Research Prototype Status
        ClearPath is an academic and engineering software prototype developed for cyber-physical simulation, multi-agent traffic negotiation, and cryptographic verification research. 
        **It is NOT certified for deployment in live municipal traffic management, life-safety operations, or real-world emergency vehicle routing.**

        ### 2. No Warranty or Safety Guarantee
        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. 

        Under no circumstances shall the authors, maintainers, or contributors be held liable for any claim, damages, traffic disruption, vehicular collision, or other liability arising from the use or misuse of this software in real-world or simulated environments.

        ### 3. Open Source MIT License
        Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, subject to the following conditions:

        The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

        ### 4. Permitted Use
        You may freely run, inspect, fork, benchmark, and extend ClearPath for educational, scientific, municipal research, and algorithmic evaluation purposes in synthetic or laboratory environments.
        """
    )


if __name__ == "__main__" or True:
    render_terms_page()

