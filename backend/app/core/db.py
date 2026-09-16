"""SQLite persistence layer (Phase P0).

Bootstrap: creates `data/sih_local.db` from database_schema/schema.sql on first
use (idempotent), seeds the demo rule pack (contract 4) if absent, and injects
three dashboard-ready demo bids (pass / fail / conflict) for live pitches.

All access goes through these helpers; the backend never talks to SQL directly
elsewhere. Contract rule rows are returned as dicts matching
`validation_rule.schema.json` (camelCase keys).
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app import REPO_ROOT
from app.core.config import settings

SCHEMA_FILE = REPO_ROOT / "database_schema" / "schema.sql"


def _connect() -> sqlite3.Connection:
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables + seed demo rules + demo bids. Safe to call repeatedly."""
    conn = _connect()
    try:
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        conn.executescript(schema)
        _seed_demo_rules(conn)
        _seed_demo_bids(conn)
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Writing
# --------------------------------------------------------------------------
def insert_bid(request_id: str, bid_id: str, tender_id: str, supplier: str,
               category: str, overall_status: str = "IN_PROGRESS") -> None:
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO bids
               (bid_id, tender_id, supplier, category, request_id, overall_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (bid_id, tender_id, supplier, category, request_id, overall_status),
        )
        conn.commit()
    finally:
        conn.close()


def update_bid_status(bid_id: str, status: str) -> None:
    conn = _connect()
    try:
        conn.execute("UPDATE bids SET overall_status = ? WHERE bid_id = ?", (status, bid_id))
        conn.commit()
    finally:
        conn.close()


def insert_document(file_id: str, bid_id: str, file_name: str, file_type: str,
                    doc_role: str, size_bytes: int, sha256: str,
                    store_path: str, stage: str = "uploaded", stage_status: str = "ok") -> None:
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO documents
               (file_id, bid_id, file_name, file_type, doc_role, size_bytes, sha256, store_path, stage, stage_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (file_id, bid_id, file_name, file_type, doc_role, size_bytes, sha256,
             store_path, stage, stage_status),
        )
        conn.commit()
    finally:
        conn.close()


def insert_pipeline_event(request_id: str, bid_id: str, stage: str, status: str,
                          ts: str, runtime_ms: int = 0, message: str = "") -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request_id, bid_id, stage, status, ts, runtime_ms, message),
        )
        conn.commit()
    finally:
        conn.close()


def update_document_stage(file_id: str, stage: str, stage_status: str = "ok") -> None:
    """Record a per-file pipeline outcome (e.g. a corrupt doc -> stage='failed')."""
    conn = _connect()
    try:
        conn.execute(
            "UPDATE documents SET stage = ?, stage_status = ? WHERE file_id = ?",
            (stage, stage_status, file_id),
        )
        conn.commit()
    finally:
        conn.close()


