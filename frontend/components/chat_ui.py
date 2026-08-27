"""Chat interface component."""

import streamlit as st


def render_chat() -> None:
    """Render the RAG chat panel (placeholder)."""
    st.subheader("Chat")
    st.info("RAG chat UI is not implemented yet.")
    st.chat_input("Ask a question about your sources…")
