"""Rules admin endpoint (Phase P4).

- GET /rules -> every validation_rule row for the reference tender (contract 4),
  including the `enabled` flag so the admin matrix can simulate toggling rules
  without rewriting rule-pack code.
"""

from fastapi import APIRouter, Query

from app.core import db
from app.core.config import settings
from app.schemas.common import ApiEnvelope

router = APIRouter(tags=["rules"])


@router.get("/rules", response_model=ApiEnvelope)
async def get_rules(tender_id: str | None = Query(None)) -> ApiEnvelope:
    """Return the full rule pack for a tender (defaults to the demo tender)."""
    rules = db.list_rules(tender_id or settings.demo_tender_id)
    return ApiEnvelope(
        status="ok",
        request_id="",
        data={"tender_id": tender_id or settings.demo_tender_id, "rules": rules},
    )