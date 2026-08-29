"""Tests for content extraction.

Extraction is delegated to newspaper4k, so these tests cover the adapter's own
behaviour: short-circuiting, field mapping, image naming, and error containment.
"""

from unittest.mock import MagicMock, patch

import lxml.html
import pytest

from rss_retriever.adapters.content import ContentExtractor
from tests.conftest import SAMPLE_ARTICLE_HTML


def _fake_newspaper_article(
    text="Body paragraph one.\n\nBody paragraph two.", images=(), top_image=None, body_html=None
):
    """images is what newspaper saw on the whole page; top_image and body_html are the article's own."""
    fake = MagicMock()
    fake.url = "https://example.org/news/story.html"
    fake.html = SAMPLE_ARTICLE_HTML
    fake.text = text
    fake.images = list(images)
    fake.top_image = top_image
    fake.top_node = lxml.html.fromstring(body_html) if body_html else None
    return fake


class TestShortCircuit:
    def test_returns_early_when_already_enriched(self, enriched_article):
        """Re-extracting an article that already has content wastes a network fetch."""
        with patch("rss_retriever.adapters.content.NewspaperArticle") as newspaper:
            ContentExtractor().enrich_article(enriched_article)
        newspaper.assert_not_called()


class TestExtraction:
    def test_populates_content_and_html(self, article):
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=_fake_newspaper_article()):
            result = ContentExtractor().enrich_article(article)

        assert result.content == "Body paragraph one.\n\nBody paragraph two."
        assert result.html_content == SAMPLE_ARTICLE_HTML

    def test_captures_study_references_from_html_and_text(self, article):
        """Phys.org keeps the DOI in a block the readability pass drops, so HTML counts."""
        fake = _fake_newspaper_article(text="Body text citing trial NCT04368728.")
        fake.html = (
            SAMPLE_ARTICLE_HTML + '<p>More information: <a href="https://doi.org/10.1242/dev.205325">paper</a></p>'
        )
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            result = ContentExtractor().enrich_article(article)

        assert result.dois == ["10.1242/dev.205325"]
        assert result.trial_ids == ["NCT04368728"]

    def test_derives_summary_from_first_paragraph_when_absent(self, article):
        article.summary = ""
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=_fake_newspaper_article()):
            result = ContentExtractor().enrich_article(article)

        assert result.summary == "Body paragraph one."

    def test_full_content_feed_summary_is_replaced_by_the_lede(self, article):
        """IEEE Spectrum puts the whole article in the summary field; that is a duplicate, not a summary."""
        body = "Lede paragraph of the article.\n\nSecond paragraph with more detail.\n\nThird paragraph."
        # As a feed delivers it: a caption the extractor drops, and a space the
        # tag stripper leaves before punctuation.
        article.summary = "Photo: a fab. " + body.replace("\n\n", " ").replace("article.", "article .")
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=_fake_newspaper_article(text=body)):
            result = ContentExtractor().enrich_article(article)

        assert result.summary == "Lede paragraph of the article."

    def test_preserves_existing_feed_summary(self, article):
        """The feed's own summary is better than a truncated first paragraph."""
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=_fake_newspaper_article()):
            result = ContentExtractor().enrich_article(article)

        assert result.summary == "A summary of the newest discovery."


class TestImages:
    def test_maps_images_with_hashed_filenames(self, article):
        fake = _fake_newspaper_article(top_image="https://example.org/img/figure1.png")
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            result = ContentExtractor().enrich_article(article)

        assert len(result.images) == 1
        image = result.images[0]
        assert image.original_url == "https://example.org/img/figure1.png"
        assert image.local_path.startswith("img_")
        assert image.local_path.endswith(".png")

    def test_extensionless_image_defaults_to_jpg(self, article):
        fake = _fake_newspaper_article(top_image="https://example.org/img/generated")
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            result = ContentExtractor().enrich_article(article)

        assert result.images[0].local_path.endswith(".jpg")

    def test_image_filenames_are_deterministic(self, article):
        """Stable names let a re-run skip images already on disk."""
        fake = _fake_newspaper_article(top_image="https://example.org/img/figure1.png")
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            first = ContentExtractor().enrich_article(article).images[0].local_path

        article.images = []
        article.content = ""
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            second = ContentExtractor().enrich_article(article).images[0].local_path

        assert first == second

    def test_no_images_is_not_an_error(self, article):
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=_fake_newspaper_article()):
            result = ContentExtractor().enrich_article(article)

        assert result.images == []


class TestErrorContainment:
    def test_download_failure_returns_article_unchanged(self, article):
        """One unreachable article must not abort the whole nightly run."""
        failing = MagicMock()
        failing.download.side_effect = OSError("connection reset")

        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=failing):
            result = ContentExtractor().enrich_article(article)

        assert result.content == ""
        assert result.title == "Newest discovery"

    def test_parse_failure_is_contained(self, article):
        failing = MagicMock()
        failing.parse.side_effect = ValueError("unparseable document")

        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=failing):
            assert ContentExtractor().enrich_article(article).content == ""


@pytest.mark.network
class TestAgainstLiveSite:
    def test_extracts_real_article(self):
        """End-to-end proof the newspaper4k integration actually works.

        Deselect in CI with: pytest -m "not network"
        """
        from datetime import UTC, datetime

        from rss_retriever.domain.article import Article

        live = Article(
            id="live",
            title="live",
            url="https://phys.org/rss-feed/",
            source_name="Phys.org",
            published_date=datetime.now(tz=UTC),
        )
        result = ContentExtractor().enrich_article(live)
        assert isinstance(result.content, str)


class TestArticleImagesOnly:
    """Measured 2026-08-29: a Phys.org page carries ~34 images, 3 of them the article's."""

    PAGE = (
        "https://cdn.example/logo.png",
        "https://cdn.example/csz/news/other-story.jpg",
        "https://cdn.example/csz/news/lead.jpg",
        "https://cdn.example/csz/news/figure.jpg",
    )
    BODY = (
        '<div><p>Text.</p><figure><img src="//cdn.example/csz/news/figure.jpg"></figure>'
        '<p>More.</p><img data-src="/gfx/profiles/author.jpg"></div>'
    )

    def test_keeps_lead_and_body_images_and_drops_the_rest_of_the_page(self, article):
        fake = _fake_newspaper_article(
            images=self.PAGE, top_image="https://cdn.example/csz/news/lead.jpg", body_html=self.BODY
        )
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            result = ContentExtractor().enrich_article(article)

        assert [i.original_url for i in result.images] == [
            "https://cdn.example/csz/news/lead.jpg",
            "https://cdn.example/csz/news/figure.jpg",  # protocol-relative src made absolute
            "https://example.org/gfx/profiles/author.jpg",  # relative data-src resolved against the page
        ]

    def test_lead_image_repeated_in_body_is_stored_once(self, article):
        body = '<div><img src="https://cdn.example/csz/news/lead.jpg"><p>Text.</p></div>'
        fake = _fake_newspaper_article(
            images=self.PAGE, top_image="https://cdn.example/csz/news/lead.jpg", body_html=body
        )
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            result = ContentExtractor().enrich_article(article)

        assert len(result.images) == 1

    def test_page_images_alone_are_not_the_articles(self, article):
        fake = _fake_newspaper_article(images=self.PAGE)
        with patch("rss_retriever.adapters.content.NewspaperArticle", return_value=fake):
            result = ContentExtractor().enrich_article(article)

        assert result.images == []
