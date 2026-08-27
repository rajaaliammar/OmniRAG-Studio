"""PDF document loader."""

from pathlib import Path


def load_pdf(file_path: str | Path) -> list[str]:
    """Extract text pages from a PDF file.

    Args:
        file_path: Path to a local PDF.

    Returns:
        One string per page (or chunk, depending on the loader).

    Raises:
        NotImplementedError: Until the PDF loader is implemented.
    """
    raise NotImplementedError("PDF loading is not implemented yet.")
