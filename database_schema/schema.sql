-- GeM Bid Compliance Platform — SQLite DDL (MVP).
-- Written to be portable to Postgres (see migrations/ for the port).

PRAGMA foreign_keys = ON;

-- A submitted bid + tender context (Stage 0).
CREATE TABLE IF NOT EXISTS bids (
    bid_id          TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL,
    supplier        TEXT NOT NULL,
    category        TEXT NOT NULL,
    request_id      TEXT NOT NULL UNIQUE,
    submitted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    overall_status  TEXT NOT NULL DEFAULT 'IN_PROGRESS' -- COMPLIANT|DISCREPANT|NEEDS_REVIEW|IN_PROGRESS
);

-- Uploaded documents (1 bid -> N documents), role-tagged.
CREATE TABLE IF NOT EXISTS documents (
    file_id         TEXT PRIMARY KEY,
    bid_id          TEXT NOT NULL REFERENCES bids(bid_id),
    file_name       TEXT NOT NULL,
    file_type       TEXT NOT NULL,             -- pdf | image | docx
    doc_role        TEXT NOT NULL,             -- technical_bid|financial_bid|emd|certificates|annexure
    size_bytes      INTEGER,
    sha256          TEXT,
    store_path      TEXT,
    stage           TEXT NOT NULL DEFAULT 'uploaded', -- uploaded|ocr_done|parsed|validated|failed
    stage_status    TEXT NOT NULL DEFAULT 'ok'        -- ok|partial|error
);

-- Compliance rule packs (contract 4). Seeded from seed_rules.sql.
CREATE TABLE IF NOT EXISTS validation_rules (
    rule_id         TEXT PRIMARY KEY,
    tender_id       TEXT NOT NULL,
    category        TEXT NOT NULL,             -- EMD | Technical | Financial | Certificates | Eligibility
    description     TEXT,
    severity        TEXT NOT NULL,             -- blocking|mandatory|advisory
    element         TEXT NOT NULL,             -- doc_role rule inspects
    target          TEXT NOT NULL,             -- entity / kv / word(...)
    operator        TEXT NOT NULL,             -- >= | contains | exists | regex | date_after | llm_judge ...
    expected_value  TEXT,
    expression      TEXT,
    notes           TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_rules_tender ON validation_rules(tender_id);

-- Per-rule verdicts (contract 5 rows).
CREATE TABLE IF NOT EXISTS rule_results (
    result_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    bid_id      TEXT NOT NULL REFERENCES bids(bid_id),
    rule_id     TEXT NOT NULL REFERENCES validation_rules(rule_id),
    status      TEXT NOT NULL,                 -- pass|fail|warn|skip|error
    evidence    TEXT,                          -- JSON {found, source_span, file_id, table_id}
    reason      TEXT,
    confidence  REAL,
    suggested_action TEXT NOT NULL DEFAULT 'none',
    evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_results_bid ON rule_results(bid_id);

-- Pipeline stage transitions -> dashboard timeline (docs/02 State Machine).
CREATE TABLE IF NOT EXISTS pipeline_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  TEXT NOT NULL,
    bid_id      TEXT NOT NULL,
    stage       TEXT NOT NULL,                 -- upload|ocr|nlp|validation|adjudication
    status      TEXT NOT NULL,                 -- pending|running|done|error
    ts          TEXT NOT NULL DEFAULT (datetime('now')),
    runtime_ms  INTEGER,
    message     TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_request ON pipeline_events(request_id);

-- Human adjudication outcome (dashboard panel).
CREATE TABLE IF NOT EXISTS adjudications (
    bid_id      TEXT PRIMARY KEY REFERENCES bids(bid_id),
    decision    TEXT NOT NULL,                 -- approved|rejected|rework_requested
    officer     TEXT,
    comment     TEXT,
    ts          TEXT NOT NULL DEFAULT (datetime('now'))
);