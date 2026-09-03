"""Per-host pacing for page fetches."""

import logging
import time
from collections.abc import Callable
from urllib.parse import urlparse

from rss_retriever.domain.ports import PagePort


logger = logging.getLogger(__name__)


def host_of(url: str) -> str:
    """The host a pacing interval is keyed on: the URL's host, lower-cased, without a leading www."""
    return urlparse(url).netloc.lower().removeprefix("www.")


class PacedPageFetcher(PagePort):
    """A PagePort that waits between requests to the same host.

    Some sites rate-limit per IP with a window of a few requests and then answer
    403 to every client for minutes. Measured 2026-09-02 on thehill.com: the
    first two requests in a burst pass, the rest fail, the block clears within
    three minutes of backing off, and one request every three minutes holds.

    ``intervals`` maps host to the minimum seconds between requests; hosts not
    listed are not paced. The clock and sleep are injectable for tests.
    """

    def __init__(
        self,
        inner: PagePort,
        intervals: dict[str, float],
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.inner = inner
        self.intervals = {host_of(f"//{host}"): seconds for host, seconds in intervals.items()}
        self._clock = clock
        self._sleep = sleep
        self._last_request: dict[str, float] = {}

    def fetch(self, url: str) -> str | None:
        """Wait out the host's interval if its last request was too recent, then fetch."""
        host = host_of(url)
        interval = self.intervals.get(host, 0)
        if interval:
            self._wait_for(host, interval)
            self._last_request[host] = self._clock()
        return self.inner.fetch(url)

    def _wait_for(self, host: str, interval: float) -> None:
        last = self._last_request.get(host)
        if last is None:
            return
        remaining = interval - (self._clock() - last)
        if remaining > 0:
            logger.info("Pacing %s: waiting %.0fs", host, remaining)
            self._sleep(remaining)
