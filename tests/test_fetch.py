"""Tests for the browser-fingerprint page fetcher."""

from unittest.mock import MagicMock, patch

from rss_retriever.adapters.fetch import BrowserPageFetcher


URL = "https://example.org/news/story.html"


def _response(status_code, text="<html>page</html>"):
    return MagicMock(status_code=status_code, text=text)


def test_returns_page_html_on_success():
    with patch("rss_retriever.adapters.fetch.curl_requests.get", return_value=_response(200)) as get:
        assert BrowserPageFetcher("chrome", timeout=7).fetch(URL) == "<html>page</html>"
    get.assert_called_once_with(URL, impersonate="chrome", timeout=7)


def test_non_200_yields_none_so_the_caller_can_try_another_way():
    with patch("rss_retriever.adapters.fetch.curl_requests.get", return_value=_response(403)):
        assert BrowserPageFetcher().fetch(URL) is None


def test_transport_error_is_contained():
    with patch("rss_retriever.adapters.fetch.curl_requests.get", side_effect=OSError("boom")):
        assert BrowserPageFetcher().fetch(URL) is None
