import base64
import io
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

from app.ingest.router import Chunk, IngestedDoc


def ingest(path: Path) -> IngestedDoc:
    chunks: list[Chunk] = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                chunks.append(Chunk(kind="text", content=text, locator=f"page {i}"))

    pdf_doc = pdfium.PdfDocument(path)
    for i in range(len(pdf_doc)):
        page = pdf_doc[i]
        bitmap = page.render(scale=150 / 72)
        pil_image = bitmap.to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        chunks.append(Chunk(kind="image", content=b64, locator=f"page {i + 1}"))

    return IngestedDoc(filename=path.name, kind="pdf", chunks=chunks)
