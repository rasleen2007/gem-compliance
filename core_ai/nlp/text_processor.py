"""Text processing — section segmentation, keyword tagging, table linkage.

Stage 2 (contract 3 precursor). Groups OCR text blocks into clean document
sections headed by heading-typed blocks, attaches domain keywords and links the
tables detected on the same page to the section.

Output shape (per document, keyed by file_id):
    {file_id: [{section_id, heading, body, keywords, page, entities, tables_normalized}]}
"""

DOMAIN_KEYWORDS = (
    "EMD", "Earnest Money", "Bank Guarantee", "Eligibility", "Financial",
    "Technical", "Certificate", "Turnover", "Price Breakup", "Price Schedule",
    "GSTIN", "PAN", "Delivery", "Warranty", "Declaration", "Valid",
    "Incorporation", "Net Worth", "Turnover", "Registration",
)


def _scan_keywords(text: str) -> list[str]:
    lowered = text.lower()
    return [kw for kw in DOMAIN_KEYWORDS if kw.lower() in lowered]


def _tables_on_page(page: dict) -> list[str]:
    return [table.get("table_id") for table in page.get("tables", [])]


def segment_sections(extraction: dict) -> dict[str, list[dict]]:
    """Segment a full `ocr_extraction` into sections grouped by file_id."""
    grouped: dict[str, list[dict]] = {}
    section_counter = 0

    for document in extraction.get("documents", []):
        file_id = document.get("file_id")
        sections: list[dict] = []
        current: dict | None = None

        for page in document.get("pages", []):
            page_no = page.get("page_no", 1)
            page_tables = _tables_on_page(page)

            for block in page.get("text_blocks", []):
                text = block.get("text", "").strip()
                if not text:
                    continue
                if block.get("block_type") == "heading":
                    if current is not None:
                        sections.append(current)
                        current = None
                    section_counter += 1
                    current = {
                        "section_id": f"s{section_counter}",
                        "heading": text[:120],
                        "body": "",
                        "keywords": _scan_keywords(text),
                        "page": page_no,
                        "entities": [],
                        "tables_normalized": list(page_tables),
                    }
                else:
                    if current is None:
                        # Body text before any heading -> preamble section
                        section_counter += 1
                        current = {
                            "section_id": f"s{section_counter}",
                            "heading": "Document Preamble",
                            "body": "",
                            "keywords": [],
                            "page": page_no,
                            "entities": [],
                            "tables_normalized": list(page_tables),
                        }
                    current["body"] += text + "\n"
                    current["keywords"].extend(_scan_keywords(text))
                    current["tables_normalized"].extend(page_tables)

            if current is not None:
                sections.append(current)
                current = None

        for section in sections:
            section["keywords"] = list(dict.fromkeys(section["keywords"]))
            section["tables_normalized"] = list(dict.fromkeys(section["tables_normalized"]))
        grouped[file_id] = sections

    return grouped