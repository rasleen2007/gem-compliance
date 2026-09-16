# AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement

**Ministry of Petroleum & Natural Gas — Smart India Hackathon 2026 · Problem ID: SIH26100**

---

## Mission Summary

Slow, entirely manual tender vetting has been the silent bottleneck of government e-procurement
for decades: procurement officers must individually open every bidder's document package, hunt
through hundreds of pages for a handful of identity and compliance attributes, and reconcile
those strings by eye across independent files.

This platform eliminates that bottleneck. It is an **integrated, fully local, fully offline
compliance verification engine** that automates the entire vetting lifecycle in a single flow:
upload your role-tagged bid documents, and the platform reads them with **local OCR, isolates the
visual structure** (tables, stamps, signatures), **extracts identity and financial tokens with
deterministic NLP**, and runs every required tender rule against the structured data inside a
relational database — producing a defensible, evidence-backed compliance verdict in seconds.

No cloud calls. No metered APIs. No bidder data leaving the review desk.

---

## System Specifications & Core Engine Pipeline

The verification engine is a tightly pipelined, contract-driven state machine. Every stage emits a
typed, versioned payload that the next stage consumes — nothing crosses a module boundary except
shapes defined in the canonical JSON Schemas under `contracts/`.

```
┌────────────────┐      ┌───────────────────────┐      ┌───────────────────────────┐
│ Document       │ ───▶ │ PyMuPDF Local OCR     │ ───▶ │ Visual Layout Parsing     │
│ Upload         │      │ (text + vector extract)│      │ (tables / stamps / sigs)  │
└────────────────┘      └───────────────────────┘      └───────────────────────────┘
                                                                  │
                                                                  ▼
┌────────────────────────┐      ┌───────────────────────┐      ┌───────────────────────┐
│ Relational Database    │ ◀─── │ NLP Token Extraction  │ ◀─── │ Deterministic Regex    │
│ Logic Validation       │      │ (GSTIN/PAN/CIN/dates) │      │ Semantic Pass          │
└────────────────────────┘      └───────────────────────┘      └───────────────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────────┐
│ Compliance Dashboard — verdict, score, per-rule evidence,     │
│ per-stage timeline (upload → OCR → layout → NLP → validation)│
└───────────────────────────────────────────────────────────────┘
```

### Stage Breakdown

| # | Stage | Engine | Responsibility |
|---|-------|--------|----------------|
| 1 | **Document Upload** | FastAPI + multipart | Role-tagged ingestion of the bidder package (Technical Bid, Financial Bid, EMD/Bank Guarantee, Certificates, Annexure). Every file is persisted, hashed, and tracked individually. |
| 2 | **Local OCR** | PyMuPDF | On-device text and vector extraction. No OCR API key, no cloud account. Corrupt or blank files are isolated at the file level without blocking the remaining documents. |
| 3 | **Visual Layout Parsing** | Layout Engine | Geometrically partitions each page into regions — stamps, tables, signatures, price breakups, annexures — and builds a per-document ownership map. |
| 4 | **NLP Token Extraction** | Rule-based / Regex NLP | Deterministically extracts identity and financial tokens (GSTIN, PAN, CIN, registration dates, EMD amounts, turnovers), each carrying a `source_span` (page, bounding box, raw text) for auditability. |
| 5 | **Relational DB Validation** | SQLite + Rules Engine | Runs the full tender rule pack (13 rules across EMD, Eligibility, Certificates, Financial, and Cross-Check families) against the structured data, scoring every rule pass / fail / warn / skip. |
| 6 | **Compliance Dashboard** | React + FastAPI | Renders the aggregate verdict (COMPLIANT / DISCREPANT / NEEDS_REVIEW), compliance score, category breakdown, per-document statuses, and expandable per-issue evidence. |

Failure isolation is engineered into the pipeline: a corrupt upload is bounded to its own file row,
marked `failed` at the document level, and the remaining valid documents continue through
validation — the global run never freezes.

---

## Value Proposition for the Ministry

- **Zero Cloud Operating Costs** — The entire pipeline runs on open-source Python libraries
  (PyMuPDF, FastAPI). No paid OCR keys, no metered LLM calls, no per-document fees. Total cost of
  compute is ₹0.
