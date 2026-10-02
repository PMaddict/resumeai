"""Persists job (JD) metadata to jobs/jobs_index.json."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import Paths
from .schema import new_id


def _index_path():
    return Paths.root / "jobs" / "jobs_index.json"


class JobsIndex:
    def __init__(self) -> None:
        index_path = _index_path()
        if index_path.exists():
            with open(index_path, encoding="utf-8") as f:
                self.jobs: dict = json.load(f)
        else:
            self.jobs = {}

    def _save(self) -> None:
        index_path = _index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.jobs, f, indent=2, ensure_ascii=False)

    def create(self, *, raw_text: str, company: str | None, role: str | None) -> dict:
        job_id = new_id("job")
        job = {
            "id": job_id,
            "raw_text": raw_text,
            "company": company,
            "role": role,
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.jobs[job_id] = job
        self._save()
        return job

    def get(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def update(self, job_id: str, **fields) -> dict:
        job = self.jobs[job_id]
        job.update(fields)
        self._save()
        return job

    def list_recent(self, limit: int = 20) -> list[dict]:
        return sorted(self.jobs.values(), key=lambda j: j["created_at"], reverse=True)[:limit]
