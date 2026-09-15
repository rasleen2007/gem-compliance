"""OCR extractor — text/table/stamp extraction from bid documents.

Input:  list[StoredDocument] (paths on disk)
Output: contracts/ocr_extraction (schema: ocr_extraction.schema.json)

TODO implement in Phase P0:
- render PDF pages via pymupdf; load images via PIL
- run PaddleOCR (settings.OCR_ENGINE/lang from env) per page
- group lines into text_blocks with block_type heuristics (heading font size/
  position, header/footer, table_cell when inside detected table bbox)
- detect stamp/signature/logo image regions (color/edge heuristics) + inline OCR
- populate full_text in reading order; emit status completed|partial|failed
"""

from dataclasses import dataclass, field


@dataclass
class StoredDocument:
    file_id: str
    doc_role: str
    path: str


class OcrExtractor:
    def __init__(self, engine: str = "paddleocr", lang: str = "en") -> None:
        self.engine = engine
        self.lang = lang
        # self._model = None  # lazy-load heavy model

    def extract(self, documents: list[StoredDocument]) -> dict:
        """Return an ocr_extraction dict (contract 2)."""
        raise NotImplementedError("implement in MVP Phase P0")

    def _extract_page(self, file_id: str, page_no: int, render: object) -> dict:
        """text_blocks/tables/images/full_text for one page."""
        raise NotImplementedError