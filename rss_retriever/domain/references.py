"""Identifiers that tie an article to the study it reports on.

Science-press articles cite the paper they cover, but the citation lives in a
"More information:" block that readability extractors often drop, so both the
raw HTML and the extracted text are scanned. A DOI is the canonical key for a
study; many syndicated articles about one paper share one DOI.
"""

import re
from collections.abc import Iterable


# Crossref: a DOI is "10." + a 4-9 digit registrant + "/" + a suffix that may
# contain almost anything. The exclusion set is what ends a DOI inside HTML
# attributes and prose, not what the spec forbids.
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>)\]]+", re.IGNORECASE)

# ClinicalTrials.gov registry IDs, the alternate key when a trial has no paper.
TRIAL_ID_PATTERN = re.compile(r"\bNCT\d{8}\b")

_SENTENCE_TRAILERS = ".,;:"


def find_dois(text: str) -> list[str]:
    """Return distinct DOIs in first-seen order, lowercased for stable keys."""
    return _unique(_clean_doi(match) for match in DOI_PATTERN.findall(text))


def find_trial_ids(text: str) -> list[str]:
    """Return distinct ClinicalTrials.gov IDs in first-seen order."""
    return _unique(TRIAL_ID_PATTERN.findall(text))


def _clean_doi(raw: str) -> str:
    # DOIs are case-insensitive by spec; a DOI at the end of a sentence carries
    # the sentence's punctuation, which is not part of the identifier.
    return raw.rstrip(_SENTENCE_TRAILERS).lower()


def _unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
