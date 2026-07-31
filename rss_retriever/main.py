"""RSS feed retrieval application entry point."""

import logging

from rss_retriever.adapters.content import ContentExtractor
from rss_retriever.adapters.rss import RSSFeedAdapter
from rss_retriever.adapters.storage import FileSystemStorage
from rss_retriever.config import Config
from rss_retriever.service.news import NewsService


logger = logging.getLogger(__name__)


def main() -> None:
    """Run the RSS feed retrieval application.

    Fetches articles from the configured RSS feeds, extracts their content and images,
    stores them locally, and logs a summary of the most recent articles.
    """
    config = Config.from_env()
    logging.basicConfig(level=config.log_level)

    # Telemetry is opt-in: it installs a global tracer provider and mutates the
    # environment, so it must never run as an import side effect.
    try:
        from rss_retriever.telemetry import setup_telemetry
    except ImportError:
        logger.debug("Telemetry extra not installed; skipping tracing setup.")
    else:
        setup_telemetry()

    if not config.rss_feeds:
        logger.error(
            "No RSS feeds configured. Set RSS_RETRIEVER_RSS_FEEDS to a JSON object "
            'mapping source name to feed URL, e.g. {"Phys.org": "https://phys.org/rss-feed/"}.'
        )
        raise SystemExit(1)

    news_service = NewsService(
        RSSFeedAdapter(config.rss_feeds),
        FileSystemStorage(config.storage_dir, request_timeout=config.request_timeout),
        ContentExtractor(),
    )

    logger.info("Starting article fetch...")
    news_service.fetch_and_store_articles(limit_per_source=config.articles_per_source)

    logger.info("Retrieving most recent articles")
    recent_articles = news_service.get_recent_articles(config.recent_articles_limit)

    for article in recent_articles:
        logger.info(
            "Article found",
            extra={
                "article_id": article.id,
                "title": article.title,
                "source": article.source_name,
                "published_date": article.published_date.isoformat(),
                "image_count": len(article.images[: config.preview_image_count]),
                "total_images": len(article.images),
            },
        )


if __name__ == "__main__":
    main()
