from __future__ import annotations

from pydantic import BaseModel


class CertificateExtraction(BaseModel):
    scheme: str | None = None  # e.g. BRCGS, IFS
    grade: str | None = None
    certificate_no: str | None = None
    valid_until: str | None = None  # ISO date string, read exactly as printed
    legible: bool = True
