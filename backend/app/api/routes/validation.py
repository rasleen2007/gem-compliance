"""Validation endpoints (Phase P1).

- POST /validate/{request_id}         -> (re)build parsed doc if needed, evaluate.
- GET  /validate/{request_id}/result  -> current validation_result (contract 5).
"""

from fastapi import APIRouter, HTTPException, Path

from app.core import db
from app.schemas.common import ApiEnvelope
from app.schemas.documents import ParsedBundle
from app.schemas.validation import ValidationResult
from app.services import orchestrator

router = APIRouter(tags=["validation"])


def _job_or_404(request_id: str):
    job = orchestrator.get_job(request_id)
    if job is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "JOB_NOT_FOUND", "message": "No job with that request_id"}).model_dump())
    return job


@router.post("/validate/{request_id}", response_model=ApiEnvelope)
async def run_validation(request_id: str = Path(...)) -> ApiEnvelope:
    job = _job_or_404(request_id)

    if job.parsed is None:
        if job.extraction is None and not job.documents:
            raise HTTPException(status_code=409, detail=ApiEnvelope(
                status="error", request_id=request_id,
                error={"code": "NOT_READY", "message": "No document to validate"}).model_dump())
        # Best-effort rebuild from the stored upload
        paths = {d["file_id"]: d["store_path"] for d in job.documents}
        parsed = orchestrator.build_parsed(job, paths)
        job.parsed = ParsedBundle.model_validate(parsed).model_dump()

    job.result = orchestrator.evaluate(job)
    job.result = ValidationResult.model_validate(job.result).model_dump()
    db.insert_rule_results(job.bid_id, job.result.get("results", []))
    db.update_bid_status(job.bid_id, job.result["overall_status"])
    job.stage = orchestrator.Stage.VALIDATION_COMPLETE

    return ApiEnvelope(status="ok", request_id=request_id, data=job.result)


@router.get("/validate/{request_id}/result", response_model=ApiEnvelope)
async def get_validation_result(request_id: str = Path(...)) -> ApiEnvelope:
    job = _job_or_404(request_id)
    if job.result is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "NO_RESULT", "message": "Validation not run yet"}).model_dump())
    return ApiEnvelope(status="ok", request_id=request_id, data=job.result)