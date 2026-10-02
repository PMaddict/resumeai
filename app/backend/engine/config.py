"""Loads config/settings.json and resolves project paths.

All paths are resolved relative to the ResumeAI project root (three levels
up from this file: app/backend/engine/config.py -> ResumeAI/).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.json"


@lru_cache
def get_settings() -> dict:
    with open(SETTINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


class Paths:
    root = PROJECT_ROOT
    source_originals = PROJECT_ROOT / "source_resumes" / "originals"
    source_processed = PROJECT_ROOT / "source_resumes" / "processed"
    evidence = PROJECT_ROOT / "evidence"
    jobs_incoming = PROJECT_ROOT / "jobs" / "incoming"
    jobs_processed = PROJECT_ROOT / "jobs" / "processed"
    outputs = PROJECT_ROOT / "outputs"
    templates = PROJECT_ROOT / "templates"
    logs = PROJECT_ROOT / "logs"

    @classmethod
    def ensure_all(cls) -> None:
        for p in [
            cls.source_originals,
            cls.source_processed,
            cls.evidence,
            cls.jobs_incoming,
            cls.jobs_processed,
            cls.outputs,
            cls.templates,
            cls.logs,
        ]:
            p.mkdir(parents=True, exist_ok=True)
