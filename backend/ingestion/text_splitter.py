"""Text splitting utilities for chunked embeddings."""


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list[str]:
    """Split raw text into overlapping chunks for the vector store.

    Args:
        text: Source document text.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.

    Returns:
        Ordered list of text chunks.

    Raises:
        NotImplementedError: Until the splitter is implemented.
    """
    raise NotImplementedError("Text splitting is not implemented yet.")
