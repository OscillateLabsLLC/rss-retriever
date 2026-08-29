"""Tests for environment-driven configuration."""

from pathlib import Path

from rss_retriever.config import Config, get_env


class TestDefaults:
    def test_defaults_are_library_safe(self):
        """A default Config must not fetch anything the caller did not ask for."""
        config = Config()
        assert config.rss_feeds == {}
        assert config.articles_per_source == 5
        assert config.storage_dir == Path("article_storage")

    def test_from_env_with_empty_environment(self, monkeypatch):
        monkeypatch.delenv("RSS_RETRIEVER_RSS_FEEDS", raising=False)
        monkeypatch.delenv("MARVIN_RSS_FEEDS", raising=False)
        assert Config.from_env().rss_feeds == {}


class TestPrefixResolution:
    def test_new_prefix_is_read(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_ARTICLES_PER_SOURCE", "12")
        assert Config.from_env().articles_per_source == 12

    def test_legacy_marvin_prefix_still_works(self, monkeypatch):
        """Deployments predating the extraction must keep working."""
        monkeypatch.delenv("RSS_RETRIEVER_ARTICLES_PER_SOURCE", raising=False)
        monkeypatch.setenv("MARVIN_ARTICLES_PER_SOURCE", "10")
        assert Config.from_env().articles_per_source == 10

    def test_new_prefix_wins_over_legacy(self, monkeypatch):
        monkeypatch.setenv("MARVIN_ARTICLES_PER_SOURCE", "10")
        monkeypatch.setenv("RSS_RETRIEVER_ARTICLES_PER_SOURCE", "7")
        assert Config.from_env().articles_per_source == 7

    def test_legacy_use_emits_deprecation_warning(self, monkeypatch, caplog):
        monkeypatch.delenv("RSS_RETRIEVER_LOG_LEVEL", raising=False)
        monkeypatch.setenv("MARVIN_LOG_LEVEL", "debug")
        with caplog.at_level("WARNING"):
            Config.from_env()
        assert "MARVIN_LOG_LEVEL is deprecated" in caplog.text


class TestCoercion:
    def test_feeds_parsed_from_json(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_RSS_FEEDS", '{"Phys.org": "https://phys.org/rss-feed/"}')
        assert Config.from_env().rss_feeds == {"Phys.org": "https://phys.org/rss-feed/"}

    def test_malformed_json_falls_back_to_default(self, monkeypatch, caplog):
        """A bad feed list must not crash startup; it degrades to the default."""
        monkeypatch.setenv("RSS_RETRIEVER_RSS_FEEDS", "{not valid json")
        with caplog.at_level("WARNING"):
            config = Config.from_env()
        assert config.rss_feeds == {}
        assert "Could not parse" in caplog.text

    def test_non_integer_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_ARTICLES_PER_SOURCE", "many")
        assert Config.from_env().articles_per_source == 5

    def test_log_level_is_upper_cased(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_LOG_LEVEL", "debug")
        assert Config.from_env().log_level == "DEBUG"

    def test_bool_coercion(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_SOME_FLAG", "YES")
        assert get_env("SOME_FLAG", False, bool) is True
        monkeypatch.setenv("RSS_RETRIEVER_SOME_FLAG", "off")
        assert get_env("SOME_FLAG", True, bool) is False


class TestImageScope:
    def test_default_is_the_whole_page(self, monkeypatch):
        monkeypatch.delenv("RSS_RETRIEVER_IMAGE_SCOPE", raising=False)
        assert Config().image_scope == "page"
        assert Config.from_env().image_scope == "page"

    def test_article_scope_is_opt_in(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_IMAGE_SCOPE", "Article")
        assert Config.from_env().image_scope == "article"

    def test_unknown_scope_falls_back_to_page(self, monkeypatch):
        monkeypatch.setenv("RSS_RETRIEVER_IMAGE_SCOPE", "everything")
        assert Config.from_env().image_scope == "page"
