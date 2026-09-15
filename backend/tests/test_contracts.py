"""Contract integrity tests: Pydantic models must round-trip sample payloads that
validate against contracts/*.schema.json.

Run: python -m pytest backend/tests -q
"""

import jsonschema
import pytest

from app.schemas.common import CONTRACTS_DIR
from app.schemas.documents import DocumentUpload, OcrExtraction
from app.schemas.validation import ValidationResult, ValidationRule

SAMPLE_UPLOAD = {
    "tender_id": "GeM/2026/B/123456",
    "bid_id": "bid-2026-001",
    "supplier": "Acme Industries Pvt Ltd",
    "category": "Petroleum Products",
    "files": [
        {"file_name": "Technical_Bid.pdf", "file_type": "pdf", "doc_role": "technical_bid"},
        {"file_name": "EMD.pdf", "file_type": "pdf", "doc_role": "emd"},
    ],
}

SAMPLE_RULE = {
    "rule_id": "RULE-EMD-001",
    "tender_id": "GeM/2026/B/123456",
    "category": "EMD",
    "description": "EMD must be >= 2% of quoted value",
    "severity": "blocking",
    "element": "all",
    "target": "EMD_PERCENTAGE",
    "operator": ">=",
    "expected_value": 2.0,
}


def validate_against(schema_name: str, payload: dict) -> None:
    schema = jsonschema.Schema()
    path = CONTRACTS_DIR / schema_name
    with path.open("r", encoding="utf-8") as fh:
        import json
        schema = json.load(fh)
    jsonschema.validate(payload, schema)


def test_upload_contract_matches_schema():
    payload = DocumentUpload.model_validate(SAMPLE_UPLOAD).model_dump()
    validate_against("document_upload.schema.json", {k: v for k, v in payload.items() if v is not None})


def test_rule_contract_matches_schema():
    payload = ValidationRule.model_validate(SAMPLE_RULE).model_dump()
    validate_against("validation_rule.schema.json", {k: v for k, v in payload.items() if v is not None})


def test_ocr_extraction_roundtrip():
    payload = {
        "request_id": "req-1", "tender_id": "T1", "bid_id": "B1", "status": "completed",
        "documents": [{
            "file_id": "f1", "doc_role": "technical_bid", "meta": {"ocr_engine": "paddleocr"},
            "pages": [{
                "page_no": 1, "full_text": "EMD 2%",
                "text_blocks": [{"block_id": "b1", "text": "EMD 2%", "conf": 0.99, "bbox": [0, 0, 100, 20], "block_type": "body"}],
                "tables": [], "images": [],
            }],
        }],
    }
    OcrExtraction.model_validate(payload)


def test_validation_result_roundtrip():
    payload = {
        "request_id": "req-1", "tender_id": "T1", "bid_id": "B1", "generated_at": "2026-09-16T00:00:00Z",
        "results": [{"rule_id": "RULE-EMD-001", "status": "pass", "confidence": 0.98}],
        "overall_status": "COMPLIANT",
        "score": {"pass": 1, "fail": 0, "warn": 0, "total": 1, "compliance_pct": 100.0},
    }
    ValidationResult.model_validate(payload)