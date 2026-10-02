"""Tests for the keyword-based safety net in matching.py.

A small local model occasionally says "unsupported" for a requirement that's
actually covered by evidence -- especially compound requirements like "SQL
and product analytics skills" where the two skills live in separate evidence
items and no single item looks like a strong match on its own. These tests
exercise that logic directly (bypassing the LLM) so they're fast and
deterministic.
"""

from app.backend.engine.jd_parser import ParsedJD
from app.backend.engine.matching import match_jd_to_evidence
from app.backend.engine.store import EvidenceStore


def _store_with_sql_and_analytics_skills():
    store = EvidenceStore.__new__(EvidenceStore)
    store.profile = {}
    store.experiences = []
    store.achievements = []
    store.projects = []
    store.skills = [
        {"id": "skill_sql", "name": "SQL"},
        {"id": "skill_analytics", "name": "Product Analytics"},
    ]
    store.index = {}
    return store


def test_compound_requirement_upgraded_from_unsupported_when_split_across_evidence(monkeypatch):
    """Simulates the model wrongly saying 'unsupported' for a requirement that
    is in fact covered, just split across two separate skill evidence items.
    """
    store = _store_with_sql_and_analytics_skills()
    parsed_jd = ParsedJD(
        raw_text="",
        company=None,
        role_title=None,
        seniority=None,
        domain=None,
        must_have=[{"requirement": "Strong SQL and product analytics skills", "category": "skill"}],
        nice_to_have=[],
        responsibilities=[],
        business_problems=[],
        keywords=[],
    )

    import app.backend.engine.matching as matching_module

    def fake_generate_json(*args, **kwargs):
        return {
            "matches": [
                {
                    "requirement": "Strong SQL and product analytics skills",
                    "priority": "must_have",
                    "strength": "unsupported",
                    "evidence_ids": [],
                    "reasoning": "model missed it",
                }
            ]
        }

    monkeypatch.setattr(matching_module, "generate_json", fake_generate_json)

    result = match_jd_to_evidence(parsed_jd, store)
    assert len(result.matches) == 1
    match = result.matches[0]
    # Must be upgraded to partial (never silently dropped, never claimed "strong").
    assert match.strength == "partial"
    assert set(match.evidence_ids) == {"skill_sql", "skill_analytics"}


def test_genuinely_unmatched_requirement_stays_unsupported(monkeypatch):
    """A requirement with no keyword overlap at all must stay unsupported --
    the safety net must not invent matches out of thin air.
    """
    store = _store_with_sql_and_analytics_skills()
    parsed_jd = ParsedJD(
        raw_text="",
        company=None,
        role_title=None,
        seniority=None,
        domain=None,
        must_have=[{"requirement": "Experience managing a team of 10+ direct reports", "category": "leadership"}],
        nice_to_have=[],
        responsibilities=[],
        business_problems=[],
        keywords=[],
    )

    import app.backend.engine.matching as matching_module

    def fake_generate_json(*args, **kwargs):
        return {
            "matches": [
                {
                    "requirement": "Experience managing a team of 10+ direct reports",
                    "priority": "must_have",
                    "strength": "unsupported",
                    "evidence_ids": [],
                    "reasoning": "no evidence",
                }
            ]
        }

    monkeypatch.setattr(matching_module, "generate_json", fake_generate_json)

    result = match_jd_to_evidence(parsed_jd, store)
    assert result.matches[0].strength == "unsupported"
    assert result.matches[0].evidence_ids == []
