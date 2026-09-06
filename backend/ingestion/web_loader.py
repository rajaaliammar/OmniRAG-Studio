"""Web page loader using requests and BeautifulSoup."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag
from langchain_core.documents import Document
from requests import HTTPError, RequestException, Timeout

from backend.ingestion.errors import IngestionError

logger = logging.getLogger(__name__)

# Structural chrome only — keep content-bearing tags intact.
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
_STRIP_ROLES = {
    "navigation",
    "banner",
    "contentinfo",
    "complementary",
    "search",
    "menu",
    "menubar",
    "tablist",
    "toolbar",
}
_REQUEST_TIMEOUT_SECONDS = 25
_MAX_HTML_BYTES = 5 * 1024 * 1024

# Mimic a mainstream desktop browser so hosts (e.g. GitHub) do not soft-block.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Exact one-line UI chrome only — never match content-bearing sentences.
_UI_NOISE_LABELS = frozenset(
    {
        "follow",
        "unfollow",
        "following",
        "followers",
        "overview",
        "repositories",
        "projects",
        "packages",
        "stars",
        "star",
        "sponsor",
        "sponsoring",
        "achievements",
        "contributions",
        "activity",
        "discussions",
        "insights",
        "settings",
        "issues",
        "pull requests",
        "actions",
        "wiki",
        "sign in",
        "sign up",
        "sign out",
        "skip to content",
        "skip to main content",
        "toggle navigation",
        "notifications",
        "marketplace",
        "dashboard",
        "load more",
        "show more",
        "view all",
        "see all",
        "block or report",
        "hireable",
    }
)

_UI_NOISE_PATTERNS = (
    re.compile(r"^\d+\s*(stars?|forks?|watching|followers?)$", re.IGNORECASE),
)

_CONTENT_SELECTORS = (
    ".markdown-body",
    "[itemprop='articleBody']",
    "article",
    "main",
    "#readme",
    ".js-profile-editable-area",
    "#user-profile-frame",
)


def load_url(url: str) -> list[Document]:
    """Fetch a public web page and extract clean main-body text.

    Uses browser-like request headers, maps network/HTTP failures to
    :class:`IngestionError`, and preserves bio / repository / README text
    while stripping basic HTML chrome.

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
    try:
        html = _fetch_html(normalized)
        title, text = _extract_main_content(html, page_url=normalized)
    except IngestionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected failure while loading URL '%s'", normalized)
        raise IngestionError(
            f"Unable to extract content from '{normalized}': {exc}"
        ) from exc

    if not text.strip():
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


def _safe_attr(el: Any, name: str, default: Any = None) -> Any:
    """Return ``el.get(name)`` only when ``el`` is a real Tag."""
    if el is None or not isinstance(el, Tag):
        return default
    try:
        value = el.get(name, default)
    except (AttributeError, TypeError):
        return default
    return default if value is None else value


def _safe_text(el: Any, separator: str = " ") -> str:
    """Return stripped text from a Tag, or ``\"\"`` when missing."""
    if el is None or not isinstance(el, Tag):
        return ""
    try:
        return el.get_text(separator, strip=True)
    except (AttributeError, TypeError):
        return ""


def _safe_select_one(root: Any, selector: str) -> Tag | None:
    """``select_one`` with null-safe root handling."""
    if root is None or not isinstance(root, (BeautifulSoup, Tag)):
        return None
    try:
        node = root.select_one(selector)
    except (AttributeError, TypeError, ValueError):
        return None
    return node if isinstance(node, Tag) else None


