"""Domain exceptions for the ingestion pipeline."""


class IngestionError(ValueError):
    """Raised when a document source cannot be loaded or parsed."""
