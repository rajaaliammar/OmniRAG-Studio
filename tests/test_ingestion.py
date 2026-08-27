"""Tests for the ingestion pipeline."""

import pytest


def test_pdf_loader_placeholder() -> None:
    """PDF loader should raise until implemented."""
    from backend.ingestion.pdf_loader import load_pdf

    with pytest.raises(NotImplementedError):
        load_pdf("sample.pdf")


def test_csv_loader_placeholder() -> None:
    """CSV loader should raise until implemented."""
    from backend.ingestion.csv_loader import load_csv

    with pytest.raises(NotImplementedError):
        load_csv("sample.csv")


def test_web_loader_placeholder() -> None:
    """Web loader should raise until implemented."""
    from backend.ingestion.web_loader import load_web

    with pytest.raises(NotImplementedError):
        load_web("https://example.com")
