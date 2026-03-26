import tempfile
import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    Table, TableStyle, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY


# ── colour palettes per format ────────────────────────────────────────────────

PALETTES = {
    "ats": {
        "primary": colors.black,
        "accent":  colors.black,
        "light":   colors.white,
        "line":    colors.black,
        "bg":      colors.white,
    },
    "modern": {
        "primary": colors.HexColor("#1a237e"),
        "accent":  colors.HexColor("#283593"),
        "light":   colors.HexColor("#e8eaf6"),
        "line":    colors.HexColor("#3949ab"),
        "bg":      colors.white,
    },
    "classic": {
        "primary": colors.HexColor("#1b1b1b"),
        "accent":  colors.HexColor("#333333"),
        "light":   colors.HexColor("#f5f5f5"),
        "line":    colors.HexColor("#555555"),
        "bg":      colors.white,
    },
    "creative": {
        "primary": colors.HexColor("#00695c"),
        "accent":  colors.HexColor("#00897b"),
        "light":   colors.HexColor("#e0f2f1"),
        "line":    colors.HexColor("#26a69a"),
        "bg":      colors.white,
    },
}


# ── style builders ────────────────────────────────────────────────────────────

def build_styles(palette, fmt):
    base = getSampleStyleSheet()

    font_name = "Helvetica" if fmt == "ats" else "Helvetica"
    font_bold = "Helvetica-Bold"

    styles = {
        "name": ParagraphStyle(
            "name",
            fontName=font_bold,
            fontSize=22 if fmt != "ats" else 18,
            textColor=palette["primary"],
            alignment=TA_CENTER if fmt != "ats" else TA_LEFT,
            spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "contact",
            fontName=font_name,
            fontSize=9,
            textColor=palette["accent"],
            alignment=TA_CENTER if fmt != "ats" else TA_LEFT,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "section",
            fontName=font_bold,
            fontSize=11,
            textColor=palette["primary"],
            spaceBefore=10,
            spaceAfter=3,
            alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "body",
            fontName=font_name,
            fontSize=9.5,
            textColor=colors.HexColor("#222222"),
            spaceAfter=3,
            leading=13,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName=font_name,
            fontSize=9.5,
            textColor=colors.HexColor("#222222"),
            spaceAfter=2,
            leading=13,
            leftIndent=12,
            bulletIndent=0,
        ),
        "job_title": ParagraphStyle(
            "job_title",
            fontName=font_bold,
            fontSize=10,
            textColor=palette["accent"],
            spaceAfter=1,
        ),
        "job_meta": ParagraphStyle(
            "job_meta",
            fontName=font_name,
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            spaceAfter=2,
            italics=True,
        ),
        "skills_chip": ParagraphStyle(
            "skills_chip",
            fontName=font_name,
            fontSize=9.5,
            textColor=colors.HexColor("#222222"),
            spaceAfter=2,
            leading=14,
        ),
    }
    return styles


# ── section helpers ───────────────────────────────────────────────────────────

def section_header(title, styles, palette, fmt):
    elems = []
    elems.append(Paragraph(title.upper(), styles["section"]))
    line_color = palette["line"]
    elems.append(HRFlowable(width="100%", thickness=1.2 if fmt != "ats" else 0.8,
                             color=line_color, spaceAfter=4))
    return elems


def contact_line(analysis):
    parts = []
    if analysis.get("candidate_email"):
        parts.append(analysis["candidate_email"])
    if analysis.get("candidate_phone"):
        parts.append(analysis["candidate_phone"])
    if analysis.get("candidate_location"):
        parts.append(analysis["candidate_location"])
    return "  |  ".join(parts)


# ── main generator ────────────────────────────────────────────────────────────

