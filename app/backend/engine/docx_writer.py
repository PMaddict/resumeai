"""Render a ResumeContent into a clean, ATS-friendly .docx.

No tables, no text boxes, no images -- just paragraphs and runs, so ATS
parsers read the content in a sane linear order. Formatting is restrained
(single font family, black text, minimal rules) and identical between runs;
only the content changes.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from .writing import ResumeContent

FONT_NAME = "Calibri"
HEADING_COLOR = RGBColor(0x1A, 0x1A, 0x1A)
BODY_COLOR = RGBColor(0x2A, 0x2A, 0x2A)
MUTED_COLOR = RGBColor(0x55, 0x55, 0x55)


def _set_doc_defaults(doc: Document) -> None:
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = Pt(10.5)
    style.font.color.rgb = BODY_COLOR
    for section in doc.sections:
        section.top_margin = Pt(36)
        section.bottom_margin = Pt(36)
        section.left_margin = Pt(50)
        section.right_margin = Pt(50)


def _heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text.upper())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = HEADING_COLOR
    border_p = doc.add_paragraph()
    border_p.paragraph_format.space_before = Pt(0)
    border_p.paragraph_format.space_after = Pt(4)
    pPr = border_p._p.get_or_add_pPr()
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "999999")
    pBdr.append(bottom)
    pPr.append(pBdr)


def render_docx(content: ResumeContent, output_path: Path) -> Path:
    doc = Document()
    _set_doc_defaults(doc)

    # Header
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = name_p.add_run(content.header.get("full_name") or "")
    run.bold = True
    run.font.size = Pt(18)
    run.font.color.rgb = HEADING_COLOR

    contact_bits = []
    contact_bits.extend(content.header.get("emails", []))
    contact_bits.extend(content.header.get("phones", []))
    if content.header.get("location"):
        contact_bits.append(content.header["location"])
    contact_bits.extend(content.header.get("links", []))
    if contact_bits:
        contact_p = doc.add_paragraph()
        contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_p.paragraph_format.space_after = Pt(6)
        run = contact_p.add_run(" | ".join(contact_bits))
        run.font.size = Pt(9.5)
        run.font.color.rgb = MUTED_COLOR

    if content.summary:
        _heading(doc, "Summary")
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.add_run(content.summary)

    if content.experiences:
        _heading(doc, "Experience")
        for exp in content.experiences:
            header_p = doc.add_paragraph()
            header_p.paragraph_format.space_before = Pt(6)
            header_p.paragraph_format.space_after = Pt(1)
            run = header_p.add_run(f"{exp.role} — {exp.company}")
            run.bold = True
            run.font.size = Pt(10.5)

            meta_bits = [b for b in [exp.dates_display, exp.location] if b]
            if meta_bits:
                meta_p = doc.add_paragraph()
                meta_p.paragraph_format.space_after = Pt(3)
                run = meta_p.add_run(" | ".join(meta_bits))
                run.italic = True
                run.font.size = Pt(9.5)
                run.font.color.rgb = MUTED_COLOR

            for bullet in exp.bullets:
                bp = doc.add_paragraph(style="List Bullet")
                bp.paragraph_format.space_after = Pt(2)
                bp.add_run(bullet.text)

    if content.projects:
        _heading(doc, "Key Projects")
        for proj in content.projects:
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(f"{proj.name}: ")
            run.bold = True
            p.add_run(proj.description)

    if content.skills:
        _heading(doc, "Skills")
        p = doc.add_paragraph()
        p.add_run(", ".join(content.skills))

    if content.education:
        _heading(doc, "Education")
        for edu in content.education:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            degree_field = edu.get("degree", "")
            if edu.get("field_of_study"):
                degree_field += f", {edu['field_of_study']}"
            dates = " - ".join([d for d in [edu.get("start_date"), edu.get("end_date")] if d])
            line = f"{degree_field} — {edu.get('institution', '')}"
            if dates:
                line += f" ({dates})"
            p.add_run(line)

    if content.certifications:
        _heading(doc, "Certifications")
        for cert in content.certifications:
            p = doc.add_paragraph(style="List Bullet")
            line = cert.get("name", "")
            if cert.get("issuer"):
                line += f" — {cert['issuer']}"
            if cert.get("date"):
                line += f" ({cert['date']})"
            p.add_run(line)

    if content.awards:
        _heading(doc, "Awards")
        for award in content.awards:
            p = doc.add_paragraph(style="List Bullet")
            line = award.get("name", "")
            if award.get("issuer"):
                line += f" — {award['issuer']}"
            if award.get("date"):
                line += f" ({award['date']})"
            p.add_run(line)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path
