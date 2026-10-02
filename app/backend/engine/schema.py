"""Evidence data model.

Every fact in this system is an "evidence item" that must carry provenance:
which source file it came from, and the verbatim source text it was derived
from. Nothing enters the evidence database without that trail, and nothing
enters a generated resume without tracing back to an evidence item here.

Evidence types:
  - experience:   a role held at a company (container for achievements)
  - achievement:  a single claim/bullet tied to one experience (or standalone
                   project), optionally carrying metrics
  - project:      a standalone project not tied to an employer role
  - skill:        a normalized skill/tool name with links to where it's evidenced
  - education:    a degree/program entry
  - certification: a certification entry
  - award:        an award entry

`source = "user_added"` marks anything the user typed in manually via the
Profile page rather than something extracted from a resume file -- it is
still real evidence, just not resume-derived.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Confidence = Literal["high", "medium", "low"]
EvidenceKind = Literal[
    "experience", "achievement", "project", "skill", "education", "certification", "award"
]


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Metric:
    id: str
    value: str
    context: str
    source_text: str
    source_file: str


@dataclass
class Experience:
    """A role held at a company. Achievements attach to this via experience_id."""

    id: str
    company: str
    role: str
    start_date: str | None
    end_date: str | None  # None/"" with is_current True means ongoing
    is_current: bool
    location: str | None
    source_file: str
    source_section: str
    source_text: str
    confidence: Confidence = "medium"
    kind: EvidenceKind = "experience"


@dataclass
class Achievement:
    """A single factual claim/bullet, optionally tied to an experience or project.

    metrics must only include numbers that the source_text establishes as
    belonging to *this* claim -- never merged in from an unrelated claim.
    """

    id: str
    claim: str
    experience_id: str | None
    project_id: str | None
    metrics: list[Metric]
    skills: list[str]
    source_file: str
    source_section: str
    source_text: str
    confidence: Confidence = "medium"
    kind: EvidenceKind = "achievement"


@dataclass
class Project:
    id: str
    name: str
    description: str
    skills: list[str]
    source_file: str
    source_section: str
    source_text: str
    confidence: Confidence = "medium"
    kind: EvidenceKind = "project"


@dataclass
class SkillEvidence:
    """A normalized skill with pointers to every evidence item that mentions it."""

    id: str
    name: str
    category: str | None  # e.g. "tool", "domain", "soft-skill", "technique"
    evidence_ids: list[str]
    source_file: str | None = None
    source_text: str | None = None
    source: Literal["resume", "user_added"] = "resume"
    kind: EvidenceKind = "skill"


@dataclass
class EducationEntry:
    id: str
    institution: str
    degree: str
    field_of_study: str | None
    start_date: str | None
    end_date: str | None
    source_file: str
    source_text: str
    kind: EvidenceKind = "education"


@dataclass
class CertificationEntry:
    id: str
    name: str
    issuer: str | None
    date: str | None
    source_file: str
    source_text: str
    kind: EvidenceKind = "certification"


@dataclass
class AwardEntry:
    id: str
    name: str
    issuer: str | None
    date: str | None
    source_file: str
    source_text: str
    kind: EvidenceKind = "award"


@dataclass
class Profile:
    """Personal info + free-text summary statements pulled from resumes."""

    full_name: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)  # LinkedIn, portfolio, GitHub, etc.
    location: str | None = None
    summaries: list[dict] = field(default_factory=list)  # [{text, source_file}]
