"""Parses a .eml file into buyer-facing preview fields (From/To/Subject/
body/attachment names) — used to render both outbound messages
(data/outbox, written by app.channel.outbox on Send) and inbound supplier
replies that arrive as .eml as an actual email, instead of a bare
filename in a list. Nothing here is invented: every field comes straight
out of the real .eml bytes on disk.
"""
from __future__ import annotations

from email import message_from_bytes
from email.message import Message
from pathlib import Path
from typing import Any


def _get_body_text(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload is not None:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True)
    if payload is not None:
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return str(msg.get_payload())


def parse_eml_bytes(raw: bytes) -> dict[str, Any]:
    msg = message_from_bytes(raw)
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            filename = part.get_filename()
            if filename:
                attachments.append(filename)
    return {
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "body": _get_body_text(msg).strip(),
        "attachments": attachments,
    }


def parse_eml_file(path: Path) -> dict[str, Any]:
    return parse_eml_bytes(path.read_bytes())
