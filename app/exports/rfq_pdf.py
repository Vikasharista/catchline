"""Builds the RFQ PDF sent to suppliers, from the signed-off draft (PRD §7.2
pre-send preview, §7.10 exports). Pure formatting — every value comes
straight from the draft.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_rfq_pdf(draft: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = []

    scope = draft.get("scope", {})
    story.append(Paragraph(scope.get("title") or "Request for Quotation", styles["Title"]))
    story.append(Spacer(1, 6))
    meta = (
        f"Delivery: {scope.get('incoterm', '')} {scope.get('incoterm_place', '')}<br/>"
        f"Price basis: {scope.get('currency', '')} per kg {scope.get('weight_basis', '')} weight<br/>"
        f"Response deadline: {scope.get('response_deadline', '')}<br/>"
        f"Award decision by: {scope.get('award_date', '')}<br/>"
        f"Contract period: {scope.get('contract_start', '')} - {scope.get('contract_end', '')}"
    )
    story.append(Paragraph(meta, styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Line items", styles["Heading2"]))
    line_rows = [["Line", "Species", "Form", "Grade", "Vol (kg)"]]
    for line in draft.get("lines", []):
        line_rows.append(
            [line["line_id"], line["species"], line["form"], line["grade"], f"{line['annual_volume_kg']:,.0f}"]
        )
    table = Table(line_rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#141414")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6E3E0")),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    if draft.get("questionnaire"):
        story.append(Paragraph("Supplier questionnaire", styles["Heading2"]))
        for q in draft["questionnaire"]:
            story.append(Paragraph(f"{q['q_id']}: {q['text']}", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
