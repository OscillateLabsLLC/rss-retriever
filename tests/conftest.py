"""Shared fixtures for the rss-retriever test suite."""

from datetime import UTC, datetime

import pytest

from rss_retriever.domain.article import Article, ArticleImage


SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Science</title>
    <link>https://example.org/</link>
    <description>Test feed</description>
    <item>
      <title>Newest discovery</title>
      <link>https://example.org/news/newest</link>
      <description>A summary of the newest discovery.</description>
      <pubDate>Wed, 29 Jul 2026 12:00:00 GMT</pubDate>
      <category>science</category>
      <category>biology</category>
    </item>
    <item>
      <title>Older discovery</title>
      <link>https://example.org/news/older</link>
      <description>A summary of the older discovery.</description>
      <pubDate>Mon, 27 Jul 2026 08:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_ARTICLE_HTML = """<!doctype html>
<html><head><title>Newest discovery</title></head>
<body>
  <article>
    <h1>Newest discovery</h1>
    <p>Researchers report a genuinely surprising result this week, and the finding
       has implications for how the field approaches the underlying problem.</p>
    <p>A second paragraph adds the necessary caveats and describes the method in
       enough detail that the work could plausibly be replicated by another lab.</p>
    <img src="https://example.org/img/figure1.png"/>
  </article>
</body></html>
"""


@pytest.fixture
def feed_file(tmp_path):
    """Write the sample RSS feed to disk and return its path.

    feedparser accepts a filesystem path, so this exercises the real parser
    without touching the network.
    """
    path = tmp_path / "feed.xml"
    path.write_text(SAMPLE_FEED, encoding="utf-8")
    return path


@pytest.fixture
def article():
    """A minimal Article with no content yet."""
    return Article(
        id="example.org_abc1234567",
        title="Newest discovery",
        url="https://example.org/news/newest",
        source_name="Example Science",
        published_date=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        summary="A summary of the newest discovery.",
    )


@pytest.fixture
def enriched_article(article):
    """An Article carrying content and one image."""
    article.content = "Full body text."
    article.html_content = "<p>Full body text.</p>"
    article.images = [ArticleImage(original_url="https://example.org/img/figure1.png", local_path="img_a1b2c3.png")]
    return article
