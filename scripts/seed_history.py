"""Seeds SYNTHETIC historical PO and past-RFQ data for the demo.

Deliberate, flagged exception to CLAUDE.md's "never hardcode/fabricate"
rule: that rule is about not faking an *extraction or pricing result* that
should come from a real document or a real calculation. This script instead
fabricates a plausible multi-year sourcing history (past purchase orders,
past RFQ rounds) because the take-home dataset only covers one RFx and no
PO history exists to seed from. It's clearly synthetic, keyed to the same 5
real supplier names as the rest of the demo, and lets the analyst answer
"what did we pay Fjordline for cod last year" style questions with numbers
that trace to a real DB row (never invented by the LLM at answer time) —
even though that row's value was itself randomly generated here, once, at
seed time.

Not run by default; call explicitly: python scripts/seed_history.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import PastRfxEvent, PurchaseOrder, Supplier

random.seed(42)

# species this supplier plausibly deals in, loosely matching the real RFx
SUPPLIER_SPECIES = {
    "Fjordline Seafood AS": [
        ("Atlantic salmon (farmed)", "HOG, frozen", "3-4 kg", 6.5, 8.5),
        ("Atlantic cod (wild)", "H&G, frozen at sea", "1-2.5 kg", 5.0, 6.5),
        ("Haddock (wild)", "H&G, frozen at sea", "1-2 kg", 3.8, 5.0),
        ("Alaska pollock (wild)", "Fillet block, PBO", "7.5 kg block", 2.8, 3.8),
    ],
    "Pacific Rim Seafoods Ltd": [
        ("Vannamei shrimp (farmed)", "HLSO, raw, block frozen", "21/25 per lb", 7.5, 9.5),
        ("Yellowfin tuna (wild)", "Loins, ultra-low temp (-60C)", "2-4 kg", 9.0, 12.0),
        ("Loligo squid (wild)", "Tubes, cleaned, IQF", "U/5 per lb", 6.5, 8.5),
    ],
    "Atlantico Pesca S.L.": [
        ("Atlantic cod (wild)", "H&G, frozen at sea", "1-2.5 kg", 5.5, 7.0),
        ("Argentine hake (wild)", "H&G, frozen", "200-400 g", 2.8, 3.8),
        ("Vannamei shrimp (farmed)", "HLSO, raw, block frozen", "16/20 per lb", 8.5, 10.5),
    ],
    "Oceanis Trading SARL": [
        ("Atlantic salmon (farmed)", "HOG, frozen", "3-4 kg", 6.8, 8.8),
        ("Vannamei shrimp (farmed)", "PD tail-on, cooked, IQF", "31/40 per lb", 9.0, 11.0),
        ("Argentine hake (wild)", "Fillet skin-on, IQF", "60-120 g", 4.0, 5.2),
    ],
    "Baltic Blue Foods Sp. z o.o.": [
        ("Atlantic salmon (farmed)", "HOG, frozen", "2-3 kg", 6.0, 7.5),
        ("Atlantic salmon (farmed)", "Fillet trim D, skin-on", "1-2 kg", 9.5, 11.5),
        ("Atlantic cod (wild)", "Fillet skinless boneless, IQF", "200-400 g", 8.5, 10.0),
    ],
}

PAST_RFX_EVENTS = [
    {"rfx_number": "RFQ-2024-FROZ-009", "year": 2024, "species": ["Atlantic salmon (farmed)", "Atlantic cod (wild)"]},
    {"rfx_number": "RFQ-2025-FROZ-013", "year": 2025, "species": ["Vannamei shrimp (farmed)", "Yellowfin tuna (wild)"]},
]


def _random_date(year: int) -> datetime:
    start = datetime(year, 1, 1)
    return start + timedelta(days=random.randint(0, 330))


def main() -> None:
    init_db()
    with Session(engine) as session:
        suppliers = {s.name: s for s in session.exec(select(Supplier)).all()}
        if not suppliers:
            print("No suppliers found — run scripts/seed.py or seed-reference via the API first.")
            return

        existing_po_count = len(session.exec(select(PurchaseOrder)).all())
        if existing_po_count:
            print(f"{existing_po_count} PurchaseOrder rows already exist — skipping (idempotent).")
        else:
            po_seq = 1000
            for supplier_name, species_list in SUPPLIER_SPECIES.items():
                supplier = suppliers.get(supplier_name)
                if supplier is None:
                    continue
                for year in (2023, 2024, 2025):
                    for species, form, grade, lo, hi in species_list:
                        if random.random() < 0.3:
                            continue  # not every supplier/species/year has a PO
                        po_seq += 1
                        order_date = _random_date(year)
                        session.add(
                            PurchaseOrder(
                                po_number=f"PO-{year}-{po_seq}",
                                supplier_id=supplier.id,
                                species=species,
                                form=form,
                                grade=grade,
                                quantity_kg=random.choice([10, 15, 20, 25, 30, 40]) * 1000,
                                price_eur_kg_net_dap=round(random.uniform(lo, hi), 2),
                                order_date=order_date,
                                delivery_date=order_date + timedelta(days=random.randint(14, 45)),
                                status="delivered",
                            )
                        )
            session.commit()
            print(f"Seeded {po_seq - 1000} synthetic PurchaseOrder rows.")

        existing_rfx_count = len(session.exec(select(PastRfxEvent)).all())
        if existing_rfx_count:
            print(f"{existing_rfx_count} PastRfxEvent rows already exist — skipping (idempotent).")
        else:
            supplier_list = list(suppliers.values())
            for event in PAST_RFX_EVENTS:
                awarded = random.choice(supplier_list)
                session.add(
                    PastRfxEvent(
                        rfx_number=event["rfx_number"],
                        year=event["year"],
                        awarded_supplier_id=awarded.id,
                        species_json=event["species"],
                        total_spend_eur=round(random.uniform(800_000, 2_500_000), 2),
                        closed_date=datetime(event["year"], random.randint(9, 11), random.randint(1, 28)),
                        notes=f"Synthetic demo record — awarded to {awarded.name}.",
                    )
                )
            session.commit()
            print(f"Seeded {len(PAST_RFX_EVENTS)} synthetic PastRfxEvent rows.")


if __name__ == "__main__":
    main()
