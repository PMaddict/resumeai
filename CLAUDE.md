# ResumeAI

A local-first resume tailoring engine. No cloud backend, no accounts, no telemetry.
Everything — your resumes, extracted evidence, generated resumes — lives on this
machine as plain files. The "AI" is a local Ollama model (`llama3.1:8b` by default);
no data ever leaves the machine.

## Core principle: zero fabrication

This is the most important constraint in the whole codebase. The system must never
put a claim into a generated resume that isn't traceable back to your original
resumes (or something you explicitly typed into the Profile page). If a JD asks for
something you have no evidence for, the system reports it as a gap — it never
invents evidence.

This is enforced at two points, not just one:
1. **Extraction** (`app/backend/engine/extraction.py` + `grounding.py`): every
   extracted fact must carry a verbatim `source_text` snippet, and that snippet is
   checked against the actual resume text before being trusted. Anything that
   doesn't match (exact or close-fuzzy) is dropped and logged, not corrected.
2. **Generation** (`app/backend/engine/writing.py` + `validation.py`): every
   rewritten bullet is checked token-by-token against its own source evidence. Any
   new number, percentage, or proper noun that wasn't in the original is rejected
   and the bullet falls back to the original wording verbatim. `validation.py` then
   re-checks the *finished* resume from scratch, independently, before any file is
   written — if it finds an error, generation is blocked rather than shipping a
   bad file.

When you touch either of these files, preserve that two-layer structure. Don't
"simplify" by trusting the LLM's own self-report of compliance — always re-verify
in plain Python against the evidence text.

## Architecture

```
app/backend/engine/    the actual pipeline, framework-agnostic
  config.py            settings.json + Paths (all project paths resolve from here)
  llm.py               thin Ollama client (generate_json)
  schema.py            evidence dataclasses (Experience, Achievement, etc.)
  readers.py           PDF/DOCX/TXT -> plain text
  grounding.py         the anti-fabrication substring/fuzzy-match checker
  extraction.py        resume text -> evidence candidates (LLM + grounding gate)
  store.py             evidence/*.json read/write + merge logic (dedupe across resumes)
  ingest_pipeline.py   orchestrates: read file -> extract -> merge into store
  jd_parser.py         JD text -> structured requirements (must/nice-to-have)
  matching.py          JD requirements <-> evidence, with a keyword safety net
                        that can upgrade a wrong "unsupported" to "partial" but
                        can NEVER upgrade anything to "strong" (see comments)
  planning.py          pure selection/ranking logic, no LLM -- this is what
                        powers the "here's what I'll emphasize" preview
  writing.py           bullet rewriting (LLM) + grounding enforcement
  validation.py        the final independent gate before any file is written
  docx_writer.py       ResumeContent -> .docx (python-docx, no tables/images)
  pdf_writer.py        ResumeContent -> .pdf (reportlab, independent of docx_writer
                        so there's no dependency on LibreOffice being installed)
  report.py            tailoring_report.md + evidence_map.json
  jobs.py              job (JD) lifecycle: create -> analyze -> generate
  storage_jobs.py       jobs/jobs_index.json persistence

app/backend/main.py    FastAPI app (serves /api/* and the built frontend)
app/backend/cli.py     CLI (resume_ai.py ingest / analyze / tailor / ...)
app/frontend/          React + Vite UI, builds into app/backend/static/
```

Data flows one way: `source_resumes/` -> `evidence/` -> (`jobs/` + evidence) ->
`outputs/`. Original resumes in `source_resumes/originals/` are never modified.
Each generation writes to a new timestamped folder under `outputs/<company-role>/`
— nothing is ever overwritten.

## Local model

Ollama binary + model files are **not** part of this project directory (they live
under `~/.local/ollama/`). Before anything that touches the model will work:

```bash
export PATH="$HOME/.local/bin:$PATH"
export OLLAMA_MODELS="$HOME/.local/ollama/models"
ollama serve
```

`app/backend/engine/llm.is_available()` is checked before any ingest/analyze/
generate operation; the API returns a 503 with a clear message if the model isn't
reachable rather than failing silently or falling back to fabricated content.

## Running things

See README.md for the exact commands. In short: `python app.py` runs the whole
app (API + built frontend) on one port; `python resume_ai.py <command>` is the
CLI; `pytest` runs the test suite (fast tests run always, `test_end_to_end.py` is
skipped automatically if Ollama isn't running).

## When extending this

- New extraction fields: update `extraction.SCHEMA_DESCRIPTION`, the parsing loop
  in `extraction.extract_from_text`, the dataclass in `schema.py`, and the merge
  logic in `store.py`. Don't skip the grounding check for new fields.
- New resume sections: thread them through `planning.ResumePlan` ->
  `writing.ResumeContent` -> both `docx_writer.py` and `pdf_writer.py` (keep them
  in sync -- they're independent renderers of the same content model).
- Keep `jd_parser.py`/`matching.py` prompts explicit about "don't invent" —
  small local models need that reinforced more than hosted frontier models do.
