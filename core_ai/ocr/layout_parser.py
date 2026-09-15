"""Layout parser — recovers reading order, headings, and table grids.

Consumes raw OCR blocks (contract 2 page shape), returns an enriched layout:
  - reading_order: list of block_ids in document order
  - heading_candidates: block_ids classified as headings (font size / whitespace / numbering)
  - table_bboxes: from pdfplumber (vector PDFs) or geometric clustering (scanned)

TODO implement in Phase P0. Pure functions where possible for testability.
"""


def parse_layout(page: dict) -> dict:
    """Return {'reading_order': [...], 'headings': [...], 'table_regions': [...]}."""
    raise NotImplementedError("implement in MVP Phase P0")


def sort_into_reading_order(blocks: list[dict]) -> list[str]:
    """Top-to-bottom, then left-to-right; used when bbox coords share a row."""
    raise NotImplementedError