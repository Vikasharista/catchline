"""Stubbed inbound channel (PRD §7.3): simulate copies the 5 seed replies
(and certificates) into data/inbox/, one by one; upload accepts a buyer's
own file. Each file is linked to a supplier by sender email or filename;
if neither matches, the caller (API layer) asks the buyer to pick one.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from app.config import settings

SEED_REPLIES = settings.data_dir / "seed" / "aerchain_fish_rfx_dataset" / "02_supplier_replies"
SEED_CERTS = settings.data_dir / "seed" / "aerchain_fish_rfx_dataset" / "03_attachments"

# filename prefix -> supplier name, so "S1_..." links to Fjordline etc.
SUPPLIER_PREFIX_MAP = {
    "S1": "Fjordline Seafood AS",
    "S2": "Pacific Rim Seafoods Ltd",
    "S3": "Atlantico Pesca S.L.",
    "S4": "Oceanis Trading SARL",
    "S5": "Baltic Blue Foods Sp. z o.o.",
}


def guess_supplier(filename: str) -> str | None:
    prefix = filename.split("_", 1)[0]
    return SUPPLIER_PREFIX_MAP.get(prefix)


def list_seed_files() -> list[Path]:
    return sorted(SEED_REPLIES.iterdir()) + sorted(SEED_CERTS.iterdir())


def copy_to_inbox(path: Path) -> Path:
    inbox_dir = settings.data_dir / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    dest = inbox_dir / path.name
    shutil.copy(path, dest)
    return dest


def save_upload(filename: str, content: bytes) -> Path:
    inbox_dir = settings.data_dir / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    dest = inbox_dir / filename
    dest.write_bytes(content)
    return dest
