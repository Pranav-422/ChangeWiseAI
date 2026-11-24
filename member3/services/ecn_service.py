"""ECN intake: extract, review, edit, confirm. Only a human confirmation makes an ECN plannable."""
import hashlib

from ..ai.ecn_extractor import FIELDS, extract_ecn_fields, validate_extracted_ecn
from ..application.access_control import require
from ..database.connection import transaction
from ..database.repositories import records
from . import audit_service


class NotReady(ValueError):
    pass


def _validate(extraction, fields, member1, dataset, confirmed=False):
    merged = {**extraction, **fields}
    return validate_extracted_ecn(merged, lambda f: member1.validate_ecn(f, dataset), confirmed)


def create_review(text, scenario_id, member1, user, provider=None, source=None):
    require(user, "SUBMIT_ECN")
    extraction = extract_ecn_fields(text, provider, source)
    return _store(extraction, text, scenario_id, member1, user)


def create_manual_review(scenario_id, member1, user):
    """Manual entry when no document can be read: every field starts empty."""
    require(user, "SUBMIT_ECN")
    extraction = {**{f: None for f in FIELDS}, "source_document": "manual entry", "ambiguous_fields": [],
                  "conflicts": [], "unsupported_values": [], "evidence": {}, "extraction_source": "manual",
                  "provider_error": None, "extraction_confidence": 0.0, "requires_human_review": True,
                  "missing_fields": list(FIELDS)}
    return _store(extraction, "", scenario_id, member1, user)


def _store(extraction, text, scenario_id, member1, user):
    fields = {f: extraction[f] for f in FIELDS}
    review_id = records.new_id("ECNR")
    validation = _validate(extraction, fields, member1, member1.load_dataset(scenario_id))
    digest = hashlib.sha256(text.encode()).hexdigest()
    with transaction() as db:
        records.insert(db, "ecn_reviews", review_id=review_id, scenario_id=scenario_id, document_text=text,
                       document_hash=digest, extraction=extraction, fields=fields, validation=validation,
                       status="NEEDS_REVIEW", created_by=user.name, created_at=records.now())
        audit_service.append(db, "ECN_RECEIVED", review_id, user, {
            "scenario_id": scenario_id, "document_hash": digest, "source": extraction["extraction_source"],
            "provider_error": extraction["provider_error"], "validation": validation["validation_status"]})
    return review_id


def get_review(review_id):
    with transaction() as db:
        return records.get(db, "ecn_reviews", review_id=review_id)


def latest_review(scenario_id, status=None):
    where = {"scenario_id": scenario_id, **({"status": status} if status else {})}
    with transaction() as db:
        return records.find(db, "ecn_reviews", **where)


def update_fields(review_id, fields, member1, user):
    """Planner corrections. The original extraction is kept unchanged beside them."""
    require(user, "SUBMIT_ECN")
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise ValueError(f"Unknown ECN fields: {', '.join(sorted(unknown))}")
    with transaction() as db:
        review = records.get(db, "ecn_reviews", review_id=review_id)
        if review["status"] == "CONFIRMED":
            raise NotReady("A confirmed ECN cannot be edited; start a new review.")
        new = {**review["fields"], **fields}
        changed = {f: {"from": review["fields"][f], "to": new[f]} for f in FIELDS if review["fields"][f] != new[f]}
        validation = _validate(review["extraction"], new, member1, member1.load_dataset(review["scenario_id"]))
        records.update(db, "ecn_reviews", "review_id", review_id, fields=new, validation=validation)
        if changed:
            audit_service.append(db, "ECN_EDITED", review_id, user, {"changes": changed})
    return validation


def confirm(review_id, member1, user):
    """Final submission. Validates again at this moment, so nothing stale gets through."""
    require(user, "SUBMIT_ECN")
    with transaction() as db:
        review = records.get(db, "ecn_reviews", review_id=review_id)
        if review["status"] == "CONFIRMED":
            raise NotReady("This ECN is already confirmed.")
        validation = _validate(review["extraction"], review["fields"], member1,
                               member1.load_dataset(review["scenario_id"]), confirmed=True)
        if not validation["ready_for_planning"]:
            raise NotReady(f"ECN is {validation['validation_status']}; it cannot be submitted.")
        records.update(db, "ecn_reviews", "review_id", review_id, validation=validation, status="CONFIRMED",
                       confirmed_by=user.name, confirmed_at=records.now())
        audit_service.append(db, "ECN_CONFIRMED", review_id, user, {"fields": review["fields"]})
    return validation
