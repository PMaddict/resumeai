"""LLM-driven structured extraction of resume text into evidence candidates.

Every candidate the model proposes is checked against `grounding.py` before
it's allowed into the evidence database. Candidates that fail grounding are
dropped and logged -- not corrected, not kept with a warning, dropped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import schema
from .grounding import check_grounded
from .llm import generate_json

logger = logging.getLogger("resumeai.extraction")

SYSTEM_PROMPT = """You are a meticulous resume parser. You extract ONLY information that is \
literally present in the resume text given to you. You never infer, estimate, or add \
information that is not explicitly stated.

Rules you must follow exactly:
1. Every object you return MUST include a "source_text" field: an exact, verbatim, \
character-for-character copy of the snippet from the input text that supports it. Do not \
paraphrase, summarize, or clean it up -- copy it exactly as it appears, including its \
original wording.
2. Never combine facts from two different bullets/sentences into one claim unless the \
source text itself explicitly connects them.
3. Never invent a metric, company, title, date, or skill. If a field is not present in the \
text, omit it or use null -- do not guess.
4. If you are not confident an item is explicitly supported by the text, leave it out \
entirely rather than include it with low confidence.
5. Output must be valid JSON matching the schema you are given. No commentary, no markdown \
fences, no explanation -- just the JSON object.
6. CRITICAL: create ONE "experiences" entry per company/role, but ONE separate "achievements" \
entry for EVERY SINGLE bullet point under that role -- never combine multiple bullet points \
into a single achievement, and never skip a bullet point. If a role has 3 bullet points in \
the source text, you must return 3 separate achievement objects for it, each with its own \
source_text copied from just that one bullet. Go through the resume bullet by bullet and do \
not stop until every single one has its own achievement object.
"""

SCHEMA_DESCRIPTION = """Return a single JSON object with this exact shape:
{
  "profile": {
    "full_name": string|null,
    "emails": [string],
    "phones": [string],
    "links": [string],
    "location": string|null,
    "summary": string|null
  },
  "experiences": [
    {
      "company": string,
      "role": string,
      "start_date": string|null,
      "end_date": string|null,
      "is_current": boolean,
      "location": string|null,
      "source_text": string
    }
  ],
  "achievements": [
    {
      "claim": string,
      "company": string|null,
      "role": string|null,
      "metrics": [ {"value": string, "context": string, "source_text": string} ],
      "skills": [string],
      "source_text": string
    }
  ],
  "projects": [
    {"name": string, "description": string, "skills": [string], "source_text": string}
  ],
  "skills": [
    {"name": string, "category": string|null, "source_text": string}
  ],
  "education": [
    {
      "institution": string, "degree": string, "field_of_study": string|null,
      "start_date": string|null, "end_date": string|null, "source_text": string
    }
  ],
  "certifications": [
    {"name": string, "issuer": string|null, "date": string|null, "source_text": string}
  ],
  "awards": [
    {"name": string, "issuer": string|null, "date": string|null, "source_text": string}
  ]
}

"company"/"role" on an achievement should match an entry in "experiences" when the \
achievement belongs to that role; use null if it's not tied to a specific employer role \
(e.g. a personal project or general skill statement).

