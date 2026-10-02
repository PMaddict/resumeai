# ResumeAI

A local-first tool that tailors your resume to a specific job description —
using only facts from your actual resumes. Runs entirely on your laptop through
your browser at `http://localhost:8000`. No cloud, no accounts, no telemetry.

**Core rule: zero fabrication.** Every claim in a generated resume traces back to
your original resumes (or something you typed into the Profile page yourself). If
a job description asks for something you don't have evidence for, ResumeAI tells
you — it never makes it up. See `CLAUDE.md` for how this is enforced.

> **This is a run-it-yourself tool, not a hosted service.** Clone this repo and
> run it on your own machine. Your resumes, extracted evidence, and generated
> resumes never leave your laptop — there's no server to send them to, and this
> project intentionally has no multi-user/hosted mode. If you're looking at this
> on GitHub: fork or clone it, follow the setup below, and it's yours.

## One-time setup

### 1. Install Ollama (the local AI model — free, runs on your machine)

```bash
mkdir -p ~/.local/ollama ~/.local/bin
curl -sL -o /tmp/ollama.zip "https://github.com/ollama/ollama/releases/latest/download/ollama-darwin.tgz"
tar -xzf /tmp/ollama.zip -C ~/.local/ollama
ln -sf ~/.local/ollama/ollama ~/.local/bin/ollama
```

(If you're on Linux or already have Ollama installed via another method, skip
this and just make sure the `ollama` command works.)

Pull the model (one-time ~4.7GB download):

```bash
export PATH="$HOME/.local/bin:$PATH"
export OLLAMA_MODELS="$HOME/.local/ollama/models"
ollama pull llama3.1:8b
```

### 2. Set up the Python backend

```bash
cd ResumeAI
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Build the frontend

```bash
cd app/frontend
npm install
npm run build
cd ../..
```

## Running it

Every time you want to use ResumeAI, you need the local model running plus the
app server:

**Terminal 1 — the local model:**

```bash
export PATH="$HOME/.local/bin:$PATH"
export OLLAMA_MODELS="$HOME/.local/ollama/models"
ollama serve
```

**Terminal 2 — the app:**

```bash
cd ResumeAI
source .venv/bin/activate
python app.py
```

Then open **http://localhost:8000** in your browser.

If `ollama serve` is already running in the background (it stays running after
your first use), you only need Terminal 2 next time.

## Using it

1. **Resume Vault** — upload 3-5 of your existing resumes (PDF, DOCX, or TXT).
   They're copied into `source_resumes/originals/` (never modified) and
   automatically parsed into a structured evidence database under `evidence/`.
2. **Profile** — review everything that was extracted. Add anything missing
   (a project, a skill, an achievement) directly here — it's tagged as
   manually-added evidence and used just like resume-derived evidence.
3. **Tailor Resume** — paste or upload a job description. ResumeAI shows you
   which of your experiences it plans to emphasize and how each JD requirement
   matches your evidence (strong / partial / unsupported) *before* generating
   anything, so you stay in control. Click Generate to get a `.docx` and `.pdf`,
   plus a tailoring report explaining every decision.
4. **History** — every past generation, each in its own timestamped folder.
   Nothing is ever overwritten.

## CLI

```bash
source .venv/bin/activate
python resume_ai.py ingest                              # (re-)ingest all resumes in source_resumes/originals/
python resume_ai.py analyze jobs/incoming/some-jd.pdf    # preview matches without generating
python resume_ai.py tailor jobs/incoming/some-jd.pdf --company Acme --role "Senior PM"
python resume_ai.py list-evidence
python resume_ai.py rebuild-index                        # wipe + re-extract everything from scratch
python resume_ai.py export                               # dump a single consolidated evidence snapshot
```

## Tests

```bash
source .venv/bin/activate
pytest
```

Fast tests (grounding, validation, matching logic) always run. The full
end-to-end pipeline test (`test_end_to_end.py`) automatically skips itself if
Ollama isn't running, and never touches your real data — it runs entirely in a
temporary directory.

## Folder structure

```
source_resumes/originals/   your original resumes — never modified, ever
source_resumes/processed/   extracted raw text (for debugging what was read)
evidence/                   the normalized evidence database (JSON)
jobs/                       job descriptions you've submitted
outputs/<company-role>/<timestamp>/   every tailored resume you've generated
config/settings.json        model name, ports, resume length targets
logs/                       application logs
```

## Troubleshooting

- **"Local model not reachable"** — make sure `ollama serve` is running (Terminal
  1 above) and that you pulled the model (`ollama list` should show `llama3.1:8b`).
- **Upload says ingested but nothing shows in Profile** — check `logs/resumeai.log`
  for rejected extraction items; the grounding check may have rejected low-quality
  extractions from a poorly-formatted PDF. Try re-exporting the resume as a cleaner
  PDF or DOCX, or use `rebuild-index` after fixing the source file.
- **Port 8000 already in use** — change `server.port` in `config/settings.json`.

## License

MIT — see `LICENSE`. Use it, fork it, modify it for your own job search.
