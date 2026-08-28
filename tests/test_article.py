"""Serialization round-trip for the Article model."""

from datetime import UTC, datetime

from rss_retriever.domain.article import Article


def test_references_survive_round_trip():
    article = Article(
        id="example.org_abc1234567",
        title="Newest discovery",
        url="https://example.org/news/newest",
        source_name="Example Science",
        published_date=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
        dois=["10.1242/dev.205325"],
        trial_ids=["NCT04368728"],
    )

    restored = Article.from_dict(article.to_dict())

    assert restored.dois == ["10.1242/dev.205325"]
    assert restored.trial_ids == ["NCT04368728"]


def test_metadata_written_before_this_field_existed_still_loads():
    legacy = {
        "id": "example.org_abc1234567",
        "title": "Old",
        "url": "https://example.org/news/old",
        "source_name": "Example Science",
        "published_date": "2026-07-29T12:00:00+00:00",
    }

    restored = Article.from_dict(legacy)

    assert restored.dois == []
    assert restored.trial_ids == []
