"""Web page loader using requests and BeautifulSoup."""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag
from langchain_core.documents import Document
from requests import RequestException

from backend.ingestion.errors import IngestionError

_STRIP_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "iframe",
    "svg",
    "canvas",
    "form",
    "nav",
    "header",
    "footer",
    "aside",
)
_REQUEST_TIMEOUT_SECONDS = 15
_USER_AGENT = (
    "OmniRAG-Studio/0.1 (+https://github.com/rajaaliammar/OmniRAG-Studio)"
)
_MAX_HTML_BYTES = 5 * 1024 * 1024


def load_url(url: str) -> list[Document]:
    """Fetch a public web page and extract clean main-body text.

    Scripts, stylesheets, navigation, headers, and footers are removed
    before text extraction.

    Args:
        url: HTTP or HTTPS page to ingest.

    Returns:
        A single document whose metadata contains ``source`` (the URL)
        and ``title`` (the HTML page title, if present).

    Raises:
        IngestionError: If the URL is invalid, the fetch fails, or no
            text content remains after cleaning.
    """
    normalized = _validate_url(url)
    html = _fetch_html(normalized)
    title, text = _extract_main_content(html)
    if not text:
        raise IngestionError(
            f"No extractable text found at '{normalized}' after cleaning."
        )
    return [
        Document(
            page_content=text,
            metadata={"source": normalized, "title": title},
        )
    ]


def load_web(url: str) -> list[Document]:
    """Alias for :func:`load_url`.

    Args:
        url: HTTP or HTTPS page to ingest.

    Returns:
        Documents produced by :func:`load_url`.
    """
    return load_url(url)


def _validate_url(url: str) -> str:
    """Require an http(s) URL with a host."""
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IngestionError(
            "URL must be an absolute http:// or https:// address."
        )
    return candidate


def _fetch_html(url: str) -> str:
    """Download HTML with a bounded timeout and size cap."""
    try:
        response = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise IngestionError(f"Timed out fetching '{url}'.") from exc
    except RequestException as exc:
        raise IngestionError(f"Failed to fetch '{url}': {exc}") from exc

    content_type = (response.headers.get("Content-Type") or "").lower()
    if content_type and not any(
        token in content_type for token in ("html", "xml", "text/plain")
    ):
        raise IngestionError(
            f"URL '{url}' did not return HTML (Content-Type: {content_type})."
        )
    if len(response.content) > _MAX_HTML_BYTES:
        raise IngestionError(
            f"Page at '{url}' exceeds the {_MAX_HTML_BYTES // (1024 * 1024)} MB size limit."
        )
    return response.text


def _extract_main_content(html: str) -> tuple[str, str]:
    """Return ``(title, cleaned_text)`` from raw HTML."""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    if not isinstance(root, Tag):
        text = soup.get_text(separator="\n", strip=True)
        return title, _normalize_whitespace(text)

    text = root.get_text(separator="\n", strip=True)
    return title, _normalize_whitespace(text)


def _normalize_whitespace(text: str) -> str:
    """Collapse blank lines while preserving paragraph breaks."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
