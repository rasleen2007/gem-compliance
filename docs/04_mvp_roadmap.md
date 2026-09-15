# 04 — Hackathon MVP Roadmap

Sequential implementation order to reach a **functional end-to-end prototype**
(one real PDF in → compliance report out). Each phase is gated by an acceptance
criterion that must be demonstrable before moving on.

## Phase P0 — Pipeline Foundation (barebones, end-to-end smoke)

Goal: *any* file in → text out → one rule out → one JSON report. Prove the
plumbing before the AI.

| # | Task | Deliverable | Owner |
| - | ---- | ----------- | ----- |
| 1 | DB bootstrap | `schema.sql` applied; `bids`, `documents`, `validation_rules`, `rule_results`, `pipeline_events` tables live | Platform |
| 2 | Storage + upload route | multipart → `uploads/{request_id}/{file_id}/`, dedup by sha256, 202 + `document_upload` | Platform |
| 3 | OCR baseline | PaddleOCR on page images → `text_blocks` + `full_text` (contract 2) | AI Core |
| 4 | First rule | hardcoded `RULE-EMD-001` `>=` compare on a regex-extracted `2%` → `validation_result` | AI Core |
| 5 | Orchestrator | async state machine driving Stages 0-4, events to DB | Platform |

**Acceptance:** upload `reference/sample_bids/TechBid.pdf` → dashboard JSON shows
`status: DISCREPANT|COMPLIANT`, `timeline[]` has 4 stages. Latency < 20 s.

## Phase P1 — Rules Engine + NLP Structuring

| # | Task | Deliverable | Owner |
| - | ---- | ----------- | ----- |
| 6 | Layout parser | reading order, heading detection, table bboxes (pdfplumber for vector PDFs) | AI Core |
| 7 | NLP structuring | section segmentation, key-value pairs, entity gazetteer, `source_span` (contract 3) | AI Core |
| 8 | Rule Registry | load + cache rule packs per tender (contract 4) from DB | AI Core |
| 9 | Full operator set | `>=, exists, regex, date_after, contains` + per-rule error isolation | AI Core |
| 10 | Validation API + jobs | `POST /validate/{request_id}`, `GET /jobs/{request_id}`, endpoint wiring | Platform |
| 11 | Contract tests | Pydantic ↔ `contracts/*.schema.json` calibration (extends `backend/tests/test_contracts.py`) | Platform |

**Acceptance:** the full `seed_rules.sql` pack evaluates on a synthetic parsed
document with per-rule pass/fail/warn + evidence; zero rule throws.

## Phase P2 — Compliance Dashboard (frontend vertical slice)

| # | Task | Deliverable | Owner |
| - | ---- | ----------- | ----- |
| 12 | Upload page | role-tagged multi-file form → `/upload` | Frontend |
| 13 | Dashboard page | poll `/dashboard/{bid_id}`, timeline, score gauge, category bars | Frontend |
| 14 | Results page | severity-sorted issues, expandable evidence spans, adjudication actions | Frontend |
| 15 | Mock fixture mode | frontend renders from `reference/mock_payloads/dashboard.json` when backend absent | Frontend |

**Acceptance:** live demo loop — upload 2-3 files → see pipeline stages animate →
click a failing rule → see highlighted source text excerpt.

## Phase P3 — Hardening & LLM Judge (polish)

| # | Task | Deliverable | Owner |
| - | ---- | ----------- | ----- |
| 16 | LLM judge adapter | `llm_judge` operator via Gemini/OpenAI, grounded on evidence spans, disabled-by-default | AI Core |
| 17 | OCR robustness | stamp/signature region detection flagging `partial`; error messages per doc | AI Core |
| 18 | Edge cases | password-protected PDFs, >50 MB, corrupt files → clean 4xx/partial responses | Platform |
| 19 | Docker bring-up | compose builds + seeded demo tender back-to-back | Platform |

**Acceptance:** demo runs on a fresh VM purely with `docker compose up` + seeded data.

## Phase P4 — Demo Narrative (last 2-3 hours)

| # | Task | Deliverable |
| - | ---- | ----------- |
| 20 | 3 scripted scenarios | (a) fully compliant bid, (b) blocking EMD shortfall, (c) low-confidence stamp → manual review |
| 21 | Evidence screenshots | captured OCR page + highlight for the standout rule failures |
| 22 | Latency slide | per-stage `runtime_ms` chart from `pipeline_events` |
| 23 | Resilience talking point | what happens when *all* docs fail (job `FAILED`, dashboard still renders) |

## Team Roles (4-5 people)

| Role | Focus |
| ---- | ----- |
| AI Core (2) | OCR/layout + NLP/rules — biggest risk, start here |
| Platform (1) | FastAPI, DB, orchestration — do P0 items 1,2,5 first |
| Frontend (1) | React dashboard — can start against mock fixture in parallel during P1 |
| QA/Demo (1) | contract tests, sample bids, acceptance criteria, scripted scenario docs |

## Risk Register

| Risk | Mitigation |
| ---- | ---------- |
| OCR accuracy on scanned stubs | pdfplumber vector text path + PaddleOCR fallback; `partial` status instead of wrong data |
| LLM cost/reliability | deterministic engine is the shipped path; LLM is additive only |
| Scope creep (auth, scaling) | explicitly out of MVP; document as "extension-ready" hooks |
| Environment friction at venue | Docker single-command bring-up + fully offline deterministic path |

## Out of Scope (MVP)

User auth/RBAC, multi-tenant tender management UI, Postgres migration, print-ready
audit reports, live GeM API integration.