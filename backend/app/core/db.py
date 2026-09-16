"""SQLite persistence layer (Phase P0).

Bootstrap: creates `data/sih_local.db` from database_schema/schema.sql on first
use (idempotent), then seeds the demo EMD rule (contract 4) if absent.

All access goes through these helpers; the backend never talks to SQL directly
elsewhere. Contract rule rows are returned as dicts matching
`validation_rule.schema.json` (camelCase keys).
"""

import json
import sqlite3
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
    """Create tables + seed demo rules. Safe to call repeatedly."""
    conn = _connect()
    try:
        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        conn.executescript(schema)
        _seed_demo_rules(conn)
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