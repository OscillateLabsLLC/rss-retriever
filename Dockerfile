# Use lightweight Python base image
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    RSS_RETRIEVER_STORAGE_DIR=/app/article_storage \
    RSS_RETRIEVER_LOG_LEVEL=INFO \
    RSS_RETRIEVER_ARTICLES_PER_SOURCE=5 \
    RSS_RETRIEVER_RECENT_ARTICLES_LIMIT=10 \
    RSS_RETRIEVER_PREVIEW_IMAGE_COUNT=3 \
    RSS_RETRIEVER_REQUEST_TIMEOUT=10 \
    RSS_RETRIEVER_CHUNK_SIZE=8192

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml README.md LICENSE /app/
COPY rss_retriever /app/rss_retriever

# Tracing is opt-in; build with --build-arg EXTRAS='[otel]' to include it.
ARG EXTRAS=""
RUN uv pip install --system ".${EXTRAS}"

RUN mkdir -p ${RSS_RETRIEVER_STORAGE_DIR} \
    && chmod -R 755 /app

CMD ["python3", "-m", "rss_retriever"]
