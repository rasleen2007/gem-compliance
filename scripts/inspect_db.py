"""Inspect data/sih_local.db after a Phase P0 e2e run."""

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "sih_local.db"

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

print("tables:", [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")])
print("\nrules:")
for r in conn.execute("SELECT rule_id, target, operator, expected_value, severity FROM validation_rules"):
    print(" ", dict(r))
print("\nbids:")
for r in conn.execute("SELECT bid_id, overall_status FROM bids"):
    print(" ", dict(r))
print("\nrule_results:")
for r in conn.execute("SELECT bid_id, rule_id, status, reason FROM rule_results"):
    print(" ", dict(r))
print("\npipeline_events (latest request):")
for r in conn.execute("SELECT request_id, stage, status, runtime_ms, message FROM pipeline_events ORDER BY event_id DESC LIMIT 8"):
    print(" ", dict(r))
conn.close()