"""File system storage adapter implementation."""

import asyncio
import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import aiohttp
import requests

from rss_retriever.config import Config
from rss_retriever.domain.article import Article
from rss_retriever.domain.ports import StoragePort


logger = logging.getLogger(__name__)


class FileSystemStorage(StoragePort):
    """Implementation of StoragePort using the file system"""

    def __init__(self, storage_dir: str | Path, request_timeout: int = Config.request_timeout):
        """Initialize with storage directory.

        Args:
            storage_dir (str | Path): Path to the directory where articles will be stored.
            request_timeout (int): Per-request timeout, in seconds, for image downloads.
        """
        self.request_timeout = request_timeout
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

        # Indexes are cached in memory and re-read only if absent. Re-parsing them
        # per article made storage cost grow quadratically with corpus size.
        self._index_cache: dict | None = None
        self._url_index_cache: dict | None = None
        self._defer_index_writes = False

        # Create index for faster access
        self.index_file = self.storage_dir / "index.json"
        if not self.index_file.exists():
            self._write_index({})

        # Create URL index for duplicate detection
        self.url_index_file = self.storage_dir / "url_index.json"
        if not self.url_index_file.exists():
            self._write_url_index({})

    @contextmanager
    def batch_writes(self) -> Iterator["FileSystemStorage"]:
        """Defer index writes until the block exits.

        Each ``save_article`` normally rewrites both index files so a crash cannot
        lose an article. That makes bulk ingestion quadratic in corpus size, so for
        backfills wrap the loop in this context manager and pay the write cost once::

            with storage.batch_writes():
                for article in many_articles:
                    storage.save_article(article)

        Article payloads are still written immediately; only the indexes are
        deferred. If the block raises, the indexes are still flushed so that what
        did land on disk stays discoverable.
        """
        self._defer_index_writes = True
        try:
            yield self
        finally:
            self._defer_index_writes = False
            if self._index_cache is not None:
                self._write_index(self._index_cache)
            if self._url_index_cache is not None:
                self._write_url_index(self._url_index_cache)

    async def _download_image(self, session: aiohttp.ClientSession, image_url: str, img_path: Path) -> bool:
        """Download a single image asynchronously.

        Args:
            session (aiohttp.ClientSession): The aiohttp session to use
            image_url (str): URL of the image to download
            img_path (Path): Where to save the image

        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            async with session.get(image_url, timeout=timeout) as response:
                if response.status == requests.codes["ok"]:
                    content = await response.read()
                    img_path.write_bytes(content)
                    logger.info("Saved image: %s", img_path)
                    return True
                logger.warning("Failed to download image: %s, status: %d", image_url, response.status)
                return False
        except Exception as e:
            logger.error("Error downloading image %s: %s", image_url, e)
            return False

    async def _download_images(self, article: Article, images_dir: Path) -> None:
        """Download all images for an article concurrently.

        Args:
            article (Article): The article containing images to download
            images_dir (Path): Directory to save images in
        """
        # Configure connection pooling
        conn = aiohttp.TCPConnector(limit=10)  # Limit concurrent connections
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)

        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            # Prepare download tasks
            tasks = []
            for i, image in enumerate(article.images):
                img_path = images_dir / image.local_path
                if not img_path.exists():
                    tasks.append((i, self._download_image(session, image.original_url, img_path)))

            # Run downloads concurrently with gather
            if tasks:
                results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

                # Update successful downloads
                for (i, _), success in zip(tasks, results, strict=True):
                    if isinstance(success, bool) and success:
                        article.images[i].local_path = f"images/{article.images[i].local_path}"

    def save_article(self, article: Article) -> None:
        """Save an article with its images to the filesystem.

        Args:
            article (Article): The article to save.
        """
        # Create directory for this article
        article_dir = self.storage_dir / article.id
        article_dir.mkdir(exist_ok=True)

        # Create images directory
        images_dir = article_dir / "images"
        images_dir.mkdir(exist_ok=True)

        # Download images concurrently
        asyncio.run(self._download_images(article, images_dir))

        # Save article content
        content_file = article_dir / "content.txt"
        content_file.write_text(article.content, encoding="utf-8")

        # Save HTML content if available
        if article.html_content:
            html_file = article_dir / "content.html"
            html_file.write_text(article.html_content, encoding="utf-8")

        # Save metadata
        metadata_file = article_dir / "metadata.json"
        metadata_file.write_text(
            json.dumps(article.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Update indices
        self._update_index(article)
        self._update_url_index(article)

        logger.info("Saved article: %s (ID: %s)", article.title, article.id)

    def get_article(self, article_id: str) -> Article | None:
        """Get article by ID.

        Args:
            article_id (str): The unique identifier of the article.

        Returns:
            Article | None: The article if found, None otherwise.
        """
        article_dir = self.storage_dir / article_id
        metadata_file = article_dir / "metadata.json"

        if not metadata_file.exists():
            logger.warning("Article not found: %s", article_id)
            return None

        try:
            article_dict = json.loads(metadata_file.read_text(encoding="utf-8"))
            return Article.from_dict(article_dict)

        except json.JSONDecodeError as e:
            logger.error("JSON parse error reading article %s: %s", article_id, e)
            return None
        except OSError as e:
            logger.error("File system error reading article %s: %s", article_id, e)
            return None
        except Exception as e:
            logger.error("Unexpected error reading article %s: %s", article_id, e)
            return None

    def get_recent_articles(self, limit: int = 50) -> list[Article]:
        """Get most recent articles from index.

        Args:
            limit (int, optional): Maximum number of articles to return. Defaults to 50.

        Returns:
            list[Article]: List of articles sorted by publication date (newest first).
        """
        index = self._read_index()

        # Sort by date (newest first)
        sorted_ids = sorted(index.keys(), key=lambda id: index[id]["published_date"], reverse=True)

        # Load articles
        articles = []
        for article_id in sorted_ids[:limit]:
            article = self.get_article(article_id)
            if article:
                articles.append(article)

        return articles

    def get_unread_articles(self, limit: int = 50) -> list[Article]:
        """Get unread articles (for future implementation).

        Args:
            limit (int, optional): Maximum number of articles to return. Defaults to 50.

        Returns:
            list[Article]: List of unread articles sorted by publication date.
        """
        # For now, just return recent articles
        # In a real implementation, we'd track read status
        return self.get_recent_articles(limit)

    def article_exists(self, url: str) -> bool:
        """Check if article with given URL exists.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if an article with the URL exists, False otherwise.
        """
        url_index = self._read_url_index()
        return url in url_index

    def _update_index(self, article: Article) -> None:
        """Update the article index.

        Args:
            article (Article): The article to update in the index.
        """
        index = self._read_index()

        # Add/update in index
        index[article.id] = {
            "title": article.title,
            "source": article.source_name,
            "published_date": article.published_date.isoformat(),
            "url": article.url,
            "categories": article.categories,
        }

        self._write_index(index)

    def _update_url_index(self, article: Article) -> None:
        """Update the URL index.

        Args:
            article (Article): The article to update in the URL index.
        """
        url_index = self._read_url_index()
        url_index[article.url] = article.id
        self._write_url_index(url_index)

    def _write_index(self, index: dict) -> None:
        """Write the article index.

        Args:
            index (dict): The index data to write.
        """
        self._index_cache = index
        if self._defer_index_writes:
            return

        try:
            self.index_file.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("File system error writing index: %s", e)
        except Exception as e:
            logger.error("Unexpected error writing index: %s", e)

    def _read_index(self) -> dict:
        """Read the article index, using the in-memory cache when warm.

        Returns:
            dict: The index data.
        """
        if self._index_cache is not None:
            return self._index_cache

        if not self.index_file.exists():
            return {}

        try:
            self._index_cache = dict(json.loads(self.index_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            logger.error("JSON parse error reading index: %s", e)
            return {}
        except OSError as e:
            logger.error("File system error reading index: %s", e)
            return {}
        except Exception as e:
            logger.error("Unexpected error reading index: %s", e)
            return {}
        return self._index_cache

    def _write_url_index(self, url_index: dict) -> None:
        """Write the URL index.

        Args:
            url_index (dict): The URL index data to write.
        """
        self._url_index_cache = url_index
        if self._defer_index_writes:
            return

        try:
            self.url_index_file.write_text(
                json.dumps(url_index, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("File system error writing URL index: %s", e)
        except Exception as e:
            logger.error("Unexpected error writing URL index: %s", e)

    def _read_url_index(self) -> dict:
        """Read the URL index, using the in-memory cache when warm.

        Returns:
            dict: The URL index data.
        """
        if self._url_index_cache is not None:
            return self._url_index_cache

        if not self.url_index_file.exists():
            return {}

        try:
            self._url_index_cache = dict(json.loads(self.url_index_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            logger.error("JSON parse error reading URL index: %s", e)
            return {}
        except OSError as e:
            logger.error("File system error reading URL index: %s", e)
            return {}
        except Exception as e:
            logger.error("Unexpected error reading URL index: %s", e)
            return {}
        return self._url_index_cache
