"""GET /dashboard/{bid_id} — aggregate compliance_dashboard (contract 6) for the UI.

Composes the payload from SQLite: bid header, per-document stage statuses,
seeded rule scores + category breakdown, critical issues with evidence, and the
pipeline timeline. The assembled dict is validated against the Pydantic
ComplianceDashboard model before returning, so the frontend receives an exact
contract-6 shape.
"""

import json

from fastapi import APIRouter, HTTPException, Path

from app.core import db
from app.schemas.common import ApiEnvelope
from app.schemas.dashboard import ComplianceDashboard

router = APIRouter(tags=["dashboard"])

PRIORITY = {"fail": 0, "warn": 1, "error": 2, "skip": 3, "pass": 4}


def _stage_label(stage: str) -> str:
    return {"ocr": "ocr", "nlp": "nlp", "validation": "validation", "upload": "upload"}.get(stage, stage)


@router.get("/dashboard/{bid_id}", response_model=ApiEnvelope)
async def get_dashboard(bid_id: str = Path(...)) -> ApiEnvelope:
    bid = db.get_bid(bid_id)
    if bid is None:
        raise HTTPException(status_code=404, detail=ApiEnvelope(
            status="error", request_id="",
            error={"code": "BID_NOT_FOUND", "message": "No bid with that bid_id"}).model_dump())

    document_rows = db.get_documents(bid_id)
    result_rows = db.get_rule_results(bid_id)
    event_rows = db.get_events_by_bid(bid_id)
    adjudication = db.get_adjudication(bid_id)

    # --- score --------------------------------------------------------------
    counts = {"pass": 0, "fail": 0, "warn": 0, "skip": 0, "error": 0}
    for row in result_rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    total = len(result_rows)
    score = {**counts, "total": total,
             "compliance_pct": round(counts["pass"] / total * 100, 1) if total else 0.0}

    # --- category breakdown --------------------------------------------------
    categories: dict[str, dict] = {}
    for row in result_rows:
        cat = row.get("category") or "General"
        bucket = categories.setdefault(cat, {"category": cat, "pass": 0, "fail": 0, "warn": 0, "total": 0})
        bucket[row["status"]] = bucket.get(row["status"], 0) + 1
        bucket["pass"] = sum(1 for r in result_rows if (r.get("category") or "General") == cat and r["status"] == "pass")
        bucket["fail"] = sum(1 for r in result_rows if (r.get("category") or "General") == cat and r["status"] == "fail")
        bucket["warn"] = sum(1 for r in result_rows if (r.get("category") or "General") == cat and r["status"] == "warn")
        bucket["total"] += 1
    category_breakdown = sorted(categories.values(), key=lambda c: c["category"])
    for bucket in category_breakdown:
        bucket["pass"] = sum(1 for r in result_rows
                             if (r.get("category") or "General") == bucket["category"] and r["status"] == "pass")
        bucket["fail"] = sum(1 for r in result_rows
                             if (r.get("category") or "General") == bucket["category"] and r["status"] == "fail")
        bucket["warn"] = sum(1 for r in result_rows
                             if (r.get("category") or "General") == bucket["category"] and r["status"] == "warn")
        bucket["total"] = sum(1 for r in result_rows if (r.get("category") or "General") == bucket["category"])

    # --- document states ------------------------------------------------------
    documents = [{
        "file_id": row["file_id"], "file_name": row["file_name"],
        "doc_role": row["doc_role"],
        "stage": row["stage"] if row["stage"] != "parsed" else "parsed",
        "status": row["stage_status"],
    } for row in document_rows]

    # --- critical issues ------------------------------------------------------
    issues = []
    for row in sorted(result_rows, key=lambda r: PRIORITY.get(r["status"], 5)):
        if row["status"] not in ("fail", "warn", "error"):
            continue
        evidence: dict = {}
        try:
            evidence = json.loads(row.get("evidence") or "{}")
        except json.JSONDecodeError:  # noqa: S110
            pass
        source_span = evidence.get("source_span") or {}
        issues.append({
            "rule_id": row["rule_id"],
            "category": row.get("category") or "General",
            "severity": row.get("severity") or "advisory",
            "status": row["status"],
            "summary": row.get("description") or row.get("reason") or row["rule_id"],
            "evidence": evidence.get("found"),
            "source_span": source_span if source_span else None,
            "suggested_action": row.get("suggested_action", "manual_review"),
        })

    # --- pipeline timeline -----------------------------------------------------
    timeline = [{
        "stage": _stage_label(row["stage"]), "status": row["status"],
        "ts": row["ts"], "runtime_ms": row.get("runtime_ms"), "message": row.get("message"),
    } for row in event_rows]

    payload = {
        "tender_id": bid["tender_id"],
        "bid_id": bid["bid_id"],
        "supplier": bid["supplier"],
        "category": bid.get("category") or "",
        "status": bid["overall_status"],
        "score": score,
        "category_breakdown": category_breakdown,
        "documents": documents,
        "issues": issues,
        "timeline": timeline,
        "adjudication": adjudication,
    }

    # contract-6 gate
    validated = ComplianceDashboard.model_validate(payload)
    return ApiEnvelope(status="ok", request_id=bid["request_id"],
                       data=validated.model_dump(by_alias=True, exclude_none=True))