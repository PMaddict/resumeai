"""Orchestrates: read file -> extract -> merge into evidence store."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .config import Paths
from .extraction import extract_from_text
from .readers import read_text
from .store import EvidenceStore

logger = logging.getLogger("resumeai.ingest")

RESUME_EXTENSIONS = (".pdf", ".docx", ".txt")


def list_resume_files() -> list[Path]:
    """Every real resume file in source_resumes/originals/ -- excludes
    dotfiles like .gitkeep, which `Path.glob("*")` would otherwise include
    (unlike shell globs, pathlib's "*" does match leading-dot filenames).
    """
    if not Paths.source_originals.exists():
        return []
    return sorted(
        p for p in Paths.source_originals.iterdir() if p.is_file() and p.suffix.lower() in RESUME_EXTENSIONS
    )


def ingest_file(source_path: Path, store: EvidenceStore | None = None) -> dict:
    """Ingest a single resume file (already sitting in source_resumes/originals/).

    Never modifies the original. Writes extracted raw text to
    source_resumes/processed/<name>.txt for inspection/debugging.
    """
    store = store or EvidenceStore()
    raw_text = read_text(source_path)

    Paths.source_processed.mkdir(parents=True, exist_ok=True)
    processed_path = Paths.source_processed / f"{source_path.stem}.txt"
    processed_path.write_text(raw_text, encoding="utf-8")

    result = extract_from_text(raw_text, source_file=source_path.name)
    summary = store.ingest_extraction(result, source_file=source_path.name)
    logger.info("Ingested %s: %s", source_path.name, summary)
    return summary


def add_resume_file(uploaded_path: Path, original_filename: str) -> Path:
    """Copy an uploaded file into source_resumes/originals/ (never overwritten)."""
    Paths.source_originals.mkdir(parents=True, exist_ok=True)
    dest = Paths.source_originals / original_filename
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        counter = 2
        while dest.exists():
            dest = Paths.source_originals / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.copyfile(uploaded_path, dest)
    return dest


def ingest_all(store: EvidenceStore | None = None) -> list[dict]:
    store = store or EvidenceStore()
    results = []
    for path in list_resume_files():
        results.append(ingest_file(path, store=store))
    return results
