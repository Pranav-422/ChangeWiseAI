"""ECN intake. Document text and fields are for engineering roles; every write needs SUBMIT_ECN."""
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, Query, UploadFile

from ...core.config import get_settings
from ...core.errors import ApiError
from ...schemas import api
from ...security.auth import Principal, needs
from ...services import ecn as service

router = APIRouter(prefix="/ecn", tags=["ecn"])
Reader = Annotated[Principal, needs("VIEW_DOCUMENTS")]
Submitter = Annotated[Principal, needs("SUBMIT_ECN")]


@router.post("/upload", response_model=api.Document, status_code=201)
def upload(user: Submitter, change_id: Annotated[str, Form()], scenario: Annotated[str, Form()] = "base",
           file: Annotated[Optional[UploadFile], File()] = None,
           text: Annotated[Optional[str], Form(max_length=200_000)] = None):
    """A PDF or text file, or pasted text."""
    if file is not None:
        content = file.file.read(get_settings().max_upload_bytes + 1)
        return service.upload(change_id, scenario, file.filename or "document", content, user)
    if text and text.strip():
        return service.upload(change_id, scenario, "pasted-text.txt", text.encode(), user, "TEXT")
    raise ApiError(422, "EMPTY_DOCUMENT", "Choose a file or paste the text.")


@router.get("/samples", response_model=list[str])
def samples(user: Reader):
    return service.samples()


@router.post("/samples", response_model=api.Document, status_code=201)
def upload_sample(body: api.SampleUpload, user: Submitter):
    return service.upload_sample(body.change_id, body.scenario, body.sample_id, user)


@router.post("/manual", response_model=api.Review, status_code=201)
def manual(body: api.ManualReview, user: Submitter):
    return service.create_manual(body.change_id, body.scenario, user)


@router.get("/documents/{document_id}/url", response_model=api.SignedUrl)
def document_url(document_id: str, user: Reader):
    return service.signed_url(document_id)


@router.post("/{document_id}/extract", response_model=api.Review)
def extract(document_id: str, user: Submitter):
    return service.extract(document_id, user)


@router.get("", response_model=api.ReviewList)
def list_reviews(user: Reader, limit: Annotated[int, Query(ge=1, le=100)] = 25, offset: Annotated[int, Query(ge=0)] = 0):
    return service.list_reviews(limit, offset)


@router.get("/{review_id}", response_model=api.Review)
def review(review_id: str, user: Reader):
    return service.review(review_id)


@router.patch("/{review_id}", response_model=api.Review)
def update(review_id: str, body: api.EcnFields, user: Submitter):
    return service.update(review_id, body.model_dump(exclude_unset=True), user)


@router.post("/{review_id}/validate", response_model=api.Review)
def validate(review_id: str, user: Submitter):
    return service.validate(review_id, user)


@router.post("/{review_id}/confirm", response_model=api.Review)
def confirm(review_id: str, user: Submitter):
    return service.confirm(review_id, user)
