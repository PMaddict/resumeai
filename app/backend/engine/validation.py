"""Final independent gate before any file is written.

This does NOT trust that extraction.py or writing.py already enforced
grounding -- it re-checks the finished ResumeContent from scratch against
the evidence database. Any "error"-level finding blocks file generation.
"warning"-level findings (e.g. resume running long) are reported but don't
block -- they're not fabrication risks, just polish concerns.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import get_settings
from .grounding import extract_numbers_and_tokens
from .store import EvidenceStore
from .writing import ResumeContent


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0


def validate_resume(content: ResumeContent, store: EvidenceStore) -> ValidationReport:
    report = ValidationReport()

    achievements_by_id = {a["id"]: a for a in store.achievements}
    experiences_by_id = {e["id"]: e for e in store.experiences}

    seen_bullet_texts: list[str] = []

    for exp in content.experiences:
        source_exp = experiences_by_id.get(exp.experience_id)
        if source_exp is None:
            report.issues.append(
                ValidationIssue("error", f"Experience '{exp.company} / {exp.role}' has no matching evidence record.")
            )
            continue
        if source_exp["company"] != exp.company:
            report.issues.append(ValidationIssue("error", f"Company name mismatch for {exp.experience_id}."))
        if source_exp["role"] != exp.role:
            report.issues.append(ValidationIssue("error", f"Job title mismatch for {exp.experience_id}."))

        for bullet in exp.bullets:
            source_ach = achievements_by_id.get(bullet.achievement_id)
            if source_ach is None:
                report.issues.append(
                    ValidationIssue("error", f"Bullet references unknown achievement id {bullet.achievement_id}.")
                )
                continue

            source_text = (
                source_ach["claim"]
                + " "
                + " ".join(source_ach.get("skills", []))
                + " "
                + " ".join(
                    m.get("context", "") + " " + str(m.get("value", "")) for m in source_ach.get("metrics", [])
                )
            )
            source_tokens = extract_numbers_and_tokens(source_text)
            bullet_tokens = extract_numbers_and_tokens(bullet.text, ignore_sentence_initial_caps=True)
            new_tokens = bullet_tokens - source_tokens
            if new_tokens:
                report.issues.append(
                    ValidationIssue(
                        "error",
                        f"Bullet for {exp.company} introduces ungrounded content not in source evidence: {sorted(new_tokens)}",
                    )
                )

            normalized = bullet.text.strip().lower()
            if normalized in seen_bullet_texts:
                report.issues.append(ValidationIssue("warning", f"Duplicate bullet text detected: '{bullet.text[:60]}...'"))
            seen_bullet_texts.append(normalized)

            for stray in ("**", "##", "<", ">", "](", "```"):
                if stray in bullet.text:
                    report.issues.append(
                        ValidationIssue("warning", f"Bullet contains stray formatting artifact '{stray}': '{bullet.text[:60]}'")
                    )

    all_store_skill_names = {s["name"].strip().lower() for s in store.skills}
    all_evidence_skill_names = {
        s.strip().lower() for a in store.achievements for s in a.get("skills", [])
    } | {s.strip().lower() for p in store.projects for s in p.get("skills", [])}
    known_skills = all_store_skill_names | all_evidence_skill_names
    for skill in content.skills:
        if skill.strip().lower() not in known_skills:
            report.issues.append(ValidationIssue("error", f"Skill '{skill}' is not backed by any evidence record."))

    settings = get_settings()["resume"]
    total_bullets = sum(len(e.bullets) for e in content.experiences)
    estimated_lines = total_bullets + len(content.experiences) * 2 + len(content.projects) * 2 + 6
    estimated_pages = max(1, round(estimated_lines / 45))
    max_pages = settings.get("target_max_pages", 2)
    if estimated_pages > max_pages:
        report.issues.append(
            ValidationIssue(
                "warning",
                f"Estimated resume length (~{estimated_pages} pages) exceeds target of {max_pages} pages; consider trimming bullets.",
            )
        )

    if content.rewrite_rejections:
        for r in content.rewrite_rejections:
            report.issues.append(
                ValidationIssue(
                    "warning",
                    f"A rewritten bullet for achievement {r['achievement_id']} was rejected and reverted to original wording ({r['reason']}).",
                )
            )

    return report
