"""CSV tabular document loader using pandas."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import BinaryIO, TextIO

import pandas as pd
from langchain_core.documents import Document
from pandas.errors import EmptyDataError, ParserError

from backend.ingestion.errors import IngestionError

CsvSource = str | Path | bytes | BinaryIO | TextIO


def load_csv(
    file_path_or_bytes: CsvSource,
    *,
    source_name: str | None = None,
) -> list[Document]:
    """Convert each CSV row into a descriptive key-value text document.

    Args:
        file_path_or_bytes: Filesystem path, raw CSV bytes, or a stream.
        source_name: Filename to store in metadata when the input is bytes.
            Ignored when a path is provided (the path name is used instead).

    Returns:
        One document per data row. ``page_content`` looks like
        ``"Row 1: Title: X, Price: Y"``. Metadata contains ``source``
        (filename) and ``row_index`` (0-based).

    Raises:
        FileNotFoundError: If a path is given and the file does not exist.
        IngestionError: If the CSV is empty, unreadable, or has no rows.
    """
    buffer, source = _resolve_csv_source(file_path_or_bytes, source_name)

    try:
        frame = pd.read_csv(
            buffer,
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
        )
    except EmptyDataError as exc:
        raise IngestionError(f"CSV '{source}' has no columns or rows.") from exc
    except (ParserError, UnicodeDecodeError, ValueError, OSError) as exc:
        raise IngestionError(f"Unable to parse CSV '{source}': {exc}") from exc

    if frame.empty:
        raise IngestionError(f"CSV '{source}' contains no data rows.")

    columns = [str(column) for column in frame.columns]
    documents: list[Document] = []
    for row_index, row in enumerate(frame.itertuples(index=False, name=None)):
        pairs = [
            f"{column}: {_stringify_cell(value)}"
            for column, value in zip(columns, row, strict=True)
        ]
        page_content = f"Row {row_index + 1}: {', '.join(pairs)}"
        documents.append(
            Document(
                page_content=page_content,
                metadata={"source": source, "row_index": row_index},
            )
        )
    return documents


def _stringify_cell(value: object) -> str:
    """Render a cell value as compact text."""
    if value is None:
        return ""
    return str(value).strip()


def _resolve_csv_source(
    file_path_or_bytes: CsvSource,
    source_name: str | None,
) -> tuple[BytesIO | BinaryIO | TextIO, str]:
    """Return a pandas-readable buffer and the metadata source filename."""
    if isinstance(file_path_or_bytes, bytes):
        if not file_path_or_bytes:
            raise IngestionError("CSV bytes are empty.")
        name = source_name or "uploaded.csv"
        return BytesIO(file_path_or_bytes), name

    if isinstance(file_path_or_bytes, (str, Path)):
        path = Path(file_path_or_bytes)
        if not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise IngestionError(f"Unable to read CSV '{path}': {exc}") from exc
        if not data:
            raise IngestionError(f"CSV file is empty: {path}")
        return BytesIO(data), path.name

    stream = file_path_or_bytes
    name = source_name or getattr(stream, "name", None) or "uploaded.csv"
    name = Path(str(name)).name
    return stream, name
