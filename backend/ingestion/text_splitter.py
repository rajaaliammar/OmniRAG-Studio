"""Text splitting utilities for chunked embeddings."""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.ingestion.errors import IngestionError


def split_documents(
    documents: list[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[Document]:
    """Split documents into overlapping chunks for the vector store.

    Metadata from each parent document is copied onto its chunks.

    Args:
        documents: Loaded documents (PDF pages, CSV rows, or web pages).
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.

    Returns:
        Ordered list of chunked documents.

    Raises:
        IngestionError: If ``documents`` is empty or splitter args are invalid.
    """
    if not documents:
        raise IngestionError("No documents were provided to split.")
    if chunk_size <= 0:
        raise IngestionError("chunk_size must be a positive integer.")
    if chunk_overlap < 0:
        raise IngestionError("chunk_overlap cannot be negative.")
    if chunk_overlap >= chunk_size:
        raise IngestionError(
            "chunk_overlap must be smaller than chunk_size."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )
    return splitter.split_documents(documents)


def split_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split raw text into overlapping string chunks.

    Args:
        text: Source document text.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Characters of overlap between consecutive chunks.

    Returns:
        Ordered list of text chunks.
    """
    documents = [Document(page_content=text, metadata={"source": "raw_text"})]
    return [
        chunk.page_content
        for chunk in split_documents(documents, chunk_size, chunk_overlap)
    ]
