"""FastAPI app: the local web backend for ResumeAI.

Run via `python app.py` from the project root (see README.md), or directly
with `uvicorn app.backend.main:app`.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .engine import jobs as jobs_engine
from .engine.config import Paths, get_settings
from .engine.ingest_pipeline import add_resume_file, ingest_all, ingest_file, list_resume_files
from .engine.llm import is_available as llm_is_available
from .engine.readers import read_text
from .engine.store import EvidenceStore
from .engine.storage_jobs import JobsIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(Paths.logs / "resumeai.log"),
        logging.StreamHandler(),
    ],
)

Paths.ensure_all()

app = FastAPI(title="ResumeAI", description="Local-first resume tailoring engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Dashboard ------------------------------------------------------------


@app.get("/api/dashboard")
def dashboard():
    store = EvidenceStore()
    jobs_index = JobsIndex()
    outputs = _list_outputs()
    return {
        "llm_available": llm_is_available(),
        "source_resume_count": len(list_resume_files()),
        "evidence_stats": store.stats(),
        "recent_jobs": jobs_index.list_recent(5),
        "recent_outputs": outputs[:5],
    }


# -- Resume Vault -----------------------------------------------------------


@app.get("/api/resumes")
def list_resumes():
    ingested = EvidenceStore().index.get("ingested_files", {})
    files = [
        {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "ingested": path.name in ingested,
            "ingestion_summary": ingested.get(path.name),
        }
        for path in list_resume_files()
    ]
    return {"resumes": files}


@app.post("/api/resumes")
async def upload_resume(file: UploadFile = File(...), auto_ingest: bool = Form(True)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx", ".txt"):
        raise HTTPException(400, f"Unsupported file type: {suffix}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    dest = add_resume_file(tmp_path, file.filename)
    tmp_path.unlink(missing_ok=True)

    result = {"filename": dest.name}
    if auto_ingest:
        if not llm_is_available():
            raise HTTPException(
                503,
                "File saved to source_resumes/originals/, but the local model isn't reachable "
                "so it couldn't be ingested yet. Start Ollama and call /api/resumes/reingest.",
            )
        result["ingestion"] = ingest_file(dest)
    return result


@app.delete("/api/resumes/{filename}")
def delete_resume(filename: str):
    path = Paths.source_originals / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    path.unlink()
    return {"deleted": filename, "note": "Run POST /api/resumes/rebuild-index to remove its evidence from the database."}


@app.post("/api/resumes/reingest")
def reingest_resumes():
    if not llm_is_available():
        raise HTTPException(503, "Local model not reachable at the configured Ollama host.")
    return {"results": ingest_all()}


@app.post("/api/resumes/rebuild-index")
def rebuild_index():
    """Wipe the evidence database and re-extract everything from scratch."""
    if not llm_is_available():
        raise HTTPException(503, "Local model not reachable at the configured Ollama host.")
    for name in ["profile.json", "experience.json", "achievements.json", "skills.json", "projects.json", "evidence_index.json"]:
        p = Paths.evidence / name
        if p.exists():
            p.unlink()
    return {"results": ingest_all()}


# -- Evidence / Profile -----------------------------------------------------


@app.get("/api/evidence")
def get_evidence():
    store = EvidenceStore()
    return {
        "profile": store.profile,
        "experiences": store.experiences,
        "achievements": store.achievements,
        "projects": store.projects,
        "skills": store.skills,
        "education": store.index.get("education", []),
        "certifications": store.index.get("certifications", []),
        "awards": store.index.get("awards", []),
    }


@app.post("/api/evidence/manual")
def add_manual_evidence(payload: dict):
    kind = payload.get("kind")
    data = payload.get("data", {})
    if kind not in ("achievement", "skill", "project"):
        raise HTTPException(400, "kind must be one of: achievement, skill, project")
    store = EvidenceStore()
    record = store.add_user_evidence(kind=kind, data=data)
    return {"created": record}


# -- JD Tailoring ------------------------------------------------------------


@app.post("/api/jobs")
async def create_job(
    company: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    text = raw_text
    if file is not None:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in (".pdf", ".docx", ".txt"):
            raise HTTPException(400, f"Unsupported file type: {suffix}")
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        text = read_text(tmp_path)
        tmp_path.unlink(missing_ok=True)

    if not text or not text.strip():
        raise HTTPException(400, "Provide either raw_text or a file.")

    job = jobs_engine.create_job(raw_text=text, company=company, role=role)
    return job


@app.get("/api/jobs")
def list_jobs():
    return {"jobs": JobsIndex().list_recent(20)}


@app.post("/api/jobs/{job_id}/analyze")
def analyze_job(job_id: str):
    if not llm_is_available():
        raise HTTPException(503, "Local model not reachable at the configured Ollama host.")
    try:
        return jobs_engine.analyze_job(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found")


@app.post("/api/jobs/{job_id}/generate")
def generate_job(job_id: str):
    if not llm_is_available():
        raise HTTPException(503, "Local model not reachable at the configured Ollama host.")
    try:
        return jobs_engine.generate_job(job_id)
    except KeyError:
        raise HTTPException(404, "Job not found")


# -- Outputs ------------------------------------------------------------


def _list_outputs() -> list[dict]:
    results = []
    if not Paths.outputs.exists():
        return results
    for company_role_dir in sorted(Paths.outputs.iterdir(), reverse=True):
        if not company_role_dir.is_dir():
            continue
        for ts_dir in sorted(company_role_dir.iterdir(), reverse=True):
            if not ts_dir.is_dir():
                continue
            files = {f.name: str(f.relative_to(Paths.root)) for f in ts_dir.iterdir()}
            results.append({"name": f"{company_role_dir.name}/{ts_dir.name}", "files": files})
    return results


@app.get("/api/outputs")
def list_outputs():
    return {"outputs": _list_outputs()}


@app.get("/api/outputs/download")
def download_output(path: str):
    full_path = (Paths.root / path).resolve()
    if Paths.outputs.resolve() not in full_path.parents:
        raise HTTPException(400, "Invalid path")
    if not full_path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(full_path), filename=full_path.name)


# -- Serve built frontend (if present) --------------------------------------

_frontend_dist = Path(__file__).resolve().parent / "static"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
