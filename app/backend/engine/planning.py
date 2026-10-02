"""Decide which evidence goes into the resume and in what order.

Pure selection/ranking logic -- no LLM calls here, so the "here's what I
plan to emphasize" preview (spec requirement: show this *before*
generating) can be computed cheaply and deterministically from the match
result produced by matching.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import get_settings
from .matching import MatchResult, keyword_score
from .store import EvidenceStore


@dataclass
class PlannedBullet:
    achievement_id: str
    claim: str
    metrics: list[dict]
    skills: list[str]
    match_strength: str  # "strong" | "partial" | "none"
    matched_requirements: list[str]
    score: float


@dataclass
class PlannedExperience:
    experience_id: str
    company: str
    role: str
    start_date: str | None
    end_date: str | None
    is_current: bool
    location: str | None
    bullets: list[PlannedBullet]


@dataclass
class PlannedProject:
    project_id: str
    name: str
    description: str
    skills: list[str]
    match_strength: str
    matched_requirements: list[str]
    score: float


@dataclass
class ResumePlan:
    experiences: list[PlannedExperience]
    projects: list[PlannedProject]  # standalone projects worth a "Key Projects" section
    skills: list[str]
    unsupported_requirements: list[dict]  # [{requirement, priority, category}]
    emphasis_by_company: dict[str, list[str]]  # company -> list of emphasis themes (skills/categories)
    estimated_bullet_count: int


def _achievement_best_match(achievement_id: str, match_result: MatchResult) -> tuple[str, list[str]]:
    """Returns (best_strength, [requirement texts]) for an achievement id."""
    strength_rank = {"strong": 2, "partial": 1, "unsupported": 0}
    best = "none"
    reqs: list[str] = []
    for m in match_result.matches:
        if achievement_id in m.evidence_ids:
            reqs.append(m.requirement)
            if strength_rank.get(m.strength, 0) > strength_rank.get(best, -1):
                best = m.strength
    return best, reqs


def _recency_score(end_date: str | None, is_current: bool) -> float:
    if is_current:
        return 1.0
    if not end_date:
        return 0.3
    # crude recency: longer/more recent-looking date strings sort later lexically
    # often enough for "YYYY" or "Mon YYYY" formats; good enough as a tiebreaker.
    return 0.5


def build_plan(store: EvidenceStore, match_result: MatchResult, jd_keywords: list[str]) -> ResumePlan:
    settings = get_settings()["resume"]
    max_bullets = settings.get("max_bullets_per_role", 6)

    strength_bonus = {"strong": 3.0, "partial": 1.5, "none": 0.0}
    exp_by_id = {e["id"]: e for e in store.experiences}

    planned_experiences: list[PlannedExperience] = []
    for exp in store.experiences:
        candidate_bullets: list[PlannedBullet] = []
        for ach in store.achievements:
            if ach.get("experience_id") != exp["id"]:
                continue
            strength, reqs = _achievement_best_match(ach["id"], match_result)
            kw_score = keyword_score(" ".join(jd_keywords), ach["claim"] + " " + " ".join(ach.get("skills", [])))
            has_metrics_bonus = 0.5 if ach.get("metrics") else 0.0
            score = strength_bonus.get(strength, 0.0) + kw_score + has_metrics_bonus
            candidate_bullets.append(
                PlannedBullet(
                    achievement_id=ach["id"],
                    claim=ach["claim"],
                    metrics=ach.get("metrics", []),
                    skills=ach.get("skills", []),
                    match_strength=strength,
                    matched_requirements=reqs,
                    score=score,
                )
            )

        candidate_bullets.sort(key=lambda b: -b.score)
        selected = candidate_bullets[:max_bullets] if candidate_bullets else []
        # Ensure every role shows at least one bullet if any evidence exists at all,
        # even when nothing matched a requirement -- we don't erase real experience.
        if not selected and candidate_bullets:
            selected = candidate_bullets[:2]

        planned_experiences.append(
            PlannedExperience(
                experience_id=exp["id"],
                company=exp["company"],
                role=exp["role"],
                start_date=exp.get("start_date"),
                end_date=exp.get("end_date"),
                is_current=exp.get("is_current", False),
                location=exp.get("location"),
                bullets=selected,
            )
        )

    # order experiences: current first, then by presence of strong matches, then as-is (resume order)
    def exp_sort_key(pe: PlannedExperience) -> tuple:
        has_strong = any(b.match_strength == "strong" for b in pe.bullets)
        return (not pe.is_current, not has_strong)

    planned_experiences.sort(key=exp_sort_key)

    planned_projects: list[PlannedProject] = []
    for proj in store.projects:
        strength, reqs = _achievement_best_match(proj["id"], match_result)
        kw_score = keyword_score(" ".join(jd_keywords), proj["name"] + " " + proj["description"])
        score = strength_bonus.get(strength, 0.0) + kw_score
        if strength != "none" or kw_score > 0.3:
            planned_projects.append(
                PlannedProject(
                    project_id=proj["id"],
                    name=proj["name"],
                    description=proj["description"],
                    skills=proj.get("skills", []),
                    match_strength=strength,
                    matched_requirements=reqs,
                    score=score,
                )
            )
    planned_projects.sort(key=lambda p: -p.score)
    planned_projects = planned_projects[:4]

    # skills: everything cited by a matched requirement, plus any skill evidence
    # the store already has, deduped.
    matched_skill_names: set[str] = set()
    for pe in planned_experiences:
        for b in pe.bullets:
            matched_skill_names.update(b.skills)
    for pp in planned_projects:
        matched_skill_names.update(pp.skills)
    for s in store.skills:
        matched_skill_names.add(s["name"])
    skills_list = sorted(matched_skill_names, key=str.lower)

    unsupported = [
        {"requirement": m.requirement, "priority": m.priority, "category": m.category}
        for m in match_result.unsupported
    ]

    emphasis_by_company: dict[str, list[str]] = {}
    for pe in planned_experiences:
        if not pe.bullets:
            continue
        themes: set[str] = set()
        for b in pe.bullets:
            if b.match_strength in ("strong", "partial"):
                themes.update(b.skills[:3])
        if themes:
            emphasis_by_company[pe.company] = sorted(themes)

    total_bullets = sum(len(pe.bullets) for pe in planned_experiences)

    return ResumePlan(
        experiences=planned_experiences,
        projects=planned_projects,
        skills=skills_list,
        unsupported_requirements=unsupported,
        emphasis_by_company=emphasis_by_company,
        estimated_bullet_count=total_bullets,
    )
