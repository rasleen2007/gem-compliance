"""POST /upload — accept role-tagged bid documents, kick off async pipeline.

Contract: documents satisfies contract 1 (document_upload).
Response: ApiEnvelope{status: accepted, data: document_upload}.
TODO implement: multipart ingestion, sha256/dedup, storage.write, orchestrator.start.
"""

from fastapi import APIRouter, UploadFile, File

from app.schemas.common import ApiEnvelope
from app.schemas.documents import DocumentUpload

router = APIRouter(tags=["upload"])


@router.post("/upload", response_model=ApiEnvelope)
async def upload(files: list[UploadFile] = File(...)) -> ApiEnvelope:
    # TODO: map form fields (tender_id, bid_id, supplier, category, doc_roles)
    # into DocumentUpload, persist, then orchestrator.start(...). Return 202.
    raise NotImplementedError("implement in MVP Phase P1")


@router.get("/upload/options", response_model=ApiEnvelope)
async def upload_options() -> ApiEnvelope:
    """Return allowed doc_role values and accepted extensions for the UI."""
    raise NotImplementedError("implement in MVP Phase P1")