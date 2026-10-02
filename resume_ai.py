#!/usr/bin/env python3
"""ResumeAI CLI entry point.

    python resume_ai.py ingest
    python resume_ai.py analyze jobs/incoming/some-jd.pdf
    python resume_ai.py tailor jobs/incoming/some-jd.pdf --company Acme --role "Senior PM"
    python resume_ai.py list-evidence
    python resume_ai.py rebuild-index
    python resume_ai.py export
"""

from app.backend.cli import cli

if __name__ == "__main__":
    cli()
