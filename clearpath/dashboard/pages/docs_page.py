"""Documentation Page for ClearPath Multi-Agent Preemption Prototype.

Reads, caches, and renders markdown files from docs/*.md with code syntax blocks,
interactive document switcher, keyword filtering, and git timestamp tracking.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List
import streamlit as st

from clearpath.dashboard.components import get_git_commit_date

_DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"


@st.cache_data
def load_all_docs() -> Dict[str, str]:
    """Cache and read all markdown documentation files from docs/."""
    docs: Dict[str, str] = {}
    if not _DOCS_DIR.exists():
        return docs

    for md_file in sorted(_DOCS_DIR.glob("*.md")):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                docs[md_file.name] = f.read()
        except Exception:
            pass
    return docs


def render_docs_page() -> None:
    """Render interactive documentation viewer."""
    st.markdown("## Engineering Documentation & Reference Manuals")
    st.markdown(
        "Complete technical specifications, message protocols, agent algorithms, security threat models, and API references."
    )

    docs = load_all_docs()
    if not docs:
        st.warning("No markdown documentation files located in docs/ directory.")
        return

    # Document Selector
    doc_names = list(docs.keys())
    default_idx = doc_names.index("ARCHITECTURE.md") if "ARCHITECTURE.md" in doc_names else 0

    selected_doc = st.selectbox(
        "Select Reference Manual",
        doc_names,
        index=default_idx,
        help="Select any technical specification to inspect its contents.",
    )

    doc_content = docs.get(selected_doc, "")

    # Filter/Search within document
    search_term = st.text_input(
        "Filter sections within this manual",
        placeholder="Enter keyword to jump to relevant sections...",
    ).strip()

    st.markdown(f"**Manual:** `{selected_doc}` | **Last Updated:** `{get_git_commit_date()}`")
    st.markdown("---")

    if search_term:
        st.caption(f"Showing paragraphs matching '{search_term}':")
        paras = doc_content.split("\n\n")
        matched = [p for p in paras if search_term.lower() in p.lower()]
        if matched:
            for m in matched:
                st.markdown(m)
                st.markdown("---")
        else:
            st.info(f"No sections matching '{search_term}' found in {selected_doc}.")
    else:
        st.markdown(doc_content)


if __name__ == "__main__" or True:
    render_docs_page()

