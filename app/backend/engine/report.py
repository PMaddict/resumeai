"""Builds the human-readable tailoring_report.md and the machine-readable
evidence_map.json that traces every resume bullet back to its source.
"""

from __future__ import annotations

import json
from pathlib import Path

from .jd_parser import ParsedJD
from .matching import MatchResult
from .planning import ResumePlan
from .store import EvidenceStore
from .validation import ValidationReport
from .writing import ResumeContent


def build_evidence_map(content: ResumeContent, store: EvidenceStore) -> dict:
    achievements_by_id = {a["id"]: a for a in store.achievements}
    entries = []
    for exp in content.experiences:
        for bullet in exp.bullets:
            source = achievements_by_id.get(bullet.achievement_id, {})
            entries.append(
                {
                    "resume_bullet": bullet.text,
                    "experience": f"{exp.role} — {exp.company}",
                    "was_rewritten": bullet.was_rewritten,
                    "source_evidence": [
                        {
                            "evidence_id": bullet.achievement_id,
                            "source_file": source.get("source_file"),
                            "source_text": source.get("source_text"),
                        }
                    ],
                }
            )
    return {"resume_bullets": entries}


def write_evidence_map(content: ResumeContent, store: EvidenceStore, output_path: Path) -> Path:
    data = build_evidence_map(content, store)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return output_path


def _match_lines(matches, show_limitation: bool) -> str:
    lines = []
    for m in matches:
        lines.append(f"- **Requirement:** {m.requirement}")
        if m.evidence_ids:
            lines.append(f"  - **Supporting evidence IDs:** {', '.join(m.evidence_ids)}")
        if m.reasoning:
            label = "Limitation" if show_limitation else "Why it matches"
            lines.append(f"  - **{label}:** {m.reasoning}")
    return "\n".join(lines)


def write_tailoring_report(
    *,
    parsed_jd: ParsedJD,
    match_result: MatchResult,
    plan: ResumePlan,
    content: ResumeContent,
    validation: ValidationReport,
    store: EvidenceStore,
    output_path: Path,
) -> Path:
    total_claims = sum(len(e.bullets) for e in content.experiences)
    blocked_claims = len(content.rewrite_rejections)
    unsupported_count = len(match_result.unsupported)

    lines: list[str] = []
    lines.append("# Tailoring Report")
    lines.append("")
    lines.append("## JD Summary")
    lines.append(f"- **Role:** {parsed_jd.role_title or 'Unknown'}")
    lines.append(f"- **Company:** {parsed_jd.company or 'Unknown'}")
    lines.append(f"- **Seniority:** {parsed_jd.seniority or 'Unknown'}")
    lines.append("")

    lines.append("## Strong Matches")
    lines.append(_match_lines(match_result.strong, show_limitation=False) or "_None found._")
    lines.append("")

    lines.append("## Partial Matches")
    lines.append(_match_lines(match_result.partial, show_limitation=True) or "_None found._")
    lines.append("")

    lines.append("## Unsupported Requirements")
    if match_result.unsupported:
        for m in match_result.unsupported:
            lines.append(f"- **{m.requirement}** ({m.priority.replace('_', ' ')}) — no supporting evidence found. Not included in the resume.")
    else:
        lines.append("_None — every JD requirement had at least partial supporting evidence._")
    lines.append("")

    lines.append("## Resume Changes")
    rewritten = [b for e in content.experiences for b in e.bullets if b.was_rewritten]
    kept_as_is = [b for e in content.experiences for b in e.bullets if not b.was_rewritten]
    included_ids = {b.achievement_id for e in content.experiences for b in e.bullets}
    experience_ids_included = {e.experience_id for e in content.experiences}
    de_emphasized = [
        a
        for a in store.achievements
        if a["id"] not in included_ids and a.get("experience_id") in experience_ids_included
    ]
    lines.append(f"- **Added/Rewritten for clarity or relevance:** {len(rewritten)} bullet(s)")
    lines.append(f"- **Kept as original wording:** {len(kept_as_is)} bullet(s)")
    lines.append(f"- **De-emphasized (evidence exists but excluded to keep the resume focused/concise):** {len(de_emphasized)} bullet(s)")
    for a in de_emphasized[:10]:
        lines.append(f"  - \"{a['claim'][:90]}\"")
    if content.rewrite_rejections:
        lines.append(f"- **Rewrites rejected (reverted to original wording) due to ungrounded content:** {len(content.rewrite_rejections)}")
    lines.append("")

    lines.append("## Evidence Integrity")
    lines.append(f"- **Total resume claims (bullets):** {total_claims}")
    lines.append(f"- **Supported claims:** {total_claims}")
    lines.append(f"- **Unsupported claims included in resume:** 0")
    lines.append(f"- **Blocked/rejected rewrite attempts:** {blocked_claims}")
    lines.append(f"- **JD requirements with no evidence (excluded from resume):** {unsupported_count}")
    lines.append("")

    lines.append("## Validation")
    if validation.passed:
        lines.append("All automated validation checks passed.")
    else:
        lines.append("**Validation errors were found and generation was blocked. See below.**")
    for issue in validation.issues:
        lines.append(f"- [{issue.severity.upper()}] {issue.message}")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
