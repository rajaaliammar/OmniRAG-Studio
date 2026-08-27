"""Document and URL upload component."""

import streamlit as st


def render_uploader() -> None:
    """Render PDF/CSV upload and URL ingest controls (placeholder)."""
    st.subheader("Ingest sources")
    st.info("Upload UI is not implemented yet.")
    st.file_uploader("PDF or CSV", type=["pdf", "csv"])
    st.text_input("Web URL")
