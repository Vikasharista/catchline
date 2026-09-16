import tempfile
from email import policy
from email.parser import BytesParser
from pathlib import Path

from app.ingest.router import Chunk, IngestedDoc


def ingest(path: Path) -> IngestedDoc:
    with open(path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    chunks: list[Chunk] = []

    headers = "\n".join(f"{k}: {msg[k]}" for k in ("From", "To", "Subject", "Date") if msg[k])
    chunks.append(Chunk(kind="text", content=headers, locator="message headers"))

    body_part = msg.get_body(preferencelist=("plain", "html"))
    if body_part is not None:
        body_text = body_part.get_content()
        chunks.append(Chunk(kind="text", content=body_text, locator="message body"))

    for part in msg.iter_attachments():
        filename = part.get_filename() or "attachment"
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        try:
            from app.ingest.router import route  # lazy import: avoid circularity

            attached_doc = route(tmp_path)
        except ValueError:
            continue
        for chunk in attached_doc.chunks:
            chunks.append(
                Chunk(kind=chunk.kind, content=chunk.content, locator=f"attachment {filename}: {chunk.locator}")
            )

    return IngestedDoc(filename=path.name, kind="eml", chunks=chunks)
