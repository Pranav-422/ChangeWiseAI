"""ECN intake: private document, extraction, human review. Member 3 extracts, Member 1 validates, a person confirms."""
import hashlib
import re
from pathlib import PurePosixPath

from member1.engine import ROOT as MEMBER1_ROOT
from member3.ai.ecn_extractor import ExtractionFailure, extract_pdf_text, extract_plain_text
from member3.application.access_control import require
from member3.database.repositories import records
from member3.services import audit_service, ecn_service

from ..core.config import get_settings
from ..core.database import acting, read, transaction
from ..core.errors import ApiError, not_found
from ..integrations import storage
from ..integrations.member1_postgres import change_of
from .change_service import scenario_key
from .engines import engines, get_provider

_SAMPLES = MEMBER1_ROOT / "documents" / "ecn_samples"
_KINDS = {".pdf": "application/pdf", ".txt": "text/plain"}
_DOCUMENT = ("document_id, change_id, scenario_id, source_kind, original_filename, mime_type, size_bytes, sha256, "
             "extraction_status, extraction_error, review_id, uploaded_by, uploaded_at, storage_path IS NOT NULL AS stored")


def _checked(filename, content):
    """The type comes from the content, never from the client's header."""
    name = re.sub(r"[^\w. ()-]", "_", PurePosixPath(filename.replace("\\", "/")).name)[-120:] or "document"
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in _KINDS:
        raise ApiError(415, "UNSUPPORTED_TYPE", "Upload a PDF or a plain text file.")
    if not content:
        raise ApiError(422, "EMPTY_DOCUMENT", "The file is empty.")
    if len(content) > get_settings().max_upload_bytes:
        raise ApiError(413, "TOO_LARGE", "The file is larger than 4 MB.")
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ApiError(415, "UNSUPPORTED_TYPE", "The file is not a PDF.")
    elif b"\x00" in content:
        raise ApiError(415, "UNSUPPORTED_TYPE", "The file is not plain text.")
    return name, _KINDS[suffix]


def upload(change_id, scenario, filename, content, user, kind="UPLOAD"):
    require(user, "SUBMIT_ECN")
    key = scenario_key(change_id, scenario)
    name, mime = _checked(filename, content)
    document_id, digest = records.new_id("DOC"), hashlib.sha256(content).hexdigest()
    path = f"{change_id}/{document_id}{PurePosixPath(name).suffix.lower()}"
    storage.put(path, content, mime)
    with acting(user.user_id), transaction() as db:
        db.execute("INSERT INTO document_metadata (document_id, change_id, scenario_id, source_kind, original_filename, "
                   "mime_type, size_bytes, sha256, storage_path) VALUES (?,?,?,?,?,?,?,?,?)",
                   [document_id, change_id, key, kind, name, mime, len(content), digest, path])
        audit_service.append(db, "DOCUMENT_STORED", document_id, user, {
            "change_id": change_id, "filename": name, "sha256": digest, "size_bytes": len(content)})
    return document(document_id)


def samples():
    """Member 1's ECN test documents."""
    return [p.stem for p in sorted(_SAMPLES.glob("*.pdf"))]


def upload_sample(change_id, scenario, sample_id, user):
    if sample_id not in samples():  # also keeps the path inside the folder
        raise not_found(f"Sample {sample_id}")
    return upload(change_id, scenario, f"{sample_id}.pdf", (_SAMPLES / f"{sample_id}.pdf").read_bytes(), user, "SAMPLE")


def document(document_id):
    with read() as db:
        row = db.execute(f"SELECT {_DOCUMENT} FROM document_metadata WHERE document_id = ?", [document_id]).fetchone()
    if row is None:
        raise not_found(f"Document {document_id}")
    return row


def signed_url(document_id):
    with read() as db:
        row = db.execute("SELECT storage_path FROM document_metadata WHERE document_id = ?", [document_id]).fetchone()
    if row is None or not row["storage_path"]:
        raise not_found(f"Document {document_id}")
    return {"url": storage.signed_url(row["storage_path"]), "expires_in": storage.SIGNED_URL_SECONDS}


