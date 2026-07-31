"""Core application service for coordinating RSS retrieval and storage."""

import logging

from opentelemetry import trace

from rss_retriever.adapters.content import ContentExtractor
from rss_retriever.domain.article import Article
from rss_retriever.domain.ports import NewsPort, StoragePort


logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class NewsService:
    """Core application service that coordinates the ports"""

    def __init__(self, news_adapter: NewsPort, storage_adapter: StoragePort, content_extractor: ContentExtractor):
        """Initialize the news service.

        Args:
            news_adapter (NewsPort): Adapter for fetching articles from news sources
            storage_adapter (StoragePort): Adapter for storing and retrieving articles
            content_extractor (ContentExtractor): Service for extracting article content
        """
        self.news_adapter = news_adapter
        self.storage_adapter = storage_adapter
        self.content_extractor = content_extractor

    def fetch_and_store_articles(self, limit_per_source: int = 10) -> list[Article]:
        """Fetch articles, extract content, and store them.

        Args:
            limit_per_source (int, optional): Maximum number of articles to fetch per source.
                Defaults to 10.

        Returns:
            list[Article]: List of fetched articles.
        """
        with tracer.start_as_current_span("fetch_and_store_articles") as span:
            span.set_attribute("limit_per_source", limit_per_source)

            # Fetch articles
            with tracer.start_span("fetch_articles") as fetch_span:
                articles = self.news_adapter.fetch_articles(limit_per_source)
                fetch_span.set_attribute("article_count", len(articles))

            stored_count = 0

            # Process each article
            for article in articles:
                with tracer.start_span("process_article") as article_span:
                    article_span.set_attributes(
                        {
                            "article.id": article.id,
                            "article.source": article.source_name,
                            "article.url": article.url,
                        }
                    )

                    # Check if we already have this article
                    if self.storage_adapter.article_exists(article.url):
                        logger.info("Skipping already saved article: %s", article.title)
                        article_span.set_attribute("article.skipped", True)
                        continue

                    # Extract content and images
                    enriched_article = self.content_extractor.enrich_article(article)
                    article_span.set_attribute("article.image_count", len(enriched_article.images))

                    # Store article
                    self.storage_adapter.save_article(enriched_article)
                    stored_count += 1
                    article_span.set_attribute("article.stored", True)

            span.set_attribute("stored_count", stored_count)
            logger.info(
                "Article processing complete",
                extra={
                    "fetched_count": len(articles),
                    "stored_count": stored_count,
                    "skipped_count": len(articles) - stored_count,
                },
            )
            return articles

    def get_recent_articles(self, limit: int = 10) -> list[Article]:
        """Get most recent articles.

        Args:
            limit (int, optional): Maximum number of articles to return. Defaults to 10.

        Returns:
            list[Article]: List of recent articles sorted by publication date.
        """
        with tracer.start_as_current_span("get_recent_articles") as span:
            span.set_attribute("limit", limit)
            articles = self.storage_adapter.get_recent_articles(limit)
            span.set_attribute("article_count", len(articles))
            return articles
