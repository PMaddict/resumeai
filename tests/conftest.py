"""Shared pytest fixtures.

`isolated_project` redirects every path the engine writes to into a pytest
tmp_path, so tests never touch the real evidence/ or outputs/ folders --
synthetic test data (fake names, fake resumes) must never leak into your
actual evidence database.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    from app.backend.engine import config, storage_jobs

    for name in [
        "source_resumes/originals",
        "source_resumes/processed",
        "evidence",
        "jobs/incoming",
        "jobs/processed",
        "outputs",
        "templates",
        "config",
        "logs",
    ]:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)

    shutil.copyfile(REAL_PROJECT_ROOT / "config" / "settings.json", tmp_path / "config" / "settings.json")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "config" / "settings.json")
    config.get_settings.cache_clear()

    monkeypatch.setattr(config.Paths, "root", tmp_path)
    monkeypatch.setattr(config.Paths, "source_originals", tmp_path / "source_resumes" / "originals")
    monkeypatch.setattr(config.Paths, "source_processed", tmp_path / "source_resumes" / "processed")
    monkeypatch.setattr(config.Paths, "evidence", tmp_path / "evidence")
    monkeypatch.setattr(config.Paths, "jobs_incoming", tmp_path / "jobs" / "incoming")
    monkeypatch.setattr(config.Paths, "jobs_processed", tmp_path / "jobs" / "processed")
    monkeypatch.setattr(config.Paths, "outputs", tmp_path / "outputs")
    monkeypatch.setattr(config.Paths, "templates", tmp_path / "templates")
    monkeypatch.setattr(config.Paths, "logs", tmp_path / "logs")

    yield tmp_path

    config.get_settings.cache_clear()


@pytest.fixture
def sample_resume_path() -> Path:
    return FIXTURES_DIR / "sample_resume.txt"


@pytest.fixture
def sample_jd_text() -> str:
    return (FIXTURES_DIR / "sample_jd.txt").read_text(encoding="utf-8")
