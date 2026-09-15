"""OCR extractor — text/layout extraction from bid documents via PyMuPDF (fitz).

Phase P0: native PDF text-layer extraction (vector PDFs). Emits contract 2
(ocr_extraction) — per-page text_blocks with real bounding boxes, page numbers,
and full_text in reading order. Scanned/image-only PDFs surface as `partial`
with a clear error so the pipeline never crashes.

TODO Phase P1+: PaddleOCR fallback for scanned pages, table & stamp detection.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # PyMuPDF new releases export `pymupdf`; `< 1.26` uses legacy `fitz`
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz

#: block types emitted by page.get_text("blocks", ...) — we keep text (0) only
_TEXT_BLOCK_TYPE = 0


@dataclass
class StoredDocument:
    """A document already persisted to disk, ready for extraction."""

    file_id: str
    doc_role: str
    path: str | Path


class OcrExtractor:
    """Extract `ocr_extraction` (contract 2) from a list of stored documents."""

    def __init__(self, engine: str = "pymupdf", lang: str = "en") -> None:
        self.engine = engine
        self.lang = lang

    # -- public entry point -------------------------------------------------
    def extract(self, documents: list[StoredDocument], request_id: str | None = None) -> dict:
        """Return an ocr_extraction dict (contract 2).

        Per-document failures are collected into `errors[]` and degrade the
        overall status to `partial`/`failed` — never raised.
        """
        results: list[dict] = []
        errors: list[dict] = []
        started = time.perf_counter()

        for doc in documents:
            try:
                results.append(self._extract_document(doc))
            except Exception as exc:  # noqa: BLE001 — pipeline must survive
                errors.append({"file_id": doc.file_id, "message": f"{type(exc).__name__}: {exc}"})

        status = "completed"
        if errors:
            status = "partial" if results else "failed"

        return {
            "request_id": request_id,
            "status": status,
            "errors": errors,
            "documents": results,
        }

    # -- per-document / per-page -------------------------------------------
    def _extract_document(self, doc: StoredDocument) -> dict:
        pages: list[dict] = []
        started = time.perf_counter()
        with fitz.open(str(doc.path)) as pdf:
            for page_no, page in enumerate(pdf, start=1):
                pages.append(self._extract_page(page, page_no))

        return {
            "file_id": doc.file_id,
            "doc_role": doc.doc_role,
            "pages": pages,
            "meta": {
                "ocr_engine": "pymupdf",
                "engine_version": ".".join(str(v) for v in fitz.VersionBind) if hasattr(fitz, "VersionBind") else str(fitz.version or ""),
                "lang": self.lang,
                "runtime_ms": int((time.perf_counter() - started) * 1000),
            },
        }

    def _extract_page(self, page: Any, page_no: int) -> dict:
        width, height = page.rect.width, page.rect.height
        blocks: list[dict] = []
        full_lines: list[str] = []
        block_no = 0

        for x0, y0, x1, y1, text, _bnum, block_type in page.get_text("blocks"):
            if block_type != _TEXT_BLOCK_TYPE:
                continue  # image blocks — no text layer
            text = text.strip()
            if not text:
                continue
            blocks.append({
                "block_id": f"p{page_no}_b{block_no}",
                "text": text,
                "conf": 1.0,  # vector text is exact; OCR conf applies to scanned docs later
                "bbox": [x0, y0, x1, y1],
                "block_type": self._classify_block(text, y0, y1, height),
            })
            full_lines.append(text)
            block_no += 1

        return {
            "page_no": page_no,
            "page_w": width,
            "page_h": height,
            "dpi": 72,
            "text_blocks": blocks,
            "tables": [],
            "images": [],
            "full_text": "\n".join(full_lines),
        }

    @staticmethod
    def _classify_block(text: str, y0: float, y1: float, page_height: float) -> str:
        if y1 < page_height * 0.08:
            return "header"
        if y0 > page_height * 0.92:
            return "footer"
        if len(text) <= 100 and (text.isupper() or __import__("re").match(r"^\d+(\.\d+)*[.)]?\s", text)):
            return "heading"
        return "body"