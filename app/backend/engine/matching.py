"""Match JD requirements against the evidence database.

Scoring combines a deterministic keyword-overlap signal (cheap, always
available, used for ranking/recency tie-breaks) with an LLM semantic
judgment (strength: strong/partial/none, with a reason) that does the real
matching work in a single call per JD. The score is only ever used to decide
how much resume space a piece of evidence earns -- never exposed as a
judgment about the candidate (no "best candidate"/"hireability" labels).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .jd_parser import ParsedJD
from .llm import LLMError, generate_json
from .store import EvidenceStore

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "be", "this", "that", "as", "at", "by", "will", "your", "you", "our", "we",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9+#.]+", text.lower()) if t not in STOPWORDS and len(t) > 1}


def keyword_score(requirement_text: str, evidence_text: str) -> float:
    req_tokens = _tokens(requirement_text)
    if not req_tokens:
        return 0.0
    ev_tokens = _tokens(evidence_text)
    overlap = req_tokens & ev_tokens
    return len(overlap) / len(req_tokens)


def _evidence_text(item: dict) -> str:
    """Flattens an evidence summary dict (as built by _evidence_summaries) into
    plain text for keyword scoring. Note: summaries store "metrics" as a list
    of plain value strings, not the full metric dict the evidence store uses.
    """
    parts = [item.get("claim") or item.get("name") or item.get("description") or ""]
    parts += item.get("skills", [])
    for m in item.get("metrics", []) or []:
        parts.append(m if isinstance(m, str) else m.get("context", ""))
    return " ".join(parts)


@dataclass
class RequirementMatch:
    requirement: str
    category: str
    priority: str  # "must_have" | "nice_to_have"
    strength: str  # "strong" | "partial" | "unsupported"
    evidence_ids: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class MatchResult:
    matches: list[RequirementMatch]
    evidence_used_ids: set[str]

    @property
    def unsupported(self) -> list[RequirementMatch]:
        return [m for m in self.matches if m.strength == "unsupported"]

    @property
    def strong(self) -> list[RequirementMatch]:
        return [m for m in self.matches if m.strength == "strong"]

    @property
    def partial(self) -> list[RequirementMatch]:
        return [m for m in self.matches if m.strength == "partial"]


SYSTEM_PROMPT = """You are matching a candidate's factual career evidence against a job \
description's requirements. For each requirement, decide which pieces of evidence (by id) \
genuinely support it, and how strongly.

