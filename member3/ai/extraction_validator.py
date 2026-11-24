"""Validation of extracted ECN fields. Extractor output is untrusted input.

Structure is checked here. Master data (does the part exist, do records agree) is checked by Member 1
through the callable passed in.
"""
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

FIELDS = ("change_id", "part_number", "old_revision", "new_revision", "effective_week",
          "use_up_end_week", "interchangeability", "reason", "approver", "approval_status")
STATUSES = ("VALID", "INVALID", "INSUFFICIENT_DATA", "NEEDS_REVIEW")


class ECNFields(BaseModel):
    """The editable part of an ECN. Missing values are None; unknown fields are refused."""
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    change_id: Optional[str] = Field(None, pattern=r"^EC[NRO]-[A-Z0-9-]+$")
    part_number: Optional[str] = Field(None, pattern=r"^[A-Z0-9][A-Z0-9-]*$")
    old_revision: Optional[str] = Field(None, pattern=r"^([A-Z]{1,2}|\d{1,2})$")
    new_revision: Optional[str] = Field(None, pattern=r"^([A-Z]{1,2}|\d{1,2})$")
    effective_week: Optional[int] = Field(None, ge=1, le=104)
    use_up_end_week: Optional[int] = Field(None, ge=1, le=104)
    interchangeability: Optional[bool] = None
    reason: Optional[str] = Field(None, min_length=1, max_length=500)
    approver: Optional[str] = Field(None, min_length=1, max_length=200)
    approval_status: Optional[Literal["APPROVED", "PENDING", "DRAFT", "REJECTED"]] = None


_AFFIRM = {"yes", "y", "true", "interchangeable", "fully interchangeable", "one-for-one", "one for one", "1:1"}
_DENY = {"no", "n", "false", "not interchangeable", "non-interchangeable"}
_STATUS = {"approved": "APPROVED", "released": "APPROVED", "pending": "PENDING", "pending approval": "PENDING",
           "in review": "PENDING", "draft": "DRAFT", "rejected": "REJECTED"}


def normalize(field, raw):
    """Turn document text into a typed value. Raises ValueError when it is not one clear value."""
    text = " ".join(str(raw).split()).strip(" .;,")
    if field in ("effective_week", "use_up_end_week"):
        match = re.fullmatch(r"(?:production\s+)?(?:cw|wk|w|week)?\s*\.?\s*0*(\d{1,3})", text, re.I)
        if match:
            return int(match[1])
    elif field in ("old_revision", "new_revision"):
        match = re.fullmatch(r"(?:rev(?:ision)?\.?\s*)?([A-Za-z]{1,2}|\d{1,2})", text, re.I)
        if match:
            return match[1].upper()
    elif field == "interchangeability":
        # "Yes - fully interchangeable": the parts before and after the dash must agree.
        parts = [p for p in re.split(r"\s+[-\u2013]\s+", text.lower()) if p]
        if parts and all(p in _AFFIRM for p in parts):
            return True
        if parts and all(p in _DENY for p in parts):
            return False
    elif field == "approval_status":
        if text.lower() in _STATUS:
            return _STATUS[text.lower()]
    elif field in ("change_id", "part_number"):
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", text):
            return text.upper()
    elif text and not re.fullmatch(r"(?i)tbd|tbc|n/?a|unknown|-+|\?+", text):
        return text
    raise ValueError(f"{field}: {text!r} is not one clear value")


def identify_missing_fields(data):
    unclear = {a["field"] for a in data.get("ambiguous_fields", [])} | {
        c["field"] for c in data.get("conflicts", [])}
    return [f for f in FIELDS if data.get(f) is None and f not in unclear]


def identify_ambiguous_fields(data):
    """Ambiguities the planner has not resolved by entering a value."""
    return [a for a in data.get("ambiguous_fields", []) if data.get(a["field"]) is None]


def validate_extracted_ecn(extracted_data, member1_validate=None, human_confirmed=False):
    """Structure, then dates, then Member 1. `member1_validate(fields)` returns error dicts."""
    errors = []
    fields = {f: extracted_data.get(f) for f in FIELDS}
    unknown = sorted(set(extracted_data) - set(FIELDS) - METADATA)
    errors += [{"code": "UNSUPPORTED_FIELD", "field": f, "message": f"{f} is not part of the ECN schema."}
               for f in unknown]
    try:
        ECNFields(**fields)
    except ValidationError as error:
        errors += [{"code": "INVALID_FIELD", "field": str(e["loc"][0]), "message": e["msg"]}
                   for e in error.errors()]
    if not errors:
        old, new = fields["old_revision"], fields["new_revision"]
        if old is not None and old == new:
            errors.append({"code": "SAME_REVISION", "field": "new_revision",
                           "message": "Old and new revision are the same."})
        start, end = fields["effective_week"], fields["use_up_end_week"]
        if start is not None and end is not None and start > end + 1:
            errors.append({"code": "DATE_CONFLICT", "field": "effective_week",
                           "message": f"No revision is permitted between use-up end W{end} and effective week W{start}."})

    missing = identify_missing_fields(extracted_data)
    ambiguous = identify_ambiguous_fields(extracted_data)
    conflicts = [c for c in extracted_data.get("conflicts", []) if extracted_data.get(c["field"]) is None]
    if member1_validate and not errors and not missing and not ambiguous and not conflicts:
        errors += member1_validate(fields)

    if errors:
        status = "INVALID"
    elif missing:
        status = "INSUFFICIENT_DATA"
    elif ambiguous or conflicts:
        status = "NEEDS_REVIEW"
    else:
        status = "VALID"
    return {
        "validation_status": status,
        "missing_fields": missing,
        "ambiguous_fields": ambiguous,
        "validation_errors": errors,
        "conflicts": conflicts,
        "requires_human_review": not human_confirmed,
        "ready_for_planning": status == "VALID" and human_confirmed,
    }


# Bookkeeping keys an extraction record carries beside the ECN fields.
METADATA = {"source_document", "extraction_confidence", "missing_fields", "ambiguous_fields", "conflicts",
            "unsupported_values", "evidence", "requires_human_review", "extraction_source", "provider_error"}
