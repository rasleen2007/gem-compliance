# 01 — Architecture Blueprint

**SIH26100: AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement**

## 1. Problem Summary

Bid evaluation on GeM is largely manual: procurement officers compare bid
PDFs/images against tender terms (EMD, eligibility, technical specs, financial
formats, certificates). Manual review is slow, inconsistent, and error-prone for
high-volume tenders (especially in petroleum sector buys).

**MVP goal:** one upload action → automated OCR of bid documents → rule-based
compliance scoring → human-in-the-loop dashboard that flags discrepancies with
evidence, so a contracting officer can approve or reject faster.

## 2. System Context Diagram

```
                        ┌─────────────────────────────────────────────┐
                        │                  UI LAYER                     │
                        │    React + Vite Dashboard (frontend/)        │
                        │  Upload | Job Status | Compliance Results    │
                        └───────────────┬─────────────────────────────┘
                                        │ HTTP (REST, JSON contracts)
                                        ▼
                        ┌─────────────────────────────────────────────┐
                        │            ORCHESTRATION LAYER               │
                        │        FastAPI (backend/app/)                │
                        │  /upload  /jobs/{id}  /validate  /dashboard │
                        │  Pipeline coordinator, storage, event log    │
                        └───────┬──────────────┬──────────────┬───────┘
                                │              │              │
                      block 1   ▼              ▼ block 3      ▼ block 4
              ┌─────────────────┐   ┌──────────────────┐  ┌────────────────┐
              │   AI CORE       │   │   RULES ENGINE   │  │    DATA         │
              │  (core_ai/)     │   │   (core_ai/rules)│  │  SQLite         │
              │ OCR ─ process.  │──▶│ rule registry ── │─▶│ bids, docs,     │
              │ layout parse    │   │ operator checks  │  │ rules, results, │
              │ NER/NLP extra   │   │ LLM judge (opt)  │  │ audit timeline  │
              └─────────────────┘   └──────────────────┘  └────────────────┘
```

## 3. Module Responsibilities

### frontend/ — Submission & Review UI
- Role-tagged file upload (technical bid / financial bid / EMD / certificates).
- Job status timeline (per-stage badges).
- Compliance score, category breakdown, discrepancy list with evidence drill-down.
- Confirmation of adjudication (accept / reject / request rework).

### backend/ — Orchestration (FastAPI)
- **API surface** (`app/api/routes/`): `upload`, `validation`, `dashboard`, `jobs`.
- **Orchestrator** (`app/services/orchestrator.py`): runs the pipeline stages as
  an async state machine, transacts with DB, fans out to `core_ai` modules.
- **Schemas** (`app/schemas/`): Pydantic models mirroring `contracts/*.schema.json`.
- **Storage** (`app/services/storage.py`): file persistence under `uploads/`, DB session.

### core_ai/ — Document Intelligence (pure Python, no HTTP)
- `ocr/` — text, table, image/stamp extraction from PDFs & images.
- `nlp/` — section segmentation, key-value pair extraction, entity normalization.
- `rules/` — deterministic rule engine: loads rule packs, applies operators,
  produces evidence-backed results; optional `llm` judge for free-text rules.
- Zero HTTP coupling: consumed as an in-process Python package by the backend.

### database_schema/
- SQLite DDL (`schema.sql`) + seed rule packs (`seed_rules.sql`) covering the
  standard petroleum/GeM compliance categories (EMD, eligibility, technical,
  financial, certificates). Written to be portable to Postgres.

### contracts/
- JSON Schema (draft-07) files; single source of truth for API payloads and
  inter-module messages. Backend Pydantic + frontend TS types generated/mirrored.

## 4. Tech Stack (MVP)

| Layer        | Choice                          | Why for a 36-hour hackathon                      |
| ------------ | ------------------------------- | ------------------------------------------------ |
| Backend      | Python 3.11 + FastAPI + Uvicorn | Native for AI, async, auto OpenAPI docs          |
| AI Core      | PaddleOCR (+pdfplumber), spaCy  | Layout tables + NER in one Python env            |
| LLM assist   | Gemini/OpenAI adapter (opt-in)  | Free-text "judge" rules, zero-cost fallback      |
| Frontend     | React 18 + Vite + axios         | Fast scaffold, component-based review UI         |
| Database     | SQLite (via sqlite3/SQLAlchemy) | Zero-config, file based; schema is Postgres-able |
| Infra        | docker-compose (dev)            | One-command multi-service bring-up               |

## 5. Design Decisions

1. **Contracts-first:** every boundary payload is defined in JSON Schema before
   any module code; Pydantic models import from a generated/shared definition.
2. **Synchronous OCR, async pipeline:** upload returns instantly with
   `request_id`; validation progresses through stages persisted in DB; dashboard polls.
3. **Evidence, not verdicts:** each rule result carries the source span/table
   reference and raw text so reviewers can trust the automation.
4. **Deterministic baseline:** rule engine works without any LLM; LLM only adds
   free-text judgment when enabled — demo works fully offline if needed.
5. **Extension-ready:** `doc_role` tagging and category-based rule packs let us
   onboard new tender templates without code changes.

## 6. Error & Failure Handling

- Per-document OCR failures produce `status: "partial"` + `errors[]`, never kill
  the job. Dashboard shows which document failed and why.
- Rule evaluations that throw are recorded as `status: "error"` with the message,
  keeping the rest of the batch usable.
- All stages log `runtime_ms` and `status` for the timeline visualization and
  for the demo pitch (show latency per stage).

## 7. Deployment (MVP)

- Docker Compose: `backend` (uvicorn) + `frontend` (vite preview/nginx) + mounted
  `data/` and `uploads/` volumes.
- Single-node; SQLite file on a shared volume. Postgres migration path is
  documented in `database_schema/migrations/`.