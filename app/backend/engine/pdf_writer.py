"""Render a ResumeContent into PDF directly (no DOCX->PDF conversion dependency).

Mirrors the DOCX layout closely using reportlab so both exports look and
read the same way.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from .writing import ResumeContent

HEADING_COLOR = colors.HexColor("#1A1A1A")
BODY_COLOR = colors.HexColor("#2A2A2A")
MUTED_COLOR = colors.HexColor("#555555")

NAME_STYLE = ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=18, textColor=HEADING_COLOR, alignment=1, spaceAfter=2)
CONTACT_STYLE = ParagraphStyle("Contact", fontName="Helvetica", fontSize=9.5, textColor=MUTED_COLOR, alignment=1, spaceAfter=8)
SECTION_STYLE = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=11, textColor=HEADING_COLOR, spaceBefore=10, spaceAfter=3)
ROLE_STYLE = ParagraphStyle("Role", fontName="Helvetica-Bold", fontSize=10.5, textColor=BODY_COLOR, spaceAfter=1)
META_STYLE = ParagraphStyle("Meta", fontName="Helvetica-Oblique", fontSize=9.5, textColor=MUTED_COLOR, spaceAfter=3)
BODY_STYLE = ParagraphStyle("Body", fontName="Helvetica", fontSize=10, textColor=BODY_COLOR, spaceAfter=4, leading=13)
BULLET_STYLE = ParagraphStyle("Bullet", fontName="Helvetica", fontSize=10, textColor=BODY_COLOR, leading=13)


def _section_heading(flow: list, text: str) -> None:
    flow.append(Paragraph(text.upper(), SECTION_STYLE))
    flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#999999"), spaceAfter=4))


def render_pdf(content: ResumeContent, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=LETTER,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        title=content.header.get("full_name") or "Resume",
    )

    flow: list = []

    flow.append(Paragraph(content.header.get("full_name") or "", NAME_STYLE))

    contact_bits = []
    contact_bits.extend(content.header.get("emails", []))
    contact_bits.extend(content.header.get("phones", []))
    if content.header.get("location"):
        contact_bits.append(content.header["location"])
    contact_bits.extend(content.header.get("links", []))
    if contact_bits:
        flow.append(Paragraph(" | ".join(contact_bits), CONTACT_STYLE))

    if content.summary:
        _section_heading(flow, "Summary")
        flow.append(Paragraph(content.summary, BODY_STYLE))

    if content.experiences:
        _section_heading(flow, "Experience")
        for exp in content.experiences:
            flow.append(Paragraph(f"{exp.role} — {exp.company}", ROLE_STYLE))
            meta_bits = [b for b in [exp.dates_display, exp.location] if b]
            if meta_bits:
                flow.append(Paragraph(" | ".join(meta_bits), META_STYLE))
            if exp.bullets:
                items = [ListItem(Paragraph(b.text, BULLET_STYLE), spaceAfter=2) for b in exp.bullets]
                flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))
            flow.append(Spacer(1, 4))

    if content.projects:
        _section_heading(flow, "Key Projects")
        items = [
            ListItem(Paragraph(f"<b>{p.name}:</b> {p.description}", BULLET_STYLE), spaceAfter=2)
            for p in content.projects
        ]
        flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))

    if content.skills:
        _section_heading(flow, "Skills")
        flow.append(Paragraph(", ".join(content.skills), BODY_STYLE))

    if content.education:
        _section_heading(flow, "Education")
        for edu in content.education:
            degree_field = edu.get("degree", "")
            if edu.get("field_of_study"):
                degree_field += f", {edu['field_of_study']}"
            dates = " - ".join([d for d in [edu.get("start_date"), edu.get("end_date")] if d])
            line = f"{degree_field} — {edu.get('institution', '')}"
            if dates:
                line += f" ({dates})"
            flow.append(Paragraph(line, BODY_STYLE))

    if content.certifications:
        _section_heading(flow, "Certifications")
        items = []
        for cert in content.certifications:
            line = cert.get("name", "")
            if cert.get("issuer"):
                line += f" — {cert['issuer']}"
            if cert.get("date"):
                line += f" ({cert['date']})"
            items.append(ListItem(Paragraph(line, BULLET_STYLE), spaceAfter=2))
        flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))

    if content.awards:
        _section_heading(flow, "Awards")
        items = []
        for award in content.awards:
            line = award.get("name", "")
            if award.get("issuer"):
                line += f" — {award['issuer']}"
            if award.get("date"):
                line += f" ({award['date']})"
            items.append(ListItem(Paragraph(line, BULLET_STYLE), spaceAfter=2))
        flow.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14))

    doc.build(flow)
    return output_path
