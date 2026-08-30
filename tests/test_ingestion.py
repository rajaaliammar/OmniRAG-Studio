"""Tests for the ingestion pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from backend.ingestion.csv_loader import load_csv
from backend.ingestion.errors import IngestionError
from backend.ingestion.pdf_loader import load_pdf
from backend.ingestion.text_splitter import split_documents, split_text
from backend.ingestion.web_loader import load_url, load_web


@pytest.fixture
def mock_vectorstore(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip OpenAI/Chroma writes in HTTP ingest tests."""
    monkeypatch.setattr(
        "backend.api.v1.ingestion.add_documents_to_vectorstore",
        lambda collection_name, documents: len(documents),
    )


def _build_pdf(text: str) -> bytes:
    """Construct a minimal single-page PDF containing ``text``."""
    escaped = (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("latin-1"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(output)


def test_load_pdf_from_bytes_attaches_page_metadata() -> None:
    """PDF pages should carry source filename and 1-based page number."""
    payload = _build_pdf("Hello OmniRAG")
    documents = load_pdf(payload, source_name="handbook.pdf")

    assert len(documents) == 1
    assert "Hello OmniRAG" in documents[0].page_content
    assert documents[0].metadata["source"] == "handbook.pdf"
    assert documents[0].metadata["page"] == 1


def test_load_pdf_from_path(tmp_path: Path) -> None:
    """PDF loader should read a file path and use the filename as source."""
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(_build_pdf("Path loaded page"))
    documents = load_pdf(pdf_path)

    assert documents[0].metadata["source"] == "notes.pdf"
    assert "Path loaded page" in documents[0].page_content


def test_load_pdf_missing_file() -> None:
    """A missing PDF path should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_pdf("definitely-missing.pdf")


def test_load_pdf_empty_bytes() -> None:
    """Empty PDF bytes should raise IngestionError."""
    with pytest.raises(IngestionError):
        load_pdf(b"")


def test_load_csv_rows_as_key_value_text() -> None:
    """Each CSV row should become descriptive key-value text."""
    csv_bytes = b"Title,Price\nWidget,9.99\nGadget,12.50\n"
    documents = load_csv(csv_bytes, source_name="catalog.csv")

    assert len(documents) == 2
    assert documents[0].page_content == "Row 1: Title: Widget, Price: 9.99"
    assert documents[1].page_content == "Row 2: Title: Gadget, Price: 12.50"
    assert documents[0].metadata == {"source": "catalog.csv", "row_index": 0}
    assert documents[1].metadata["row_index"] == 1


def test_load_csv_from_path(tmp_path: Path) -> None:
    """CSV loader should read a file path."""
    csv_path = tmp_path / "items.csv"
    csv_path.write_text("Name,Qty\nBolt,4\n", encoding="utf-8")
    documents = load_csv(csv_path)

    assert documents[0].metadata["source"] == "items.csv"
    assert "Name: Bolt" in documents[0].page_content
    assert "Qty: 4" in documents[0].page_content


def test_load_csv_header_only_raises() -> None:
    """A header-only CSV has no data rows and should fail."""
    with pytest.raises(IngestionError):
        load_csv(b"Title,Price\n", source_name="empty.csv")


def test_load_url_strips_chrome_and_keeps_main_text() -> None:
    """Scripts, CSS, nav, header, and footer must not appear in the document."""
    html = """
    <html>
      <head><title>Widget Spec</title>
        <style>.hidden { display:none }</style>
        <script>alert('xss')</script>
      </head>
      <body>
        <header>Site Header</header>
        <nav>Home | Docs</nav>
        <main>
          <h1>Installation</h1>
          <p>Run pip install omnirag-studio.</p>
        </main>
        <footer>Copyright</footer>
      </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.content = html.encode("utf-8")
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    with patch(
        "backend.ingestion.web_loader.requests.get",
        return_value=mock_response,
    ) as mocked_get:
        documents = load_url("https://example.com/docs")

    mocked_get.assert_called_once()
    assert len(documents) == 1
    content = documents[0].page_content
    assert "Installation" in content
    assert "pip install omnirag-studio" in content
    assert "alert" not in content
    assert "Site Header" not in content
    assert "Home | Docs" not in content
    assert "Copyright" not in content
    assert documents[0].metadata["source"] == "https://example.com/docs"
    assert documents[0].metadata["title"] == "Widget Spec"


def test_load_web_is_alias_for_load_url() -> None:
    """load_web should delegate to load_url."""
    with patch(
        "backend.ingestion.web_loader.load_url",
        return_value=[Document(page_content="ok", metadata={})],
    ) as mocked:
        result = load_web("https://example.com")
    mocked.assert_called_once_with("https://example.com")
    assert result[0].page_content == "ok"


def test_load_url_rejects_non_http() -> None:
    """file:// and other schemes must be rejected."""
    with pytest.raises(IngestionError):
        load_url("file:///etc/passwd")


def test_split_documents_preserves_metadata() -> None:
    """Splitter should copy parent metadata onto chunks."""
    documents = [
        Document(
            page_content="A" * 50 + "\n\n" + "B" * 50,
            metadata={"source": "notes.pdf", "page": 2},
        )
    ]
    chunks = split_documents(documents, chunk_size=40, chunk_overlap=10)
    assert len(chunks) >= 2
    assert all(chunk.metadata["source"] == "notes.pdf" for chunk in chunks)
    assert all(chunk.metadata["page"] == 2 for chunk in chunks)


def test_split_documents_rejects_bad_overlap() -> None:
    """Overlap must be smaller than chunk size."""
    documents = [Document(page_content="hello", metadata={})]
    with pytest.raises(IngestionError):
        split_documents(documents, chunk_size=10, chunk_overlap=10)


def test_split_text_returns_strings() -> None:
    """split_text should return raw chunk strings."""
    chunks = split_text("abcdefghijklmnopqrstuvwxyz", chunk_size=10, chunk_overlap=2)
    assert chunks
    assert all(isinstance(chunk, str) for chunk in chunks)


def test_ingest_pdf_endpoint_returns_counts_and_snippets(
    mock_vectorstore: None,
) -> None:
    """POST /api/v1/ingest/pdf should parse a PDF and return snippets."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/pdf",
        files={"file": ("handbook.pdf", _build_pdf("Hello OmniRAG"), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "handbook.pdf"
    assert body["document_count"] == 1
    assert body["chunk_count"] >= 1
    assert body["snippets"]
    assert "Hello OmniRAG" in body["snippets"][0]
    assert body["collection_name"] == "default_collection"
    assert body["stored_count"] == body["chunk_count"]


def test_ingest_csv_endpoint_returns_row_snippets(
    mock_vectorstore: None,
) -> None:
    """POST /api/v1/ingest/csv should parse rows into snippets."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/csv",
        files={
            "file": (
                "catalog.csv",
                b"Title,Price\nWidget,9.99\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "catalog.csv"
    assert body["document_count"] == 1
    assert "Widget" in body["snippets"][0]


def test_ingest_url_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    mock_vectorstore: None,
) -> None:
    """POST /api/v1/ingest/url should return chunk counts for a fetched page."""
    from fastapi.testclient import TestClient

    from backend.main import app

    page = Document(
        page_content="Main article about OmniRAG Studio.",
        metadata={"source": "https://example.com/article", "title": "Article"},
    )
    monkeypatch.setattr(
        "backend.api.v1.ingestion.load_url",
        lambda url: [page],
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/url",
        json={"url": "https://example.com/article"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "https://example.com/article"
    assert body["document_count"] == 1
    assert body["chunk_count"] >= 1
    assert "OmniRAG" in body["snippets"][0]
    assert body["collection_name"] == "default_collection"


def test_ingest_pdf_rejects_wrong_extension() -> None:
    """Non-PDF uploads should be rejected with 400."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/pdf",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_ingest_pdf_accepts_collection_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDF ingest should persist chunks into the requested collection."""
    from fastapi.testclient import TestClient

    from backend.main import app

    captured: dict[str, object] = {}

    def _fake_add(collection_name: str, documents: list) -> int:
        captured["name"] = collection_name
        captured["count"] = len(documents)
        return len(documents)

    monkeypatch.setattr(
        "backend.api.v1.ingestion.add_documents_to_vectorstore",
        _fake_add,
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/pdf",
        data={"collection_name": "pdf_handbook"},
        files={
            "file": ("handbook.pdf", _build_pdf("Hello OmniRAG"), "application/pdf")
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["collection_name"] == "pdf_handbook"
    assert captured["name"] == "pdf_handbook"
    assert captured["count"] == body["chunk_count"]


def test_ingest_store_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/v1/ingest/store should embed and save prepared documents."""
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr(
        "backend.api.v1.ingestion.add_documents_to_vectorstore",
        lambda collection_name, documents: len(documents),
    )
    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/store",
        json={
            "collection_name": "manual_chunks",
            "documents": [
                {
                    "page_content": "OmniRAG Studio indexes PDF, CSV, and web sources.",
                    "metadata": {"source": "notes.md"},
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "store"
    assert body["collection_name"] == "manual_chunks"
    assert body["document_count"] == 1
    assert body["stored_count"] >= 1
    assert "OmniRAG Studio" in body["snippets"][0]


def test_docs_endpoint_does_not_load_huggingface() -> None:
    """GET /docs must work without initializing HuggingFaceEmbeddings."""
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.vectorstore import embeddings as embeddings_mod

    embeddings_mod.reset_embedding_clients()
    embeddings_mod.HuggingFaceEmbeddings = None
    client = TestClient(app)
    response = client.get("/docs")
    assert response.status_code == 200
    assert embeddings_mod.HuggingFaceEmbeddings is None
    assert embeddings_mod.HuggingFaceEmbeddingsHolder._clients == {}


def test_ingest_file_dispatches_pdf(mock_vectorstore: None) -> None:
    """POST /api/v1/ingest/file should accept a PDF by extension."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/file",
        files={
            "file": (
                "handbook.pdf",
                _build_pdf("Hello OmniRAG"),
                "application/pdf",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"] == "handbook.pdf"
    assert body["stored_count"] >= 1
    assert isinstance(body["document_count"], int)
    assert isinstance(body["chunk_count"], int)


def test_ingest_file_dispatches_csv(mock_vectorstore: None) -> None:
    """POST /api/v1/ingest/file should accept a CSV by extension."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/file",
        files={
            "file": (
                "catalog.csv",
                b"Title,Price\nWidget,9.99\n",
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "catalog.csv"


def test_ingest_file_rejects_unsupported_extension() -> None:
    """POST /api/v1/ingest/file should reject non-PDF/CSV uploads with 400."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/file",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


def test_ingest_pdf_rejects_empty_file() -> None:
    """Empty uploads should return HTTP 400, not a 500."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/pdf",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "empty" in str(response.json()["detail"]).lower()


def test_ingest_csv_rejects_header_only_file(mock_vectorstore: None) -> None:
    """A CSV with headers but no rows should return HTTP 400."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("empty.csv", b"Title,Price\n", "text/csv")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]


def test_ingest_url_rejects_invalid_url() -> None:
    """Malformed URLs should fail Pydantic validation with HTTP 422."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/url",
        json={"url": "not-a-url", "collection_name": "docs"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]


def test_ingest_url_empty_page_returns_400(
    monkeypatch: pytest.MonkeyPatch,
    mock_vectorstore: None,
) -> None:
    """A page with no extractable text should return HTTP 400."""
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr("backend.api.v1.ingestion.load_url", lambda url: [])
    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/url",
        json={"url": "https://example.com/blank"},
    )
    assert response.status_code == 400
    assert "extractable" in str(response.json()["detail"]).lower()


def test_ingest_store_rejects_empty_page_content() -> None:
    """Prepared documents with blank page_content should return HTTP 422."""
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/ingest/store",
        json={
            "collection_name": "manual_chunks",
            "documents": [{"page_content": "", "metadata": {}}],
        },
    )
    assert response.status_code == 422

