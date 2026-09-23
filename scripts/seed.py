"""Seeds a fully populated demo RFx: the reference draft (30 lines, 12
questions, terms), the 5 demo suppliers, and synthetic PO/RFQ history.
Kept as a standalone script for scripts that want a ready-to-use demo RFx
without going through the UI/API (e.g. reset_demo.py). Note this is the
full reference draft (app.bootstrap.seed_reference_draft), not what a new
RFx gets through the app itself now — that starts blank and is built up
through chat with the co-pilot (app.bootstrap.seed_new_rfx).
"""
from sqlmodel import Session, select

from app.bootstrap import seed_new_rfx, seed_reference_draft
from app.db import engine, init_db
from app.models import Rfx


def main() -> None:
    init_db()
    with Session(engine) as session:
        rfx = session.exec(select(Rfx)).first()
        if rfx is None:
            rfx = Rfx()
            session.add(rfx)
            session.commit()
            session.refresh(rfx)
        rfx_id = rfx.id
        seed_new_rfx(session, rfx_id)
        seed_reference_draft(session, rfx_id)
        print(f"Seeded RFx {rfx_id}.")


if __name__ == "__main__":
    main()
