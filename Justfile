# List all recipes
default:
    @just --list

# Install dependencies from the lockfile
install:
    uv sync

install-all:
    uv sync --all-extras

# Generate lockfile from pyproject.toml
lock:
    uv lock

# Update dependencies and regenerate lockfile
upgrade:
    uv lock --upgrade

# Run Ruff linter
lint:
    uv run ruff check .

# Run Ruff formatter
fmt:
    uv run ruff format .

# Run the type checker
typecheck:
    uv run mypy rss_retriever/

# Run linting, formatting, and type checking
check: lint fmt typecheck

# Run the unit tests (no network required)
test:
    uv run pytest -m "not network"

# Run every test, including those that hit live sites
test-all:
    uv run pytest

# Run both tests and checks
validate: check test

# Run the RSS retriever
run:
    uv run python -m rss_retriever

# Run with console tracing for debugging
run-debug:
    OTEL_EXPORTER=console uv run python -m rss_retriever

# Run Phoenix locally for tracing
phoenix:
    docker run -p 6006:6006 ghcr.io/arize-ai/phoenix:latest

# Build Docker image
docker-build:
    docker build -t rss-retriever .

# Clean up Python cache and build files
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name "*.pyd" -delete
    find . -type f -name ".coverage" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} +
    find . -type d -name "*.egg" -exec rm -rf {} +
    find . -type d -name ".pytest_cache" -exec rm -rf {} +
    find . -type d -name ".ruff_cache" -exec rm -rf {} +