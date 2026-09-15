"""GET /jobs/{request_id} — pipeline status + timeline (polled by frontend)."""

from fastapi import APIRouter, Path

from app.schemas.common import ApiEnvelope

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{request_id}", response_model=ApiEnvelope)
async def get_job(request_id: str = Path(...)) -> ApiEnvelope:
    raise NotImplementedError("implement in MVP Phase P1")