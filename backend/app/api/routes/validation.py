"""Validation endpoints (Phase P0).

- POST /validate/{request_id}      -> (re)evaluate rules against extracted text.
- GET  /validate/{request_id}/result -> current validation_result (contract 5).
"""

from fastapi import APIRouter, HTTPException, Path

from app.core import db
from app.core.config import settings
from app.schemas.common import ApiEnvelope
from app.services import orchestrator
from core_ai.rules.engine import RuleEngine
from core_ai.rules.rule_registry import RuleRegistry

router = APIRouter(tags=["validation"])


@router.post("/validate/{request_id}", response_model=ApiEnvelope)
async def run_validation(request_id: str = Path(...)) -> ApiEnvelope:
    job = orchestrator.get_job(request_id)
    if job is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "JOB_NOT_FOUND", "message": "No job with that request_id"}).model_dump())
    if job.extraction is None:
        raise HTTPException(status_code=409, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "NOT_READY", "message": "Text extraction not finished yet"}).model_dump())

    rules = db.fetch_rules(job.tender_id)
    registry = RuleRegistry()
    registry.load_rules(rules)
    engine = RuleEngine(registry=registry, llm_enabled=settings.llm_enabled)
    job.result = engine.evaluate(job.extraction, job.tender_id)

    return ApiEnvelope(status="ok", request_id=request_id, data=job.result)


@router.get("/validate/{request_id}/result", response_model=ApiEnvelope)
async def get_validation_result(request_id: str = Path(...)) -> ApiEnvelope:
    job = orchestrator.get_job(request_id)
    if job is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "JOB_NOT_FOUND", "message": "No job with that request_id"}).model_dump())
    if job.result is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id=request_id,
            error={"code": "NO_RESULT", "message": "Validation not run yet"}).model_dump())
    return ApiEnvelope(status="ok", request_id=request_id, data=job.result)