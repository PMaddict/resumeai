"""Validator tests using hand-built evidence/content -- no LLM involved.

This is the last line of defense against fabrication, so it must catch a
bad bullet even if every earlier stage somehow let one through.
"""

from app.backend.engine.store import EvidenceStore
from app.backend.engine.validation import validate_resume
from app.backend.engine.writing import ResumeContent, WrittenBullet, WrittenExperience


def _store_with_one_role():
    store = EvidenceStore.__new__(EvidenceStore)
    store.profile = {"full_name": "Test Person", "emails": [], "phones": [], "links": [], "location": None, "summaries": []}
    store.experiences = [
        {"id": "exp_1", "company": "Acme", "role": "PM", "start_date": "2022", "end_date": None, "is_current": True, "location": None}
    ]
    store.achievements = [
        {
            "id": "ach_1",
            "claim": "Improved activation by 18% via onboarding experiments",
            "experience_id": "exp_1",
            "skills": ["experimentation"],
            "metrics": [{"value": "18%", "context": "activation", "source_text": "18%"}],
            "source_file": "resume.pdf",
        }
    ]
    store.skills = [{"name": "experimentation"}]
    store.projects = []
    store.index = {"education": [], "certifications": [], "awards": []}
    return store


def test_validation_passes_for_grounded_bullet():
    store = _store_with_one_role()
    content = ResumeContent(
        header={"full_name": "Test Person", "emails": [], "phones": [], "links": []},
        summary=None,
        experiences=[
            WrittenExperience(
                experience_id="exp_1",
                company="Acme",
                role="PM",
                dates_display="2022 - Present",
                location=None,
                bullets=[WrittenBullet(achievement_id="ach_1", text="Improved activation by 18% via onboarding experiments", was_rewritten=False, metrics=[])],
            )
        ],
        projects=[],
        skills=["experimentation"],
        education=[],
        certifications=[],
        awards=[],
    )
    report = validate_resume(content, store)
    assert report.passed, [i.message for i in report.errors]


def test_validation_blocks_fabricated_metric():
    store = _store_with_one_role()
    content = ResumeContent(
        header={"full_name": "Test Person", "emails": [], "phones": [], "links": []},
        summary=None,
        experiences=[
            WrittenExperience(
                experience_id="exp_1",
                company="Acme",
                role="PM",
                dates_display="2022 - Present",
                location=None,
                # 95% was never in the source evidence -- this must be blocked.
                bullets=[WrittenBullet(achievement_id="ach_1", text="Improved activation by 95% via onboarding experiments", was_rewritten=True, metrics=[])],
            )
        ],
        projects=[],
        skills=["experimentation"],
        education=[],
        certifications=[],
        awards=[],
    )
    report = validate_resume(content, store)
    assert not report.passed
    assert any("ungrounded" in i.message.lower() for i in report.errors)


def test_validation_blocks_unknown_skill():
    store = _store_with_one_role()
    content = ResumeContent(
        header={"full_name": "Test Person", "emails": [], "phones": [], "links": []},
        summary=None,
        experiences=[],
        projects=[],
        skills=["Quantum Computing"],  # never evidenced anywhere
        education=[],
        certifications=[],
        awards=[],
    )
    report = validate_resume(content, store)
    assert not report.passed
    assert any("not backed by any evidence" in i.message for i in report.errors)
