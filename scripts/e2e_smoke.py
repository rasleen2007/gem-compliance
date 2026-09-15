"""Phase P0 end-to-end smoke test (no network needed).

Builds a synthetic PDF with an EMD clause, uploads it through the real FastAPI
upload route, polls the job, and prints the validation_result.

Run (from repo root or anywhere):
    python scripts/e2e_smoke.py

Expected: two documents (pass + fail) each showing status=done, result with
RULE-EMD-001 verdict, evidence, compliance_pct, and overall_status.
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

PASS_TEXT = ("SECTION 5.2 EARNEST MONEY DEPOSIT\n"
             "The bidder shall furnish EMD of Rs. 75,000 by way of Bank Guarantee\n"
             "along with the bid. The Earnest Money Deposit must remain valid for 90 days.")
FAIL_TEXT = ("SECTION 5.2 EARNEST MONEY DEPOSIT\n"
             "The bidder has deposited a Fixed Deposit of Rs. 10,000 against EMD.\n"
             "No separate Earnest Money instrument is being furnished.")


def make_pdf(path: Path, text: str) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=10)
    doc.save(str(path))
    doc.close()


def run_case(client: TestClient, name: str, text: str) -> dict:
    pdf = Path(f"reference/../tmp_{name}.pdf") if False else Path("tmp_smoke.pdf")
    make_pdf(pdf, text)

    with pdf.open("rb") as fh:
        resp = client.post("/api/v1/upload",
                           files={"file": (f"{name}.pdf", fh, "application/pdf")},
                           data={"tender_id": "GeM/2026/B/123456", "bid_id": f"smoke-{name}",
                                 "supplier": "Acme Industries Pvt Ltd", "category": "Petroleum Products",
                                 "doc_role": "technical_bid"})
    assert resp.status_code == 202, resp.text
    envelope = resp.json()
    request_id = envelope["data"]["request_id"]
    assert envelope["status"] == "accepted"

    for _ in range(60):  # poll up to ~15s
        job = client.get(f"/api/v1/jobs/{request_id}").json()["data"]
        if job["status"] != "running":
            break
        time.sleep(0.25)

    assert job["status"] == "done", json.dumps(job, indent=2)
    pdf.unlink(missing_ok=True)
    return job


def main() -> int:
    with TestClient(app) as client:
        db.init_db()
        passed = run_case(client, "pass", PASS_TEXT)
        failed = run_case(client, "fail", FAIL_TEXT)

    print("\n=== PASS CASE ===")
    print(json.dumps(passed["result"], indent=2))
    print("\n=== FAIL CASE ===")
    print(json.dumps(failed["result"], indent=2))
    print("\nPASS CASE  ->", passed["result"]["overall_status"][0])
    print("FAIL CASE  ->", failed["result"]["overall_status"][0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())