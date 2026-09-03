"""Tests for the HTTP image fetcher, against a real local server."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from rss_retriever.adapters.images import AiohttpImageFetcher


PNG_BYTES = b"\x89PNG fake image bytes"


class _ImageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ok.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(PNG_BYTES)
        else:
            self.send_error(404)

    def log_message(self, *_):
        pass


@pytest.fixture(scope="module")
def image_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ImageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_returns_bytes_in_url_order_with_none_for_failures(image_server):
    urls = [f"{image_server}/ok.png", f"{image_server}/missing.png", f"{image_server}/ok.png"]
    assert AiohttpImageFetcher(timeout=5).fetch_many(urls) == [PNG_BYTES, None, PNG_BYTES]


def test_unreachable_host_is_contained():
    assert AiohttpImageFetcher(timeout=1).fetch_many(["http://127.0.0.1:9/never.png"]) == [None]


def test_no_urls_means_no_network():
    assert AiohttpImageFetcher().fetch_many([]) == []