def _safe_select(root: Any, selector: str) -> list[Tag]:
    """``select`` with null-safe root handling."""
    if root is None or not isinstance(root, (BeautifulSoup, Tag)):
        return []
    try:
        nodes = root.select(selector)
    except (AttributeError, TypeError, ValueError):
        return []
    return [node for node in nodes if isinstance(node, Tag)]


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
    """Download HTML with browser headers, timeout, and size cap."""
    try:
        response = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers=_BROWSER_HEADERS,
            allow_redirects=True,
        )
        response.raise_for_status()
    except Timeout as exc:
        raise IngestionError(
            f"Timed out fetching '{url}'. The remote host did not respond "
            f"within {_REQUEST_TIMEOUT_SECONDS}s."
        ) from exc
    except HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in {401, 403}:
            raise IngestionError(
                f"Access denied while fetching '{url}' (HTTP {status}). "
                "The site may block scrapers or require authentication."
            ) from exc
        if status == 404:
            raise IngestionError(f"Page not found at '{url}' (HTTP 404).") from exc
        if status == 429:
            raise IngestionError(
                f"Rate-limited while fetching '{url}' (HTTP 429). Try again later."
            ) from exc
        raise IngestionError(
            f"Failed to fetch '{url}'"
            + (f" (HTTP {status})" if status else "")
            + f": {exc}"
        ) from exc
    except RequestException as exc:
        raise IngestionError(f"Network error while fetching '{url}': {exc}") from exc

    headers = getattr(response, "headers", None) or {}
    content_type = str(headers.get("Content-Type") or "").lower()
    if content_type and not any(
        token in content_type for token in ("html", "xml", "text/plain", "json")
    ):
        raise IngestionError(
            f"URL '{url}' did not return HTML (Content-Type: {content_type})."
        )
    content = getattr(response, "content", b"") or b""
    if len(content) > _MAX_HTML_BYTES:
        raise IngestionError(
            f"Page at '{url}' exceeds the "
            f"{_MAX_HTML_BYTES // (1024 * 1024)} MB size limit."
        )
    response.encoding = (
        getattr(response, "apparent_encoding", None)
        or getattr(response, "encoding", None)
        or "utf-8"
    )
    return response.text or ""


def _extract_main_content(html: str, page_url: str = "") -> tuple[str, str]:
    """Return ``(title, cleaned_text)`` from raw HTML."""
    if not (html or "").strip():
        return "", ""

    soup = BeautifulSoup(html, "html.parser")
    title = ""
    title_tag = getattr(soup, "title", None)
    if isinstance(title_tag, Tag) and title_tag.string:
        title = str(title_tag.string).strip()

    _strip_chrome(soup)

    host = urlparse(page_url).netloc.lower()
    parts: list[str] = []
    if "github.com" in host:
        github_text = _extract_github_content(soup, title=title)
        if github_text:
            # Prefer the structured GitHub extract; skip noisy body fallback.
            return title, github_text

    root = _pick_content_root(soup)
    if isinstance(root, Tag):
        root_text = _filter_noise_lines(
            _safe_text(root, separator="\n")
        )
        if root_text:
            parts.append(root_text)
    else:
        body = getattr(soup, "body", None)
        body_text = _filter_noise_lines(
            _safe_text(body, separator="\n")
            if isinstance(body, Tag)
            else soup.get_text(separator="\n", strip=True)
        )
        if body_text:
            parts.append(body_text)

    merged = _merge_unique_blocks(parts)
    if merged:
        return title, merged

    fallback = _normalize_whitespace(soup.get_text(separator="\n", strip=True))
    return title, fallback


def _strip_chrome(soup: BeautifulSoup) -> None:
    """Remove structural chrome tags without deleting article content."""
    for tag in list(soup.find_all(_STRIP_TAGS)):
        if isinstance(tag, Tag):
            tag.decompose()

    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        role = str(_safe_attr(tag, "role", "") or "").strip().lower()
        if role in _STRIP_ROLES:
            tag.decompose()
            continue
        class_attr = _safe_attr(tag, "class", []) or []
        if isinstance(class_attr, str):
            classes = class_attr.lower()
        else:
            try:
                classes = " ".join(str(item) for item in class_attr).lower()
            except TypeError:
                classes = ""
        if any(
            token in classes
            for token in (
                "underline-nav",
                "underlinenav",
                "tabnav",
                "navbar",
                "breadcrumb",
                "site-footer",
                "footer",
                "site-header",
                "app-header",
            )
        ):
            tag.decompose()


def _pick_content_root(soup: BeautifulSoup) -> Tag | None:
    """Prefer semantic content containers over the full body."""
    for selector in _CONTENT_SELECTORS:
        node = _safe_select_one(soup, selector)
        if isinstance(node, Tag):
            text = _safe_text(node)
            if len(text) >= 20:
                return node
    body = getattr(soup, "body", None)
    return body if isinstance(body, Tag) else None


