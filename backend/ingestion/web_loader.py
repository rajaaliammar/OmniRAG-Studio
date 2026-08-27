"""Web page loader."""


def load_web(url: str) -> list[str]:
    """Fetch and extract text from a public web URL.

    Args:
        url: HTTP or HTTPS page to ingest.

    Returns:
        Extracted text segments from the page.

    Raises:
        NotImplementedError: Until the web loader is implemented.
    """
    raise NotImplementedError("Web loading is not implemented yet.")