The top-level "skills" array is for skills/tools explicitly listed in a dedicated \
Skills/Tools/Technologies section of the resume (not ones already captured inside an \
achievement or project bullet).
"""


@dataclass
class ExtractionResult:
    profile: dict
    experiences: list[schema.Experience]
    achievements: list[schema.Achievement]
    projects: list[schema.Project]
    skills: list[schema.SkillEvidence]
    education: list[schema.EducationEntry]
    certifications: list[schema.CertificationEntry]
    awards: list[schema.AwardEntry]
    rejected: list[dict]  # items dropped for failing grounding, kept for logs/audit


def extract_from_text(raw_text: str, source_file: str) -> ExtractionResult:
    user_prompt = (
        f"{SCHEMA_DESCRIPTION}\n\n"
        f"Resume text to extract from (source file: {source_file}):\n"
        f"---\n{raw_text}\n---"
    )
    data = generate_json(SYSTEM_PROMPT, user_prompt, retries=1)

    rejected: list[dict] = []

    def grounded_or_reject(item: dict, item_type: str) -> bool:
        source_text = item.get("source_text", "")
        result = check_grounded(source_text, raw_text)
        if not result.grounded:
            rejected.append(
                {
                    "type": item_type,
                    "item": item,
                    "reason": result.reason,
                    "similarity": round(result.similarity, 3),
                    "source_file": source_file,
                }
            )
            logger.warning(
                "Rejected %s from %s (similarity %.2f): %s",
                item_type, source_file, result.similarity, item.get("claim") or item.get("company") or item,
            )
        return result.grounded

    experiences: list[schema.Experience] = []
    for exp in data.get("experiences", []) or []:
        if not grounded_or_reject(exp, "experience"):
            continue
        experiences.append(
            schema.Experience(
                id=schema.new_id("exp"),
                company=exp.get("company", "").strip(),
                role=exp.get("role", "").strip(),
                start_date=exp.get("start_date"),
                end_date=exp.get("end_date"),
                is_current=bool(exp.get("is_current", False)),
                location=exp.get("location"),
                source_file=source_file,
                source_section="Experience",
                source_text=exp["source_text"],
                confidence="high",
            )
        )

    def find_experience_id(company: str | None, role: str | None) -> str | None:
        if not company:
            return None
        company_norm = company.strip().lower()
        for e in experiences:
            if e.company.strip().lower() == company_norm:
                if not role or e.role.strip().lower() == role.strip().lower():
                    return e.id
        return None

    achievements: list[schema.Achievement] = []
    for ach in data.get("achievements", []) or []:
        if not grounded_or_reject(ach, "achievement"):
            continue
        metrics: list[schema.Metric] = []
        for m in ach.get("metrics", []) or []:
            m_result = check_grounded(m.get("source_text", ""), raw_text)
            if not m_result.grounded:
                rejected.append(
                    {
                        "type": "metric",
                        "item": m,
                        "reason": m_result.reason,
                        "similarity": round(m_result.similarity, 3),
                        "source_file": source_file,
                    }
                )
                continue
            metrics.append(
                schema.Metric(
                    id=schema.new_id("metric"),
                    value=str(m.get("value", "")),
                    context=m.get("context", ""),
                    source_text=m["source_text"],
                    source_file=source_file,
                )
            )
        achievements.append(
            schema.Achievement(
                id=schema.new_id("ach"),
                claim=ach.get("claim", "").strip(),
                experience_id=find_experience_id(ach.get("company"), ach.get("role")),
                project_id=None,
                metrics=metrics,
                skills=[s.strip() for s in (ach.get("skills") or []) if s.strip()],
                source_file=source_file,
                source_section="Experience",
                source_text=ach["source_text"],
                confidence="high",
            )
        )

    projects: list[schema.Project] = []
    for proj in data.get("projects", []) or []:
        if not grounded_or_reject(proj, "project"):
            continue
        projects.append(
            schema.Project(
                id=schema.new_id("proj"),
                name=proj.get("name", "").strip(),
                description=proj.get("description", "").strip(),
                skills=[s.strip() for s in (proj.get("skills") or []) if s.strip()],
                source_file=source_file,
                source_section="Projects",
                source_text=proj["source_text"],
                confidence="high",
            )
        )

    top_level_skills: list[schema.SkillEvidence] = []
    for sk in data.get("skills", []) or []:
        if not grounded_or_reject(sk, "skill"):
            continue
        name = sk.get("name", "").strip()
        if not name:
            continue
        top_level_skills.append(
            schema.SkillEvidence(
                id=schema.new_id("skill"),
                name=name,
                category=sk.get("category"),
                evidence_ids=[],
                source_file=source_file,
                source_text=sk["source_text"],
                source="resume",
            )
        )

    education: list[schema.EducationEntry] = []
    for edu in data.get("education", []) or []:
        if not grounded_or_reject(edu, "education"):
            continue
        education.append(
            schema.EducationEntry(
                id=schema.new_id("edu"),
                institution=edu.get("institution", "").strip(),
                degree=edu.get("degree", "").strip(),
                field_of_study=edu.get("field_of_study"),
                start_date=edu.get("start_date"),
                end_date=edu.get("end_date"),
                source_file=source_file,
                source_text=edu["source_text"],
            )
        )

    certifications: list[schema.CertificationEntry] = []
    for cert in data.get("certifications", []) or []:
        if not grounded_or_reject(cert, "certification"):
            continue
        certifications.append(
            schema.CertificationEntry(
                id=schema.new_id("cert"),
                name=cert.get("name", "").strip(),
                issuer=cert.get("issuer"),
                date=cert.get("date"),
                source_file=source_file,
                source_text=cert["source_text"],
            )
        )

    awards: list[schema.AwardEntry] = []
    for award in data.get("awards", []) or []:
        if not grounded_or_reject(award, "award"):
            continue
        awards.append(
            schema.AwardEntry(
                id=schema.new_id("award"),
                name=award.get("name", "").strip(),
                issuer=award.get("issuer"),
                date=award.get("date"),
                source_file=source_file,
                source_text=award["source_text"],
            )
        )

    profile = data.get("profile", {}) or {}

    return ExtractionResult(
        profile=profile,
        experiences=experiences,
        achievements=achievements,
        projects=projects,
        skills=top_level_skills,
        education=education,
        certifications=certifications,
        awards=awards,
        rejected=rejected,
    )
