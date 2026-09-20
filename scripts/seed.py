"""Seeds a demo RFx: reference draft, the 5 demo suppliers, and synthetic
PO/RFQ history — the same auto-seed a new RFx gets when created through the
app (app.bootstrap.seed_new_rfx). Kept as a standalone script for scripts
that want a demo RFx to exist without going through the UI/API (e.g.
reset_demo.py).
"""
from sqlmodel import Session, select

from app.bootstrap import seed_new_rfx
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
        print(f"Seeded RFx {rfx_id}.")


if __name__ == "__main__":
    main()
