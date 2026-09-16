"""Award memo (PRD §7.10). The LLM writes narrative text from tool results
only (app/analyst/agent.py produces that text); this module lays it out as a
PDF alongside the actual numbers, which come straight from the award table —
never re-derived or restated by the model.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

MEMO_SYSTEM_PROMPT = """You write a one-page award recommendation memo for a VP of
Procurement, using only the tool results you're given — total spend, the award
table, last-year comparison, risks and assumptions. Do not invent or restate
numbers differently than given. Plain, direct language. Structure: a short
recommendation paragraph, then bullet risks, then a closing line on next steps.
"""


def build_memo_pdf(
    recommendation_text: str,
    total_spend_eur: float,
    award_table: list[dict],
    risks: list[str],
    assumptions: dict,
    n_logged_decisions: int,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("Award recommendation", styles["Title"]), Spacer(1, 8)]

    story.append(Paragraph(recommendation_text.replace("\n", "<br/>"), styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"Total spend: EUR {total_spend_eur:,.0f}", styles["Heading3"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Award by line", styles["Heading2"]))
    rows = [["Line", "Supplier", "EUR/kg net DAP"]] + [
        [r["line_id"], r["supplier_id"], f"{r['eur_kg_net_dap']:.2f}"] for r in award_table
    ]
    table = Table(rows, repeatRows=1)
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
    story.append(Spacer(1, 10))

    if risks:
        story.append(Paragraph("Risks", styles["Heading2"]))
        for r in risks:
            story.append(Paragraph(f"• {r}", styles["Normal"]))
        story.append(Spacer(1, 10))

    story.append(Paragraph("Assumptions", styles["Heading2"]))
    for k, v in assumptions.items():
        story.append(Paragraph(f"{k}: {v}", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"{n_logged_decisions} decisions logged in the audit trail.", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
