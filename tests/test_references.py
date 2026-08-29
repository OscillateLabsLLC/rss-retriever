"""Tests for study-identifier extraction.

The patterns run over raw HTML and extracted prose alike, so the cases cover
both: DOIs inside hrefs, DOIs ending a sentence, and the noise around them.
"""

from rss_retriever.domain.references import find_dois, find_trial_ids


class TestDois:
    def test_finds_doi_inside_href(self):
        html = '<p>More information: <a href="https://dx.doi.org/10.1242/dev.205325">Development</a></p>'
        assert find_dois(html) == ["10.1242/dev.205325"]

    def test_strips_sentence_punctuation(self):
        assert find_dois("Published as DOI: 10.1016/j.cell.2026.07.040.") == ["10.1016/j.cell.2026.07.040"]

    def test_lowercases_for_stable_keys(self):
        assert find_dois("10.1038/S41586-026-10949-Y") == ["10.1038/s41586-026-10949-y"]

    def test_dedups_across_html_and_text(self):
        text = 'href="https://doi.org/10.1038/s41586-026-10949-y" ... DOI: 10.1038/s41586-026-10949-y'
        assert find_dois(text) == ["10.1038/s41586-026-10949-y"]

    def test_preserves_first_seen_order(self):
        text = "10.1000/first then 10.1000/second and 10.1000/first again"
        assert find_dois(text) == ["10.1000/first", "10.1000/second"]

    def test_ignores_version_numbers_that_look_similar(self):
        assert find_dois("released 10.15 on Tuesday, build 10.2/3") == []

    def test_empty_input(self):
        assert find_dois("") == []


class TestTrialIds:
    def test_finds_registry_id(self):
        assert find_trial_ids("registered as NCT04368728 in 2020") == ["NCT04368728"]

    def test_requires_exactly_eight_digits(self):
        assert find_trial_ids("NCT1234567 and NCT123456789") == []

    def test_dedups(self):
        assert find_trial_ids("NCT04368728, see NCT04368728") == ["NCT04368728"]


class TestDoiArtifacts:
    """Shapes measured on the stored corpus, 2026-08-29: each had been minted as a study."""

    def test_balanced_parentheses_are_part_of_the_doi(self):
        assert find_dois("see 10.1016/S0140-6736(17)30001-1 for details") == ["10.1016/s0140-6736(17)30001-1"]

    def test_unbalanced_parenthesis_ends_the_match(self):
        assert find_dois("10.1002/(issn") == []

    def test_url_fragment_and_encoding_are_stripped(self):
        assert find_dois("https://doi.org/10.1080/00231940.2025.2553441#d1e171") == ["10.1080/00231940.2025.2553441"]
        assert find_dois("10.1371/journal.pone.0353607%20and") == ["10.1371/journal.pone.0353607"]

    def test_publisher_path_suffix_is_stripped(self):
        assert find_dois("https://www.degruyter.com/document/doi/10.1525/9780520321373-011/html") == [
            "10.1525/9780520321373-011"
        ]
