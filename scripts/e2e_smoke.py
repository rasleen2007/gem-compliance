"""Phase P1 end-to-end smoke test (no network needed).

Builds two synthetic PDFs and pushes them through the real FastAPI upload →
OCR+layout → NLP → rules pipeline, then verifies expected compliance verdicts.

Run (from repo root or anywhere):
    python scripts/e2e_smoke.py

Expected (asserted):
    compliant PDF  -> overall_status COMPLIANT + 7 seeded rules evaluated
    discrepant PDF -> overall_status DISCREPANT with multiple fails
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0] / ".." / "backend"))

import pymupdf  # PyMuPDF
from fastapi.testclient import TestClient

from app.main import app
from app.core import db

PASS_TEXT = """GeM Tender Technical And Financial Bid
Supplier GSTIN: 27AAPCA0405F1Z4
PAN No. AABTG1234C
Certificate Validity: The GST Registration Certificate is valid till 2027-03-31.
Date of Incorporation: 2018-04-12
Financial Year 2023-24 Turnover Rs. 2,50,00,000
Financial Year 2022-23 Turnover Rs. 1,80,00,000
EMD of Rs. 75,000 by way of Bank Guarantee.
Itemized Price Breakup attached below."""

FAIL_TEXT = """GeM Tender Technical And Financial Bid
Supplier GST Registration is pending; Tax ID awaited.
Certificate Validity: GST Registration Certificate expired on 2025-11-30.
Date of Incorporation: 2021-09-15
Financial Year 2023-24 Turnover Rs. 25,00,000
EMD of Rs. 10,000 deposited as Fixed Deposit.
No detailed schedule attached."""

EXPECTED_RESULTS = 7  # RULE-EMD-001, RULE-DOC-001..003, RULE-DATE-001..002, RULE-FIN-001


def make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    doc.save(str(path))
    doc.close()


def run_case(client: TestClient, name: str, text: str) -> dict:
    pdf = Path("tmp_smoke.pdf")
    make_pdf(pdf, text)

    with pdf.open("rb") as fh:
        resp = client.post("/api/v1/upload",
                           files={"file": (f"{name}.pdf", fh, "application/pdf")},
                           data={"tender_id": "GeM/2026/B/123456", "bid_id": f"smoke-{name}",
                                 "supplier": "Acme Industries Pvt Ltd", "category": "Petroleum Products",
                                 "doc_role": "technical_bid"})
    pdf.unlink(missing_ok=True)
    assert resp.status_code == 202, resp.text
    envelope = resp.json()
    request_id = envelope["data"]["request_id"]
    assert envelope["status"] == "accepted"

    for _ in range(80):  # poll up to ~20s
        job = client.get(f"/api/v1/jobs/{request_id}").json()["data"]
        if job["status"] != "running":
            break
        time.sleep(0.25)

    assert job["status"] == "done", json.dumps(job, indent=2)
    result = job["result"]
    assert len(result["results"]) == EXPECTED_RESULTS, result["results"]
    return job


def main() -> int:
    db.init_db()
    with TestClient(app) as client:
        passed = run_case(client, "pass", PASS_TEXT)
        failed = run_case(client, "fail", FAIL_TEXT)
        dashboard_pass = client.get("/api/v1/dashboard/smoke-pass").json()["data"]
        dashboard_fail = client.get("/api/v1/dashboard/smoke-fail").json()["data"]

    def status_summary(job: dict) -> list[str]:
        return [f"{r['rule_id']}={r['status']}" for r in job["result"]["results"]]

    print("\n=== PASS CASE ===")
    print(json.dumps(passed["result"], indent=2))
    print("summary:", status_summary(passed))
    print("\n=== FAIL CASE ===")
    print(json.dumps(failed["result"], indent=2))
    print("summary:", status_summary(failed))

    assert passed["result"]["overall_status"] == "COMPLIANT", "pass case should be COMPLIANT"
    assert failed["result"]["overall_status"] == "DISCREPANT", "fail case should be DISCREPANT"
    assert dashboard_pass["status"] == "COMPLIANT"
    assert dashboard_fail["status"] == "DISCREPANT"
    assert dashboard_fail["issues"], "fail case dashboard must surface critical issues"
    assert dashboard_pass["score"]["compliance_pct"] == 100.0
    assert any(item["stage"] == "nlp" for item in dashboard_pass["timeline"]), "timeline must include NLP stage"

    print("\nPASS CASE  ->", passed["result"]["overall_status"])
    print("FAIL CASE  ->", failed["result"]["overall_status"])
    print("DASHBOARD pass ->", dashboard_pass["status"],
          "| issues:", len(dashboard_pass["issues"]))
    print("DASHBOARD fail ->", dashboard_fail["status"],
          "| issues:", len(dashboard_fail["issues"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())