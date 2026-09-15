"""Text processing — normalize OCR text, section segmentation, summaries.

Input:  ocr_extraction (contract 2)
Output: paragraph/section segmentation consumed by entity_extractor.

TODO implement in Phase P0:
- clean OCR noise (stray glyphs, page footers, page numbers)
- section segmentation using layout parser headings + body text
- keyword tagging per section (gazetteer: EMD, Bank Guarantee, GSTIN, warranties...)
"""


def clean_text(raw: str) -> str:
    raise NotImplementedError("implement in MVP Phase P0")


def segment_sections(page_blocks: list[dict], layout: dict) -> list[dict]:
    """Return list of {'section_id', 'heading', 'body', 'page', 'keywords'}."""
    raise NotImplementedError