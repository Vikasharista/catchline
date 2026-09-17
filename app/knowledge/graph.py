"""A lightweight sourcing knowledge graph: the real entities (suppliers,
items/SKUs/species, certificates, RFx/PO numbers) plus domain vocabulary,
used to gate what the co-pilot and analyst agents will even attempt to
answer. Deterministic substring/word matching against data pulled from the
DB — no embeddings, no vector store; this app's entity count (a few dozen
suppliers/lines) doesn't need one, and a rule-based gate is faster, free,
and fully auditable (PRD's own "the model never decides risk/eligibility by
itself" spirit extended to "the model doesn't decide its own scope either").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models import Certificate, PastRfxEvent, PurchaseOrder, Supplier

# General sourcing/procurement vocabulary. A question containing one of these
# is treated as in-domain even before checking for a specific named entity —
# "what's our payment terms policy" is in scope even with no supplier named.
DOMAIN_TERMS = [
    "rfx", "rfq", "po", "purchase order", "quote", "quotation", "price", "pricing",
    "certificate", "certification", "cert", "eligib", "glaze", "incoterm",
    "supplier", "vendor", "customer", "buyer", "line", "sku", "item", "species",
    "contract", "award", "freight", "currency", "fx", "exchange rate",
    "delivery", "shipment", "invoice", "payment term", "audit", "questionnaire",
    "compare", "comparison", "spread", "discount", "rebate", "volume", "tonnage",
    "net weight", "gross weight", "dap", "boulogne", "seafood", "fish", "shrimp",
    "salmon", "cod", "haddock", "pollock", "tuna", "hake", "squid",
]

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass
class EntityGraph:
    supplier_names: set[str] = field(default_factory=set)
    species: set[str] = field(default_factory=set)
    line_ids: set[str] = field(default_factory=set)
    cert_schemes: set[str] = field(default_factory=set)
    po_numbers: set[str] = field(default_factory=set)
    rfx_numbers: set[str] = field(default_factory=set)

    def all_entity_phrases(self) -> set[str]:
        return self.supplier_names | self.species | self.line_ids | self.cert_schemes | self.po_numbers | self.rfx_numbers


def build_entity_graph(session: Session, draft_lines: list[dict] | None = None) -> EntityGraph:
    """Pulls real entity names from the DB (all suppliers/certs/history, not
    scoped to one RFx — the buyer can ask about Nordcap's wider sourcing
    history) plus the current draft's line items.
    """
    graph = EntityGraph()

    for supplier in session.exec(select(Supplier)).all():
        graph.supplier_names.add(supplier.name.lower())
        # first word too, e.g. "fjordline" out of "Fjordline Seafood AS"
        graph.supplier_names.add(supplier.name.lower().split()[0])

    for cert in session.exec(select(Certificate)).all():
        graph.cert_schemes.add(cert.scheme.lower())

    for po in session.exec(select(PurchaseOrder)).all():
        graph.po_numbers.add(po.po_number.lower())
        graph.species.add(po.species.lower())

    for event in session.exec(select(PastRfxEvent)).all():
        graph.rfx_numbers.add(event.rfx_number.lower())
        for sp in event.species_json or []:
            graph.species.add(str(sp).lower())

    for line in draft_lines or []:
        graph.line_ids.add(str(line.get("line_id", "")).lower())
        if line.get("species"):
            graph.species.add(str(line["species"]).lower())

    # Common certificate schemes even if none happen to be in the DB yet.
    graph.cert_schemes |= {"brcgs", "ifs", "msc", "asc", "haccp"}

    return graph


def is_in_scope(text: str, graph: EntityGraph) -> tuple[bool, str]:
    """Returns (in_scope, reason). Matches whole words/phrases against the
    domain vocabulary and the real entity graph — a question needs to hit at
    least one to pass.
    """
    lowered = text.lower()
    words = set(_WORD_RE.findall(lowered))

    for term in DOMAIN_TERMS:
        if " " in term:
            if term in lowered:
                return True, f"matched domain term '{term}'"
        elif term in words:
            return True, f"matched domain term '{term}'"

    for phrase in graph.all_entity_phrases():
        if not phrase:
            continue
        if " " in phrase or "-" in phrase:
            if phrase in lowered:
                return True, f"matched known entity '{phrase}'"
        elif phrase in words:
            return True, f"matched known entity '{phrase}'"

    return False, "no recognized sourcing entity or topic in this RFx or Nordcap's sourcing history"
