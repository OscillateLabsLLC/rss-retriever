"""Tests for per-host pacing of page fetches."""

from rss_retriever.adapters.pacing import PacedPageFetcher, host_of
from rss_retriever.domain.ports import PagePort


class FakePage(PagePort):
    def __init__(self):
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        return "<html/>"


class FakeTime:
    """A clock that only moves when something sleeps."""

    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


def _paced(intervals):
    inner, t = FakePage(), FakeTime()
    return PacedPageFetcher(inner, intervals, clock=t.clock, sleep=t.sleep), inner, t


def test_host_of_ignores_scheme_case_and_www():
    assert host_of("https://www.TheHill.com/policy/x") == "thehill.com"
    assert host_of("http://thehill.com/") == "thehill.com"


def test_first_request_to_a_host_is_immediate():
    paced, inner, t = _paced({"thehill.com": 180})
    assert paced.fetch("https://thehill.com/a") == "<html/>"
    assert t.slept == []
    assert inner.fetched == ["https://thehill.com/a"]


def test_second_request_inside_the_interval_waits_the_remainder():
    paced, _, t = _paced({"thehill.com": 180})
    paced.fetch("https://thehill.com/a")
    t.now += 50
    paced.fetch("https://www.thehill.com/b")
    assert t.slept == [130]


def test_request_after_the_interval_does_not_wait():
    paced, _, t = _paced({"thehill.com": 180})
    paced.fetch("https://thehill.com/a")
    t.now += 200
    paced.fetch("https://thehill.com/b")
    assert t.slept == []


def test_unlisted_hosts_are_never_paced():
    paced, _, t = _paced({"thehill.com": 180})
    paced.fetch("https://www.politico.com/a")
    paced.fetch("https://www.politico.com/b")
    assert t.slept == []


def test_hosts_are_paced_independently():
    paced, _, t = _paced({"thehill.com": 180, "politico.com": 60})
    paced.fetch("https://thehill.com/a")
    paced.fetch("https://politico.com/a")
    assert t.slept == []
    paced.fetch("https://politico.com/b")
    assert t.slept == [60]


def test_interval_keys_are_normalised_like_urls():
    paced, _, t = _paced({"www.TheHill.com": 180})
    paced.fetch("https://thehill.com/a")
    paced.fetch("https://thehill.com/b")
    assert t.slept == [180]
