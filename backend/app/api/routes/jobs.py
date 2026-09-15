"""GET /jobs/{request_id} — poll pipeline status + timeline for a verification job."""

from fastapi import APIRouter, HTTPException, Path

from app.schemas.common import ApiEnvelope
from app.services import orchestrator

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{request_id}", response_model=ApiEnvelope)
async def get_job(request_id: str = Path(...)) -> ApiEnvelope:
    job = orchestrator.get_job(request_id)
    if job is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "JOB_NOT_FOUND", "message": "No job with that request_id"}).model_dump())
    return ApiEnvelope(status="ok", request_id=request_id, data=job.to_dict())