def extract(document_id, user):
    require(user, "SUBMIT_ECN")
    with read() as db:
        row = db.execute("SELECT * FROM document_metadata WHERE document_id = ?", [document_id]).fetchone()
    if row is None:
        raise not_found(f"Document {document_id}")
    if row["review_id"]:
        return review(row["review_id"])
    content = storage.get(row["storage_path"])
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        raise ApiError(409, "DOCUMENT_ALTERED", "The stored document no longer matches its recorded hash.")
    try:
        text = (extract_pdf_text if row["mime_type"] == "application/pdf" else extract_plain_text)(content)
    except ExtractionFailure as error:
        with acting(user.user_id), transaction() as db:
            db.execute("UPDATE document_metadata SET extraction_status = 'FAILED', extraction_error = ? WHERE document_id = ?",
                       [str(error), document_id])
            audit_service.append(db, "EXTRACTION_FAILED", document_id, user, {"reason": str(error)})
        raise
    with acting(user.user_id):
        review_id = ecn_service.create_review(text, row["scenario_id"], engines()[0], user, get_provider(), row["original_filename"])
        with transaction() as db:
            db.execute("UPDATE document_metadata SET extraction_status = 'EXTRACTED', extraction_error = NULL, review_id = ? "
                       "WHERE document_id = ?", [review_id, document_id])
    return review(review_id)


def create_manual(change_id, scenario, user):
    key = scenario_key(change_id, scenario)
    with acting(user.user_id):
        review_id = ecn_service.create_manual_review(key, engines()[0], user)
    return review(review_id)


def list_reviews(limit, offset):
    with read() as db:
        rows = db.execute("SELECT r.review_id, r.scenario_id, r.status, r.fields, r.validation->>'validation_status' AS "
                          "validation_status, r.extraction->>'extraction_source' AS extraction_source, r.created_by, r.created_at, "
                          "r.confirmed_by, r.confirmed_at, d.document_id, d.original_filename FROM ecn_reviews r "
                          "LEFT JOIN document_metadata d USING (review_id) ORDER BY r.rowid DESC LIMIT ? OFFSET ?",
                          [limit, offset]).fetchall()
        failed = db.execute(f"SELECT {_DOCUMENT} FROM document_metadata WHERE review_id IS NULL "
                            "ORDER BY uploaded_at DESC LIMIT 20").fetchall()
        total = db.execute("SELECT count(*) AS n FROM ecn_reviews").fetchone()["n"]
    return {"items": [{**records._decode(r), "change_id": change_of(r["scenario_id"]),
                       "scenario_id": r["scenario_id"].partition("@")[0]} for r in rows],
            "unread_documents": failed, "total": total}


def review(review_id):
    try:
        found = ecn_service.get_review(review_id)
    except LookupError as error:
        raise not_found(f"Review {review_id}") from error
    with read() as db:
        row = db.execute(f"SELECT {_DOCUMENT} FROM document_metadata WHERE review_id = ?", [review_id]).fetchone()
        run = db.execute("SELECT run_id FROM planning_runs WHERE review_id = ? ORDER BY rowid DESC LIMIT 1", [review_id]).fetchone()
    return {**found, "change_id": change_of(found["scenario_id"]), "scenario_id": found["scenario_id"].partition("@")[0],
            "document": row, "latest_run_id": run and run["run_id"]}


def _known(review_id):
    review(review_id)


def update(review_id, fields, user):
    _known(review_id)
    with acting(user.user_id):
        ecn_service.update_fields(review_id, fields, engines()[0], user)
    return review(review_id)


def validate(review_id, user):
    """Runs the validation again on the current records, without changing a field."""
    return update(review_id, {}, user)


def confirm(review_id, user):
    _known(review_id)
    with acting(user.user_id):
        ecn_service.confirm(review_id, engines()[0], user)
    return review(review_id)
