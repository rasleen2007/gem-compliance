# AI-Powered Integrated Bid Compliance Verification Platform

**SIH 2026 Problem Statement SIH26100** — Ministry of Petroleum & Natural Gas

Automated verification of GeM (Government e-Marketplace) bid documents against
tender rules: upload → OCR/layout parsing → NLP validation → compliance dashboard.

## Module Map

| Path                  | Purpose                                                              |
| --------------------- | -------------------------------------------------------------------- |
| `contracts/`          | Canonical JSON Schemas for every inter-module message (source of truth) |
| `backend/`            | FastAPI orchestration service (upload, jobs, validation, dashboard API) |
| `core_ai/`            | OCR, layout parser, NLP entity extraction, rules engine, LLM assist    |
| `database_schema/`    | SQLite/portable DDL + seed rule packs                                  |
| `frontend/`           | React + Vite compliance dashboard                                      |
| `reference/`          | Offline fixtures: sample tender PDFs, rule packs, mock payloads        |
| `docs/`               | Blueprint, workflow, contracts spec, MVP roadmap                       |

## Ground Rules

1. **Contracts-first.** Nothing crosses a module boundary except shapes defined in
   `contracts/*.schema.json`. Backend Pydantic models mirror them.
2. **Stages.** Validation runs as an async pipeline keyed by `request_id` /
   `bid_id`. Every stage emits status + timestamps so the dashboard can render a timeline.
3. **Determine the engine later.** MVP ships with a deterministic rules engine
   + optional LLM "judge" adapter; swap the LLM provider via env config.

## Quick Start (placeholder)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Contracts lint (generates/validates against JSON Schema)
python scripts/validate_contracts.py
```

See `docs/01_architecture_blueprint.md` for the full blueprint and
`docs/04_mvp_roadmap.md` for the build order.