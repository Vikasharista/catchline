"""A small, real reference dictionary the co-pilot can ground its answers
in when a buyer asks an informational/advisory question mid-draft (e.g.
"what's a reasonable glaze cap?", "what does DAP mean?").

Two kinds of entries, kept separate so the agent never blurs them:
- TERM_DEFINITIONS: standard frozen-seafood/trade terminology. Facts about
  vocabulary, not business data — safe to state as fact.
- NORDCAP_PRECEDENT: real figures from this buyer's own past RFQ policy
  (data/seed/aerchain_fish_rfx_dataset/04_buyer_reference_data/award_rules.md,
  and the same values already used in reference_draft.py's structured
  award_rules). These are precedent, not a rule for whatever new RFQ the
  buyer is currently drafting from a blank start — the co-pilot must offer
  them as "last time we did X" and let the buyer decide, never write them
  into the new draft unasked.
"""
from __future__ import annotations

TERM_DEFINITIONS: dict[str, str] = {
    "DAP": "Delivered At Place (Incoterm) — the seller/supplier pays freight and risk up to the named destination; the buyer handles import clearance/duties from there.",
    "FCA": "Free Carrier (Incoterm) — the seller delivers to a named place/carrier; the buyer takes on freight and risk from that point.",
    "CFR": "Cost and Freight (Incoterm) — the seller pays freight to the named port; risk transfers to the buyer once the goods are on the vessel.",
    "CIF": "Cost, Insurance and Freight (Incoterm) — like CFR, plus the seller also arranges minimum insurance for the sea leg.",
    "FOB": "Free On Board (Incoterm) — risk and cost transfer to the buyer once the goods are loaded on the vessel at the named port.",
    "EXW": "Ex Works (Incoterm) — the buyer takes on all freight, risk and export clearance from the seller's own premises.",
    "DDP": "Delivered Duty Paid (Incoterm) — the seller pays freight, risk and import duties all the way to the buyer's door.",
    "weight basis": "Whether price/volume is quoted on net weight (product only) or gross weight (product + ice glaze). Net is more common for buyer comparison since it isolates the actual edible product being paid for.",
    "glaze": "A thin ice coating applied to frozen seafood to prevent freezer burn/dehydration during storage and transport. Glaze adds weight but not usable product, so a glaze % (glaze weight as a share of total frozen weight) is used to convert a gross-weight price back to a net-weight price for fair comparison.",
    "glaze cap": "The maximum glaze % a buyer will accept on a quote before requiring it to be declared and price-converted to net weight — protects against paying product price for ice weight.",
    "MOQ": "Minimum Order Quantity — the smallest volume a supplier will accept per order/shipment.",
    "lead time": "How long from order placement to delivery/availability.",
    "IQF": "Individually Quick Frozen — pieces frozen separately (not in a block), so they don't stick together and can be portioned as needed.",
    "HOG": "Headed and Gutted — a whole-fish form with the head and internal organs removed.",
    "HLSO": "Headless, Shell-On — a shrimp form: head removed, shell left on.",
    "block frozen": "Product frozen together as a solid block rather than as individual pieces (IQF) — cheaper to produce but harder to portion.",
    "BRCGS": "Brand Reputation through Compliance Global Standards — a widely used food-safety certification scheme.",
    "IFS": "International Featured Standards — another widely used food-safety certification scheme, often accepted interchangeably with BRCGS.",
    "MSC": "Marine Stewardship Council — sustainability certification for wild-caught seafood.",
    "ASC": "Aquaculture Stewardship Council — sustainability certification for farmed seafood.",
    "HACCP": "Hazard Analysis and Critical Control Points — a food-safety process-control system, often audited rather than certified.",
    "IUU": "Illegal, Unreported and Unregulated (fishing) — an EU catch certificate confirms wild-caught product wasn't sourced from IUU fishing.",
    "eval weights": "How a buyer scores competing quotes across price, quality and commercial factors — the three weights should sum to 100.",
}

# Real values already used for Nordcap's own reference/demo RFQ terms, sourced
# from award_rules.md — precedent to offer, never to silently assume.
NORDCAP_PRECEDENT: dict[str, str] = {
    "glaze_cap_pct": "Nordcap's last RFQ set a 10% glaze cap (shrimp/squid glaze above 10% had to be declared and price-converted to net weight).",
    "payment_terms": "Nordcap's last RFQ used 30 days from invoice.",
    "quote_validity_days": "Nordcap's last RFQ required quotes to stay valid for 30 days.",
    "eval_weights": "Nordcap's last RFQ weighted evaluation 60% price / 25% quality / 15% commercial.",
    "certificates": "Nordcap's last RFQ required a valid BRCGS or IFS certificate on the award date to be eligible.",
    "additive_ban": "Nordcap's last RFQ banned phosphates (E450-E452) on raw shrimp for the retail range.",
    "max_supplier_share": "Nordcap's last RFQ capped any one supplier at 60% of a species' volume (dual sourcing).",
}


def glossary_context() -> str:
    """Renders both dictionaries as compact reference text for the co-pilot's
    system prompt — small enough to always include rather than gate behind
    a tool call the model would have to decide to make."""
    terms = "\n".join(f"- {term}: {definition}" for term, definition in TERM_DEFINITIONS.items())
    precedent = "\n".join(f"- {note}" for note in NORDCAP_PRECEDENT.values())
    return (
        "TERM DEFINITIONS (state these as fact when asked):\n"
        f"{terms}\n\n"
        "NORDCAP PRECEDENT (real figures from Nordcap's last RFQ — offer as "
        "precedent/context for the buyer to decide on, never write into the "
        "new draft unless the buyer confirms it):\n"
        f"{precedent}"
    )
