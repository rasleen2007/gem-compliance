"""Pipeline orchestrator — drives Stages 0-4 from docs/02_core_workflow.md.

Phase P0 flow (single file end-to-end):
  upload (accepted) -> OCR/text extraction -> rule validation -> result.

Jobs run on a background thread pool; `pipeline_events` are persisted to SQLite
on every transition so the /jobs endpoint (and later dashboard) can rebuild the
timeline even mid-run.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.core import db
from app.core.config import settings
from core_ai.ocr.extractor import OcrExtractor, StoredDocument
from core_ai.rules.engine import RuleEngine
from core_ai.rules.rule_registry import RuleRegistry


class Stage(str, Enum):
    PENDING = "pending"
    OCR_RUNNING = "ocr_running"
    OCR_COMPLETE = "ocr_complete"
    NLP_RUNNING = "nlp_running"
    VALIDATION_RUNNING = "validation_running"
    VALIDATION_COMPLETE = "validation_complete"
    FAILED = "failed"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class PipelineJob:
    request_id: str
    bid_id: str
    tender_id: str
    supplier: str
    category: str
    stage: Stage = Stage.PENDING
    documents: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    extraction: dict | None = None
    result: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        status = "running"
        if self.stage == Stage.FAILED:
            status = "error"
        elif self.stage == Stage.VALIDATION_COMPLETE:
            status = "done"
        return {
            "request_id": self.request_id,
            "bid_id": self.bid_id,
            "tender_id": self.tender_id,
            "supplier": self.supplier,
            "category": self.category,
            "stage": self.stage.value,
            "status": status,
            "documents": [{"file_id": d["file_id"], "file_name": d.get("file_name"),
                           "doc_role": d.get("doc_role"), "stage_status": d.get("stage_status", "ok")}
                          for d in self.documents],
            "events": self.events,
            "result": self.result,
            "error": self.error,
        }


# --------------------------------------------------------------------------
# Job store (in-memory, phase P0) + background executor
# --------------------------------------------------------------------------
_jobs: dict[str, PipelineJob] = {}
_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pipeline")


def create_job(request_id: str, bid_id: str, tender_id: str, supplier: str,
               category: str, documents: list[dict]) -> PipelineJob:
    with _lock:
        job = PipelineJob(request_id=request_id, bid_id=bid_id, tender_id=tender_id,
                          supplier=supplier, category=category, documents=documents)
        _jobs[request_id] = job
        return job


def get_job(request_id: str) -> PipelineJob | None:
    with _lock:
        return _jobs.get(request_id)


def start(job: PipelineJob) -> None:
    """Kick off the pipeline in a background thread; returns immediately."""
    _executor.submit(run_pipeline, job)


def _record(job: PipelineJob, stage: str, status: str, runtime_ms: int = 0, message: str = "") -> None:
    event = {"stage": stage, "status": status, "ts": _now(),
             "runtime_ms": runtime_ms, "message": message}
    job.events.append(event)
    try:
        db.insert_pipeline_event(job.request_id, job.bid_id, stage, status,
                                 event["ts"], runtime_ms, message)
    except Exception:  # noqa: BLE001 — event logging must never kill the pipeline
        pass


# --------------------------------------------------------------------------
# Pipeline execution
# --------------------------------------------------------------------------
def run_pipeline(job: PipelineJob) -> None:
    if not job.documents:
        job.error = "No documents to process"
        job.stage = Stage.FAILED
        _record(job, "upload", "error", 0, job.error)
        return

    try:
        _record(job, "upload", "done", 0, f"{len(job.documents)} file(s) accepted")

        # --- Stage 1: OCR / text extraction -------------------------------
        job.stage = Stage.OCR_RUNNING
        _record(job, "ocr", "running", 0, "Extracting text from documents")

        started = time.perf_counter()
        docs = [StoredDocument(file_id=d["file_id"], doc_role=d["doc_role"], path=d["store_path"])
                for d in job.documents]
        extraction = OcrExtractor(engine=settings.ocr_engine, lang=settings.ocr_lang).extract(
            docs, request_id=job.request_id
        )
        extraction["tender_id"] = job.tender_id
        extraction["bid_id"] = job.bid_id
        job.extraction = extraction

        pages = sum(len(d.get("pages", [])) for d in extraction.get("documents", []))
        blocks = sum(len(p.get("text_blocks", []))
                     for d in extraction.get("documents", [])
                     for p in d.get("pages", []))
        ocr_ms = int((time.perf_counter() - started) * 1000)
        job.stage = Stage.OCR_COMPLETE
        _record(job, "ocr", "done", ocr_ms,
                f"{pages} page(s), {blocks} block(s); extraction status={extraction['status']}")

        # --- Stage 3: rule validation (Stage 2 NLP is a no-op in P0) -------
        job.stage = Stage.VALIDATION_RUNNING
        _record(job, "validation", "running", 0, "Evaluating compliance rules")

        started = time.perf_counter()
        rules = db.fetch_rules(job.tender_id)
        registry = RuleRegistry()
        registry.load_rules(rules)
        engine = RuleEngine(registry=registry, llm_enabled=settings.llm_enabled)
        job.result = engine.evaluate(extraction, job.tender_id)

        db.insert_rule_results(job.bid_id, job.result.get("results", []))
        db.update_bid_status(job.bid_id, job.result["overall_status"])

        ms = int((time.perf_counter() - started) * 1000)
        n = len(job.result.get("results", []))
        job.stage = Stage.VALIDATION_COMPLETE
        _record(job, "validation", "done", ms,
                f"{n} rule(s) evaluated -> {job.result['overall_status']}")
    except Exception as exc:  # noqa: BLE001
        job.error = f"{type(exc).__name__}: {exc}"
        job.stage = Stage.FAILED
        _record(job, "validation", "error", 0, job.error)