"""Reads/writes the normalized evidence database under evidence/*.json.

Ingesting a new resume never overwrites what's already there -- it merges.
Overlapping experience (same company+role) is consolidated into one record
that accumulates provenance (source_files) rather than duplicating; distinct
achievements are kept distinct even when they belong to the same experience.
"""

from __future__ import annotations

import dataclasses
import difflib
import json
import logging
from pathlib import Path
from typing import Any

from . import schema
from .config import Paths
from .extraction import ExtractionResult

logger = logging.getLogger("resumeai.store")

DUPLICATE_ACHIEVEMENT_THRESHOLD = 0.9


def _path(name: str) -> Path:
    return Paths.evidence / name


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _asdict(obj) -> dict:
    return dataclasses.asdict(obj)


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


class EvidenceStore:
    """In-memory view of the evidence database, loaded from / saved to disk."""

    def __init__(self) -> None:
        self.profile: dict = _load_json(
            _path("profile.json"),
            {"full_name": None, "emails": [], "phones": [], "links": [], "location": None, "summaries": []},
        )
        self.experiences: list[dict] = _load_json(_path("experience.json"), [])
        self.achievements: list[dict] = _load_json(_path("achievements.json"), [])
        self.skills: list[dict] = _load_json(_path("skills.json"), [])
        self.projects: list[dict] = _load_json(_path("projects.json"), [])
        self.index: dict = _load_json(
            _path("evidence_index.json"),
            {"ingested_files": {}, "education": [], "certifications": [], "awards": [], "item_index": {}},
        )

    def save(self) -> None:
        _save_json(_path("profile.json"), self.profile)
        _save_json(_path("experience.json"), self.experiences)
        _save_json(_path("achievements.json"), self.achievements)
        _save_json(_path("skills.json"), self.skills)
        _save_json(_path("projects.json"), self.projects)
        _save_json(_path("evidence_index.json"), self.index)

    # -- merge logic -----------------------------------------------------

    def _merge_profile(self, incoming: dict, source_file: str) -> None:
        if incoming.get("full_name") and not self.profile.get("full_name"):
            self.profile["full_name"] = incoming["full_name"]
        for key in ("emails", "phones", "links"):
            existing = set(self.profile.get(key, []))
            for v in incoming.get(key) or []:
                if v and v not in existing:
                    self.profile.setdefault(key, []).append(v)
                    existing.add(v)
        if incoming.get("location") and not self.profile.get("location"):
            self.profile["location"] = incoming["location"]
        if incoming.get("summary"):
            self.profile.setdefault("summaries", []).append(
                {"text": incoming["summary"], "source_file": source_file}
            )

    def _find_matching_experience(self, company: str, role: str) -> dict | None:
        company_n, role_n = _normalize(company), _normalize(role)
        for e in self.experiences:
            if _normalize(e["company"]) == company_n and _normalize(e["role"]) == role_n:
                return e
        return None

    def _merge_experience(self, exp: schema.Experience) -> str:
        existing = self._find_matching_experience(exp.company, exp.role)
        if existing is None:
            record = _asdict(exp)
            record["source_files"] = [{"file": exp.source_file, "source_text": exp.source_text}]
            self.experiences.append(record)
            self._index_item(record["id"], "experience", "experience.json", exp.source_file)
            return record["id"]

        existing.setdefault("source_files", [{"file": existing["source_file"], "source_text": existing["source_text"]}])
        if not any(sf["file"] == exp.source_file for sf in existing["source_files"]):
            existing["source_files"].append({"file": exp.source_file, "source_text": exp.source_text})
        # fill gaps (e.g. one resume has end_date, another doesn't)
        for field in ("start_date", "end_date", "location"):
            if not existing.get(field) and getattr(exp, field):
                existing[field] = getattr(exp, field)
        return existing["id"]

    def _find_duplicate_achievement(self, claim: str, experience_id: str | None) -> dict | None:
        claim_n = _normalize(claim)
        for a in self.achievements:
            if a.get("experience_id") != experience_id:
                continue
            ratio = difflib.SequenceMatcher(None, claim_n, _normalize(a["claim"])).ratio()
            if ratio >= DUPLICATE_ACHIEVEMENT_THRESHOLD:
                return a
        return None

    def _merge_achievement(self, ach: schema.Achievement, experience_id_map: dict[str, str]) -> None:
        resolved_exp_id = experience_id_map.get(ach.experience_id) if ach.experience_id else None
        duplicate = self._find_duplicate_achievement(ach.claim, resolved_exp_id)
        if duplicate is not None:
            duplicate.setdefault("source_files", [{"file": duplicate["source_file"], "source_text": duplicate["source_text"]}])
            if not any(sf["file"] == ach.source_file for sf in duplicate["source_files"]):
                duplicate["source_files"].append({"file": ach.source_file, "source_text": ach.source_text})
            return

        record = _asdict(ach)
        record["experience_id"] = resolved_exp_id
        record["source_files"] = [{"file": ach.source_file, "source_text": ach.source_text}]
        self.achievements.append(record)
        self._index_item(record["id"], "achievement", "achievements.json", ach.source_file)

    def _merge_project(self, proj: schema.Project) -> None:
        name_n = _normalize(proj.name)
        for p in self.projects:
            if _normalize(p["name"]) == name_n:
                p.setdefault("source_files", [{"file": p["source_file"], "source_text": p["source_text"]}])
                if not any(sf["file"] == proj.source_file for sf in p["source_files"]):
                    p["source_files"].append({"file": proj.source_file, "source_text": proj.source_text})
                return
        record = _asdict(proj)
        record["source_files"] = [{"file": proj.source_file, "source_text": proj.source_text}]
        self.projects.append(record)
        self._index_item(record["id"], "project", "projects.json", proj.source_file)

    def _merge_skill(self, skill: schema.SkillEvidence) -> None:
        name_n = _normalize(skill.name)
        for s in self.skills:
            if _normalize(s["name"]) == name_n:
                s.setdefault("source_files", [])
                if skill.source_file and not any(sf.get("file") == skill.source_file for sf in s["source_files"]):
                    s["source_files"].append({"file": skill.source_file, "source_text": skill.source_text})
                return
        record = _asdict(skill)
        record["source_files"] = [{"file": skill.source_file, "source_text": skill.source_text}] if skill.source_file else []
        self.skills.append(record)
        self._index_item(record["id"], "skill", "skills.json", skill.source_file or "user_added")

    def _index_item(self, item_id: str, kind: str, file: str, source_file: str) -> None:
        self.index.setdefault("item_index", {})[item_id] = {"kind": kind, "file": file, "source_file": source_file}

    def ingest_extraction(self, result: ExtractionResult, source_file: str) -> dict:
        self._merge_profile(result.profile, source_file)

        experience_id_map: dict[str, str] = {}
        for exp in result.experiences:
            merged_id = self._merge_experience(exp)
            experience_id_map[exp.id] = merged_id

        for ach in result.achievements:
            self._merge_achievement(ach, experience_id_map)

        for proj in result.projects:
            self._merge_project(proj)

        for skill in result.skills:
            self._merge_skill(skill)

        # education/certifications/awards: dedupe by normalized name
        for edu in result.education:
            if not any(_normalize(e["institution"]) == _normalize(edu.institution) and _normalize(e["degree"]) == _normalize(edu.degree) for e in self.index["education"]):
                self.index["education"].append(_asdict(edu))
        for cert in result.certifications:
            if not any(_normalize(c["name"]) == _normalize(cert.name) for c in self.index["certifications"]):
                self.index["certifications"].append(_asdict(cert))
        for award in result.awards:
            if not any(_normalize(a["name"]) == _normalize(award.name) for a in self.index["awards"]):
                self.index["awards"].append(_asdict(award))

        self.index.setdefault("ingested_files", {})[source_file] = {
            "num_experiences": len(result.experiences),
            "num_achievements": len(result.achievements),
            "num_projects": len(result.projects),
            "num_skills": len(result.skills),
            "rejected_count": len(result.rejected),
        }

        self.save()

        return {
            "source_file": source_file,
            "experiences_added": len(result.experiences),
            "achievements_added": len(result.achievements),
            "projects_added": len(result.projects),
            "skills_added": len(result.skills),
            "rejected": result.rejected,
        }

    def add_user_evidence(self, *, kind: str, data: dict) -> dict:
        """Manual additions from the Profile page. Always tagged source=user_added."""
        if kind == "achievement":
            record = {
                "id": schema.new_id("ach"),
                "claim": data["claim"],
                "experience_id": data.get("experience_id"),
                "project_id": data.get("project_id"),
                "metrics": data.get("metrics", []),
                "skills": data.get("skills", []),
                "source_file": "user_added",
                "source_section": "Manual",
                "source_text": data["claim"],
                "confidence": "high",
                "kind": "achievement",
                "source_files": [{"file": "user_added", "source_text": data["claim"]}],
            }
            self.achievements.append(record)
            self._index_item(record["id"], "achievement", "achievements.json", "user_added")
        elif kind == "skill":
            skill = schema.SkillEvidence(
                id=schema.new_id("skill"),
                name=data["name"],
                category=data.get("category"),
                evidence_ids=[],
                source_file=None,
                source_text=None,
                source="user_added",
            )
            record = _asdict(skill)
            record["source_files"] = []
            self.skills.append(record)
            self._index_item(record["id"], "skill", "skills.json", "user_added")
        elif kind == "project":
            proj = schema.Project(
                id=schema.new_id("proj"),
                name=data["name"],
                description=data.get("description", ""),
                skills=data.get("skills", []),
                source_file="user_added",
                source_section="Manual",
                source_text=data.get("description", data["name"]),
                confidence="high",
            )
            record = _asdict(proj)
            record["source_files"] = [{"file": "user_added", "source_text": record["source_text"]}]
            self.projects.append(record)
            self._index_item(record["id"], "project", "projects.json", "user_added")
        else:
            raise ValueError(f"Unsupported manual evidence kind: {kind}")

        self.save()
        return record

    def all_evidence_flat(self) -> list[dict]:
        """Every achievement + project, the two kinds that can support a resume bullet."""
        return [{"evidence_type": "achievement", **a} for a in self.achievements] + [
            {"evidence_type": "project", **p} for p in self.projects
        ]

    def stats(self) -> dict:
        return {
            "experiences": len(self.experiences),
            "achievements": len(self.achievements),
            "projects": len(self.projects),
            "skills": len(self.skills),
            "education": len(self.index.get("education", [])),
            "certifications": len(self.index.get("certifications", [])),
            "awards": len(self.index.get("awards", [])),
            "ingested_files": list(self.index.get("ingested_files", {}).keys()),
        }
