"""list_resume_files must ignore dotfiles like .gitkeep.

Unlike a shell glob, pathlib's Path.glob("*") matches leading-dot filenames
too -- so a naive glob("*") over source_resumes/originals/ would show the
.gitkeep placeholder as if it were an uploaded resume.
"""

from app.backend.engine.ingest_pipeline import list_resume_files


def test_gitkeep_and_hidden_files_are_excluded(isolated_project):
    originals = isolated_project / "source_resumes" / "originals"
    (originals / ".gitkeep").touch()
    (originals / ".DS_Store").touch()
    (originals / "real_resume.txt").write_text("hello", encoding="utf-8")

    files = list_resume_files()

    assert [f.name for f in files] == ["real_resume.txt"]


def test_non_resume_extensions_are_excluded(isolated_project):
    originals = isolated_project / "source_resumes" / "originals"
    (originals / "notes.md").write_text("not a resume", encoding="utf-8")
    (originals / "resume.pdf").write_text("fake pdf bytes", encoding="utf-8")

    files = list_resume_files()

    assert [f.name for f in files] == ["resume.pdf"]
