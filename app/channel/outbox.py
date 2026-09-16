"""Stubbed outbound channel (PRD §7.3): writes .eml files instead of sending
real email.
"""
from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from app.config import settings

BUYER_EMAIL = "sourcing@nordcap.example"


def write_eml(to_email: str, subject: str, body: str, attachments: list[tuple[str, bytes, str]] | None = None) -> Path:
    """attachments: list of (filename, content_bytes, mime_subtype)."""
    msg = EmailMessage()
    msg["From"] = BUYER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    for filename, content, subtype in attachments or []:
        maintype = "application" if subtype not in ("plain",) else "text"
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)

    outbox_dir = settings.data_dir / "outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    safe_name = to_email.replace("@", "_at_").replace(".", "_")
    path = outbox_dir / f"{safe_name}_{subject[:40].strip().replace(' ', '_')}.eml"
    path.write_bytes(bytes(msg))
    return path


def send_rfx_to_suppliers(suppliers: list[dict], rfq_pdf_bytes: bytes, template_xlsx_bytes: bytes, rfx_title: str) -> list[Path]:
    paths = []
    for supplier in suppliers:
        if not supplier.get("email"):
            continue
        path = write_eml(
            to_email=supplier["email"],
            subject=f"RFQ: {rfx_title}",
            body=f"Dear {supplier['name']},\n\nPlease find attached our request for quotation.\n\nBest regards,\nNordcap Sourcing",
            attachments=[
                ("RFQ.pdf", rfq_pdf_bytes, "pdf"),
                ("response_template.xlsx", template_xlsx_bytes, "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ],
        )
        paths.append(path)
    return paths
