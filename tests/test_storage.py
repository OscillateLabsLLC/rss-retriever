"""Tests for the filesystem storage adapter."""

import json

import pytest

from rss_retriever.adapters.storage import FileSystemStorage


class TestLayout:
    def test_creates_indexes_on_init(self, tmp_path):
        storage = FileSystemStorage(tmp_path / "store")
        assert storage.index_file.exists()
        assert storage.url_index_file.exists()

    def test_writes_expected_files(self, tmp_path, enriched_article):
        """Downstream services read these exact filenames; the layout is a contract."""
        storage = FileSystemStorage(tmp_path / "store")
        storage.save_article(enriched_article)

        article_dir = storage.storage_dir / enriched_article.id
        assert (article_dir / "content.txt").read_text(encoding="utf-8") == "Full body text."
        assert (article_dir / "content.html").exists()
        assert (article_dir / "metadata.json").exists()
        assert (article_dir / "images").is_dir()

    def test_metadata_is_valid_json_round_trip(self, tmp_path, enriched_article):
        storage = FileSystemStorage(tmp_path / "store")
        storage.save_article(enriched_article)

        raw = (storage.storage_dir / enriched_article.id / "metadata.json").read_text(encoding="utf-8")
        assert json.loads(raw)["title"] == enriched_article.title


class TestRoundTrip:
    def test_saved_article_can_be_read_back(self, tmp_path, enriched_article):
        storage = FileSystemStorage(tmp_path / "store")
        storage.save_article(enriched_article)

        loaded = storage.get_article(enriched_article.id)
        assert loaded is not None
        assert loaded.title == enriched_article.title
        assert loaded.url == enriched_article.url
        assert loaded.content == enriched_article.content
        assert loaded.published_date == enriched_article.published_date

    def test_missing_article_returns_none(self, tmp_path):
        assert FileSystemStorage(tmp_path / "store").get_article("does_not_exist") is None

    def test_corrupt_metadata_returns_none_without_raising(self, tmp_path, enriched_article):
        storage = FileSystemStorage(tmp_path / "store")
        storage.save_article(enriched_article)
        (storage.storage_dir / enriched_article.id / "metadata.json").write_text("{ not json", encoding="utf-8")

        assert storage.get_article(enriched_article.id) is None


class TestDeduplication:
    def test_article_exists_is_false_before_save(self, tmp_path, enriched_article):
        storage = FileSystemStorage(tmp_path / "store")
        assert storage.article_exists(enriched_article.url) is False

    def test_article_exists_is_true_after_save(self, tmp_path, enriched_article):
        """This check is what stops the pipeline re-fetching the same article daily."""
        storage = FileSystemStorage(tmp_path / "store")
        storage.save_article(enriched_article)
        assert storage.article_exists(enriched_article.url) is True

    def test_unknown_url_is_not_reported_as_seen(self, tmp_path, enriched_article):
        storage = FileSystemStorage(tmp_path / "store")
        storage.save_article(enriched_article)
        assert storage.article_exists("https://example.org/news/something-else") is False

    def test_indexes_survive_reinstantiation(self, tmp_path, enriched_article):
        """A new process must see what a previous run stored."""
        store_dir = tmp_path / "store"
        FileSystemStorage(store_dir).save_article(enriched_article)

        assert FileSystemStorage(store_dir).article_exists(enriched_article.url) is True


class TestRecentArticles:
    def test_returns_newest_first(self, tmp_path, article):
        from datetime import UTC, datetime

        storage = FileSystemStorage(tmp_path / "store")
        for offset, title in enumerate(["oldest", "middle", "newest"]):
            article.id = f"example.org_{title}"
            article.title = title
            article.url = f"https://example.org/{title}"
            article.published_date = datetime(2026, 7, 20 + offset, tzinfo=UTC)
            storage.save_article(article)

        assert [a.title for a in storage.get_recent_articles()] == ["newest", "middle", "oldest"]

    def test_respects_limit(self, tmp_path, article):
        from datetime import UTC, datetime

        storage = FileSystemStorage(tmp_path / "store")
        for offset in range(4):
            article.id = f"example.org_{offset}"
            article.url = f"https://example.org/{offset}"
            article.published_date = datetime(2026, 7, 20 + offset, tzinfo=UTC)
            storage.save_article(article)

        assert len(storage.get_recent_articles(limit=2)) == 2

    def test_empty_store_returns_empty_list(self, tmp_path):
        assert FileSystemStorage(tmp_path / "store").get_recent_articles() == []


class TestBatchWrites:
    def test_articles_are_discoverable_after_batch(self, tmp_path, article):
        from datetime import UTC, datetime

        store_dir = tmp_path / "store"
        storage = FileSystemStorage(store_dir)

        with storage.batch_writes():
            for i in range(3):
                article.id = f"example.org_{i}"
                article.url = f"https://example.org/{i}"
                article.published_date = datetime(2026, 7, 20 + i, tzinfo=UTC)
                storage.save_article(article)

        reopened = FileSystemStorage(store_dir)
        assert reopened.article_exists("https://example.org/1") is True
        assert len(reopened.get_recent_articles()) == 3

    def test_indexes_are_not_written_until_exit(self, tmp_path, article):
        """The whole point is to skip per-article index rewrites."""
        storage = FileSystemStorage(tmp_path / "store")

        with storage.batch_writes():
            storage.save_article(article)
            on_disk = json.loads(storage.index_file.read_text(encoding="utf-8"))
            assert on_disk == {}

        assert article.id in json.loads(storage.index_file.read_text(encoding="utf-8"))

    def test_indexes_flushed_even_if_block_raises(self, tmp_path, article):
        """A failed backfill must not leave saved articles unreachable."""
        store_dir = tmp_path / "store"
        storage = FileSystemStorage(store_dir)

        aborted = RuntimeError("backfill aborted")
        with pytest.raises(RuntimeError), storage.batch_writes():
            storage.save_article(article)
            raise aborted

        assert FileSystemStorage(store_dir).article_exists(article.url) is True

    def test_writes_resume_after_batch(self, tmp_path, article):
        from datetime import UTC, datetime

        store_dir = tmp_path / "store"
        storage = FileSystemStorage(store_dir)

        with storage.batch_writes():
            storage.save_article(article)

        article.id = "example.org_after"
        article.url = "https://example.org/after"
        article.published_date = datetime(2026, 7, 25, tzinfo=UTC)
        storage.save_article(article)

        on_disk = json.loads(storage.index_file.read_text(encoding="utf-8"))
        assert "example.org_after" in on_disk


class TestConfiguration:
    def test_request_timeout_is_injectable(self, tmp_path):
        """Timeout must be a constructor argument, not a module-level global."""
        assert FileSystemStorage(tmp_path / "store", request_timeout=42).request_timeout == 42

    def test_request_timeout_defaults(self, tmp_path):
        assert FileSystemStorage(tmp_path / "store").request_timeout == 10
