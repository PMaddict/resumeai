"""Verbatim-grounding checks -- the core anti-fabrication safeguard.

Any time the LLM claims a piece of text came from a source document, we
verify that claim against the actual document text before trusting it.
This runs at two points:
  1. Extraction: reject any extracted evidence item whose source_text isn't
     actually present in the resume it claims to come from.
  2. Resume generation: reject any generated bullet that introduces a
     number, skill, or proper noun not traceable to the evidence it cites.

Matching is tolerant of whitespace/line-break differences introduced by
PDF/DOCX text extraction, but not of paraphrasing -- a close fuzzy match
(>= threshold) against some window of the source text is required.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

DEFAULT_THRESHOLD = 0.82


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class GroundingResult:
    grounded: bool
    similarity: float
    reason: str


def check_grounded(claimed_source_text: str, full_source_document: str, *, threshold: float = DEFAULT_THRESHOLD) -> GroundingResult:
    """Check whether `claimed_source_text` is actually present (verbatim or
    near-verbatim) inside `full_source_document`.
    """
    claim = _normalize(claimed_source_text)
    doc = _normalize(full_source_document)

    if not claim:
        return GroundingResult(False, 0.0, "empty source_text")

    if claim in doc:
        return GroundingResult(True, 1.0, "exact substring match")

    # Fuzzy fallback: slide a window roughly the size of the claim across the
    # document and take the best ratio. This tolerates minor OCR/extraction
    # noise (stray spaces, hyphenation) without accepting paraphrased content.
    window = max(len(claim), 20)
    best = 0.0
    step = max(window // 2, 10)
    for start in range(0, max(len(doc) - window, 0) + 1, step):
        chunk = doc[start : start + window]
        ratio = difflib.SequenceMatcher(None, claim, chunk).ratio()
        if ratio > best:
            best = ratio
        if best >= threshold:
            break

    if best >= threshold:
        return GroundingResult(True, best, "fuzzy match above threshold")
    return GroundingResult(False, best, "no matching passage found in source document")


def extract_numbers_and_tokens(text: str, *, ignore_sentence_initial_caps: bool = False) -> set[str]:
    """Pull out the "hard facts" a resume bullet might contain: numbers,
    percentages, and capitalized proper-noun-looking tokens. Used to check
    that a rewritten bullet doesn't introduce new numbers/names.

    A sentence's first word is capitalized purely by English grammar, not
    because it's a proper noun -- "Redesigned the funnel..." vs "Owned the
    funnel redesign...". Without `ignore_sentence_initial_caps`, swapping the
    leading verb during a rewrite would otherwise look identical to
    introducing a new company/tool name. Pass it when checking a *rewritten*
    bullet against its source; leave it False when building the source's own
    token baseline (more inclusive baseline is safer).
    """
    numbers = set(re.findall(r"\d[\d,.]*%?", text))
    search_text = text
    if ignore_sentence_initial_caps:
        stripped = text.lstrip()
        if stripped:
            first_word_len = len(stripped.split(" ", 1)[0])
            lead = len(text) - len(stripped)
            search_text = text[: lead] + stripped[0].lower() + stripped[1:]
    proper_nouns = set(re.findall(r"\b[A-Z][a-zA-Z0-9+#.]{1,}\b", search_text))
    return numbers | proper_nouns
