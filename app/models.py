"""SQLModel tables — see PRD §8 for the field-by-field spec."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


class Rfx(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="drafting")  # drafting / sent / closed
    current_version: int = Field(default=0)
    created_at: datetime = Field(default_factory=_now)


class RfxVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_id: int = Field(foreign_key="rfx.id")
    version: int
    draft_json: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)
    created_by: str
    cause: str  # proposal_id / restore / seed


class SectionState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_id: int = Field(foreign_key="rfx.id")
    section_key: str
    status: str = Field(default="drafting")  # drafting / signed_off / reopened
    signed_by: Optional[str] = None
    signed_at: Optional[datetime] = None
    last_check_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class ChangeProposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_id: int = Field(foreign_key="rfx.id")
    chat_turn_id: Optional[int] = Field(default=None, foreign_key="chatturn.id")
    section_key: str
    op: str  # add / update / remove
    target: str
    before_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    after_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    reason: str
    origin: str  # from_you / suggested
    risk: str = Field(default="normal")  # money_or_eligibility / normal
    status: str = Field(default="pending")  # pending/accepted/edited/rejected/held/failed
    error: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_now)


class CopilotQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_id: int = Field(foreign_key="rfx.id")
    chat_turn_id: Optional[int] = Field(default=None, foreign_key="chatturn.id")
    question: str
    options_json: Optional[list] = Field(default=None, sa_column=Column(JSON))
    answer: Optional[str] = None
    answered_at: Optional[datetime] = None


class ChatTurn(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_id: int = Field(foreign_key="rfx.id")
    thread: str  # copilot / analyst
    role: str
    content: str
    tool_calls_json: Optional[list] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now)


class Supplier(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_id: int = Field(foreign_key="rfx.id")
    name: str
    country: Optional[str] = None
    email: Optional[str] = None


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: int = Field(foreign_key="supplier.id")
    filename: str
    kind: str  # xlsx/pdf/docx/jpg/png/eml
    sha256: str
    path: str
    received_at: datetime = Field(default_factory=_now)
    status: str = Field(default="received")


class ExtractedItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id")
    fields_json: dict = Field(sa_column=Column(JSON))
    raw_text: str
    locator_json: dict = Field(sa_column=Column(JSON))
    confidence: float
    legibility: str  # clear / partial / illegible
    matched_line_id: Optional[str] = None
    match_reason: Optional[str] = None
    match_confidence: Optional[float] = None


class NormalizedQuote(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="extracteditem.id")
    supplier_id: int = Field(foreign_key="supplier.id")
    line_id: str
    eur_kg_net_dap: Optional[float] = None
    steps_json: list = Field(sa_column=Column(JSON))
    status: str = Field(default="auto")  # auto/confirmed/edited/inferred/illegible/excluded/ask_supplier


class Flag(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str
    entity_id: int
    code: str
    severity: str  # red / amber / info
    message: str
    evidence_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    resolved: bool = Field(default=False)


class QaAnswer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: int = Field(foreign_key="supplier.id")
    q_id: str
    answer: Optional[str] = None
    raw_text: Optional[str] = None
    locator_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    result: str = Field(default="unknown")  # pass / fail / unknown


class Certificate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: int = Field(foreign_key="supplier.id")
    scheme: str
    grade: Optional[str] = None
    valid_until: Optional[datetime] = None
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")


class Eligibility(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: int = Field(foreign_key="supplier.id")
    status: str  # eligible / not_eligible / conditional / unknown
    blocked_lines_json: Optional[list] = Field(default=None, sa_column=Column(JSON))
    reasons_json: Optional[list] = Field(default=None, sa_column=Column(JSON))
    overridden_by: Optional[str] = None
    override_reason: Optional[str] = None


class Assumption(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value_json: dict = Field(sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=_now)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=_now)
    actor: str  # buyer / agent:copilot / agent:extractor / agent:analyst / system
    action: str
    entity: str
    before_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    after_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    reason: Optional[str] = None


class PurchaseOrder(SQLModel, table=True):
    """Historical PO record. SYNTHETIC DEMO DATA (scripts/seed_history.py) —
    not derived from any real document. Answers "past PO" questions from the
    analyst; never fed to an extraction or copilot prompt.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    po_number: str
    supplier_id: int = Field(foreign_key="supplier.id")
    species: str
    form: str
    grade: str
    quantity_kg: float
    price_eur_kg_net_dap: float
    order_date: datetime
    delivery_date: Optional[datetime] = None
    status: str = Field(default="delivered")  # delivered / cancelled / open


class PastRfxEvent(SQLModel, table=True):
    """A prior sourcing event (RFQ round), for "past RFQs" questions.
    SYNTHETIC DEMO DATA (scripts/seed_history.py) — same caveat as PurchaseOrder.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    rfx_number: str
    year: int
    awarded_supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    species_json: list = Field(sa_column=Column(JSON))
    total_spend_eur: float
    closed_date: datetime
    notes: Optional[str] = None
