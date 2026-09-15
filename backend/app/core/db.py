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
    conn = _connect()
    try:
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
    """Phase P0 demo rule: EMD amount >= threshold (env-tunable, default 50,000 INR)."""
    threshold = settings.emd_threshold
    conn.execute(
        """INSERT OR IGNORE INTO validation_rules
           (rule_id, tender_id, category, description, severity, element, target, operator, expected_value, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("RULE-EMD-001", settings.demo_tender_id, "EMD",
         f"Earnest Money Deposit (EMD) must be at least {int(float(threshold)):,} INR",
         "blocking", "all", "EMD_AMOUNT", ">=", threshold,
         "Phase P0 demo rule — scanned from EMD / financial sections"),
    )