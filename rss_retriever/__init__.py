"""RSS feed retrieval and storage system.

This package provides functionality for fetching, processing, and storing articles from RSS feeds,
including content extraction and image downloading capabilities.
"""

from rss_retriever.adapters.content import ContentExtractor
from rss_retriever.adapters.rss import RSSFeedAdapter
from rss_retriever.adapters.storage import FileSystemStorage
from rss_retriever.domain.article import Article, ArticleImage
from rss_retriever.domain.ports import NewsPort, StoragePort
from rss_retriever.service.news import NewsService


__version__ = "0.4.0"

__all__ = [
    "Article",
    "ArticleImage",
    "ContentExtractor",
    "FileSystemStorage",
    "NewsPort",
    "NewsService",
    "RSSFeedAdapter",
    "StoragePort",
]
