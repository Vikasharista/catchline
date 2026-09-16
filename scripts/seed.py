"""Seeds demo suppliers for the RFx. Draft content (lines, questionnaire,
terms) is seeded by the "Load reference RFx" flow described in PRD §7.2,
built alongside the co-pilot schema in Day 1 PM / Day 2.
"""
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Rfx, Supplier

SUPPLIERS = [
    {"name": "Fjordline", "country": "Norway", "email": "sales@fjordline.example"},
    {"name": "Pacific Rim", "country": "USA", "email": "offers@pacificrim.example"},
    {"name": "Atlantico Pesca", "country": "Spain", "email": "ventas@atlanticopesca.example"},
    {"name": "Oceanis", "country": "Netherlands", "email": "info@oceanis.example"},
    {"name": "Baltic Blue", "country": "Poland", "email": "reply@balticblue.example"},
]


def main() -> None:
    init_db()
    with Session(engine) as session:
        rfx = session.exec(select(Rfx)).first()
        if rfx is None:
            rfx = Rfx()
            session.add(rfx)
            session.commit()
            session.refresh(rfx)

        existing = {s.name for s in session.exec(select(Supplier).where(Supplier.rfx_id == rfx.id)).all()}
        for sup in SUPPLIERS:
            if sup["name"] not in existing:
                session.add(Supplier(rfx_id=rfx.id, **sup))
        session.commit()
        print(f"Seeded RFx {rfx.id} with {len(SUPPLIERS)} suppliers.")


if __name__ == "__main__":
    main()
