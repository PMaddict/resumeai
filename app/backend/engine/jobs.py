"""Job (JD) lifecycle: create -> analyze (preview) -> generate (final resume).

A "job" is one JD you're tailoring a resume for. Analyze and generate are
separate steps so the UI can show you the planned evidence emphasis before
committing to generation (spec requirement: user control over the narrative).

Each generate call writes to a fresh timestamped output folder -- previous
generations for the same company/role are never overwritten.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from . import jd_parser, matching, planning, report, validation, writing
from .config import Paths
from .docx_writer import render_docx
from .pdf_writer import render_pdf
from .store import EvidenceStore
from .storage_jobs import JobsIndex

logger = logging.getLogger("resumeai.jobs")


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return text or "untitled"


def create_job(*, raw_text: str, company: str | None, role: str | None) -> dict:
    jobs_index = JobsIndex()
    job = jobs_index.create(raw_text=raw_text, company=company, role=role)
    Paths.jobs_incoming.mkdir(parents=True, exist_ok=True)
    (Paths.jobs_incoming / f"{job['id']}.txt").write_text(raw_text, encoding="utf-8")
    return job


def analyze_job(job_id: str) -> dict:
    jobs_index = JobsIndex()
    job = jobs_index.get(job_id)
    if job is None:
        raise KeyError(f"No such job: {job_id}")

    store = EvidenceStore()
    parsed_jd = jd_parser.parse_jd(job["raw_text"])
    if job.get("company"):
        parsed_jd.company = job["company"]
    if job.get("role"):
        parsed_jd.role_title = job["role"]

    match_result = matching.match_jd_to_evidence(parsed_jd, store)
    plan = planning.build_plan(store, match_result, parsed_jd.keywords)

    analysis = {
        "parsed_jd": dataclasses.asdict(parsed_jd),
        "matches": [dataclasses.asdict(m) for m in match_result.matches],
        "plan": {
            "experiences": [dataclasses.asdict(pe) for pe in plan.experiences],
            "projects": [dataclasses.asdict(pp) for pp in plan.projects],
            "skills": plan.skills,
            "unsupported_requirements": plan.unsupported_requirements,
            "emphasis_by_company": plan.emphasis_by_company,
            "estimated_bullet_count": plan.estimated_bullet_count,
        },
    }

    Paths.jobs_processed.mkdir(parents=True, exist_ok=True)
    (Paths.jobs_processed / f"{job_id}_analysis.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    jobs_index.update(job_id, status="analyzed", company=parsed_jd.company, role=parsed_jd.role_title)

    return analysis


def generate_job(job_id: str) -> dict:
    """Re-runs analysis (cheap, deterministic given the current evidence base)
    then writes, validates, and renders the tailored resume + reports.
    """
    jobs_index = JobsIndex()
    job = jobs_index.get(job_id)
    if job is None:
        raise KeyError(f"No such job: {job_id}")

    store = EvidenceStore()
    parsed_jd = jd_parser.parse_jd(job["raw_text"])
    if job.get("company"):
        parsed_jd.company = job["company"]
    if job.get("role"):
        parsed_jd.role_title = job["role"]

    match_result = matching.match_jd_to_evidence(parsed_jd, store)
    plan = planning.build_plan(store, match_result, parsed_jd.keywords)
    content = writing.write_resume(store, plan, parsed_jd.keywords, parsed_jd.role_title)
    val_report = validation.validate_resume(content, store)

    company_slug = _slugify(parsed_jd.company or job.get("company") or "company")
    role_slug = _slugify(parsed_jd.role_title or job.get("role") or "role")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Paths.outputs / f"{company_slug}-{role_slug}" / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "job_id": job_id,
        "output_dir": str(out_dir.relative_to(Paths.root)),
        "validation": {
            "passed": val_report.passed,
            "issues": [dataclasses.asdict(i) for i in val_report.issues],
        },
    }

    if not val_report.passed:
        # Hard stop: do NOT silently produce resume files if a fabrication-risk
        # error was found. Still write the report so the user can see why.
        report.write_tailoring_report(
            parsed_jd=parsed_jd,
            match_result=match_result,
            plan=plan,
            content=content,
            validation=val_report,
            store=store,
            output_path=out_dir / "tailoring_report.md",
        )
        jobs_index.update(job_id, status="generation_blocked")
        result["blocked"] = True
        return result

    docx_path = render_docx(content, out_dir / "tailored_resume.docx")
    pdf_path = render_pdf(content, out_dir / "tailored_resume.pdf")
    report.write_evidence_map(content, store, out_dir / "evidence_map.json")
    report.write_tailoring_report(
        parsed_jd=parsed_jd,
        match_result=match_result,
        plan=plan,
        content=content,
        validation=val_report,
        store=store,
        output_path=out_dir / "tailoring_report.md",
    )

    jobs_index.update(job_id, status="generated", last_output_dir=str(out_dir.relative_to(Paths.root)))

    result["blocked"] = False
    result["docx_path"] = str(docx_path.relative_to(Paths.root))
    result["pdf_path"] = str(pdf_path.relative_to(Paths.root))
    return result
