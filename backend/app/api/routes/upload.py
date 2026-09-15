"""POST /upload — accept a role-tagged bid document, persist it, and kick off
the async verification pipeline.

Request (multipart/form-data): file + tender_id, bid_id, supplier, category, doc_role.
Response: ApiEnvelope{status: accepted, data: document_upload (contract 1)}.
"""

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core import db
from app.core.config import settings
from app.schemas.common import ApiEnvelope
from app.schemas.documents import DOC_ROLES, FILE_TYPES
from app.services import orchestrator
from app.services.storage import Storage

router = APIRouter(tags=["upload"])


def _error(code: str, message: str, status: int = 400) -> HTTPException:
    """Envelope-shaped HTTP error (matches contracts/api_envelope.schema.json)."""
    return HTTPException(status_code=status, detail=ApiEnvelope(
        status="error", request_id="", error={"code": code, "message": message}).model_dump())


def _clean_filename(filename: str | None) -> str:
    filename = (filename or "").strip()
    return filename or "bid_upload.pdf"


@router.post("/upload", response_model=ApiEnvelope, status_code=202)
async def upload(
    file: UploadFile = File(...),
    tender_id: str = Form(...),
    bid_id: str = Form(...),
    supplier: str = Form(...),
    category: str = Form(""),
    doc_role: str = Form("technical_bid"),
) -> ApiEnvelope:
    filename = _clean_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in settings.allowed_extensions or ext not in FILE_TYPES:
        raise _error("INVALID_FILE_TYPE",
                     f"Unsupported file type '{ext or 'none'}'; allowed: {', '.join(sorted(settings.allowed_extensions))}")
    if doc_role not in DOC_ROLES:
        raise _error("INVALID_DOC_ROLE", f"doc_role must be one of: {', '.join(DOC_ROLES)}")

    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise _error("FILE_TOO_LARGE", f"File exceeds {settings.max_upload_mb} MB limit", status=413)

    request_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    sha256 = hashlib.sha256(content).hexdigest()

    store = Storage(settings.upload_dir, settings.db_path)
    path = store.save(request_id, file_id, filename, content)

    db.init_db()
    db.insert_bid(request_id=request_id, bid_id=bid_id, tender_id=tender_id,
                  supplier=supplier, category=category)
    db.insert_document(file_id=file_id, bid_id=bid_id, file_name=filename, file_type=ext,
                       doc_role=doc_role, size_bytes=len(content), sha256=sha256,
                       store_path=str(path))

    job = orchestrator.create_job(
        request_id=request_id, bid_id=bid_id, tender_id=tender_id,
        supplier=supplier, category=category,
        documents=[{"file_id": file_id, "file_name": filename, "doc_role": doc_role,
                    "file_type": ext, "size_bytes": len(content), "sha256": sha256,
                    "store_path": str(path)}],
    )
    orchestrator.start(job)

    payload = {
        "request_id": request_id,
        "tender_id": tender_id,
        "bid_id": bid_id,
        "supplier": supplier,
        "category": category,
        "submitted_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": [{"file_id": file_id, "file_name": filename, "file_type": ext,
                   "size_bytes": len(content), "sha256": sha256, "doc_role": doc_role}],
    }
    return ApiEnvelope(status="accepted", request_id=request_id, data=payload)


@router.get("/upload/options", response_model=ApiEnvelope)
async def upload_options() -> ApiEnvelope:
    """Allowed doc roles and accepted extensions for the frontend upload form."""
    return ApiEnvelope(status="ok", request_id="", data={
        "doc_roles": DOC_ROLES,
        "file_types": sorted(settings.allowed_extensions),
        "max_upload_mb": settings.max_upload_mb,
    })