"""The reference RFx draft, transcribed from the buyer's own RFQ PDF
(data/seed/.../01_buyer_rfx/RFQ-2026-FROZ-017_request_for_quotation.pdf).
This is RFx *content* the buyer already wrote, not a computed answer — the
"Load reference RFx" demo shortcut (PRD §7.2) seeds it so the demo doesn't
have to dictate 30 lines by chat. Nothing here is a price, a conversion
result, or any other number CLAUDE.md forbids hardcoding.
"""
from __future__ import annotations

_LINES_RAW = [
    ("L01", "Atlantic salmon (farmed)", "HOG, frozen", "2-3 kg", 40),
    ("L02", "Atlantic salmon (farmed)", "HOG, frozen", "3-4 kg", 60),
    ("L03", "Atlantic salmon (farmed)", "HOG, frozen", "4-5 kg", 60),
    ("L04", "Atlantic salmon (farmed)", "HOG, frozen", "5-6 kg", 40),
    ("L05", "Atlantic salmon (farmed)", "HOG, frozen", "6+ kg", 20),
    ("L06", "Atlantic salmon (farmed)", "Fillet trim D, skin-on", "1-2 kg", 30),
    ("L07", "Atlantic cod (wild)", "H&G, frozen at sea", "1-2.5 kg", 50),
    ("L08", "Atlantic cod (wild)", "H&G, frozen at sea", "2.5 kg+", 30),
    ("L09", "Atlantic cod (wild)", "Fillet skinless boneless, IQF", "200-400 g", 45),
    ("L10", "Atlantic cod (wild)", "Fillet skinless boneless, IQF", "400-800 g", 25),
    ("L11", "Atlantic cod (wild)", "Loins, IQF", "150-250 g", 20),
    ("L12", "Haddock (wild)", "H&G, frozen at sea", "1-2 kg", 25),
    ("L13", "Haddock (wild)", "Fillet skin-on PBI, IQF", "170-230 g", 20),
    ("L14", "Alaska pollock (wild)", "Fillet block, PBO", "7.5 kg block", 80),
    ("L15", "Alaska pollock (wild)", "Minced block", "7.5 kg block", 50),
    ("L16", "Alaska pollock (wild)", "Fillet skinless boneless, IQF", "113-170 g", 40),
    ("L17", "Vannamei shrimp (farmed)", "HLSO, raw, block frozen", "16/20 per lb", 35),
    ("L18", "Vannamei shrimp (farmed)", "HLSO, raw, block frozen", "21/25 per lb", 45),
    ("L19", "Vannamei shrimp (farmed)", "HLSO, raw, block frozen", "26/30 per lb", 45),
    ("L20", "Vannamei shrimp (farmed)", "PD tail-on, cooked, IQF", "31/40 per lb", 30),
    ("L21", "Vannamei shrimp (farmed)", "PD tail-on, cooked, IQF", "41/50 per lb", 30),
    ("L22", "Vannamei shrimp (farmed)", "PUD, raw, IQF", "71/90 per lb", 25),
    ("L23", "Black tiger shrimp (farmed)", "HLSO, raw, block frozen", "8/12 per lb", 10),
    ("L24", "Black tiger shrimp (farmed)", "HLSO, raw, block frozen", "13/15 per lb", 12),
    ("L25", "Yellowfin tuna (wild)", "Loins, ultra-low temp (-60C)", "2-4 kg", 15),
    ("L26", "Yellowfin tuna (wild)", "Saku blocks, IVP", "200-300 g", 8),
    ("L27", "Argentine hake (wild)", "H&G, frozen", "200-400 g", 30),
    ("L28", "Argentine hake (wild)", "Fillet skin-on, IQF", "60-120 g", 25),
    ("L29", "Loligo squid (wild)", "Tubes, cleaned, IQF", "U/5 per lb", 15),
    ("L30", "Loligo squid (wild)", "Rings, IQF", "2-5 cm", 12),
]

_QUESTIONS_RAW = [
    ("Q01", "certifications", "Food safety certificate (BRCGS / IFS) and grade; expiry date"),
    ("Q02", "certifications", "Sustainability certification (MSC / ASC) and which lines it covers"),
    ("Q03", "certifications", "HACCP plan in place and last audit date"),
    ("Q04", "quality", "Glaze % and whether price is on net or gross weight"),
    ("Q05", "quality", "Use of phosphates / soaking agents (declare E-numbers)"),
    ("Q06", "quality", "Freezing method (IQF, block, frozen-at-sea, ULT)"),
    ("Q07", "traceability", "Catch area (FAO zone) or farm country for each species"),
    ("Q08", "traceability", "EU IUU catch certificate available for wild-caught lines"),
    ("Q09", "traceability", "Antibiotic residue testing for farmed lines (lab, frequency)"),
    ("Q10", "commercial", "MOQ per order and lead time (days)"),
    ("Q11", "commercial", "Payment terms"),
    ("Q12", "commercial", "Shelf life (months) and monthly capacity (tonnes)"),
]

SUPPLIERS = [
    {"name": "Fjordline Seafood AS", "email": "sales@fjordline.example"},
    {"name": "Pacific Rim Seafoods Ltd", "email": "offers@pacificrim.example"},
    {"name": "Atlantico Pesca S.L.", "email": "ventas@atlanticopesca.example"},
    {"name": "Oceanis Trading SARL", "email": "info@oceanis.example"},
    {"name": "Baltic Blue Foods Sp. z o.o.", "email": "reply@balticblue.example"},
]


def reference_draft_dict() -> dict:
    return {
        "version": 0,
        "scope": {
            "title": "Frozen seafood raw material, multi-species annual contract",
            "category": "Frozen seafood raw material",
            "buyer_site": "Nordcap Seafood Processing SAS",
            "contract_start": "2026-10-01",
            "contract_end": "2027-09-30",
            "incoterm": "DAP",
            "incoterm_place": "Boulogne",
            "currency": "EUR",
            "weight_basis": "net",
            "response_deadline": "2026-09-10",
            "award_date": "2026-09-30",
        },
        "lines": [
            {
                "line_id": line_id,
                "species": species,
                "form": form,
                "grade": grade,
                "spec_notes": None,
                "unit": "kg",
                "annual_volume_kg": tonnes * 1000,
                "custom_fields": {},
            }
            for line_id, species, form, grade, tonnes in _LINES_RAW
        ],
        "questionnaire": [
            {
                "q_id": q_id,
                "group": group,
                "text": text,
                "answer_type": "file" if q_id == "Q01" else "text",
                "pass_rule": (
                    {"type": "require_cert_valid_on", "ref": "award_date"} if q_id == "Q01" else None
                ),
            }
            for q_id, group, text in _QUESTIONS_RAW
        ],
        "terms": {
            "payment_terms": "30 days from invoice",
            "glaze_cap_pct": 0.10,
            "quote_validity_days": 30,
            "partial_quotes_allowed": True,
            "eval_weights": {"price": 60, "quality": 25, "commercial": 15},
            "award_rules": [
                {"type": "require_valid_cert", "schemes": ["BRCGS", "IFS"], "value": None, "codes": None, "applies_to": None},
                {
                    "type": "ban_additive",
                    "codes": ["E450", "E451", "E452"],
                    "applies_to": "raw shrimp",
                    "value": None,
                    "schemes": None,
                },
                {"type": "max_share_per_supplier_per_species", "value": 0.6, "schemes": None, "codes": None, "applies_to": None},
            ],
        },
        "custom_sections": [],
        "suppliers": SUPPLIERS,
    }
