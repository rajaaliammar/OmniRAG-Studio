"""PDF document loader using pypdf."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from langchain_core.documents import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PyPdfError

from backend.ingestion.errors import IngestionError

PdfSource = str | Path | bytes | BinaryIO


def load_pdf(
    file_path_or_bytes: PdfSource,
    *,
    source_name: str | None = None,
) -> list[Document]:
    """Extract text from a PDF, one LangChain document per page.

    Args:
        file_path_or_bytes: Filesystem path, raw PDF bytes, or a binary stream.
        source_name: Filename to store in metadata when the input is bytes.
            Ignored when a path is provided (the path name is used instead).

    Returns:
        Documents whose ``page_content`` is the page text and whose metadata
        contains ``source`` (filename) and ``page`` (1-based page number).

    Raises:
        FileNotFoundError: If a path is given and the file does not exist.
        IngestionError: If the PDF is unreadable, encrypted, or has no text.
    """
    stream, source = _resolve_pdf_source(file_path_or_bytes, source_name)

    try:
        reader = PdfReader(stream, strict=False)
    except (PdfReadError, PyPdfError, OSError) as exc:
        raise IngestionError(f"Unable to parse PDF '{source}': {exc}") from exc

    if reader.is_encrypted:
        raise IngestionError(
            f"PDF '{source}' is password-protected and cannot be ingested."
        )

    documents: list[Document] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:  # noqa: BLE001 — pypdf page errors vary
            raise IngestionError(
                f"Failed to extract text from '{source}' page {page_number}: {exc}"
            ) from exc
        if not text:
            continue
        documents.append(
            Document(
                page_content=text,
                metadata={"source": source, "page": page_number},
            )
        )

    if not documents:
        raise IngestionError(
            f"No extractable text found in PDF '{source}'."
        )
    return documents


def _resolve_pdf_source(
    file_path_or_bytes: PdfSource,
    source_name: str | None,
) -> tuple[BytesIO | BinaryIO, str]:
    """Return a readable binary stream and the metadata source filename."""
    if isinstance(file_path_or_bytes, bytes):
        if not file_path_or_bytes:
            raise IngestionError("PDF bytes are empty.")
        name = source_name or "uploaded.pdf"
        return BytesIO(file_path_or_bytes), name

    if isinstance(file_path_or_bytes, (str, Path)):
        path = Path(file_path_or_bytes)
        if not path.is_file():
            raise FileNotFoundError(f"PDF file not found: {path}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise IngestionError(f"Unable to read PDF '{path}': {exc}") from exc
        if not data:
            raise IngestionError(f"PDF file is empty: {path}")
        return BytesIO(data), path.name

    stream = file_path_or_bytes
    name = source_name or getattr(stream, "name", None) or "uploaded.pdf"
    name = Path(str(name)).name
    return stream, name
