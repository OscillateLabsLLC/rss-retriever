"""Content extraction service implementation."""

import hashlib
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from newspaper import Article as NewspaperArticle

from rss_retriever.domain.article import Article, ArticleImage
from rss_retriever.domain.references import find_dois, find_trial_ids


logger = logging.getLogger(__name__)


# A full-content feed (IEEE Spectrum, for one) ships the whole article in the
# summary field. Once the body has been extracted that text is a duplicate, not
# a summary, and the lede paragraph is the right summary -- exactly as for a
# feed that sent no summary at all. The extractor may drop a caption or byline
# the feed kept, so "duplicate" tolerates a shortfall rather than demanding
# equality; a real summary is a small fraction of its article.
BODY_DUPLICATE_RATIO = 0.8
_LEAD_CHARS = 150


def _letters_and_digits(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def summary_is_the_body(summary: str, body: str) -> bool:
    """True when the feed summary is the article text itself."""
    # Tag stripping leaves spaces before punctuation ("Act ,"), so compare on
    # letters and digits only.
    summary_n, body_n = _letters_and_digits(summary), _letters_and_digits(body)
    if not summary_n or not body_n:
        return False
    if len(summary_n) < BODY_DUPLICATE_RATIO * len(body_n):
        return False
    # Either opening found in the other: the feed may prepend a caption or
    # byline the extractor drops, or vice versa.
    return body_n[:_LEAD_CHARS] in summary_n or summary_n[:_LEAD_CHARS] in body_n


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

        if news_article.text and (not article.summary or summary_is_the_body(article.summary, news_article.text)):
            article.summary = news_article.text.split("\n\n")[0]

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
        """Record the article's own images: the lead image and those inside the body.

        Not every image on the page. A Phys.org page carries ~34 images, of
        which three belong to the article; the rest are logos, icons, and
        sidebar thumbnails of other stories served from the same CDN path,
        which no size or URL rule can tell apart. newspaper already knows
        which node is the article body, so the rule is "images of the
        article, not of the page" (measured 2026-08-29: ~10x fewer).

        Args:
            article (Article): The article to update with images.
            news_article (NewspaperArticle): The parsed newspaper article.
        """
        urls = _article_image_urls(news_article)
        if not urls:
            return

        logger.info("Keeping %d of %d page images", len(urls), len(news_article.images or ()))
        for img_url in urls:
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


def _article_image_urls(news_article: NewspaperArticle) -> list[str]:
    """The lead image, then the images inside the article body, in page order, deduplicated."""
    urls: list[str] = []
    if news_article.top_image:
        urls.append(news_article.top_image)
    body = getattr(news_article, "top_node", None)
    if body is not None:
        for img in body.iter("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                # Body sources are often protocol-relative ("//cdn/...") or
                # relative; the page URL makes them absolute.
                urls.append(urljoin(news_article.url or "", src.strip()))
    return list(dict.fromkeys(urls))
