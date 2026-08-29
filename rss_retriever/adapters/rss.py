"""RSS feed adapter implementation."""

import hashlib
import html
import logging
import re
from calendar import timegm
from datetime import UTC, datetime

import feedparser
import requests

from rss_retriever.domain.article import Article
from rss_retriever.domain.ports import NewsPort


logger = logging.getLogger(__name__)


class RSSFeedAdapter(NewsPort):
    """Implementation of NewsPort using RSS feeds"""

    def __init__(self, feed_urls: dict[str, str]):
        """Initialize with RSS feed URLs.

        Args:
            feed_urls (dict[str, str]): Dictionary mapping source names to their RSS feed URLs.
        """
        self.feed_urls = feed_urls

    def fetch_articles(self, limit_per_source: int = 10) -> list[Article]:
        """Fetch latest articles from all configured sources.

        Args:
            limit_per_source (int, optional): Maximum number of articles to fetch per source.
                Defaults to 10.

        Returns:
            list[Article]: List of fetched articles, sorted by publication date (newest first).
        """
        all_articles = []

        for source_name, feed_url in self.feed_urls.items():
            articles = self._fetch_from_source(source_name, feed_url, limit_per_source)
            all_articles.extend(articles)

        # Sort by publication date (newest first)
        sorted_articles = sorted(all_articles, key=lambda x: x.published_date, reverse=True)
        logger.info("Total articles fetched: %d", len(sorted_articles))
        return sorted_articles

    def _fetch_from_source(self, source_name: str, feed_url: str, limit: int) -> list[Article]:
        """Fetch articles from a single source.

        Args:
            source_name (str): Name of the source
            feed_url (str): URL of the RSS feed
            limit (int): Maximum number of articles to fetch

        Returns:
            list[Article]: Articles fetched from this source
        """
        articles = []
        try:
            logger.info("Fetching from %s...", source_name)
            feed = feedparser.parse(feed_url)

            for entry in feed.entries[:limit]:
                article = self._create_article_from_entry(entry, source_name)
                articles.append(article)

            logger.info("Retrieved %d articles from %s", len(feed.entries[:limit]), source_name)

        except requests.RequestException as e:
            logger.error("Network error fetching from %s: %s", source_name, str(e))
        except (ValueError, AttributeError) as e:
            logger.error("Parse error from %s: %s", source_name, str(e))
        except Exception as e:
            logger.error("Unexpected error fetching from %s: %s", source_name, str(e))

        return articles

    def _create_article_from_entry(self, entry, source_name: str) -> Article:
        """Create an Article object from a feedparser entry.

        Args:
            entry: Feed entry from feedparser
            source_name (str): Name of the source

        Returns:
            Article: Constructed Article object
        """
        # Handle publication date
        pub_date = self._extract_publication_date(entry)

        # Get categories if available
        categories = self._extract_categories(entry)

        # Get summary if available
        summary = self._extract_summary(entry)

        # Generate a stable ID based on URL
        url_hash = hashlib.md5(entry.link.encode()).hexdigest()
        article_id = f"{source_name.lower().replace(' ', '_')}_{url_hash[:10]}"

        return Article(
            id=article_id,
            title=entry.title,
            url=entry.link,
            source_name=source_name,
            published_date=pub_date,
            summary=summary,
            categories=categories,
        )

    def _extract_publication_date(self, entry) -> datetime:
        """Extract publication date from entry.

        Args:
            entry: Feed entry from feedparser

        Returns:
            datetime: Publication date
        """
        # feedparser normalises *_parsed to UTC, so convert with timegm. time.mktime
        # would reinterpret the struct as local time and skew every date by the
        # host's UTC offset.
        pub_date = datetime.now(tz=UTC)
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub_date = datetime.fromtimestamp(timegm(entry.published_parsed), tz=UTC)
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            pub_date = datetime.fromtimestamp(timegm(entry.updated_parsed), tz=UTC)
        return pub_date

    def _extract_categories(self, entry) -> list[str]:
        """Extract categories from entry.

        Args:
            entry: Feed entry from feedparser

        Returns:
            list[str]: List of categories
        """
        categories = []
        if hasattr(entry, "tags"):
            categories = [tag.term for tag in entry.tags if hasattr(tag, "term")]
        elif hasattr(entry, "categories"):
            categories = list(entry.categories)
        return categories

    def _extract_summary(self, entry) -> str:
        """Extract summary from entry.

        Args:
            entry: Feed entry from feedparser

        Returns:
            str: Article summary
        """
        summary = ""
        if hasattr(entry, "summary"):
            summary = entry.summary
        elif hasattr(entry, "description"):
            summary = entry.description
        return plain_text_summary(summary)


# Full-content feeds (IEEE Spectrum, for one) put the entire article, as HTML,
# in the summary field. A summary is a few sentences of prose, so anything
# beyond this is the body and belongs in content instead.
MAX_SUMMARY_CHARS = 1000
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def plain_text_summary(raw: str) -> str:
    """Reduce a feed summary to plain prose of bounded length."""
    text = _WHITESPACE.sub(" ", html.unescape(_TAG.sub(" ", raw))).strip()
    if len(text) <= MAX_SUMMARY_CHARS:
        return text
    cut = text.rfind(" ", 0, MAX_SUMMARY_CHARS)
    return text[: cut if cut > 0 else MAX_SUMMARY_CHARS].rstrip() + "…"
