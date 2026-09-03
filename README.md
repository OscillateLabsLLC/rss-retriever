# rss-retriever

[![Status: Active](https://img.shields.io/badge/status-active-brightgreen)](https://github.com/OscillateLabsLLC/.github/blob/main/SUPPORT_STATUS.md)
[![Run Unit Tests](https://github.com/OscillateLabsLLC/rss-retriever/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/OscillateLabsLLC/rss-retriever/actions/workflows/unit-tests.yml)
[![PyPI](https://img.shields.io/pypi/v/rss-retriever)](https://pypi.org/project/rss-retriever/)

Fetch articles from RSS feeds, extract their full text and images, and store them on disk.

Built around ports and adapters, so the pieces are usable independently: take the feed adapter
without the storage layer, swap in your own storage backend, or drive the whole pipeline from the
bundled CLI.

## Install

```bash
pip install rss-retriever
```

Optional tracing support (OpenTelemetry SDK, OTLP exporters, and Arize Phoenix):

```bash
pip install "rss-retriever[otel]"
```

The base install deliberately stays light. `opentelemetry-api` is included because it is a no-op
without an SDK, so instrumented code paths cost nothing when tracing is not configured.

Requires Python 3.12+.

## Library usage

```python
from rss_retriever import ContentExtractor, FileSystemStorage, NewsService, RSSFeedAdapter

service = NewsService(
    RSSFeedAdapter({"Phys.org": "https://phys.org/rss-feed/"}),
    FileSystemStorage("article_storage"),
    ContentExtractor(),
)

articles = service.fetch_and_store_articles(limit_per_source=5)
for article in service.get_recent_articles(limit=10):
    print(article.source_name, article.title)
```

Articles already present in storage are skipped before the expensive extraction step, so re-running
against the same feeds is cheap.

### Bulk imports

`save_article` rewrites both index files on every call so a crash cannot orphan an article. That is
the right default for a nightly run but makes a large backfill quadratic in corpus size. Wrap bulk
ingestion in `batch_writes()` to pay the index cost once:

```python
with storage.batch_writes():
    for article in many_articles:
        storage.save_article(article)
```

Article payloads are still written immediately; only the indexes are deferred, and they are flushed
even if the block raises. On a 5,000-article import this is roughly 12x faster.

### Public API

| Object                    | Role                                                                    |
| ------------------------- | ----------------------------------------------------------------------- |
| `NewsService`             | Orchestrates fetch, extract, and store                                  |
| `RSSFeedAdapter`          | `NewsPort` implementation backed by feedparser                          |
| `ContentExtractor`        | `ContentPort` implementation: full text and images via newspaper4k      |
| `BrowserPageFetcher`      | `PagePort` implementation presenting a browser's TLS fingerprint        |
| `PacedPageFetcher`        | `PagePort` decorator enforcing a minimum interval per host              |
| `AiohttpImageFetcher`     | `ImagePort` implementation downloading images concurrently              |
| `FileSystemStorage`       | `StoragePort` implementation writing to disk                            |
| `NewsPort`, `ContentPort`, `PagePort`, `ImagePort`, `StoragePort` | Abstract ports for custom implementations |
| `Article`, `ArticleImage` | Domain models, with `to_dict()` / `from_dict()`                         |

### Custom backends

Implement `StoragePort` to store somewhere other than the filesystem:

```python
from rss_retriever import StoragePort


class S3Storage(StoragePort):
    def save_article(self, article): ...
    def get_article(self, article_id): ...
    def get_recent_articles(self, limit=50): ...
    def get_unread_articles(self, limit=50): ...
    def article_exists(self, url) -> bool: ...
```

## CLI

```bash
export RSS_RETRIEVER_RSS_FEEDS='{"Phys.org": "https://phys.org/rss-feed/"}'
export RSS_RETRIEVER_STORAGE_DIR=./article_storage
rss-retriever
```

## Configuration

Read from the environment by `Config.from_env()`. Construct `Config` directly to bypass the
environment entirely.

| Variable                              | Default           | Meaning                                         |
| ------------------------------------- | ----------------- | ----------------------------------------------- |
| `RSS_RETRIEVER_RSS_FEEDS`             | `{}`              | JSON object mapping source name to feed URL     |
| `RSS_RETRIEVER_STORAGE_DIR`           | `article_storage` | Where articles are written                      |
| `RSS_RETRIEVER_ARTICLES_PER_SOURCE`   | `5`               | Max articles fetched per feed per run           |
| `RSS_RETRIEVER_RECENT_ARTICLES_LIMIT` | `10`              | Max articles returned by recent-article queries |
| `RSS_RETRIEVER_PREVIEW_IMAGE_COUNT`   | `3`               | Images summarised per article in CLI output     |
| `RSS_RETRIEVER_LOG_LEVEL`             | `INFO`            | Root log level                                  |
| `RSS_RETRIEVER_REQUEST_TIMEOUT`       | `10`              | Per-request timeout in seconds                  |
| `RSS_RETRIEVER_CHUNK_SIZE`            | `8192`            | Download chunk size in bytes                    |
| `RSS_RETRIEVER_IMAGE_SCOPE`           | `page`            | `page`: every image on the page; `article`: the lead image plus those inside the article body |
| `RSS_RETRIEVER_IMPERSONATE`           | `chrome`          | Browser whose TLS fingerprint article fetches present (a [curl_cffi](https://github.com/lexiforest/curl_cffi) name); empty leaves the download to newspaper |
| `RSS_RETRIEVER_HOST_INTERVALS`        | `{}`              | JSON object of host to minimum seconds between page fetches, e.g. `{"thehill.com": 180}`, for sites that rate-limit bursts |

There are no default feeds: a library should not fetch anything the caller did not ask for.
`rss_retriever.config.EXAMPLE_FEEDS` holds a starting set if you want one.

## Storage layout

```
article_storage/
├── index.json                  # article_id -> metadata, for recency queries
├── url_index.json              # url -> article_id, for deduplication
└── <source>_<url_hash>/
    ├── content.txt
    ├── content.html
    ├── metadata.json
    └── images/
```

Article IDs are `<source_slug>_<first 10 hex of md5(url)>` and are stable across runs.

## Tracing

```python
from rss_retriever.telemetry import setup_telemetry

setup_telemetry(service_name="my-service")
```

Configured through the standard `OTEL_*` environment variables. Requires the `otel` extra. Note
that this installs a global tracer provider and sets OTLP defaults, so call it from an application
entry point rather than from library code.

## Development

```bash
uv sync --extra dev
uv run pytest -m "not network"   # unit tests, no network
uv run pytest                    # includes live-network tests
uv run ruff check .
uv run mypy rss_retriever/
```

## License

MIT
