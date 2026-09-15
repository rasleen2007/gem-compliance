"""GET /dashboard/{bid_id} — aggregate compliance_dashboard (contract 6) for the UI."""

from fastapi import APIRouter, Path

from app.schemas.common import ApiEnvelope

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/{bid_id}", response_model=ApiEnvelope)
async def get_dashboard(bid_id: str = Path(...)) -> ApiEnvelope:
    raise NotImplementedError("implement in MVP Phase P2")