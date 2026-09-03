"""RSS feed retrieval and storage system.

This package provides functionality for fetching, processing, and storing articles from RSS feeds,
including content extraction and image downloading capabilities.
"""

from rss_retriever.adapters.content import ContentExtractor
from rss_retriever.adapters.fetch import BrowserPageFetcher
from rss_retriever.adapters.images import AiohttpImageFetcher
from rss_retriever.adapters.pacing import PacedPageFetcher
from rss_retriever.adapters.rss import RSSFeedAdapter
from rss_retriever.adapters.storage import FileSystemStorage
from rss_retriever.domain.article import Article, ArticleImage
from rss_retriever.domain.ports import ContentPort, ImagePort, NewsPort, PagePort, StoragePort
from rss_retriever.service.news import NewsService


__version__ = "0.5.0"

__all__ = [
    "AiohttpImageFetcher",
    "Article",
    "ArticleImage",
    "BrowserPageFetcher",
    "ContentExtractor",
    "ContentPort",
    "FileSystemStorage",
    "ImagePort",
    "NewsPort",
    "NewsService",
    "PacedPageFetcher",
    "PagePort",
    "RSSFeedAdapter",
    "StoragePort",
]
