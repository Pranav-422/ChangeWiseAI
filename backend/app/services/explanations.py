"""Explanations and their verification records. The text and the verdict come from Member 3's AI modules."""
import json

from member3.ai.explanation_generator import generate_explanation
from member3.ai.fallback_templates import SECTIONS
from member3.database.repositories import records
from member3.services import audit_service, planning_service

from ..core.database import acting, read, transaction
from ..core.errors import not_found
from .engines import engines, get_provider

TEMPLATE_ONLY = "NOT_APPLICABLE"  # templates are filled from engine facts, so there is no AI text to verify


def store(db, subject_type, subject_id, explanation, user_name):
    explanation_id = records.new_id("EXPL")
    db.execute("INSERT INTO explanation_records (explanation_id, subject_type, subject_id, label, source, content, created_by) "
               "VALUES (?,?,?,?,?,?,?)", [explanation_id, subject_type, subject_id, explanation["label"],
                                          explanation["source"], json.dumps(explanation, ensure_ascii=False), user_name])
    verification = explanation["verification"]
    db.execute("INSERT INTO explanation_verifications VALUES (?,?,?)",
               [explanation_id, verification["status"] if verification else TEMPLATE_ONLY,
                json.dumps(verification, ensure_ascii=False) if verification else None])
    return explanation_id


def _view(row):
    content = json.loads(row["content"])
    ordered = [t for t in SECTIONS if t in content["sections"]]
    draft = content.get("draft")
    return {"explanation_id": row["explanation_id"], "subject_type": row["subject_type"],
            "subject_id": row["subject_id"], "label": row["label"], "source": row["source"],
            "sections": [{"title": t, "text": content["sections"][t]} for t in ordered],
            "draft": [{"title": t, "text": x} for t, x in draft.items()] if draft else None,
            "warning": content["warning"], "facts": content["facts"],
            "verification_status": row["status"], "verification": row["detail"] and json.loads(row["detail"]),
            "created_at": row["created_at"]}


_SELECT = ("SELECT e.*, v.status, v.detail FROM explanation_records e JOIN explanation_verifications v "
           "USING (explanation_id) ")


def get(explanation_id):
    with read() as db:
        row = db.execute(_SELECT + "WHERE explanation_id = ?", [explanation_id]).fetchone()
    if row is None:
        raise not_found(f"Explanation {explanation_id}")
    return _view(row)


def latest(subject_type, subject_id):
    with read() as db:
        row = db.execute(_SELECT + "WHERE subject_type = ? AND subject_id = ? ORDER BY e.created_at DESC LIMIT 1",
                         [subject_type, subject_id]).fetchone()
    return _view(row) if row else None


def generate(run, user):
    """A new explanation of a stored run. The run itself is not touched."""
    from . import planning  # planning stores the first explanation of a run through this module
    decided = planning.summary(run["run_id"])["approval"]
    facts = planning_service.facts_for(run, approved=bool(decided and decided["decision"] == "APPROVED"))
    explanation = generate_explanation(facts, get_provider())
    with acting(user.user_id), transaction() as db:
        explanation_id = store(db, "RUN", run["run_id"], explanation, user.name)
        audit_service.append(db, "EXPLANATION_GENERATED", run["run_id"], user, {
            "explanation_id": explanation_id, "label": explanation["label"], "source": explanation["source"],
            "verification": explanation["verification"]})
    return get(explanation_id)


def for_what_if(outcome, run, data):
    """Explains a scenario's own best plan. A constrained request is explained by the comparison text instead."""
    member1, _ = engines()
    baseline = member1.baseline(data)
    facts = planning_service.facts_for({
        "run_id": outcome["parameters"]["scenario_id"], "dataset": data, "result": outcome["result"],
        "context": {"baseline": baseline, "exceptions": member1.exceptions(data, baseline), "bom": run["context"]["bom"]}})
    return generate_explanation(facts, get_provider())
