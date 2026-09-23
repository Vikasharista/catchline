"""Fixed analyst tools (PRD §7.9), tried before the sandbox. Every number the
analyst states must come from one of these — enforced by the system prompt,
not by code, but every tool here returns exactly what it computed so "How I
got this" can show real arguments and real rows.

`quotes` is a read-only DataFrame with columns: line_id, species, form,
grade, volume_kg, supplier_id, supplier_name, eur_kg_net_dap, status, flags
(list), conditions (list), eligibility, line_blocked (bool), native_price,
native_unit, currency, incoterm.
"""
from __future__ import annotations

import pandas as pd
from sqlmodel import Session, select

from app.normalize.reference import load_last_year_prices


class AnalystTools:
    def __init__(
        self,
        quotes: pd.DataFrame,
        all_line_ids: list[str],
        all_supplier_ids: list[str],
        session: Session | None = None,
        rfx_id: int | None = None,
    ):
        self.quotes = quotes
        self.all_line_ids = all_line_ids
        self.all_supplier_ids = all_supplier_ids
        self.session = session
        self.rfx_id = rfx_id

    def coverage(self) -> dict:
        counts = self.quotes.groupby("supplier_id")["line_id"].nunique().to_dict()
        by_supplier = {sid: counts.get(sid, 0) for sid in self.all_supplier_ids}
        line_counts = self.quotes.groupby("line_id")["supplier_id"].nunique()
        under_quoted = [lid for lid in self.all_line_ids if line_counts.get(lid, 0) < 3]
        return {"lines_quoted_per_supplier": by_supplier, "lines_with_fewer_than_3_quotes": under_quoted}

    def uncertain_items(self) -> dict:
        uncertain = self.quotes[self.quotes["status"] != "confirmed"]
        grouped: dict[str, list[dict]] = {}
        for _, row in uncertain.iterrows():
            for flag in row["flags"] or ["unconfirmed"]:
                grouped.setdefault(flag, []).append(
                    {"supplier_id": row["supplier_id"], "line_id": row["line_id"], "status": row["status"]}
                )
        return grouped

    def explain_cell(self, supplier_id: str, line_id: str) -> dict:
        rows = self.quotes[(self.quotes.supplier_id == supplier_id) & (self.quotes.line_id == line_id)]
        if rows.empty:
            return {"found": False}
        row = rows.iloc[0]
        return {
            "found": True,
            "eur_kg_net_dap": row["eur_kg_net_dap"],
            "native_price": row["native_price"],
            "native_unit": row["native_unit"],
            "currency": row["currency"],
            "incoterm": row["incoterm"],
            "status": row["status"],
            "flags": row["flags"],
            "conditions": row["conditions"],
        }

    def cheapest_per_line(
        self, eligible_only: bool = True, exclude_suppliers: list[str] | None = None, species: str | None = None
    ) -> dict:
        df = self.quotes.copy()
        if eligible_only:
            df = df[(df.eligibility == "eligible") | (df.eligibility == "conditional") & (~df.line_blocked)]
        if exclude_suppliers:
            df = df[~df.supplier_id.isin(exclude_suppliers)]
        if species:
            df = df[df.species == species]
        df = df[df.eur_kg_net_dap.notna()]

        winners = df.loc[df.groupby("line_id")["eur_kg_net_dap"].idxmin()] if not df.empty else df
        total_spend = float((winners.eur_kg_net_dap * winners.volume_kg).sum())
        by_supplier = winners.groupby("supplier_id")["line_id"].apply(list).to_dict()
        covered = set(winners.line_id)
        uncovered = [lid for lid in self.all_line_ids if lid not in covered]

        return {
            "total_spend_eur": round(total_spend, 2),
            "winners_by_supplier": by_supplier,
            "award_table": winners[["line_id", "supplier_id", "eur_kg_net_dap", "volume_kg"]].to_dict("records"),
            "uncovered_lines": uncovered,
        }

    def split_award(self, max_share_per_supplier_per_species: float, eligible_only: bool = True) -> dict:
        df = self.quotes.copy()
        if eligible_only:
            df = df[(df.eligibility == "eligible") | ((df.eligibility == "conditional") & (~df.line_blocked))]
        df = df[df.eur_kg_net_dap.notna()].sort_values("eur_kg_net_dap")

        species_volume_by_supplier: dict[tuple[str, str], float] = {}
        species_total_volume: dict[str, float] = self.quotes.drop_duplicates("line_id").groupby("species")[
            "volume_kg"
        ].sum().to_dict()

        assignments = []
        cap_unmet_species = set()
        assigned_lines = set()

        for _, row in df.iterrows():
            if row.line_id in assigned_lines:
                continue
            key = (row.species, row.supplier_id)
            current = species_volume_by_supplier.get(key, 0)
            cap = max_share_per_supplier_per_species * species_total_volume.get(row.species, 0)
            if current + row.volume_kg <= cap or cap == 0:
                species_volume_by_supplier[key] = current + row.volume_kg
                assignments.append({"line_id": row.line_id, "supplier_id": row.supplier_id, "eur_kg_net_dap": row.eur_kg_net_dap})
                assigned_lines.add(row.line_id)

        for line_id in self.all_line_ids:
            if line_id not in assigned_lines:
                species = self.quotes[self.quotes.line_id == line_id]["species"].iloc[0] if not self.quotes[self.quotes.line_id == line_id].empty else None
                if species:
                    cap_unmet_species.add(species)

        return {"assignments": assignments, "cap_cannot_be_met_for_species": sorted(cap_unmet_species)}

    def price_spread(self) -> dict:
        df = self.quotes[self.quotes.eur_kg_net_dap.notna()]
        result = []
        for line_id, group in df.groupby("line_id"):
            if len(group) < 2:
                continue
            lo, hi = group.eur_kg_net_dap.min(), group.eur_kg_net_dap.max()
            spread_pct = (hi - lo) / lo if lo else 0
            result.append({"line_id": line_id, "min": round(lo, 3), "max": round(hi, 3), "spread_pct": round(spread_pct, 4)})
        return {"lines": sorted(result, key=lambda r: -r["spread_pct"])}

    def compare_last_year(self, supplier_id: str | None = None) -> dict:
        last_year = load_last_year_prices()
        df = self.quotes if supplier_id is None else self.quotes[self.quotes.supplier_id == supplier_id]
        rows = []
        for _, row in df.iterrows():
            prior = last_year.get((row.supplier_name, row.line_id))
            if prior is None or pd.isna(row.eur_kg_net_dap):
                continue
            rows.append(
                {
                    "supplier_id": row.supplier_id,
                    "line_id": row.line_id,
                    "last_year": prior,
                    "this_year": row.eur_kg_net_dap,
                    "change_pct": round((row.eur_kg_net_dap - prior) / prior, 4) if prior else None,
                }
            )
        return {"comparisons": rows, "lines_with_history": len(rows)}

    def past_orders(self, supplier_name: str | None = None, species: str | None = None) -> dict:
        """Historical purchase orders (PRD extension: "questions on ...
        transactional data on past PO"). Source data is synthetic demo
        fixture data (scripts/seed_history.py) — see that script's docstring.
        """
        from app.models import PurchaseOrder, Supplier

        if self.session is None:
            return {"orders": [], "note": "no DB session available"}

        query = select(PurchaseOrder, Supplier).join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
        if supplier_name:
            query = query.where(Supplier.name.ilike(f"%{supplier_name}%"))
        if species:
            query = query.where(PurchaseOrder.species.ilike(f"%{species}%"))

        rows = self.session.exec(query).all()
        orders = [
            {
                "po_number": po.po_number,
                "supplier": supplier.name,
                "species": po.species,
                "form": po.form,
                "grade": po.grade,
                "quantity_kg": po.quantity_kg,
                "price_eur_kg_net_dap": po.price_eur_kg_net_dap,
                "order_date": po.order_date.isoformat(),
                "status": po.status,
            }
            for po, supplier in rows
        ]
        return {"orders": orders, "count": len(orders)}

    def past_rfqs(self) -> dict:
        """Prior RFQ rounds (PRD extension). Synthetic demo fixture data —
        see scripts/seed_history.py.
        """
        from app.models import PastRfxEvent, Supplier

        if self.session is None:
            return {"events": [], "note": "no DB session available"}

        events = self.session.exec(select(PastRfxEvent)).all()
        result = []
        for e in events:
            supplier = self.session.get(Supplier, e.awarded_supplier_id) if e.awarded_supplier_id else None
            result.append(
                {
                    "rfx_number": e.rfx_number,
                    "year": e.year,
                    "awarded_supplier": supplier.name if supplier else None,
                    "species": e.species_json,
                    "total_spend_eur": e.total_spend_eur,
                    "closed_date": e.closed_date.isoformat(),
                }
            )
        return {"events": result, "count": len(result)}

    def certificates(self, supplier_name: str | None = None) -> dict:
        """Certificate records for suppliers — scheme, grade, validity."""
        from app.models import Certificate, Supplier

        if self.session is None:
            return {"certificates": [], "note": "no DB session available"}

        query = select(Certificate, Supplier).join(Supplier, Certificate.supplier_id == Supplier.id)
        if supplier_name:
            query = query.where(Supplier.name.ilike(f"%{supplier_name}%"))

        rows = self.session.exec(query).all()
        certs = [
            {
                "supplier": supplier.name,
                "scheme": cert.scheme,
                "grade": cert.grade,
                "valid_until": cert.valid_until.isoformat() if cert.valid_until else None,
            }
            for cert, supplier in rows
        ]
        return {"certificates": certs, "count": len(certs)}

    def qualified_vendors(self, line_id: str | None = None) -> dict:
        """Per SKU/line: qualified suppliers (eligible, price, delivery SLA)."""
        from app.validate.service import qualified_vendors_table

        if self.session is None or self.rfx_id is None:
            return {"rows": [], "note": "no DB session available"}
        rows = qualified_vendors_table(self.session, self.rfx_id)
        if line_id:
            rows = [r for r in rows if r["line_id"] == line_id]
        return {"rows": rows, "count": len(rows)}

    def questionnaire_answers(self, supplier_name: str | None = None, group: str | None = None) -> dict:
        """Supplier-level data: what each supplier actually answered (or
        didn't) against this RFQ's own questionnaire — real QaAnswer rows
        from real document extraction, matched against the draft's
        question text/group so the answer is legible, not just a q_id.
        """
        from app.copilot.tools import get_current_draft
        from app.models import QaAnswer, Supplier
        from app.schemas.draft import RfxDraft

        if self.session is None or self.rfx_id is None:
            return {"answers": [], "unanswered": [], "note": "no DB session available"}

        draft = RfxDraft.model_validate(get_current_draft(self.session, self.rfx_id))
        questions_by_id = {q.q_id: q for q in draft.questionnaire}

        suppliers = {
            s.id: s for s in self.session.exec(select(Supplier).where(Supplier.rfx_id == self.rfx_id)).all()
        }
        rows = self.session.exec(select(QaAnswer).where(QaAnswer.supplier_id.in_(suppliers.keys()))).all()

        answers, answered_by_supplier = [], {}
        for a in rows:
            supplier = suppliers.get(a.supplier_id)
            if supplier is None:
                continue
            if supplier_name and supplier_name.lower() not in supplier.name.lower():
                continue
            question = questions_by_id.get(a.q_id)
            if group and (question is None or question.group != group):
                continue
            answers.append(
                {
                    "supplier": supplier.name,
                    "q_id": a.q_id,
                    "question": question.text if question else None,
                    "group": question.group if question else None,
                    "answer": a.answer,
                    "result": a.result,
                }
            )
            answered_by_supplier.setdefault(a.supplier_id, set()).add(a.q_id)

        unanswered = []
        for supplier in suppliers.values():
            if supplier_name and supplier_name.lower() not in supplier.name.lower():
                continue
            answered = answered_by_supplier.get(supplier.id, set())
            for q in draft.questionnaire:
                if group and q.group != group:
                    continue
                if q.q_id not in answered:
                    unanswered.append({"supplier": supplier.name, "q_id": q.q_id, "question": q.text})

        return {"answers": answers, "unanswered": unanswered, "count": len(answers)}

    def rfx_summary(self) -> dict:
        """RFQ-level data: this RFQ's own scope and commercial terms, plus
        line/supplier/question counts — the buyer's draft itself, not a
        quote or comparison number."""
        from app.copilot.tools import get_current_draft
        from app.schemas.draft import RfxDraft

        if self.session is None or self.rfx_id is None:
            return {"note": "no DB session available"}
        draft = RfxDraft.model_validate(get_current_draft(self.session, self.rfx_id))
        return {
            "scope": draft.scope.model_dump(),
            "terms": draft.terms.model_dump(),
            "line_count": len(draft.lines),
            "questionnaire_count": len(draft.questionnaire),
            "supplier_count": len(self.all_supplier_ids),
        }

    def sku_breakdown(self, line_id: str | None = None) -> dict:
        """SKU-wise price and quantity: for each line, the RFQ's own
        requested volume plus every supplier's quoted price and the
        implied spend at that price and volume — cheapest first."""
        df = self.quotes.copy()
        if line_id:
            df = df[df.line_id == line_id]

        lines = []
        for lid, group in df.groupby("line_id"):
            volume = float(group["volume_kg"].iloc[0]) if not group.empty else None
            offers = []
            for _, row in group.sort_values("eur_kg_net_dap", na_position="last").iterrows():
                price = row["eur_kg_net_dap"]
                spend = round(price * volume, 2) if price is not None and volume is not None else None
                offers.append(
                    {
                        "supplier_id": row["supplier_id"],
                        "supplier_name": row["supplier_name"],
                        "price_eur_kg_net_dap": price,
                        "implied_spend_eur": spend,
                        "eligibility": row["eligibility"],
                        "status": row["status"],
                    }
                )
            lines.append(
                {
                    "line_id": lid,
                    "species": group["species"].iloc[0],
                    "form": group["form"].iloc[0],
                    "grade": group["grade"].iloc[0],
                    "requested_volume_kg": volume,
                    "offers": offers,
                }
            )
        return {"lines": sorted(lines, key=lambda l: l["line_id"])}

    def location_breakdown(self) -> dict:
        """Delivery-location breakdown: where each supplier ships from
        (their own stated incoterm + place, from real extracted quotes)
        and the freight adder actually available for that origin — real
        buyer reference data (04_buyer_reference_data/freight_adders...),
        not invented. Useful for reviewing shipping-distance/cost
        implications by supplier before awarding.
        """
        from app.copilot.tools import get_current_draft
        from app.models import Document, ExtractedItem, Supplier
        from app.normalize.reference import load_freight_adders
        from app.schemas.draft import RfxDraft

        if self.session is None or self.rfx_id is None:
            return {"suppliers": [], "note": "no DB session available"}

        draft = RfxDraft.model_validate(get_current_draft(self.session, self.rfx_id))
        freight_adders = load_freight_adders()
        suppliers = {
            s.id: s for s in self.session.exec(select(Supplier).where(Supplier.rfx_id == self.rfx_id)).all()
        }

        rows = self.session.exec(
            select(ExtractedItem, Document)
            .join(Document, ExtractedItem.document_id == Document.id)
            .where(Document.supplier_id.in_(suppliers.keys()))
        ).all()

        origins_by_supplier: dict[int, set[str]] = {}
        for item, document in rows:
            fields = item.fields_json or {}
            incoterm, place = fields.get("incoterm"), fields.get("incoterm_place")
            if incoterm and place:
                origins_by_supplier.setdefault(document.supplier_id, set()).add(f"{incoterm} {place}")

        result = []
        for supplier_id, supplier in suppliers.items():
            origins = sorted(origins_by_supplier.get(supplier_id, []))
            result.append(
                {
                    "supplier": supplier.name,
                    "stated_origins": origins,
                    "freight_adders_eur_kg": {o: freight_adders.get(o) for o in origins},
                }
            )

        return {
            "delivery_terms": {
                "incoterm": draft.scope.incoterm,
                "place": draft.scope.incoterm_place,
                "buyer_site": draft.scope.buyer_site,
            },
            "known_freight_adders_eur_kg": freight_adders,
            "suppliers": result,
        }
