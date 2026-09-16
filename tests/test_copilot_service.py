import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.copilot import service
from app.copilot.tools import CopilotTools, get_current_draft
from app.models import ChangeProposal, Rfx, SectionState

LINE = {
    "line_id": "L01",
    "species": "Atlantic salmon (farmed)",
    "form": "HOG, frozen",
    "grade": "2-3 kg",
    "unit": "kg",
    "annual_volume_kg": 40000,
    "custom_fields": {},
}


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        rfx = Rfx()
        s.add(rfx)
        s.commit()
        s.refresh(rfx)
        yield s, rfx.id


def test_accept_applies_to_draft(session):
    s, rfx_id = session
    tools = CopilotTools(s, rfx_id)
    tools.propose_change("scope", "update", "scope.currency", "EUR", "buyer said EUR", "from_you")
    proposal = s.exec(select(ChangeProposal)).first()

    assert get_current_draft(s, rfx_id)["scope"].get("currency") is None  # unchanged until accept

    accepted = service.accept_proposal(s, proposal.id)
    assert accepted.status == "accepted"
    assert get_current_draft(s, rfx_id)["scope"]["currency"] == "EUR"


def test_reject_does_not_change_draft(session):
    s, rfx_id = session
    tools = CopilotTools(s, rfx_id)
    tools.propose_change("scope", "update", "scope.currency", "EUR", "buyer said EUR", "from_you")
    proposal = s.exec(select(ChangeProposal)).first()

    rejected = service.reject_proposal(s, proposal.id)
    assert rejected.status == "rejected"
    assert get_current_draft(s, rfx_id)["scope"].get("currency") is None


def test_accept_all_skips_money_or_eligibility(session):
    s, rfx_id = session
    tools = CopilotTools(s, rfx_id)
    tools.propose_change("scope", "update", "scope.title", "Frozen seafood RFx", "buyer said so", "from_you")
    tools.propose_change("lines", "add", "lines", LINE, "buyer added a line", "from_you")

    proposals = s.exec(select(ChangeProposal)).all()
    ids = [p.id for p in proposals]

    result = service.accept_all_visible(s, rfx_id, ids)
    assert len(result["accepted"]) == 1
    assert len(result["skipped"]) == 1

    draft = get_current_draft(s, rfx_id)
    assert draft["scope"]["title"] == "Frozen seafood RFx"
    assert draft["lines"] == []  # money_or_eligibility proposal was skipped


def test_sign_off_blocked_until_checks_pass(session):
    s, rfx_id = session
    ok, failures = service.sign_off_section(s, rfx_id, "lines", "buyer")
    assert not ok
    assert "At least one line item is required" in failures

    tools = CopilotTools(s, rfx_id)
    tools.propose_change("lines", "add", "lines", LINE, "buyer added a line", "from_you")
    proposal = s.exec(select(ChangeProposal)).first()
    service.accept_proposal(s, proposal.id)

    ok, failures = service.sign_off_section(s, rfx_id, "lines", "buyer")
    assert ok
    assert failures == []


def test_reopen_releases_held_proposals(session):
    s, rfx_id = session
    tools = CopilotTools(s, rfx_id)
    tools.propose_change("lines", "add", "lines", LINE, "buyer added a line", "from_you")
    proposal = s.exec(select(ChangeProposal)).first()
    service.accept_proposal(s, proposal.id)
    service.sign_off_section(s, rfx_id, "lines", "buyer")

    # A new proposal targeting a signed-off section is held, not pending.
    tools.propose_change("lines", "update", "lines[L01].annual_volume_kg", 50000, "buyer wants more", "from_you")
    held = [p for p in s.exec(select(ChangeProposal)).all() if p.status == "held"]
    assert len(held) == 1

    service.reopen_section(s, rfx_id, "lines", "buyer")
    held_after = s.get(ChangeProposal, held[0].id)
    assert held_after.status == "pending"

    state = s.exec(
        select(SectionState).where(SectionState.rfx_id == rfx_id, SectionState.section_key == "lines")
    ).first()
    assert state.status == "reopened"


def test_restore_version_reopens_changed_sections(session):
    s, rfx_id = session
    tools = CopilotTools(s, rfx_id)
    tools.propose_change("scope", "update", "scope.currency", "EUR", "v1", "from_you")
    p1 = s.exec(select(ChangeProposal)).first()
    service.accept_proposal(s, p1.id)  # version 1

    tools.propose_change("scope", "update", "scope.currency", "USD", "v2", "from_you")
    p2 = s.exec(select(ChangeProposal).where(ChangeProposal.id != p1.id)).first()
    service.accept_proposal(s, p2.id)  # version 2, currency now USD

    assert get_current_draft(s, rfx_id)["scope"]["currency"] == "USD"

    service.restore_version(s, rfx_id, 1, "buyer")  # restore to EUR
    assert get_current_draft(s, rfx_id)["scope"]["currency"] == "EUR"
