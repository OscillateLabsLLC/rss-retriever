"""Content extraction service implementation."""

import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import requests
from newspaper import Article as NewspaperArticle

from rss_retriever.domain.article import Article, ArticleImage
from rss_retriever.domain.references import find_dois, find_trial_ids


logger = logging.getLogger(__name__)


class ContentExtractor:
    """Service for extracting full content and images from articles"""

    def enrich_article(self, article: Article) -> Article:
        """Add full content and images to an article.

        Args:
            article (Article): The article to enrich with content and images.

        Returns:
            Article: The enriched article.
        """
        if article.content and article.images:
            logger.info("Article already has content and images")
            return article

        try:
            logger.info("Extracting content from %s", article.url)
            news_article = NewspaperArticle(article.url)
            news_article.download()
            news_article.parse()

            self._extract_content(article, news_article)
            self._extract_references(article, news_article)
            self._extract_images(article, news_article)

        except requests.RequestException as e:
            logger.error("Network error extracting content from %s: %s", article.url, e)
        except (ValueError, AttributeError) as e:
            logger.error("Parse error extracting content from %s: %s", article.url, e)
        except Exception as e:
            logger.error("Unexpected error extracting content from %s: %s", article.url, e)

        return article

    def _extract_content(self, article: Article, news_article: NewspaperArticle) -> None:
        """Extract text content from the article.

        Args:
            article (Article): The article to update with content.
            news_article (NewspaperArticle): The parsed newspaper article.
        """
        article.html_content = news_article.html
        article.content = news_article.text

        if not article.summary and news_article.text:
            paragraphs = news_article.text.split("\n\n")
            if paragraphs:
                article.summary = paragraphs[0]

        logger.info("Successfully extracted %d chars of content", len(article.content))

    def _extract_references(self, article: Article, news_article: NewspaperArticle) -> None:
        """Record the studies the article cites.

        Science-press sites put the citation in a "More information:" block that
        the readability pass drops, so the raw HTML is scanned as well as the
        extracted text.
        """
        searchable = f"{news_article.html or ''}\n{news_article.text or ''}"
        article.dois = find_dois(searchable)
        article.trial_ids = find_trial_ids(searchable)
        if article.dois or article.trial_ids:
            logger.info("Found %d DOIs and %d trial IDs", len(article.dois), len(article.trial_ids))

    def _extract_images(self, article: Article, news_article: NewspaperArticle) -> None:
        """Extract images from the article.

        Args:
            article (Article): The article to update with images.
            news_article (NewspaperArticle): The parsed newspaper article.
        """
        if not news_article.images:
            return

        logger.info("Found %d images", len(news_article.images))
        for img_url in news_article.images:
            try:
                img_hash = hashlib.md5(img_url.encode()).hexdigest()[:10]
                parsed_url = urlparse(img_url)
                img_path = Path(parsed_url.path).name
                ext = Path(img_path).suffix or ".jpg"
                img_filename = f"img_{img_hash}{ext}"

                article.images.append(ArticleImage(original_url=img_url, local_path=img_filename))
            except (ValueError, OSError) as e:
                logger.error("Error processing image path %s: %s", img_url, e)
            except Exception as e:
                logger.error("Unexpected error processing image %s: %s", img_url, e)
