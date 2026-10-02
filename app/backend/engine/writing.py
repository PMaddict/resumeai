"""Turn a ResumePlan into final resume text.

Bullet rewriting goes through the LLM (for natural phrasing / JD terminology)
but every rewritten bullet is then checked token-by-token against its own
source evidence: if the rewrite introduces any number, percentage, or
proper-noun-looking token that wasn't already in the original claim/metrics/
skills text, the rewrite is thrown away and we fall back to the original
wording verbatim. The summary line is built deterministically from evidence
with no LLM involved at all, since it's the highest-visibility line in the
document.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .grounding import extract_numbers_and_tokens
from .llm import LLMError, generate_json
from .planning import PlannedBullet, PlannedExperience, PlannedProject, ResumePlan
from .store import EvidenceStore

logger = logging.getLogger("resumeai.writing")

SYSTEM_PROMPT = """You rewrite resume bullet points for clarity and conciseness. You NEVER \
add a fact that isn't already present in the text you're given: no new numbers, no new \
percentages, no new company/tool/skill names, no new scope claims. You may reorder words, \
tighten phrasing, lead with the action verb, and naturally weave in the given target \
keywords ONLY where they describe something already present in the original text. Output \
valid JSON only.
"""


def _source_tokens_for_bullet(b: PlannedBullet) -> set[str]:
    text = b.claim + " " + " ".join(b.skills) + " " + " ".join(m.get("context", "") + " " + str(m.get("value", "")) for m in b.metrics)
    return extract_numbers_and_tokens(text)


def _rewrite_bullets(bullets: list[PlannedBullet], jd_keywords: list[str]) -> dict[str, str]:
    if not bullets:
        return {}
    items = [
        {
            "achievement_id": b.achievement_id,
            "original_claim": b.claim,
            "metrics": [m.get("value") for m in b.metrics],
        }
        for b in bullets
    ]
    prompt = (
        "Rewrite each of these resume bullets for clarity and impact, in one sentence each. "
        f"Where accurate and natural, weave in relevant terms from this target role's keywords: "
        f"{jd_keywords}. Do not add any fact not already present in the original_claim/metrics.\n\n"
        f'Return JSON: {{"bullets": [{{"achievement_id": string, "text": string}}]}}\n\n'
        f"Bullets:\n{items}"
    )
    try:
        data = generate_json(SYSTEM_PROMPT, prompt, retries=1)
    except LLMError as exc:
        logger.warning("Bullet rewriting unavailable, falling back to original wording: %s", exc)
        return {}

    result: dict[str, str] = {}
    for item in data.get("bullets", []) or []:
        aid = item.get("achievement_id")
        text = item.get("text", "").strip()
        if aid and text:
            result[aid] = text
    return result


@dataclass
class WrittenBullet:
    achievement_id: str
    text: str
    was_rewritten: bool
    metrics: list[dict]


@dataclass
class WrittenExperience:
    experience_id: str
    company: str
    role: str
    dates_display: str
    location: str | None
    bullets: list[WrittenBullet]


@dataclass
class WrittenProject:
    project_id: str
    name: str
    description: str


@dataclass
class ResumeContent:
    header: dict
    summary: str | None
    experiences: list[WrittenExperience]
    projects: list[WrittenProject]
    skills: list[str]
    education: list[dict]
    certifications: list[dict]
    awards: list[dict]
    rewrite_rejections: list[dict] = field(default_factory=list)


def _format_dates(start: str | None, end: str | None, is_current: bool) -> str:
    start_s = start or ""
    end_s = "Present" if is_current else (end or "")
    if start_s and end_s:
        return f"{start_s} - {end_s}"
    return start_s or end_s or ""


def _build_summary(store: EvidenceStore, plan: ResumePlan, parsed_jd_role: str | None) -> str | None:
    companies = [pe.company for pe in plan.experiences if pe.bullets][:3]
    all_themes: list[str] = []
    for themes in plan.emphasis_by_company.values():
        all_themes.extend(themes)
    # dedupe preserving order
    seen: set[str] = set()
    themes = [t for t in all_themes if not (t.lower() in seen or seen.add(t.lower()))][:4]

    current_role = next((pe.role for pe in plan.experiences if pe.is_current), None)
    title = current_role or (plan.experiences[0].role if plan.experiences else None)

    if not title and not companies:
        return None

    pieces = []
    if title:
        pieces.append(title)
    if companies:
        pieces.append(f"with experience at {', '.join(companies)}")
    if themes:
        pieces.append(f"focused on {', '.join(themes)}")

    if not pieces:
        return None
    sentence = " ".join(pieces).strip()
    return sentence[0].upper() + sentence[1:] + "."


def write_resume(store: EvidenceStore, plan: ResumePlan, jd_keywords: list[str], role_title: str | None) -> ResumeContent:
    all_bullets = [b for pe in plan.experiences for b in pe.bullets]
    rewritten_map = _rewrite_bullets(all_bullets, jd_keywords)

    rejections: list[dict] = []
    written_experiences: list[WrittenExperience] = []
    for pe in plan.experiences:
        written_bullets: list[WrittenBullet] = []
        for b in pe.bullets:
            source_tokens = _source_tokens_for_bullet(b)
            candidate = rewritten_map.get(b.achievement_id)
            final_text = b.claim
            was_rewritten = False
            if candidate:
                new_tokens = extract_numbers_and_tokens(candidate, ignore_sentence_initial_caps=True) - source_tokens
                if new_tokens:
                    rejections.append(
                        {
                            "achievement_id": b.achievement_id,
                            "rejected_text": candidate,
                            "reason": f"introduced ungrounded tokens: {sorted(new_tokens)}",
                        }
                    )
                else:
                    final_text = candidate
                    was_rewritten = True
            written_bullets.append(
                WrittenBullet(
                    achievement_id=b.achievement_id,
                    text=final_text,
                    was_rewritten=was_rewritten,
                    metrics=b.metrics,
                )
            )
        written_experiences.append(
            WrittenExperience(
                experience_id=pe.experience_id,
                company=pe.company,
                role=pe.role,
                dates_display=_format_dates(pe.start_date, pe.end_date, pe.is_current),
                location=pe.location,
                bullets=written_bullets,
            )
        )

    written_projects = [
        WrittenProject(project_id=p.project_id, name=p.name, description=p.description) for p in plan.projects
    ]

    header = {
        "full_name": store.profile.get("full_name"),
        "emails": store.profile.get("emails", []),
        "phones": store.profile.get("phones", []),
        "links": store.profile.get("links", []),
        "location": store.profile.get("location"),
    }

    summary = _build_summary(store, plan, role_title)

    return ResumeContent(
        header=header,
        summary=summary,
        experiences=written_experiences,
        projects=written_projects,
        skills=plan.skills,
        education=store.index.get("education", []),
        certifications=store.index.get("certifications", []),
        awards=store.index.get("awards", []),
        rewrite_rejections=rejections,
    )
