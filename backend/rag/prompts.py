"""Prompt templates for grounded RAG answers."""

SYSTEM_PROMPT = (
    "You are OmniRAG Studio. Answer only from the provided context. "
    "Cite sources. If the context is insufficient, say you do not know."
)


def get_qa_prompt() -> str:
    """Return the default question-answering prompt template.

    Returns:
        A prompt string with placeholders for context and question.
    """
    return (
        f"{SYSTEM_PROMPT}\n\n"
        "Context:\n{context}\n\n"
        "Question: {question}\n\n"
        "Answer:"
    )
