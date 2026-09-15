"""Validation endpoints.

- POST /validate/{request_id} -> run rules; body: nothing (uses stored parsing).
- GET  /validate/{request_id}/result -> ApiEnvelope{data: validation_result}.
Rules come from database_schema.seed_rules, validated against contract 4.
"""

from fastapi import APIRouter, Path

from app.schemas.common import ApiEnvelope

router = APIRouter(tags=["validation"])


@router.post("/validate/{request_id}", response_model=ApiEnvelope)
async def run_validation(request_id: str = Path(...)) -> ApiEnvelope:
    raise NotImplementedError("implement in MVP Phase P1")


@router.get("/validate/{request_id}/result", response_model=ApiEnvelope)
async def get_validation_result(request_id: str = Path(...)) -> ApiEnvelope:
    raise NotImplementedError("implement in MVP Phase P1")