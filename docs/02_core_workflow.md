# 02 — Core Workflow Specification

End-to-end automated steps, from upload to compliance dashboard, with the
contract used at each hop, the owner module, timing expectations, and failure
policy.

## Pipeline Overview

```
STAGE 0            STAGE 1            STAGE 2                STAGE 3              STAGE 4
Upload           OCR / Layout      NLP Structuring        Rule Validation      Dashboard
───────          ─────────────     ─────────────────      ───────────────      ──────────
POST /upload     core_ai/ocr/      core_ai/nlp/           core_ai/rules/       GET /dashboard/{bid_id}
multi-file       PaddleOCR +        section seg, key-      rule packs vs        category score,
role-tagged      pdfplumber         value pairs, entities  extracted entities   discrepancy list,
└──────▶ store   └───────────▶      └───────────────▶      └─────────────▶      evidence drill-down
    request_id      ocr_extraction     parsed_document        validation_result     compliance_dashboard
     (contract 1)    (contract 2)        (contract 3)          (contract 5)         (contract 6)
                    validation_rule (contract 4) supplied alongside
```

## STAGE 0 — Document Upload

**Owner:** `backend.app.api.routes.upload`

1. Client POSTs files, each tagged with `doc_role`
   (`technical_bid | financial_bid | emd | certificates | annexure`), plus
   tender/bid context (tender_id, bid_id, supplier, category).
2. Backend validates extension/size (env-driven), computes `sha256`, assigns UUIDs,
   persists files under `uploads/{request_id}/{file_id}/`.
3. Inserts a `bids` + `documents` row, creates an async pipeline job
   (`status = PENDING`).
4. Returns `document_upload` contract + `request_id` immediately (202 Accepted).

**Gate:** at least one file present; every file must have a valid `doc_role`.
**Fail policy:** synchronous 400 with field-level errors; nothing is half-written.

## STAGE 1 — OCR / Layout Parsing

**Owner:** `core_ai.ocr.extractor` + `core_ai.ocr.layout_parser`

1. Convert each uploaded file to page images (pdfium/pymupdf; PIL for images).
2. Run OCR (default PaddleOCR) with layout awareness:
   - text blocks (heading/body/header/footer/table_cell)
   - tables (bounding box + grid of cells)
   - images (stamp / signature / logo) with inline OCR text if legible.
3. Emit `ocr_extraction` contract: per-page `text_blocks`, `tables`, `images`,
   `full_text`, plus per-block confidence.
4. Store raw extraction; update job stage to `OCR_COMPLETE`.

**Timing target:** ≤ 15 s/doc for a 20-page PDF on demo hardware.
**Fail policy:** per-document failure ⇒ `status=partial`, `errors[]` populated;
pipeline continues with remaining documents.

## STAGE 2 — NLP Structuring

**Owner:** `core_ai.nlp.entity_extractor` + `core_ai.nlp.text_processor`

1. From `ocr_extraction`, assemble a page-aware `full_text`.
2. Segment into sections by heading-level text blocks (heading detection via
   font/bbox heuristics + spaCy rules).
3. Extract:
   - key-value pairs (`key: value` patterns — GSTIN, valid until, EMD amount…)
   - typed entities via NER + gazetteer (EMD_PERCENTAGE, CERT_DATE, BANK_GUARANTEE…)
   - table references (link tables to the section that mentions them).
4. Emit `parsed_document` contract with `sections`, `key_value_pairs`, `entities`,
   `tables_normalized`, `summary`, `confidence`.

**Timing target:** ≤ 2 s/doc.
**Fail policy:** empty extraction ⇒ `status=warn` on entities with low coverage;
job continues to rules with whatever was extracted.

## STAGE 3 — Rule Validation

**Owner:** `core_ai.rules.engine` (+ optional `core_ai.llm.client` judge)

1. Load rule pack for `tender_id` (`validation_rule` contract
   — see `database_schema/seed_rules.sql`).
2. For each rule:
   - resolve target entities/pairs from `parsed_document`;
   - apply `operator` (>=, <=, contains, exists, regex, date_after, llm_judge);
   - produce `pass | fail | warn | skip | error` with `evidence` (source span/table
     reference + raw text) and `suggested_action`.
3. Aggregate into `validation_result`: `overall_status`
   (`COMPLIANT | DISCREPANT | NEEDS_REVIEW`), indexed scores by category.
4. Update job stage to `VALIDATION_COMPLETE`.

**Severity model:** `blocking` (auto-fail bid), `mandatory` (must pass,
manual override allowed), `advisory` (best effort). Free-text/clause rules use
`llm_judge` only when `LLM_ENABLED=true`.

## STAGE 4 — Compliance Dashboard

**Owner:** `backend.app.api.routes.dashboard` + `frontend/`

1. `GET /dashboard/{bid_id}` returns `compliance_dashboard` contract.
2. UI renders:
   - overall status + compliance percentage gauge;
   - category breakdown (EMD / Technical / Financial / Certificates);
   - discrepancy list (severity-sorted) with expandable evidence (page, bbox,
     raw text excerpt, linked table);
   - per-document stage/status pills + pipeline timeline;
   - adjudication action (accept / reject / request rework) persisted to DB.

**Polling contract:** dashboard polls every ~2 s while `status` is not terminal.

## State Machine

```
PENDING → OCR_RUNNING → OCR_COMPLETE → NLP_RUNNING → VALIDATION_RUNNING
        → VALIDATION_COMPLETE → (dashboard render OK)
        → any stage sets FAILED(partial) if ALL documents error
```

Every transition inserts an event into `pipeline_events`
(`stage`, `status`, `ts`, `runtime_ms`, `message`) — this powers both the
timeline UI and the demo narrative.

## Latency & Scale Targets (MVP)

| Stage          | Target          | Notes                          |
| -------------- | --------------- | ------------------------------ |
| Upload         | < 2 s           | async job handoff              |
| OCR+layout     | ≤ 15 s per 20p  | page-parallelizable in later phase |
| NLP structuring| ≤ 2 s per doc   | spaCy + regex rules            |
| Rules          | < 1 s for 50 rules | in-memory rule registry     |
| Dashboard      | < 1 s          | indexed by bid_id              |