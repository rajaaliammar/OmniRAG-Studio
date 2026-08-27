"""CSV tabular document loader."""

from pathlib import Path


def load_csv(file_path: str | Path) -> list[str]:
    """Convert CSV rows into text documents for embedding.

    Args:
        file_path: Path to a local CSV file.

    Returns:
        Text representations of rows or grouped records.

    Raises:
        NotImplementedError: Until the CSV loader is implemented.
    """
    raise NotImplementedError("CSV loading is not implemented yet.")