- **Ultimate Data Privacy** — Sensitive government procurement data and bidder packages never leave
  the local workstation. Everything is processed on the laptop file system — ideal for closed
  government review environments and air-gapped infrastructure.
- **Advanced Cross-Document Fraud Detection** — Identity strings (Company Names, PAN, GSTIN,
  incorporation dates) are intentionally reconciled **across** independent file uploads. A supplier
  that lists "Sri Ganesh Electricals Pvt Ltd" in its Financial Bid but "Sri Ganesh Electronics Pvt
  Ltd" in its Certificates is automatically flagged as a discrepancy with matched evidence.
- **Defensive Failure Isolation** — Corrupted or blank uploads are safely contained at the file
  level: the failing document is marked `failed` while every valid document continues through the
  pipeline. No document, no matter how broken, can freeze the server run.

---

## Local Tech Stack & Prerequisites

| Layer | Technology | Version |
|-------|-----------|---------|
| Runtime | Python | **3.13+** |
| Backend framework | FastAPI (ASGI) | current |
| ASGI server | Uvicorn (`uvicorn[standard]`) | current |
| Document parsing | PyMuPDF | current |
| Database | SQLite (local, file-based) | bundled |
| Validation / contracts | Pydantic ≥ 2.0 · python-multipart · jsonschema | current |
| Frontend framework | React | **18** |
| Frontend tooling | Vite (dev server / bundler) | **5.x** |
| HTTP client | Axios | current |

All runtime dependencies are declared in `backend/requirements.txt` and `frontend/package.json`.
No paid services and no cloud credentials are required at any point.

---

## Local Quick-Start Launch Guide

Boot the full stack locally for free in three steps.

### 1. Backend — initialize the database

```bash
cd backend
pip install -r requirements.txt

python -c "from app.core.db import init_db; init_db()"
```

The bootstrap `init_db()` is idempotent: it creates `data/sih_local.db` from
`database_schema/schema.sql`, seeds the 13-rule tender pack for the demo tender
(`GeM/2026/B/123456`), and provisions the three demo bids used by the compliance dashboard.

### 2. Backend — launch the API server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The FastAPI application exposes the v1 REST surface under `/api/v1`:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/upload` | Role-tagged multipart bid upload → creates the pipeline job |
| `GET  /api/v1/jobs/{request_id}` | Pipeline job status + stage timeline |
| `GET  /api/v1/dashboard/{bid_id}` | Aggregate compliance verdict, score, documents, issues |
| `GET  /api/v1/rules` | The full tender verification rule pack (admin matrix) |

Health check: `http://localhost:8000/health`.

### 3. Frontend — launch the React dev server

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server boots on `http://localhost:5173` and proxies `/api` to the local backend on
port `8000`. Open the browser and land on the **System Specifications** view, then use the header
navigation to verify a new bid, inspect the Rules Matrix, or browse the live compliance dashboard.

> The app boots directly onto the About/System Specification landing view; the verified flow is
> **Verify New Bid → Compliance Dashboard → Compliance Review**, with the Rules Matrix and System
> Specs available from the persistent header at any time.

---

## Repository Layout

| Path | Purpose |
|------|---------|
| `contracts/` | Canonical JSON Schemas for every inter-module message (source of truth) |
| `backend/` | FastAPI orchestration service (upload, jobs, dashboard, rules API) |
| `backend/app/core/` | SQLite data layer + idempotent bootstrapping (`db.py`, `config.py`) |
| `backend/app/api/routes/` | HTTP routers (upload, jobs, dashboard, rules, validation) |
| `backend/app/schemas/` | Pydantic models mirroring the contract JSON Schemas |
| `core_ai/` | OCR, layout parser, NLP entity extraction, rules engine |
| `database_schema/` | SQLite portable DDL + seeded rule packs |
| `frontend/` | React + Vite compliance dashboard (App shell, Upload, Dashboard, Rules, About) |
| `reference/` | Offline fixtures: sample tender PDFs, rule packs, mock payloads |
| `docs/` | Architecture blueprint, workflow, contracts spec, MVP roadmap |

---

*Designed and built for the Government e-Marketplace — deploy anywhere, cost nothing, leak nothing.*