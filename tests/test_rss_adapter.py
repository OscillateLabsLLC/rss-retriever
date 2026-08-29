"""Tests for the RSS feed adapter, parsed from a local fixture rather than the network."""

from datetime import UTC, datetime

from rss_retriever.adapters.rss import RSSFeedAdapter


class TestFetchArticles:
    def test_parses_all_entries(self, feed_file):
        articles = RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
        assert len(articles) == 2
        assert {a.title for a in articles} == {"Newest discovery", "Older discovery"}

    def test_respects_limit_per_source(self, feed_file):
        articles = RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles(limit_per_source=1)
        assert len(articles) == 1

    def test_sorted_newest_first(self, feed_file):
        articles = RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
        assert [a.title for a in articles] == ["Newest discovery", "Older discovery"]

    def test_merges_multiple_sources(self, feed_file):
        adapter = RSSFeedAdapter({"Source A": str(feed_file), "Source B": str(feed_file)})
        assert len(adapter.fetch_articles()) == 4

    def test_unreachable_feed_yields_no_articles_without_raising(self):
        """One broken feed must not abort the whole run."""
        articles = RSSFeedAdapter({"Broken": "/nonexistent/path/feed.xml"}).fetch_articles()
        assert articles == []

    def test_broken_source_does_not_suppress_working_source(self, feed_file):
        adapter = RSSFeedAdapter({"Broken": "/nonexistent/feed.xml", "Example Science": str(feed_file)})
        assert len(adapter.fetch_articles()) == 2


class TestArticleMapping:
    def test_id_is_source_prefixed_url_hash(self, feed_file):
        articles = RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
        newest = next(a for a in articles if a.title == "Newest discovery")
        assert newest.id.startswith("example_science_")
        # source slug + 10 hex chars of the url digest
        assert len(newest.id.split("example_science_")[1]) == 10

    def test_id_is_stable_across_runs(self, feed_file):
        adapter = RSSFeedAdapter({"Example Science": str(feed_file)})
        first = {a.id for a in adapter.fetch_articles()}
        second = {a.id for a in adapter.fetch_articles()}
        assert first == second

    def test_maps_core_fields(self, feed_file):
        newest = next(
            a
            for a in RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
            if a.title == "Newest discovery"
        )
        assert newest.url == "https://example.org/news/newest"
        assert newest.source_name == "Example Science"
        assert "newest discovery" in newest.summary.lower()

    def test_publication_date_is_timezone_aware_utc(self, feed_file):
        articles = RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
        newest = next(a for a in articles if a.title == "Newest discovery")
        assert newest.published_date.tzinfo is not None
        assert newest.published_date == datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

    def test_date_is_not_skewed_by_host_timezone(self, feed_file, monkeypatch):
        """Regression: mktime() reinterpreted feedparser's UTC struct as local time.

        The bug is invisible in a UTC container and shifts every timestamp by the
        host offset anywhere else, so pin a non-UTC zone explicitly.
        """
        import time

        monkeypatch.setenv("TZ", "America/Chicago")
        time.tzset()
        try:
            articles = RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
            newest = next(a for a in articles if a.title == "Newest discovery")
            assert newest.published_date == datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
        finally:
            monkeypatch.delenv("TZ", raising=False)
            time.tzset()

    def test_falls_back_to_updated_date(self, tmp_path):
        """Atom-style feeds carry <updated> rather than <pubDate>."""
        feed = tmp_path / "atom.xml"
        feed.write_text(
            '<?xml version="1.0" encoding="utf-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            "<title>Atom feed</title>"
            "<entry><title>Updated only</title>"
            '<link href="https://example.org/atom/one"/>'
            "<updated>2026-07-29T12:00:00Z</updated>"
            "</entry></feed>",
            encoding="utf-8",
        )
        articles = RSSFeedAdapter({"Atom": str(feed)}).fetch_articles()
        assert articles[0].published_date == datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

    def test_categories_extracted_when_present(self, feed_file):
        newest = next(
            a
            for a in RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
            if a.title == "Newest discovery"
        )
        assert "science" in newest.categories

    def test_missing_categories_default_to_empty(self, feed_file):
        older = next(
            a
            for a in RSSFeedAdapter({"Example Science": str(feed_file)}).fetch_articles()
            if a.title == "Older discovery"
        )
        assert older.categories == []


class TestPlainTextSummary:
    def test_strips_markup_and_entities(self):
        from rss_retriever.adapters.rss import plain_text_summary

        assert plain_text_summary("<p>Fast &amp; <b>loose</b></p>\n<p>text</p>") == "Fast & loose text"

    def test_plain_summary_is_unchanged(self):
        from rss_retriever.adapters.rss import plain_text_summary

        assert plain_text_summary("A summary of the newest discovery.") == "A summary of the newest discovery."
