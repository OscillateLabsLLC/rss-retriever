"""Abstract interfaces (ports) for the RSS retriever system."""

from abc import ABC, abstractmethod

from rss_retriever.domain.article import Article


class NewsPort(ABC):
    """Abstract interface for fetching news articles from various sources.

    This port defines the contract for retrieving articles from news sources.
    Implementations might include RSS feeds, web scrapers, or API clients.
    """

    @abstractmethod
    def fetch_articles(self, limit_per_source: int = 10) -> list[Article]:
        """Fetch latest articles from configured sources.

        Args:
            limit_per_source (int, optional): Maximum number of articles to fetch
                from each source. Defaults to 10.

        Returns:
            list[Article]: list of fetched articles, sorted by publication date.
        """
        raise NotImplementedError


class ContentPort(ABC):
    """Abstract interface for enriching an article with its full content.

    The feed gives a title, a link and usually a summary; this port fills in the
    body, the images and the references. Implementations might parse the page,
    call an extraction API, or do nothing for a feed that ships full content.
    """

    @abstractmethod
    def enrich_article(self, article: Article) -> Article:
        """Add full content and images to an article.

        Args:
            article (Article): The article to enrich.

        Returns:
            Article: The same article, enriched where extraction succeeded.
        """
        raise NotImplementedError


class StoragePort(ABC):
    """Abstract interface for storing and retrieving articles.

    This port defines the contract for article persistence operations.
    Implementations might include file system storage, databases, or cloud storage.
    """

    @abstractmethod
    def save_article(self, article: Article) -> None:
        """Save an article to storage.

        Args:
            article (Article): The article to save.
        """
        raise NotImplementedError

    @abstractmethod
    def get_article(self, article_id: str) -> Article | None:
        """Retrieve an article by its ID.

        Args:
            article_id (str): The unique identifier of the article.

        Returns:
            Article | None: The article if found, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def get_recent_articles(self, limit: int = 50) -> list[Article]:
        """Retrieve the most recent articles.

        Args:
            limit (int, optional): Maximum number of articles to return. Defaults to 50.

        Returns:
            list[Article]: list of articles sorted by publication date (newest first).
        """
        raise NotImplementedError

    @abstractmethod
    def get_unread_articles(self, limit: int = 50) -> list[Article]:
        """Retrieve unread articles.

        Args:
            limit (int, optional): Maximum number of articles to return. Defaults to 50.

        Returns:
            list[Article]: list of unread articles sorted by publication date.
        """
        raise NotImplementedError

    @abstractmethod
    def article_exists(self, url: str) -> bool:
        """Check if an article with the given URL exists in storage.

        Args:
            url (str): The URL to check.

        Returns:
            bool: True if an article with the URL exists, False otherwise.
        """
        raise NotImplementedError
