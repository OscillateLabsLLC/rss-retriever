"""Configuration for the RSS retriever.

Configuration is read from the environment following 12-Factor App principles, but
resolution happens in :meth:`Config.from_env` rather than at import time so that
library consumers can construct a :class:`Config` directly and tests can vary the
environment without reimporting the module.

Variables use the ``RSS_RETRIEVER_`` prefix. A legacy prefix is still honoured as a
deprecated fallback for deployments predating the extraction of this package.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar, cast


logger = logging.getLogger(__name__)

T = TypeVar("T")

ENV_PREFIX = "RSS_RETRIEVER_"
LEGACY_ENV_PREFIX = "MARVIN_"

# Sensible starting points for a news-oriented deployment. Not applied by default:
# a library should never fetch a feed the caller did not ask for.
EXAMPLE_FEEDS = {
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "SciTechDaily": "https://scitechdaily.com/feed/",
    "Medical Xpress": "https://medicalxpress.com/rss-feed/",
    "Phys.org": "https://phys.org/rss-feed/",
    "Popular Mechanics": "https://www.popularmechanics.com/rss/",
    "Psychology Today": "https://www.psychologytoday.com/us/front/feed",
}


def _read_env(suffix: str) -> str | None:
    """Read ``RSS_RETRIEVER_<suffix>``, falling back to the legacy ``MARVIN_`` name."""
    value = os.getenv(f"{ENV_PREFIX}{suffix}")
    if value is not None:
        return value

    legacy = os.getenv(f"{LEGACY_ENV_PREFIX}{suffix}")
    if legacy is not None:
        logger.warning(
            "%s%s is deprecated; use %s%s instead.",
            LEGACY_ENV_PREFIX,
            suffix,
            ENV_PREFIX,
            suffix,
        )
    return legacy


def get_env(suffix: str, default: T, type_cast: type = str) -> T:
    """Get an environment variable with type casting and a default.

    Falls back to the default if the variable is unset or cannot be coerced.

    Args:
        suffix: Variable name without the prefix, e.g. ``"LOG_LEVEL"``.
        default: Value to use when unset or invalid.
        type_cast: Type to coerce the raw string into.

    Returns:
        The coerced value, or ``default``.
    """
    value = _read_env(suffix)
    if value is None:
        return default
    try:
        if type_cast is bool:
            return cast("T", value.strip().lower() in ("true", "1", "yes"))
        if type_cast is dict:
            return cast("T", json.loads(value))
        return cast("T", type_cast(value))
    except (ValueError, json.JSONDecodeError):
        logger.warning("Could not parse %s%s as %s; using default.", ENV_PREFIX, suffix, type_cast.__name__)
        return default


@dataclass(frozen=True)
class Config:
    """Runtime configuration for a retrieval run."""

    storage_dir: Path = Path("article_storage")
    rss_feeds: dict[str, str] = field(default_factory=dict)
    articles_per_source: int = 5
    recent_articles_limit: int = 10
    preview_image_count: int = 3
    log_level: str = "INFO"
    request_timeout: int = 10
    chunk_size: int = 8192
    # "page" records every image on the page (the long-standing behaviour);
    # "article" records only the lead image and those inside the article body.
    image_scope: str = "page"
    # Browser whose TLS fingerprint article fetches present (a curl_cffi name such
    # as "chrome", "safari", "firefox"); empty leaves the download to newspaper.
    impersonate: str = "chrome"

    @classmethod
    def from_env(cls) -> "Config":
        """Build a configuration from environment variables.

        ``RSS_RETRIEVER_RSS_FEEDS`` is a JSON object mapping source name to feed URL.
        """
        return cls(
            storage_dir=Path(get_env("STORAGE_DIR", "article_storage")),
            rss_feeds=get_env("RSS_FEEDS", {}, dict),
            articles_per_source=get_env("ARTICLES_PER_SOURCE", 5, int),
            recent_articles_limit=get_env("RECENT_ARTICLES_LIMIT", 10, int),
            preview_image_count=get_env("PREVIEW_IMAGE_COUNT", 3, int),
            log_level=get_env("LOG_LEVEL", "INFO").upper(),
            request_timeout=get_env("REQUEST_TIMEOUT", 10, int),
            chunk_size=get_env("CHUNK_SIZE", 8192, int),
            image_scope=_image_scope(get_env("IMAGE_SCOPE", "page")),
            impersonate=get_env("IMPERSONATE", "chrome").strip(),
        )


def _image_scope(value: str) -> str:
    """An unknown scope keeps the default rather than breaking a run."""
    scope = value.strip().lower()
    if scope in ("page", "article"):
        return scope
    logger.warning("%sIMAGE_SCOPE must be 'page' or 'article', not %r; using 'page'.", ENV_PREFIX, value)
    return "page"
