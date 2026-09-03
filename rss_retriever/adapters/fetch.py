"""Page fetching with a browser's TLS fingerprint."""

import logging

from curl_cffi import requests as curl_requests

from rss_retriever.domain.ports import PagePort


logger = logging.getLogger(__name__)

HTTP_OK = 200


class BrowserPageFetcher(PagePort):
    """Fetch pages presenting a real browser's TLS handshake and header set.

    Some news sites answer a plain ``requests`` download with 403 regardless of
    the User-Agent: the block is on the shape of the handshake, which bot
    managers fingerprint. ``curl_cffi`` reproduces a browser's. Measured
    2026-09-02: Politico returned 403 to ``requests`` and newspaper4k on every
    article and 200 with the full page when impersonating Chrome.
    """

    def __init__(self, impersonate: str = "chrome", timeout: int = 10):
        """``impersonate`` is a curl_cffi browser name ("chrome", "safari", "firefox", ...)."""
        self.impersonate = impersonate
        self.timeout = timeout

    def fetch(self, url: str) -> str | None:
        """The page HTML, or ``None`` on any failure so the caller can try another way."""
        try:
            response = curl_requests.get(url, impersonate=self.impersonate, timeout=self.timeout)
        except Exception as e:
            logger.warning("Browser-fingerprint fetch failed for %s: %s", url, e)
            return None
        if response.status_code != HTTP_OK:
            logger.warning("Browser-fingerprint fetch of %s returned %d", url, response.status_code)
            return None
        return response.text
