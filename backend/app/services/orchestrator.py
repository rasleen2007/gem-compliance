"""Pipeline orchestrator — drives Stages 1-3 from docs/02_core_workflow.md.

Phase P1 flow:
  upload (accepted) -> OCR text extraction -> layout parsing (tables/stamps/
  signatures) -> NLP structuring (parsed_document) -> rule validation.

Jobs run on a background thread pool; `pipeline_events` are persisted to SQLite
on every transition so /jobs and /dashboard can rebuild the timeline.
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
from core_ai.ocr.layout_parser import LayoutParser
from core_ai.nlp.entity_extractor import to_parsed_document
from core_ai.rules.engine import RuleEngine
from core_ai.rules.rule_registry import RuleRegistry
from app.schemas.documents import ParsedBundle
from app.schemas.validation import ValidationResult


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
    parsed: dict | None = None
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
# Job store (in-memory, P0/P1) + background executor
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
    _executor.submit(run_pipeline, job)


def _record(job: PipelineJob, stage: str, status: str, runtime_ms: int = 0, message: str = "") -> None:
    event = {"stage": stage, "status": status, "ts": _now(),
             "runtime_ms": runtime_ms, "message": message}
    job.events.append(event)
    try:
        db.insert_pipeline_event(job.request_id, job.bid_id, stage, status,
                                 event["ts"], runtime_ms, message)
    except Exception:  # noqa: BLE001 — event logging never kills the pipeline
        pass


# --------------------------------------------------------------------------
# Stage helpers (also used by POST /validate re-runs)
# --------------------------------------------------------------------------
def _extract_job_documents(job: PipelineJob, paths: dict[str, str]) -> dict:
    """Stage 1+2, per-file resilient: a single corrupt/empty document must not
    kill the whole pipeline.

    OcrExtractor already isolates per-file failures into ``extraction["errors"]``
    (degrading status to "partial"). Here we surface each failure as its own
    `ocr` error pipeline_event, flip that document's DB row to stage='failed',
    and keep going with the remaining valid files.
    """
    docs = [StoredDocument(file_id=d["file_id"], doc_role=d["doc_role"], path=d["store_path"])
            for d in job.documents]
    extraction = OcrExtractor(engine=settings.ocr_engine, lang=settings.ocr_lang).extract(
        docs, request_id=job.request_id)
    extraction["tender_id"] = job.tender_id
    extraction["bid_id"] = job.bid_id
    LayoutParser().enrich(extraction, paths)

    for err in extraction.get("errors", []):
        file_id = err.get("file_id", "?")
        message = err.get("message", "Unknown extraction error")
        _record(job, "ocr", "error", 0, f"File {file_id} failed ({message})")
        try:
            db.update_document_stage(file_id, stage="failed", stage_status="error")
        except Exception:  # noqa: BLE001 — doc-stage update never kills the pipeline
            pass
    return extraction


def build_parsed(job: PipelineJob, paths: dict[str, str]) -> dict:
    """Stage 1+2: re-run extraction + layout + NLP for a job's stored documents."""
    extraction = _extract_job_documents(job, paths)
    return to_parsed_document(extraction, job.request_id, job.tender_id, job.bid_id)


def evaluate(job: PipelineJob) -> dict:
    """Stage 3: run the rule pack against the job's parsed bundle."""
    rules = db.fetch_rules(job.tender_id)
    registry = RuleRegistry()
    registry.load_rules(rules)
    engine = RuleEngine(registry=registry, llm_enabled=settings.llm_enabled)
    return engine.evaluate(job.parsed, job.tender_id)


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
        paths = {d["file_id"]: d["store_path"] for d in job.documents}

        # --- Stage 1: OCR + layout ----------------------------------------
        job.stage = Stage.OCR_RUNNING
        _record(job, "ocr", "running", 0, "Extracting text and layout regions")

        started = time.perf_counter()
        extraction = _extract_job_documents(job, paths)
        job.extraction = extraction

        valid_docs = extraction.get("documents", [])
        failed_docs = extraction.get("errors", [])
        if not valid_docs:
            job.error = ("All uploaded files failed text extraction - no usable document remains. "
                         "Re-upload valid PDF files.")
            job.stage = Stage.FAILED
            _record(job, "ocr", "error", int((time.perf_counter() - started) * 1000), job.error)
            return

        pages = sum(len(d.get("pages", [])) for d in valid_docs)
        blocks = sum(len(p.get("text_blocks", []))
                     for d in valid_docs
                     for p in d.get("pages", []))
        tables = sum(len(p.get("tables", []))
                     for d in valid_docs
                     for p in d.get("pages", []))
        regions = sum(len(p.get("images", []))
                      for d in valid_docs
                      for p in d.get("pages", []))
        ocr_ms = int((time.perf_counter() - started) * 1000)
        job.stage = Stage.OCR_COMPLETE
        ocr_summary = f"{pages} page(s), {blocks} block(s), {tables} table(s), {regions} region(s)"
        if failed_docs:
            ocr_summary += (f" - {len(failed_docs)} corrupt file(s) isolated; "
                            f"remaining {len(valid_docs)} doc(s) validated")
        _record(job, "ocr", "done", ocr_ms, ocr_summary)

        # --- Stage 2: NLP structuring --------------------------------------
        job.stage = Stage.NLP_RUNNING
        _record(job, "nlp", "running", 0, "Structuring sections and extracting entities")

        started = time.perf_counter()
        parsed_bundle = to_parsed_document(extraction, job.request_id, job.tender_id, job.bid_id)
        job.parsed = ParsedBundle.model_validate(parsed_bundle).model_dump()  # contract-3 gate

        n_docs = len(job.parsed.get("documents", []))
        n_sections = sum(len(d.get("sections", [])) for d in job.parsed.get("documents", []))
        n_entities = sum(len(d.get("entities", [])) for d in job.parsed.get("documents", []))
        nlp_ms = int((time.perf_counter() - started) * 1000)
        job.stage = Stage.NLP_RUNNING
        _record(job, "nlp", "done", nlp_ms,
                f"{n_docs} doc(s), {n_sections} section(s), {n_entities} entit(ies)")

        # --- Stage 3: rule validation ---------------------------------------
        job.stage = Stage.VALIDATION_RUNNING
        _record(job, "validation", "running", 0, "Evaluating compliance rules")

        started = time.perf_counter()
        job.result = evaluate(job)
        job.result = ValidationResult.model_validate(job.result).model_dump(by_alias=True)  # contract-5 gate

        db.insert_rule_results(job.bid_id, job.result.get("results", []))
        db.update_bid_status(job.bid_id, job.result["overall_status"])

        ms = int((time.perf_counter() - started) * 1000)
        n = len(job.result.get("results", []))
        job.stage = Stage.VALIDATION_COMPLETE
        _record(job, "validation", "done", ms,
                f"{n} rule(s) evaluated -> {job.result['overall_status']}")

        for doc in extraction.get("documents", []):
            try:
                db.update_document_stage(doc.get("file_id"), stage="validated", stage_status="ok")
            except Exception:  # noqa: BLE001 — doc-stage update never kills the pipeline
                pass
    except Exception as exc:  # noqa: BLE001
        job.error = f"{type(exc).__name__}: {exc}"
        job.stage = Stage.FAILED
        _record(job, "validation", "error", 0, job.error)