def _extract_github_content(soup: BeautifulSoup, title: str = "") -> str:
    """Pull profile bio, pinned repos, languages, and README text."""
    blocks: list[str] = []
    if title:
        blocks.append(title)

    bio = _safe_select_one(
        soup, ".js-profile-editable-area .p-note"
    ) or _safe_select_one(soup, "[data-bio-text]")
    bio_text = _safe_text(bio)
    if bio_text:
        blocks.append(f"Bio: {bio_text}")

    name = _safe_select_one(soup, ".p-name") or _safe_select_one(
        soup, "[itemprop='name']"
    )
    name_text = _safe_text(name)
    if name_text:
        blocks.append(f"Name: {name_text}")

    handle = _safe_select_one(soup, ".p-nickname") or _safe_select_one(
        soup, "[itemprop='additionalName']"
    )
    handle_text = _safe_text(handle)
    if handle_text:
        blocks.append(f"Username: {handle_text}")

    for item in _safe_select(
        soup,
        ".pinned-item-list-item, "
        "[data-testid='pinned-item'], "
        ".js-pinned-items-reorder-list li",
    ):
        line = _format_repo_card(item, pinned=True)
        if line:
            blocks.append(line)

    for item in _safe_select(
        soup,
        "#user-repositories-list li, .js-repo-list li, article.Box-row",
    ):
        line = _format_repo_card(item, pinned=False)
        if line and line not in blocks:
            blocks.append(line)

    readme = _safe_select_one(soup, "#readme .markdown-body") or _safe_select_one(
        soup, ".markdown-body"
    )
    readme_text = _filter_noise_lines(_safe_text(readme, separator="\n"))
    if readme_text:
        blocks.append("README:")
        blocks.append(readme_text[:4000])

    return _filter_noise_lines("\n".join(blocks))


def _format_repo_card(item: Tag, *, pinned: bool) -> str:
    """Build a clean repository line from a GitHub card element."""
    if not isinstance(item, Tag):
        return ""

    repo_name = (
        _safe_select_one(item, "a[itemprop='url']")
        or _safe_select_one(item, "[itemprop='name codeRepository']")
        or _safe_select_one(item, "a.Link--primary")
        or _safe_select_one(item, "span.repo")
        or _safe_select_one(item, "h3 a")
        or _safe_select_one(item, "a[href*='/']")
    )
    name_text = _safe_text(repo_name)
    # Prefer href path tail when the anchor text is empty chrome.
    if not name_text or _is_ui_noise_line(name_text):
        href = str(_safe_attr(repo_name, "href", "") or "")
        if href and href.count("/") >= 1:
            name_text = href.rstrip("/").split("/")[-1]
    if not name_text or _is_ui_noise_line(name_text):
        return ""

    description = (
        _safe_select_one(item, ".pinned-item-desc")
        or _safe_select_one(item, "[itemprop='description']")
        or _safe_select_one(item, "p.color-fg-muted")
        or _safe_select_one(item, "p")
    )
    desc_text = _safe_text(description)
    if desc_text and (
        _is_ui_noise_line(desc_text) or len(desc_text) <= 2
    ):
        desc_text = ""

    language = _safe_select_one(item, "[itemprop='programmingLanguage']")
    language_text = _safe_text(language)

    prefix = "Pinned repository" if pinned else "Repository"
    line = f"{prefix}: {name_text}"
    if desc_text:
        line = f"{line} — {desc_text}"
    if language_text and not _is_ui_noise_line(language_text):
        line = f"{line} (Language: {language_text})"
    return line


def _is_ui_noise_line(line: str) -> bool:
    """Return True for exact navigation / chrome labels and counters."""
    cleaned = " ".join((line or "").split()).strip()
    if not cleaned:
        return True
    lowered = cleaned.lower().rstrip(":")
    if lowered in _UI_NOISE_LABELS:
        return True
    if any(pattern.match(cleaned) for pattern in _UI_NOISE_PATTERNS):
        return True
    # Empty nav anchors often render as "#" or "/" only.
    if cleaned in {"#", "/", "•", "|", "-"}:
        return True
    return False


def _filter_noise_lines(text: str) -> str:
    """Drop exact UI chrome lines; keep all other content intact."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if _is_ui_noise_line(line):
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(line)
    return "\n".join(kept)


def _merge_unique_blocks(parts: list[str]) -> str:
    """Join extraction passes while skipping duplicate lines."""
    kept: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for line in part.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            kept.append(cleaned)
    return "\n".join(kept)


def _normalize_whitespace(text: str) -> str:
    """Collapse blank lines while preserving paragraph breaks."""
    lines = [line.strip() for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line)
