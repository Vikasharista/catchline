from sqlmodel import Session, SQLModel, create_engine, select

import app.db as db_module
import scripts.seed_history as seed_history_module
from app.models import PastRfxEvent, PurchaseOrder, Rfx, Supplier

SUPPLIER_NAMES = [
    "Fjordline Seafood AS",
    "Pacific Rim Seafoods Ltd",
    "Atlantico Pesca S.L.",
    "Oceanis Trading SARL",
    "Baltic Blue Foods Sp. z o.o.",
]


def test_seed_history_is_idempotent_and_produces_rows(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)
        for name in SUPPLIER_NAMES:
            s.add(Supplier(rfx_id=rfx.id, name=name))
        s.commit()

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(seed_history_module, "engine", engine)
    monkeypatch.setattr(seed_history_module, "init_db", lambda: None)

    seed_history_module.main()

    with Session(engine) as s:
        pos = s.exec(select(PurchaseOrder)).all()
        events = s.exec(select(PastRfxEvent)).all()
        assert len(pos) > 0
        assert len(events) == 2
        # every PO references a real seeded supplier
        supplier_ids = {sup.id for sup in s.exec(select(Supplier)).all()}
        assert all(po.supplier_id in supplier_ids for po in pos)

    # second run should not duplicate rows
    seed_history_module.main()
    with Session(engine) as s:
        assert len(s.exec(select(PurchaseOrder)).all()) == len(pos)
        assert len(s.exec(select(PastRfxEvent)).all()) == 2
