"""Streamlit entrypoint for OmniRAG Studio."""

import streamlit as st

from components.chat_ui import render_chat
from components.dashboard_ui import render_dashboard
from components.uploader_ui import render_uploader

st.set_page_config(page_title="OmniRAG Studio", layout="wide")


def main() -> None:
    """Render the Streamlit shell: ingest, chat, and analytics tabs."""
    st.title("OmniRAG Studio")
    st.caption("Multi-source RAG chatbot with real-time analytics.")

    tab_chat, tab_ingest, tab_analytics = st.tabs(
        ["Chat", "Ingest", "Analytics"]
    )
    with tab_chat:
        render_chat()
    with tab_ingest:
        render_uploader()
    with tab_analytics:
        render_dashboard()


if __name__ == "__main__":
    main()
