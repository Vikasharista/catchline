"""Parses .eml files into buyer-facing preview fields — used to render
both a sent RFQ email and an inbound supplier reply as an actual email in
the UI, instead of a bare filename."""
from email.message import EmailMessage

from app.channel.eml_preview import parse_eml_bytes


def test_parses_plain_text_email():
    msg = EmailMessage()
    msg["From"] = "vendor@example.com"
    msg["To"] = "buyer@example.com"
    msg["Subject"] = "RE: RFQ"
    msg["Date"] = "Mon, 01 Sep 2025 10:00:00 +0000"
    msg.set_content("Here's our quote: salmon HOG 3-4kg at 7.25 EUR/kg.")

    result = parse_eml_bytes(bytes(msg))
    assert result["from"] == "vendor@example.com"
    assert result["to"] == "buyer@example.com"
    assert result["subject"] == "RE: RFQ"
    assert "7.25 EUR/kg" in result["body"]
    assert result["attachments"] == []


def test_parses_attachments():
    msg = EmailMessage()
    msg["From"] = "buyer@nordcap.example"
    msg["To"] = "vendor@example.com"
    msg["Subject"] = "RFQ: Frozen seafood"
    msg.set_content("Please find attached.")
    msg.add_attachment(b"%PDF-fake", maintype="application", subtype="pdf", filename="RFQ.pdf")
    msg.add_attachment(b"fake-xlsx", maintype="application", subtype="vnd.ms-excel", filename="template.xlsx")

    result = parse_eml_bytes(bytes(msg))
    assert set(result["attachments"]) == {"RFQ.pdf", "template.xlsx"}
    assert "Please find attached" in result["body"]