def generate_resume(analysis: dict, jd: str, fmt: str = "ats") -> str:
    palette = PALETTES.get(fmt, PALETTES["ats"])
    styles = build_styles(palette, fmt)

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    pdf_path = tmp.name

    margin = 0.65 * inch
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    name = analysis.get("candidate_name", "Your Name")
    story.append(Paragraph(name, styles["name"]))

    contact = contact_line(analysis)
    if contact:
        story.append(Paragraph(contact, styles["contact"]))

    if fmt != "ats":
        story.append(HRFlowable(width="100%", thickness=2, color=palette["primary"], spaceAfter=6))

    story.append(Spacer(1, 4))

    # ── Professional Summary ──────────────────────────────────────────────────
    summary = analysis.get("improved_summary", "")
    if summary:
        story += section_header("Professional Summary", styles, palette, fmt)
        story.append(Paragraph(summary, styles["body"]))
        story.append(Spacer(1, 4))

    # ── Skills ────────────────────────────────────────────────────────────────
    skills = analysis.get("skills", [])
    missing = analysis.get("missing_keywords", [])
    all_skills = list(dict.fromkeys(skills + missing))  # deduplicate, add missing keywords

    if all_skills:
        story += section_header("Skills", styles, palette, fmt)
        if fmt == "ats":
            story.append(Paragraph(" | ".join(all_skills), styles["skills_chip"]))
        else:
            # 3-column table for visual formats
            chunk = [all_skills[i:i+3] for i in range(0, len(all_skills), 3)]
            rows = []
            for row in chunk:
                rows.append([Paragraph(f"• {s}", styles["bullet"]) for s in row] +
                             [Paragraph("", styles["bullet"])] * (3 - len(row)))
            t = Table(rows, colWidths=["33%", "33%", "34%"])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                   ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                   ("TOPPADDING", (0, 0), (-1, -1), 1),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
            story.append(t)
        story.append(Spacer(1, 4))

    # ── Experience ────────────────────────────────────────────────────────────
    experience = analysis.get("experience", [])
    if experience:
        story += section_header("Work Experience", styles, palette, fmt)
        for exp in experience:
            block = []
            title_line = exp.get("title", "")
            company = exp.get("company", "")
            duration = exp.get("duration", "")

            if fmt == "ats":
                block.append(Paragraph(f"<b>{title_line}</b> — {company}", styles["job_title"]))
                block.append(Paragraph(duration, styles["job_meta"]))
            else:
                # Two-column: title/company left, duration right
                tbl = Table(
                    [[Paragraph(f"<b>{title_line}</b>", styles["job_title"]),
                      Paragraph(duration, ParagraphStyle("r", fontName="Helvetica",
                                                          fontSize=9, alignment=TA_RIGHT,
                                                          textColor=colors.HexColor("#555555")))]],
                    colWidths=["75%", "25%"]
                )
                tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                          ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                          ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                          ("TOPPADDING", (0, 0), (-1, -1), 0),
                                          ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
                block.append(tbl)
                block.append(Paragraph(company, styles["job_meta"]))

            for bullet in exp.get("bullets", []):
                block.append(Paragraph(f"• {bullet}", styles["bullet"]))
            block.append(Spacer(1, 6))
            story.append(KeepTogether(block))

    # ── Education ─────────────────────────────────────────────────────────────
    education = analysis.get("education", [])
    if education:
        story += section_header("Education", styles, palette, fmt)
        for edu in education:
            degree = edu.get("degree", "")
            institution = edu.get("institution", "")
            year = edu.get("year", "")
            story.append(Paragraph(f"<b>{degree}</b>", styles["job_title"]))
            story.append(Paragraph(f"{institution}  {year}", styles["job_meta"]))
            story.append(Spacer(1, 4))

    # ── Certifications ────────────────────────────────────────────────────────
    certs = analysis.get("certifications", [])
    if certs and certs[0]:
        story += section_header("Certifications", styles, palette, fmt)
        for cert in certs:
            story.append(Paragraph(f"• {cert}", styles["bullet"]))
        story.append(Spacer(1, 4))

    doc.build(story)
    return pdf_path