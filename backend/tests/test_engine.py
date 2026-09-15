"""Unit tests for the Phase P0 EMD rules engine (core_ai/rules)."""

import app  # noqa: F401 — injects repo root onto sys.path (app/__init__.py)

from core_ai.rules.engine import RuleEngine, _to_float
from core_ai.rules.rule_registry import RuleRegistry

RULE_EMD = {
    "rule_id": "RULE-EMD-001", "tender_id": "GeM/2026/B/123456", "category": "EMD",
    "description": "EMD must be at least 50,000 INR", "severity": "blocking",
    "element": "all", "target": "EMD_AMOUNT", "operator": ">=", "expected_value": "50000",
}


def _extraction(text: str, request_id: str = "req-1", bid_id: str = "bid-1") -> dict:
    return {
        "request_id": request_id, "tender_id": "GeM/2026/B/123456", "bid_id": bid_id,
        "status": "completed", "documents": [{
            "file_id": "f1", "doc_role": "technical_bid", "meta": {},
            "pages": [{"page_no": 1, "text_blocks": [
                {"block_id": "b0", "text": text, "conf": 1.0, "bbox": [0, 0, 100, 20],
                 "block_type": "body"}],
                "tables": [], "images": [], "full_text": text}],
        }],
    }


def _engine(text: str) -> RuleEngine:
    registry = RuleRegistry()
    registry.load_rules([RULE_EMD])
    return RuleEngine(registry=registry)


def test_amount_parser_lakh_and_crore():
    assert _to_float("50000", None) == 50_000
    assert _to_float("75,000", None) == 75_000
    assert _to_float("1.5", "lakh") == 150_000
    assert _to_float("2", "crore") == 20_000_000


def test_emd_passes_above_threshold():
    result = _engine("EMD of Rs. 75,000 furnished via Bank Guarantee.").evaluate(
        _extraction("EMD of Rs. 75,000 furnished via Bank Guarantee."), "GeM/2026/B/123456")
    rule = result["results"][0]
    assert rule["status"] == "pass"
    assert rule["evidence"]["found"]
    assert rule["evidence"]["source_span"]["page"] == 1
    assert result["overall_status"] == "COMPLIANT"
    assert result["score"]["compliance_pct"] == 100.0


def test_emd_fails_below_threshold():
    result = _engine("Earnest Money Deposit of INR 10,000 deposited.").evaluate(
        _extraction("Earnest Money Deposit of INR 10,000 deposited."), "GeM/2026/B/123456")
    rule = result["results"][0]
    assert rule["status"] == "fail"
    assert result["overall_status"] == "DISCREPANT"
    assert result["score"]["compliance_pct"] == 0.0


def test_emd_missing_warns_for_manual_review():
    result = _engine("The bidder is an MSME and is exempt from EMD due to a valid Udyam certificate.").evaluate(
        _extraction("The bidder is an MSME and is exempt from EMD due to a valid Udyam certificate."),
        "GeM/2026/B/123456")
    assert result["results"][0]["status"] == "warn"
    assert result["overall_status"] == "NEEDS_REVIEW"