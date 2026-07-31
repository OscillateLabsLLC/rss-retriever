# Contributing to rss-retriever

Thanks for your interest in contributing!

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

### Getting Started

```bash
git clone https://github.com/OscillateLabsLLC/rss-retriever
cd rss-retriever

# Install dependencies (including dev extras)
uv sync --extra dev
```

## Common Commands

This repo uses [just](https://github.com/casey/just) as its task runner. `just --list` shows
everything available; the `uv` equivalents are given below in case you'd rather not install it.

```bash
just test          # unit tests, no network access required
just test-all      # everything, including tests that hit live sites
just check         # lint, format and type-check
just validate      # check + test
```

Without `just`:

```bash
uv run pytest -m "not network"
uv run pytest
uv run ruff check .
uv run mypy rss_retriever/
```

Tests that reach the network are marked with `@pytest.mark.network` so they can be deselected in
CI and offline development. Prefer fixtures over live requests when adding tests.

## Pull Requests

1. Create a feature branch: `git checkout -b feat/my-feature`
2. Make your changes and add tests where applicable
3. Run `uv run pytest -m "not network"` to ensure everything passes
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `docs:`)
5. Open a pull request

**PR Guidelines:**

- Keep PRs focused on a single concern
- Include tests for new functionality
- Ensure all CI checks pass

Releases are automated with release-please: merged conventional commits drive the version bump and
publish to PyPI, so commit messages matter.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