def insert_adjudication(bid_id: str, decision: str, officer: str = "",
                        comment: str = "", ts: str | None = None) -> None:
    """Record a reviewer decision for a bid (upsert: one adjudication per bid)."""
    conn = _connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO adjudications (bid_id, decision, officer, comment, ts)
               VALUES (?, ?, ?, ?, ?)""",
            (bid_id, decision, officer, comment,
             ts or datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def insert_rule_results(bid_id: str, results: list[dict]) -> None:
    """Replace a bid's evaluation results (a bid always has exactly one, latest run)."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM rule_results WHERE bid_id = ?", (bid_id,))
        for r in results:
            conn.execute(
                "INSERT INTO rule_results (bid_id, rule_id, status, evidence, reason, confidence, suggested_action)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (bid_id, r.get("rule_id"), r.get("status"),
                 json.dumps(r.get("evidence") or {}), r.get("reason"),
                 r.get("confidence"), r.get("suggested_action", "none")),
            )
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------
def fetch_rules(tender_id: str) -> list[dict]:
    """Rule rows as contract-4 dicts (camelCase keys), ordered by severity."""
    conn = _connect()
    try:
        order = "CASE severity WHEN 'blocking' THEN 0 WHEN 'mandatory' THEN 1 ELSE 2 END"
        rows = conn.execute(
            f"SELECT rule_id, tender_id, category, description, severity, element,"
            f" target, operator, expected_value, notes FROM validation_rules"
            f" WHERE tender_id = ? AND enabled = 1 ORDER BY {order}",
            (tender_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_rules(tender_id: str | None = None) -> list[dict]:
    """Every rule (enabled or not) for the reference tender, for the admin matrix."""
    conn = _connect()
    try:
        if tender_id:
            rows = conn.execute(
                """SELECT rule_id, tender_id, category, description, severity, element,
                          target, operator, expected_value, expression, notes, enabled
                   FROM validation_rules
                   WHERE tender_id = ?
                   ORDER BY CASE severity WHEN 'blocking' THEN 0
                            WHEN 'mandatory' THEN 1 ELSE 2 END, rule_id""",
                (tender_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT rule_id, tender_id, category, description, severity, element,
                          target, operator, expected_value, expression, notes, enabled
                   FROM validation_rules
                   ORDER BY CASE severity WHEN 'blocking' THEN 0
                            WHEN 'mandatory' THEN 1 ELSE 2 END, rule_id""",
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Dashboard reads (contract 6)
# ---------------------------------------------------------------------------
def get_bid(bid_id: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT bid_id, tender_id, supplier, category, request_id, overall_status, submitted_at"
            " FROM bids WHERE bid_id = ?", (bid_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_documents(bid_id: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT file_id, file_name, doc_role, stage, stage_status, size_bytes"
            " FROM documents WHERE bid_id = ?", (bid_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_rule_results(bid_id: str) -> list[dict]:
    """Rule results joined with rule metadata; failing/warning first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT rr.rule_id, rr.status, rr.evidence, rr.reason, rr.confidence,
                      rr.suggested_action, vr.category, vr.severity, vr.description, vr.element
               FROM rule_results rr
               LEFT JOIN validation_rules vr ON vr.rule_id = rr.rule_id
               WHERE rr.bid_id = ?
               ORDER BY CASE rr.status WHEN 'fail' THEN 0 WHEN 'warn' THEN 1
                        WHEN 'error' THEN 2 ELSE 3 END, rr.rule_id""",
            (bid_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_events_by_bid(bid_id: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT stage, status, ts, runtime_ms, message
               FROM pipeline_events
               WHERE bid_id = ? AND request_id = (
                   SELECT request_id FROM pipeline_events
                   WHERE bid_id = ? ORDER BY event_id DESC LIMIT 1)
               ORDER BY event_id""", (bid_id, bid_id)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_adjudication(bid_id: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT decision, officer, comment, ts FROM adjudications WHERE bid_id = ?",
            (bid_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_events(request_id: str) -> list[dict]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT stage, status, ts, runtime_ms, message FROM pipeline_events"
            " WHERE request_id = ? ORDER BY event_id", (request_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Seeding
# --------------------------------------------------------------------------
def _seed_demo_rules(conn: sqlite3.Connection) -> None:
    """Phase P1 demo rule pack for the reference tender (contract 4 values).

    Covers all five rule families: EMD amount, document presence (GSTIN/PAN),
    date comparison (certificate validity / incorporation), financial turnover,
    and multi-document identity cross-checking (Rule-XCHK).
    """
    threshold = settings.emd_threshold
    demo_rules = [
        # --- Rule-EMD: financial threshold on EMD amount -------------------
        ("RULE-EMD-001", "EMD", "blocking", "all", "EMD_AMOUNT", ">=", threshold,
         "Earnest Money Deposit (EMD) must be at least "
         f"{int(float(threshold)):,} INR"),
        # --- Rule-DOC: mandatory document presence --------------------------
        ("RULE-DOC-001", "Eligibility", "blocking", "all", "GSTIN", "exists", None,
         "Supplier GSTIN registration must be present"),
        ("RULE-DOC-002", "Eligibility", "mandatory", "all", "PAN", "exists", None,
         "Supplier PAN must be present"),
        ("RULE-DOC-003", "Financial", "advisory", "financial_bid", "table:PRICE_BREAKUP", "exists", None,
         "Itemized price breakup table must be attached"),
        # --- Rule-DATE: dates vs tender deadlines ---------------------------
        ("RULE-DATE-001", "Certificates", "mandatory", "certificates", "CERT_VALIDITY", "date_after", "2026-06-30",
         "Certificate/document validity must extend past the tender deadline (2026-06-30)"),
        ("RULE-DATE-002", "Eligibility", "advisory", "all", "INCORPORATION_DATE", "date_before", "2020-01-01",
         "Company incorporation date must precede 2020-01-01 (eligibility criterion)"),
        # --- Rule-FIN: past-years turnover threshold -------------------------
        ("RULE-FIN-001", "Financial", "mandatory", "financial_bid", "TURNOVER", ">=", "10000000",
         "Latest financial year turnover must be at least 1,00,00,000 INR (1 crore)"),
        # --- Rule-XCHK: multi-document identity reconciliation --------------
        ("RULE-XCHK-001", "Cross-Check", "blocking", "all", "COMPANY_NAME", "cross_check", None,
         "Company legal name must match across every uploaded document "
         "(financial spreadsheet vs Certificate of Incorporation)"),
        ("RULE-XCHK-002", "Cross-Check", "blocking", "all", "PAN", "cross_check", None,
         "PAN must be identical across every uploaded document"),
        ("RULE-XCHK-003", "Cross-Check", "blocking", "all", "GSTIN", "cross_check", None,
         "GSTIN must be identical across every uploaded document"),
        ("RULE-XCHK-004", "Cross-Check", "mandatory", "all", "CIN", "cross_check", None,
         "CIN (Certificate of Incorporation) must match on all referenced documents"),
        ("RULE-XCHK-005", "Cross-Check", "mandatory", "all", "COMPANY_REGISTRATION_NUMBER", "cross_check", None,
         "Company registration number must agree across all uploaded documents"),
        ("RULE-XCHK-006", "Cross-Check", "advisory", "all", "INCORPORATION_DATE", "cross_check", None,
         "Incorporation date must agree across all uploaded documents"),
    ]
    for rule_id, category, severity, element, target, operator, expected, description in demo_rules:
        conn.execute(
            """INSERT OR IGNORE INTO validation_rules
               (rule_id, tender_id, category, description, severity, element, target, operator, expected_value, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, settings.demo_tender_id, category, description, severity,
             element, target, operator, expected,
             f"Phase P1 demo rule — {operator} against {target}"),
        )


# --------------------------------------------------------------------------
# Demo bids (Phase P4) — dashboard-ready history for live presentations
# --------------------------------------------------------------------------
_DEMO_TENDER = "GeM/2026/B/123456"


def _r(rule_id: str, status: str, reason: str, confidence: float,
       action: str = "none", evidence: dict | None = None) -> dict:
    return {
        "rule_id": rule_id, "status": status, "reason": reason,
        "confidence": confidence, "suggested_action": action,
        "evidence": evidence if evidence is not None else {"found": reason},
    }


def _ev(stage: str, status: str, ts: str, message: str, runtime_ms: int = 0) -> dict:
    return {"stage": stage, "status": status, "ts": ts,
            "message": message, "runtime_ms": runtime_ms}


def _doc(file_id: str, file_name: str, file_type: str, doc_role: str, size_bytes: int,
         sha256: str, store_path: str, stage: str = "validated", stage_status: str = "ok") -> dict:
    return {
        "file_id": file_id, "file_name": file_name, "file_type": file_type,
        "doc_role": doc_role, "size_bytes": size_bytes, "sha256": sha256,
        "store_path": store_path, "stage": stage, "stage_status": stage_status,
    }


def _seed_bid_record(conn: sqlite3.Connection, *, bid_id: str, request_id: str,
                     supplier: str, category: str, overall_status: str,
                     documents: list[dict], rule_results: list[dict],
                     events: list[dict], adjudication: dict | None = None) -> None:
    """Insert one fully-populated demo bid so /dashboard renders end-to-end."""
    conn.execute(
        """INSERT OR IGNORE INTO bids
           (bid_id, tender_id, supplier, category, request_id, overall_status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (bid_id, _DEMO_TENDER, supplier, category, request_id, overall_status),
    )
    for doc in documents:
        conn.execute(
            """INSERT OR IGNORE INTO documents
               (file_id, bid_id, file_name, file_type, doc_role, size_bytes, sha256, store_path, stage, stage_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (doc["file_id"], bid_id, doc["file_name"], doc["file_type"], doc["doc_role"],
             doc["size_bytes"], doc["sha256"], doc["store_path"], doc["stage"], doc["stage_status"]),
        )
    conn.execute("DELETE FROM rule_results WHERE bid_id = ?", (bid_id,))
    for r in rule_results:
        conn.execute(
            "INSERT INTO rule_results (bid_id, rule_id, status, evidence, reason, confidence, suggested_action)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (bid_id, r["rule_id"], r["status"], json.dumps(r.get("evidence") or {}),
             r["reason"], r["confidence"], r.get("suggested_action", "none")),
        )
    for ev in events:
        conn.execute(
            "INSERT INTO pipeline_events (request_id, bid_id, stage, status, ts, runtime_ms, message)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request_id, bid_id, ev["stage"], ev["status"], ev["ts"],
             ev.get("runtime_ms", 0), ev.get("message", "")),
        )
    if adjudication:
        conn.execute(
            """INSERT OR REPLACE INTO adjudications (bid_id, decision, officer, comment, ts)
               VALUES (?, ?, ?, ?, ?)""",
            (bid_id, adjudication["decision"], adjudication["officer"],
             adjudication["comment"], adjudication["ts"]),
        )


def _seed_demo_bids(conn: sqlite3.Connection) -> None:
    """Seed three kitchen-sink demo bids ONLY if none exist yet. Idempotent.

    demo-pass-001    -> every rule passes   -> COMPLIANT
    demo-fail-001    -> missing docs + weak financials, one corrupt file -> DISCREPANT
    demo-conflict-001-> XCHK identity conflict (COMPANY_NAME/INCORPORATION_DATE) -> DISCREPANT
    """
    if conn.execute("SELECT COUNT(*) AS c FROM bids WHERE bid_id LIKE 'demo-%'").fetchone()["c"]:
        return

    # -- PASS: Bharat Infrastructure Ltd ---------------------------------------
    pass_results = [
        _r("RULE-EMD-001", "pass", "Extracted 75000.0 >= required 50000.0", 0.95,
           evidence={"found": "EMD of Rs. 75,000 furnished via Bank Guarantee"}),
        _r("RULE-DOC-001", "pass", "GSTIN present in parsed document", 0.9,
           evidence={"found": "27AABCA1234F1Z5"}),
        _r("RULE-DOC-002", "pass", "PAN present in parsed document", 0.9,
           evidence={"found": "AABCA1234D"}),
        _r("RULE-DOC-003", "pass", "table:PRICE_BREAKUP present in parsed document", 0.9,
           evidence={"found": "Itemized price breakup table detected"}),
        _r("RULE-DATE-001", "pass", "CERT_VALIDITY 2027-12-31 is after 2026-06-30", 0.9,
           evidence={"found": "valid till 2027-12-31"}),
        _r("RULE-DATE-002", "pass", "INCORPORATION_DATE 2015-03-20 is before 2020-01-01", 0.9,
           evidence={"found": "Date of Incorporation: 2015-03-20"}),
        _r("RULE-FIN-001", "pass", "Extracted 2.5e+07 >= required 1e+07", 0.95,
           evidence={"found": "Financial Year 2025-26 turnover of Rs. 2.50 crore"}),
        _r("RULE-XCHK-001", "pass", "COMPANY_NAME consistent across 4 document(s)", 0.9),
        _r("RULE-XCHK-002", "pass", "PAN consistent across 4 document(s)", 0.9),
        _r("RULE-XCHK-003", "pass", "GSTIN consistent across 4 document(s)", 0.9),
        _r("RULE-XCHK-004", "pass", "CIN consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-005", "pass", "COMPANY_REGISTRATION_NUMBER consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-006", "pass", "INCORPORATION_DATE consistent across 4 document(s)", 0.9),
    ]
    _seed_bid_record(
        conn, bid_id="demo-pass-001", request_id="req-demo-pass-001",
        supplier="Bharat Infrastructure Ltd", category="Civil Works",
        overall_status="COMPLIANT",
        documents=[
            _doc("demo-file-pass-tech", "technical_bid_bharat.pdf", "pdf", "technical_bid", 482132,
                 "9f9f9f9f" * 8, "demo/pass/technical_bid_bharat.pdf"),
            _doc("demo-file-pass-fin", "financial_bid_bharat.pdf", "pdf", "financial_bid", 315840,
                 "8e8e8e8e" * 8, "demo/pass/financial_bid_bharat.pdf"),
            _doc("demo-file-pass-cert", "certificate_bharat.pdf", "pdf", "certificates", 1029440,
                 "7d7d7d7d" * 8, "demo/pass/certificate_bharat.pdf"),
            _doc("demo-file-pass-emd", "emd_receipt_bharat.pdf", "pdf", "emd", 88240,
                 "6c6c6c6c" * 8, "demo/pass/emd_receipt_bharat.pdf"),
        ],
        rule_results=pass_results,
        events=[
            _ev("upload", "done", "2026-09-10T09:30:00+00:00", "4 file(s) accepted"),
            _ev("ocr", "running", "2026-09-10T09:30:00+00:00", "Extracting text and layout regions"),
            _ev("ocr", "done", "2026-09-10T09:30:04+00:00", "14 page(s), 98 block(s), 6 table(s), 2 region(s)", 4210),
            _ev("nlp", "running", "2026-09-10T09:30:04+00:00", "Structuring sections and extracting entities"),
            _ev("nlp", "done", "2026-09-10T09:30:06+00:00", "4 doc(s), 19 section(s), 47 entit(ies)", 1820),
            _ev("validation", "running", "2026-09-10T09:30:06+00:00", "Evaluating compliance rules"),
            _ev("validation", "done", "2026-09-10T09:30:06+00:00", "13 rule(s) evaluated -> COMPLIANT", 130),
        ],
    )

    # -- FAIL: missing identities + weak financials + one corrupt file --------
    fail_evidence = {"found": None, "conflict": False}
    fail_results = [
        _r("RULE-EMD-001", "fail", "Extracted 10000.0 < required 50000.0", 0.9, "attach_missing_doc",
           evidence={"found": "EMD of Rs. 10,000 furnished (below threshold)"}),
        _r("RULE-DOC-001", "fail", "GSTIN: [] not found in parsed document", 0.9, "attach_missing_doc",
           evidence={"found": None, "missing": ["GSTIN"]}),
        _r("RULE-DOC-002", "fail", "PAN: [] not found in parsed document", 0.9, "attach_missing_doc",
           evidence={"found": None, "missing": ["PAN"]}),
        _r("RULE-DOC-003", "fail", "table:PRICE_BREAKUP present in parsed document", 0.9, "attach_missing_doc",
           evidence={"found": None, "missing": ["table:PRICE_BREAKUP"]}),
        _r("RULE-DATE-001", "skip", "No comparable date available", 0.5, "manual_review"),
        _r("RULE-DATE-002", "skip", "No comparable date available", 0.5, "manual_review"),
        _r("RULE-FIN-001", "fail", "Extracted 2.5e+06 < required 1e+07", 0.9, "attach_missing_doc",
           evidence={"found": "Financial Year 2025-26 turnover of Rs. 25 lakh (below 1 crore)"}),
        _r("RULE-XCHK-001", "pass", "COMPANY_NAME consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-002", "pass", "PAN consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-003", "pass", "GSTIN consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-004", "pass", "CIN consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-005", "pass", "COMPANY_REGISTRATION_NUMBER consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-006", "pass", "INCORPORATION_DATE consistent across 2 document(s)", 0.9),
    ]
    _seed_bid_record(
        conn, bid_id="demo-fail-001", request_id="req-demo-fail-001",
        supplier="Global Parts Exports", category="Industrial Supplies",
        overall_status="DISCREPANT",
        documents=[
            _doc("demo-file-fail-tech", "technical_bid_global.pdf", "pdf", "technical_bid", 391044,
                 "5b5b5b5b" * 8, "demo/fail/technical_bid_global.pdf"),
            _doc("demo-file-fail-fin", "financial_bid_global.pdf", "pdf", "financial_bid", 262180,
                 "4a4a4a4a" * 8, "demo/fail/financial_bid_global.pdf"),
            _doc("demo-file-fail-cert", "certificate_global.pdf", "pdf", "certificates", 0,
                 "39393939" * 8, "demo/fail/certificate_global.pdf",
                 stage="failed", stage_status="error"),
        ],
        rule_results=fail_results,
        events=[
            _ev("upload", "done", "2026-09-11T11:45:00+00:00", "3 file(s) accepted"),
            _ev("ocr", "running", "2026-09-11T11:45:00+00:00", "Extracting text and layout regions"),
            _ev("ocr", "error", "2026-09-11T11:45:02+00:00",
                "File demo-file-fail-cert failed (fitz.FileDataError: cannot open broken document)"),
            _ev("ocr", "done", "2026-09-11T11:45:03+00:00",
                "6 page(s), 41 block(s), 1 table(s), 0 region(s) - 1 corrupt file(s) isolated; remaining 2 doc(s) validated", 3150),
            _ev("nlp", "running", "2026-09-11T11:45:03+00:00", "Structuring sections and extracting entities"),
            _ev("nlp", "done", "2026-09-11T11:45:05+00:00", "2 doc(s), 11 section(s), 26 entit(ies)", 1420),
            _ev("validation", "running", "2026-09-11T11:45:05+00:00", "Evaluating compliance rules"),
            _ev("validation", "done", "2026-09-11T11:45:05+00:00", "13 rule(s) evaluated -> DISCREPANT", 120),
        ],
    )

    # -- CONFLICT: XCHK identity mismatch streaks across docs ------------------
    conflict_name = {
        "found": "COMPANY_NAME disagrees across 2 document(s): SRI GANESH ELECTRICALS PVT LTD, "
                 "SRI GANESH ELECTRONICS PVT LTD",
        "source_span": None, "file_id": None, "table_id": None,
        "distinct_values": ["SRI GANESH ELECTRICALS PVT LTD", "SRI GANESH ELECTRONICS PVT LTD"],
        "conflict_records": [
            {"field": "COMPANY_NAME", "status": "conflict", "file_id": "demo-file-conflict-fin",
             "doc_role": "financial_bid", "value": "Sri Ganesh Electricals Pvt Ltd",
             "normalized_value": "SRI GANESH ELECTRICALS PVT LTD", "confidence": 0.86,
             "source_span": {"page": 1, "start": 18, "end": 47}},
            {"field": "COMPANY_NAME", "status": "conflict", "file_id": "demo-file-conflict-cert",
             "doc_role": "certificates", "value": "Sri Ganesh Electronics Pvt Ltd",
             "normalized_value": "SRI GANESH ELECTRONICS PVT LTD", "confidence": 0.86,
             "source_span": {"page": 1, "start": 24, "end": 55}},
        ],
        "cross_check_conflict": True,
    }
    conflict_date = {
        "found": "INCORPORATION_DATE disagrees across 2 document(s): 2016-04-01, 2018-11-25",
        "source_span": None, "file_id": None, "table_id": None,
        "distinct_values": ["2016-04-01", "2018-11-25"],
        "conflict_records": [
            {"field": "INCORPORATION_DATE", "status": "conflict", "file_id": "demo-file-conflict-fin",
             "doc_role": "financial_bid", "value": "2016-04-01", "normalized_value": "2016-04-01",
             "confidence": 0.9, "source_span": {"page": 1, "start": 90, "end": 100}},
            {"field": "INCORPORATION_DATE", "status": "conflict", "file_id": "demo-file-conflict-cert",
             "doc_role": "certificates", "value": "2018-11-25", "normalized_value": "2018-11-25",
             "confidence": 0.94, "source_span": {"page": 1, "start": 33, "end": 43}},
        ],
        "cross_check_conflict": True,
    }
    conflict_results = [
        _r("RULE-EMD-001", "pass", "Extracted 60000.0 >= required 50000.0", 0.95,
           evidence={"found": "EMD of Rs. 60,000 furnished via Bank Guarantee"}),
        _r("RULE-DOC-001", "pass", "GSTIN present in parsed document", 0.9,
           evidence={"found": "33AACCS1234F1Z8"}),
        _r("RULE-DOC-002", "pass", "PAN present in parsed document", 0.9,
           evidence={"found": "AACCS1234K"}),
        _r("RULE-DOC-003", "pass", "table:PRICE_BREAKUP present in parsed document", 0.9,
           evidence={"found": "Itemized price breakup table detected"}),
        _r("RULE-DATE-001", "pass", "CERT_VALIDITY 2028-06-30 is after 2026-06-30", 0.9,
           evidence={"found": "valid till 2028-06-30"}),
        _r("RULE-DATE-002", "pass", "INCORPORATION_DATE 2016-04-01 is before 2020-01-01", 0.9,
           evidence={"found": "Date of Incorporation: 2016-04-01"}),
        _r("RULE-FIN-001", "pass", "Extracted 1.8e+07 >= required 1e+07", 0.95,
           evidence={"found": "Financial Year 2025-26 turnover of Rs. 1.80 crore"}),
        _r("RULE-XCHK-001", "fail", "COMPANY_NAME disagrees across 2 document(s)", 0.86,
           "manual_review", evidence=conflict_name),
        _r("RULE-XCHK-002", "pass", "PAN consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-003", "pass", "GSTIN consistent across 2 document(s)", 0.9),
        _r("RULE-XCHK-004", "pass", "CIN consistent across 1 document(s)", 0.9),
        _r("RULE-XCHK-005", "pass", "COMPANY_REGISTRATION_NUMBER consistent across 1 document(s)", 0.9),
        _r("RULE-XCHK-006", "fail", "INCORPORATION_DATE disagrees across 2 document(s)", 0.9,
           "manual_review", evidence=conflict_date),
    ]
    _seed_bid_record(
        conn, bid_id="demo-conflict-001", request_id="req-demo-conflict-001",
        supplier="Sri Ganesh Electricals", category="Electrical Goods",
        overall_status="DISCREPANT",
        documents=[
            _doc("demo-file-conflict-fin", "financial_bid_ganesh.pdf", "pdf", "financial_bid", 298644,
                 "2f2f2f2f" * 8, "demo/conflict/financial_bid_ganesh.pdf"),
            _doc("demo-file-conflict-cert", "certificate_ganesh.pdf", "pdf", "certificates", 1145100,
                 "10101010" * 8, "demo/conflict/certificate_ganesh.pdf"),
        ],
        rule_results=conflict_results,
        events=[
            _ev("upload", "done", "2026-09-12T15:20:00+00:00", "2 file(s) accepted"),
            _ev("ocr", "running", "2026-09-12T15:20:00+00:00", "Extracting text and layout regions"),
            _ev("ocr", "done", "2026-09-12T15:20:03+00:00", "9 page(s), 60 block(s), 2 table(s), 1 region(s)", 3120),
            _ev("nlp", "running", "2026-09-12T15:20:03+00:00", "Structuring sections and extracting entities"),
            _ev("nlp", "done", "2026-09-12T15:20:05+00:00", "2 doc(s), 10 section(s), 31 entit(ies)", 1540),
            _ev("validation", "running", "2026-09-12T15:20:05+00:00", "Evaluating compliance rules"),
            _ev("validation", "done", "2026-09-12T15:20:05+00:00",
                "13 rule(s) evaluated -> DISCREPANT (cross-check conflict detected)", 140),
        ],
        adjudication={
            "decision": "rework_requested",
            "officer": "Review Desk",
            "comment": "Company legal name on the Certificate of Incorporation does not match the "
                       "financial sheet. Please re-submit consistent identity documents.",
            "ts": "2026-09-13T10:05:00+00:00",
        },
    )