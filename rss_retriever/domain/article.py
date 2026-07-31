"""Domain models for articles and related entities."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ArticleImage:
    """Represents an image associated with an article.

    Attributes:
        original_url (str): The original URL where the image was found
        local_path (str): Local filesystem path where the image is stored
        caption (str): Optional caption text for the image, defaults to empty string
    """

    original_url: str
    local_path: str
    caption: str = ""


@dataclass
class Article:
    """Represents a news article with its metadata and content.

    This class encapsulates all information related to a news article, including its
    content, metadata, and associated media (images). It provides methods for
    serialization and deserialization.

    Attributes:
        id (str): Unique identifier for the article
        title (str): The article's headline or title
        url (str): Original URL where the article was published
        source_name (str): Name of the publication or source
        published_date (datetime): When the article was published
        summary (str): Brief summary or description of the article
        content (str): Full text content of the article
        html_content (str): HTML version of the article content
        categories (list[str]): list of categories or tags
        images (list[ArticleImage]): list of images associated with the article
    """

    id: str
    title: str
    url: str
    source_name: str
    published_date: datetime
    summary: str = ""
    content: str = ""
    html_content: str = ""
    categories: list[str] = field(default_factory=list)
    images: list[ArticleImage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the article to a dictionary format for serialization.

        Returns:
            dict[str, Any]: Dictionary containing all article attributes, with datetime
                converted to ISO format and images converted to dictionaries.
        """
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "source_name": self.source_name,
            "published_date": self.published_date.isoformat(),
            "summary": self.summary,
            "content": self.content,
            "html_content": self.html_content,
            "categories": self.categories,
            "images": [
                {"original_url": img.original_url, "local_path": img.local_path, "caption": img.caption}
                for img in self.images
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Article":
        """Create an Article instance from a dictionary.

        Args:
            data (dict[str, Any]): Dictionary containing article data, typically
                created by to_dict() method.

        Returns:
            Article: A new Article instance populated with the dictionary data.
        """
        article = cls(
            id=data["id"],
            title=data["title"],
            url=data["url"],
            source_name=data["source_name"],
            published_date=datetime.fromisoformat(data["published_date"]),
            summary=data.get("summary", ""),
            content=data.get("content", ""),
            html_content=data.get("html_content", ""),
            categories=data.get("categories", []),
        )

        # Add images if present
        if "images" in data:
            article.images = [
                ArticleImage(
                    original_url=img["original_url"], local_path=img["local_path"], caption=img.get("caption", "")
                )
                for img in data["images"]
            ]

        return article
