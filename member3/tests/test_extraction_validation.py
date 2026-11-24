import pytest

from member3.ai.ecn_extractor import extract_ecn_fields
from member3.ai.extraction_validator import normalize, validate_extracted_ecn

GOOD = {"change_id": "ECN-1001", "part_number": "BRK-100", "old_revision": "B", "new_revision": "C",
        "effective_week": 6, "use_up_end_week": 7, "interchangeability": True, "reason": "cracks",
        "approver": "R. Rao", "approval_status": "APPROVED"}


def status(member1=None, confirmed=False, **changes):
    check = (lambda f: member1.validate_ecn(f, member1.load_dataset("BASE"))) if member1 else None
    return validate_extracted_ecn({**GOOD, **changes}, check, confirmed)


def test_valid_still_needs_a_human(member1):
    assert status(member1)["validation_status"] == "VALID"
    assert not status(member1)["ready_for_planning"]
    assert status(member1, confirmed=True)["ready_for_planning"]


@pytest.mark.parametrize("changes", [
    {"effective_week": "6"}, {"effective_week": 0}, {"effective_week": 6.5}, {"old_revision": "BBB"},
    {"change_id": "1001"}, {"approval_status": "MAYBE"}, {"interchangeability": "yes"}, {"reason": ""},
    {"new_revision": "B"}, {"effective_week": 9}, {"price": 5}])
def test_invalid(changes):
    result = status(**changes)
    assert result["validation_status"] == "INVALID" and result["validation_errors"]


def test_missing_and_unclear_fields():
    assert status(approver=None)["missing_fields"] == ["approver"]
    assert status(approver=None)["validation_status"] == "INSUFFICIENT_DATA"
    unclear = status(effective_week=None, ambiguous_fields=[{"field": "effective_week", "source_text": "TBD"}])
    assert unclear["validation_status"] == "NEEDS_REVIEW" and unclear["missing_fields"] == []
    conflict = {"field": "effective_week", "values": []}
    assert status(effective_week=None, conflicts=[conflict])["conflicts"] == [conflict]
    # A value typed by the planner resolves the conflict.
    assert status(effective_week=6, conflicts=[conflict])["validation_status"] == "VALID"


@pytest.mark.parametrize("changes,code", [
    ({"part_number": "BRK-999"}, "UNKNOWN_PART"), ({"new_revision": "D"}, "UNKNOWN_REVISION"),
    ({"change_id": "ECN-9"}, "UNKNOWN_CHANGE"), ({"use_up_end_week": 8}, "RECORD_MISMATCH"),
    ({"approval_status": "DRAFT"}, "RECORD_MISMATCH"), ({"interchangeability": False}, "RECORD_MISMATCH")])
def test_member1_has_the_last_word(member1, changes, code):
    result = status(member1, confirmed=True, **changes)
    assert code in {e["code"] for e in result["validation_errors"]} and not result["ready_for_planning"]


def test_member1_is_not_asked_about_incomplete_data():
    def explode(fields):
        raise AssertionError("must not be called")
    assert validate_extracted_ecn({**GOOD, "approver": None}, explode)["validation_status"] == "INSUFFICIENT_DATA"


@pytest.mark.parametrize("field,raw,value", [
    ("effective_week", "W06", 6), ("effective_week", "week 12", 12), ("old_revision", "Rev. b", "B"),
    ("interchangeability", "Yes - fully interchangeable", True), ("interchangeability", "No - not interchangeable", False),
    ("interchangeability", "Not interchangeable", False), ("approval_status", "released", "APPROVED")])
def test_normalize(field, raw, value):
    assert normalize(field, raw) == value


@pytest.mark.parametrize("field,raw", [
    ("effective_week", "6/7"), ("effective_week", "15 March"), ("old_revision", "B and C"),
    ("interchangeability", "partly"), ("interchangeability", "Yes - not interchangeable"), ("approval_status", "nearly"), ("reason", "TBD"), ("approver", "??")])
def test_normalize_refuses_unclear_text(field, raw):
    with pytest.raises(ValueError):
        normalize(field, raw)


def test_negated_interchangeability_is_not_read_as_yes(ecn_text):
    record = extract_ecn_fields(ecn_text.replace("Interchangeable: Yes", "Interchangeable: No"))
    assert record["interchangeability"] is False
