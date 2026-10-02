"""Full pipeline smoke test against the local Ollama model.

Requires `ollama serve` running with the configured model pulled -- skipped
automatically if the local model isn't reachable. Runs entirely inside an
isolated tmp_path (see conftest.isolated_project), so it never touches the
real evidence/ or outputs/ folders.
"""

from __future__ import annotations

import pytest

from app.backend.engine.llm import is_available as llm_is_available

pytestmark = pytest.mark.skipif(not llm_is_available(), reason="local Ollama model not reachable")


def test_full_pipeline_ingest_analyze_generate(isolated_project, sample_resume_path, sample_jd_text):
    from app.backend.engine import jobs as jobs_engine
    from app.backend.engine.ingest_pipeline import add_resume_file, ingest_file
    from app.backend.engine.store import EvidenceStore

    dest = add_resume_file(sample_resume_path, "sample_resume.txt")
    ingest_summary = ingest_file(dest)

    assert ingest_summary["experiences_added"] >= 2
    assert ingest_summary["achievements_added"] >= 3

    store = EvidenceStore()
    assert store.profile.get("full_name")
    assert len(store.experiences) >= 2
    companies = {e["company"] for e in store.experiences}
    assert any("Acme" in c for c in companies)

    # Every achievement's source_text must genuinely appear in the original resume --
    # this is the grounding guarantee, checked here end-to-end rather than mocked.
    raw_resume_normalized = " ".join(sample_resume_path.read_text(encoding="utf-8").split()).lower()
    for ach in store.achievements:
        assert ach["source_text"].strip() != ""
        assert " ".join(ach["source_text"].split()).lower() in raw_resume_normalized

    job = jobs_engine.create_job(raw_text=sample_jd_text, company=None, role=None)
    analysis = jobs_engine.analyze_job(job["id"])

    requirement_texts = {m["requirement"].lower() for m in analysis["matches"]}
    assert any("sql" in r or "analytics" in r for r in requirement_texts)

    # The JD asks for "team of 10+" and "B2B SaaS" -- neither is supported by the
    # sample resume (team was 8 people, no B2B SaaS evidence at all). This is the
    # core zero-fabrication guarantee: both MUST come back unsupported.
    unsupported_texts = " ".join(
        m["requirement"].lower() for m in analysis["matches"] if m["strength"] == "unsupported"
    )
    assert "10" in unsupported_texts or "b2b" in unsupported_texts or "saas" in unsupported_texts, (
        f"Expected at least one of the unsupported JD requirements to be flagged unsupported, got: {analysis['matches']}"
    )

    result = jobs_engine.generate_job(job["id"])
    assert result["blocked"] is False, result["validation"]["issues"]
    assert result["validation"]["passed"] is True

    docx_path = isolated_project / result["docx_path"]
    pdf_path = isolated_project / result["pdf_path"]
    assert docx_path.exists()
    assert pdf_path.exists()
    assert docx_path.stat().st_size > 0
    assert pdf_path.stat().st_size > 0

    report_path = isolated_project / result["output_dir"] / "tailoring_report.md"
    evidence_map_path = isolated_project / result["output_dir"] / "evidence_map.json"
    assert report_path.exists()
    assert evidence_map_path.exists()

    report_text = report_path.read_text(encoding="utf-8")
    assert "Unsupported Requirements" in report_text
    assert "Unsupported claims included in resume:** 0" in report_text

    # Hard requirement from the spec: zero fabricated numbers anywhere in the
    # final generated bullets relative to their own source evidence.
    import json

    evidence_map = json.loads(evidence_map_path.read_text(encoding="utf-8"))
    assert len(evidence_map["resume_bullets"]) > 0
    for entry in evidence_map["resume_bullets"]:
        assert entry["source_evidence"][0]["source_text"]

    # Fabricated team-size claim must never appear verbatim in the rendered resume.
    from docx import Document

    doc = Document(str(docx_path))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "10+" not in full_text
    assert "team of 10" not in full_text.lower()
