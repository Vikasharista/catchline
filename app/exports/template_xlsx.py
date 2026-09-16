"""Builds the response template xlsx suppliers fill in (PRD §7.2 pre-send
preview, §7.10 exports).
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Font


def build_template_xlsx(draft: dict) -> bytes:
    wb = Workbook()

    lines_ws = wb.active
    lines_ws.title = "Quote"
    header = ["Line", "Species", "Form", "Grade", "Volume (kg)", "Your price", "Unit", "Currency", "Incoterm", "Notes"]
    lines_ws.append(header)
    for cell in lines_ws[1]:
        cell.font = Font(bold=True)
    for line in draft.get("lines", []):
        lines_ws.append(
            [line["line_id"], line["species"], line["form"], line["grade"], line["annual_volume_kg"], None, None, None, None, None]
        )

    qa_ws = wb.create_sheet("Questionnaire")
    qa_ws.append(["Question ID", "Group", "Question", "Your answer"])
    for cell in qa_ws[1]:
        cell.font = Font(bold=True)
    for q in draft.get("questionnaire", []):
        qa_ws.append([q["q_id"], q["group"], q["text"], None])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