Rules:
1. Only cite evidence ids that are actually relevant -- do not cite an evidence item just \
because it shares one keyword with the requirement if the underlying substance doesn't match.
2. strength = "strong" if evidence directly and clearly demonstrates the requirement; \
"partial" if evidence is related/adjacent but doesn't fully demonstrate it; "unsupported" if \
no evidence meaningfully supports it. When strength is "unsupported", evidence_ids must be [].
3. Never fabricate a connection. If nothing in the evidence list genuinely relates to a \
requirement, mark it unsupported even if that feels disappointing.
4. Output valid JSON only, no commentary, no markdown fences.
"""


def _build_prompt(parsed_jd: ParsedJD, evidence_summaries: list[dict]) -> str:
    requirements = [
        {"requirement": r["requirement"], "category": r.get("category", "skill"), "priority": "must_have"}
        for r in parsed_jd.must_have
    ] + [
        {"requirement": r["requirement"], "category": r.get("category", "skill"), "priority": "nice_to_have"}
        for r in parsed_jd.nice_to_have
    ]

    schema_desc = """Return a JSON object: {"matches": [
  {"requirement": string, "priority": "must_have"|"nice_to_have", "strength": "strong"|"partial"|"unsupported",
   "evidence_ids": [string], "reasoning": string}
]}
Include exactly one entry per requirement given below, in the same order."""

    return (
        f"{schema_desc}\n\n"
        f"Requirements to evaluate:\n{requirements}\n\n"
        f"Available evidence (id, type, company/role if applicable, claim, skills, metrics):\n"
        f"{evidence_summaries}"
    )


def _evidence_summaries(store: EvidenceStore) -> list[dict]:
    summaries = []
    exp_by_id = {e["id"]: e for e in store.experiences}
    for a in store.achievements:
        exp = exp_by_id.get(a.get("experience_id"))
        summaries.append(
            {
                "id": a["id"],
                "type": "achievement",
                "company": exp["company"] if exp else None,
                "role": exp["role"] if exp else None,
                "claim": a["claim"],
                "skills": a.get("skills", []),
                "metrics": [m.get("value") for m in a.get("metrics", [])],
            }
        )
    for p in store.projects:
        summaries.append(
            {
                "id": p["id"],
                "type": "project",
                "name": p["name"],
                "description": p["description"],
                "skills": p.get("skills", []),
            }
        )
    for s in store.skills:
        summaries.append({"id": s["id"], "type": "skill", "name": s["name"]})
    return summaries


def match_jd_to_evidence(parsed_jd: ParsedJD, store: EvidenceStore) -> MatchResult:
    summaries = _evidence_summaries(store)
    valid_ids = {s["id"] for s in summaries}

    all_requirements = [
        (r["requirement"], r.get("category", "skill"), "must_have") for r in parsed_jd.must_have
    ] + [(r["requirement"], r.get("category", "skill"), "nice_to_have") for r in parsed_jd.nice_to_have]

    try:
        prompt = _build_prompt(parsed_jd, summaries)
        data = generate_json(SYSTEM_PROMPT, prompt, retries=1)
        raw_matches = data.get("matches", [])
    except LLMError:
        raw_matches = []

    matches: list[RequirementMatch] = []
    evidence_used: set[str] = set()

    matched_by_text = {m.get("requirement", "").strip().lower(): m for m in raw_matches}

    for requirement, category, priority in all_requirements:
        llm_match = matched_by_text.get(requirement.strip().lower())
        if llm_match:
            strength = llm_match.get("strength", "unsupported")
            evidence_ids = [eid for eid in llm_match.get("evidence_ids", []) if eid in valid_ids]
            if strength == "unsupported" or not evidence_ids:
                strength, evidence_ids = "unsupported", []
            reasoning = llm_match.get("reasoning", "")

            # Safety net: a small local model occasionally misses an obvious match
            # (e.g. a compound requirement like "SQL and product analytics skills"
            # is fully covered by evidence, but split across two separate skill
            # entries so no single item looks like a strong match). We only ever
            # use keyword overlap to *upgrade* a false "unsupported" to "partial"
            # here -- never to claim "strong", since overclaiming is the one
            # mistake this system must never make. Coverage is checked against
            # the whole evidence corpus (so a compound requirement can be
            # satisfied by multiple items combined); the cited evidence_ids are
            # then just the individual items that contributed any overlap.
            if strength == "unsupported":
                corpus_text = " ".join(_evidence_text(s) for s in summaries)
                coverage = keyword_score(requirement, corpus_text)
                if coverage >= 0.5:
                    scored = sorted(
                        ((s["id"], keyword_score(requirement, _evidence_text(s))) for s in summaries),
                        key=lambda x: -x[1],
                    )
                    top = [eid for eid, score in scored if score > 0][:3]
                    strength = "partial"
                    evidence_ids = top
                    reasoning = (
                        "Upgraded from the model's 'unsupported' verdict: strong keyword overlap was found "
                        "across existing evidence, so this is surfaced as a partial match for your review rather "
                        "than silently excluded."
                    )
        else:
            # LLM didn't return this one (or was unavailable) -- fall back to
            # keyword overlap only, conservatively.
            scored = sorted(
                ((s["id"], keyword_score(requirement, _evidence_text(s))) for s in summaries),
                key=lambda x: -x[1],
            )
            top = [eid for eid, score in scored if score >= 0.4][:3]
            strength = "partial" if top else "unsupported"
            evidence_ids = top
            reasoning = "Keyword-based fallback match (local model unavailable or skipped this item)."

        matches.append(
            RequirementMatch(
                requirement=requirement,
                category=category,
                priority=priority,
                strength=strength,
                evidence_ids=evidence_ids,
                reasoning=reasoning,
            )
        )
        evidence_used.update(evidence_ids)

    return MatchResult(matches=matches, evidence_used_ids=evidence_used)
