"""Image fetching over HTTP."""

import asyncio
import logging
from http import HTTPStatus

import aiohttp

from rss_retriever.domain.ports import ImagePort


logger = logging.getLogger(__name__)

# Enough parallelism to fetch a page's images in one round trip without
# opening a socket per image on sites that carry dozens.
MAX_CONNECTIONS = 10


class AiohttpImageFetcher(ImagePort):
    """Fetch images concurrently with aiohttp."""

    def __init__(self, timeout: int = 10, max_connections: int = MAX_CONNECTIONS):
        self.timeout = timeout
        self.max_connections = max_connections

    def fetch_many(self, urls: list[str]) -> list[bytes | None]:
        """One result per URL, None where the fetch failed; all in flight at once."""
        if not urls:
            return []
        return asyncio.run(self._fetch_all(urls))

    async def _fetch_all(self, urls: list[str]) -> list[bytes | None]:
        conn = aiohttp.TCPConnector(limit=self.max_connections)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            return list(await asyncio.gather(*(self._fetch_one(session, url) for url in urls)))

    async def _fetch_one(self, session: aiohttp.ClientSession, url: str) -> bytes | None:
        try:
            async with session.get(url) as response:
                if response.status == HTTPStatus.OK:
                    return await response.read()
                logger.warning("Failed to download image: %s, status: %d", url, response.status)
                return None
        except Exception as e:
            logger.error("Error downloading image %s: %s", url, e)
            return None
