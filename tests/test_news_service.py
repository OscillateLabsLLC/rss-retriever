"""Tests for NewsService orchestration, driven through fake ports.

The point of the ports/adapters split is that the service can be exercised without
a network or a filesystem, so these tests use in-memory doubles.
"""

from dataclasses import replace

import pytest

from rss_retriever.domain.ports import NewsPort, StoragePort
from rss_retriever.service.news import NewsService


class FakeNewsAdapter(NewsPort):
    def __init__(self, articles):
        self.articles = articles
        self.calls = []

    def fetch_articles(self, limit_per_source: int = 10):
        self.calls.append(limit_per_source)
        return list(self.articles)


class FakeStorage(StoragePort):
    def __init__(self, known_urls=()):
        self.saved = []
        self.known_urls = set(known_urls)

    def save_article(self, article):
        self.saved.append(article)
        self.known_urls.add(article.url)

    def get_article(self, article_id):
        return next((a for a in self.saved if a.id == article_id), None)

    def get_recent_articles(self, limit: int = 50):
        return self.saved[:limit]

    def get_unread_articles(self, limit: int = 50):
        return self.get_recent_articles(limit)

    def article_exists(self, url: str) -> bool:
        return url in self.known_urls


class FakeExtractor:
    def __init__(self):
        self.enriched = []

    def enrich_article(self, article):
        self.enriched.append(article)
        article.content = "extracted body"
        return article


@pytest.fixture
def two_articles(article):
    second = replace(article, id="example.org_second", url="https://example.org/news/second", title="Second")
    return [article, second]


class TestFetchAndStore:
    def test_stores_every_new_article(self, two_articles):
        storage = FakeStorage()
        service = NewsService(FakeNewsAdapter(two_articles), storage, FakeExtractor())

        service.fetch_and_store_articles()

        assert len(storage.saved) == 2

    def test_enriches_before_storing(self, two_articles):
        extractor = FakeExtractor()
        storage = FakeStorage()
        NewsService(FakeNewsAdapter(two_articles), storage, extractor).fetch_and_store_articles()

        assert len(extractor.enriched) == 2
        assert all(a.content == "extracted body" for a in storage.saved)

    def test_skips_articles_already_stored(self, two_articles):
        """Dedup is what keeps the nightly run from reprocessing the whole corpus."""
        storage = FakeStorage(known_urls={two_articles[0].url})
        extractor = FakeExtractor()

        NewsService(FakeNewsAdapter(two_articles), storage, extractor).fetch_and_store_articles()

        assert [a.id for a in storage.saved] == ["example.org_second"]

    def test_skipped_articles_are_never_extracted(self, two_articles):
        """Extraction is the expensive step; skipping must happen before it."""
        storage = FakeStorage(known_urls={a.url for a in two_articles})
        extractor = FakeExtractor()

        NewsService(FakeNewsAdapter(two_articles), storage, extractor).fetch_and_store_articles()

        assert extractor.enriched == []
        assert storage.saved == []

    def test_returns_all_fetched_articles_including_skipped(self, two_articles):
        storage = FakeStorage(known_urls={two_articles[0].url})
        service = NewsService(FakeNewsAdapter(two_articles), storage, FakeExtractor())

        assert len(service.fetch_and_store_articles()) == 2

    def test_passes_limit_through_to_adapter(self, two_articles):
        adapter = FakeNewsAdapter(two_articles)
        NewsService(adapter, FakeStorage(), FakeExtractor()).fetch_and_store_articles(limit_per_source=3)

        assert adapter.calls == [3]

    def test_empty_feed_is_a_no_op(self):
        storage = FakeStorage()
        service = NewsService(FakeNewsAdapter([]), storage, FakeExtractor())

        assert service.fetch_and_store_articles() == []
        assert storage.saved == []


class TestGetRecentArticles:
    def test_delegates_to_storage(self, two_articles):
        storage = FakeStorage()
        for a in two_articles:
            storage.save_article(a)
        service = NewsService(FakeNewsAdapter([]), storage, FakeExtractor())

        assert len(service.get_recent_articles(limit=1)) == 1
