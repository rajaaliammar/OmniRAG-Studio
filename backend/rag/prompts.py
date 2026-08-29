"""Prompt templates for grounded RAG answers."""

SYSTEM_PROMPT = (
    "You are OmniRAG Studio. Answer only from the provided context. "
    "Cite sources. If the context is insufficient, say you do not know."
)

GROUNDED_SYSTEM_PROMPT = (
    "You are OmniRAG Studio, a retrieval-augmented assistant. "
    "Use ONLY the numbered CONTEXT passages. Do not use outside knowledge. "
    "If the context does not contain the answer, say you do not know. "
    "Cite supporting passages with bracket markers like [1] and [2]. "
    "Do not invent sources, page numbers, row indices, or URLs."
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


def build_grounded_user_prompt(
    question: str,
    context: str,
    history: str = "",
) -> str:
    """Build the user turn that carries history, context, and the question.

    Args:
        question: Current user question.
        context: Numbered retrieved passages.
        history: Optional formatted prior turns.

    Returns:
        Prompt text for the human message.
    """
    parts: list[str] = []
    if history.strip():
        parts.append("CONVERSATION HISTORY:")
        parts.append(history.strip())
        parts.append("")
    parts.append("CONTEXT:")
    parts.append(context.strip() or "(no passages retrieved)")
    parts.append("")
    parts.append(f"QUESTION: {question.strip()}")
    parts.append("")
    parts.append("ANSWER:")
    return "\n".join(parts)
