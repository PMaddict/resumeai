"""CLI for ResumeAI.

Usage (from the project root, with the virtualenv active):
    python resume_ai.py ingest
    python resume_ai.py analyze jobs/incoming/some-jd.pdf
    python resume_ai.py tailor jobs/incoming/some-jd.pdf --company Acme --role "Senior PM"
    python resume_ai.py list-evidence
    python resume_ai.py rebuild-index
    python resume_ai.py export
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from .engine import jobs as jobs_engine
from .engine.config import Paths
from .engine.ingest_pipeline import ingest_all
from .engine.llm import is_available as llm_is_available
from .engine.readers import read_text
from .engine.store import EvidenceStore


def _require_llm():
    if not llm_is_available():
        raise click.ClickException(
            "Local model not reachable. Start it with 'ollama serve' (and make sure the model "
            "configured in config/settings.json has been pulled)."
        )


@click.group()
def cli():
    """ResumeAI command-line interface."""


@cli.command()
def ingest():
    """Ingest every resume in source_resumes/originals/ into the evidence database."""
    _require_llm()
    results = ingest_all()
    for r in results:
        click.echo(
            f"  {r['source_file']}: +{r['experiences_added']} experience(s), "
            f"+{r['achievements_added']} achievement(s), +{r['projects_added']} project(s), "
            f"+{r['skills_added']} skill(s), {len(r['rejected'])} rejected"
        )
    if not results:
        click.echo("No resume files found in source_resumes/originals/.")


@cli.command()
@click.argument("jd_path_or_text")
@click.option("--company", default=None)
@click.option("--role", default=None)
def analyze(jd_path_or_text: str, company: str | None, role: str | None):
    """Analyze a JD (file path or raw text) against the evidence database without generating a resume."""
    _require_llm()
    raw_text = _resolve_jd_text(jd_path_or_text)
    job = jobs_engine.create_job(raw_text=raw_text, company=company, role=role)
    analysis = jobs_engine.analyze_job(job["id"])

    click.echo(f"\nJob ID: {job['id']}")
    click.echo(f"Role: {analysis['parsed_jd'].get('role_title')}  Company: {analysis['parsed_jd'].get('company')}\n")

    click.echo("Strong matches:")
    for m in analysis["matches"]:
        if m["strength"] == "strong":
            click.echo(f"  - {m['requirement']}  (evidence: {', '.join(m['evidence_ids'])})")

    click.echo("\nPartial matches:")
    for m in analysis["matches"]:
        if m["strength"] == "partial":
            click.echo(f"  - {m['requirement']}  (evidence: {', '.join(m['evidence_ids'])})")

    click.echo("\nUnsupported requirements (will be excluded, not fabricated):")
    for m in analysis["matches"]:
        if m["strength"] == "unsupported":
            click.echo(f"  - {m['requirement']}")

    click.echo(f"\nFull analysis saved to jobs/processed/{job['id']}_analysis.json")


@cli.command()
@click.argument("jd_path_or_text")
@click.option("--company", default=None)
@click.option("--role", default=None)
def tailor(jd_path_or_text: str, company: str | None, role: str | None):
    """Full pipeline: analyze a JD and generate a tailored resume (DOCX + PDF + report)."""
    _require_llm()
    raw_text = _resolve_jd_text(jd_path_or_text)
    job = jobs_engine.create_job(raw_text=raw_text, company=company, role=role)
    jobs_engine.analyze_job(job["id"])
    result = jobs_engine.generate_job(job["id"])

    if result.get("blocked"):
        click.echo("\nGeneration BLOCKED by validation -- see the report for details:")
        for issue in result["validation"]["issues"]:
            click.echo(f"  [{issue['severity'].upper()}] {issue['message']}")
        click.echo(f"\nReport: {result['output_dir']}/tailoring_report.md")
        raise SystemExit(1)

    click.echo(f"\nTailored resume generated in: {result['output_dir']}")
    click.echo(f"  DOCX: {result['docx_path']}")
    click.echo(f"  PDF:  {result['pdf_path']}")
    click.echo(f"  Report: {result['output_dir']}/tailoring_report.md")
    click.echo(f"  Evidence map: {result['output_dir']}/evidence_map.json")


@cli.command("list-evidence")
def list_evidence():
    """Print a summary of everything currently in the evidence database."""
    store = EvidenceStore()
    stats = store.stats()
    click.echo(json.dumps(stats, indent=2))


@cli.command("rebuild-index")
def rebuild_index():
    """Wipe the evidence database and re-extract everything from scratch."""
    _require_llm()
    for name in ["profile.json", "experience.json", "achievements.json", "skills.json", "projects.json", "evidence_index.json"]:
        p = Paths.evidence / name
        if p.exists():
            p.unlink()
    results = ingest_all()
    click.echo(f"Rebuilt index from {len(results)} source file(s).")


@cli.command()
def export():
    """Write a single consolidated snapshot of the evidence database for backup/review."""
    store = EvidenceStore()
    snapshot = {
        "profile": store.profile,
        "experiences": store.experiences,
        "achievements": store.achievements,
        "projects": store.projects,
        "skills": store.skills,
        "education": store.index.get("education", []),
        "certifications": store.index.get("certifications", []),
        "awards": store.index.get("awards", []),
    }
    out_path = Paths.evidence / "master_profile_export.json"
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(f"Exported master profile to {out_path}")


def _resolve_jd_text(jd_path_or_text: str) -> str:
    path = Path(jd_path_or_text)
    if path.exists() and path.is_file():
        return read_text(path)
    return jd_path_or_text


if __name__ == "__main__":
    cli()
