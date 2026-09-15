"""Entity extraction — typed entities + key-value pairs for the rules engine.

Consumes an (optionally layout-enriched) `ocr_extraction`, segments it via
`text_processor`, and produces the structured **parsed_document** bundle
(contract 3) exactly per `parsed_document.schema.json`:

    parsed_document { request_id, tender_id, bid_id, status, documents[] }
    documents[]      { file_id, doc_role, sections[], key_value_pairs[],
                       entities[], tables_normalized[], summary, confidence }

Extracted field vocabulary (used by rule `target` values):
    GSTIN, PAN, CIN, COMPANY_REGISTRATION_NUMBER,
    CERT_VALIDITY (certificate/doc validity date),
    INCORPORATION_DATE, TURNOVER_<FY> (financial year turnover amounts).

All extraction is local regex + keyword vocabulary — no external APIs.
"""

import re

from core_ai.nlp.text_processor import segment_sections

# --------------------------------------------------------------------------
# Vocabularies / patterns
# --------------------------------------------------------------------------
#: canonical GSTIN: 2 state digits + PAN(10) + entity code(1) + Z + checksum(1)
GSTIN_RE = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
#: PAN: 5 letters + 4 digits + 1 letter (word-boundary isolated)
PAN_RE = re.compile(r"(?<![0-9A-Z])[A-Z]{5}[0-9]{4}[A-Z](?![0-9A-Z])")
#: CIN: L|U + 5 digits + 2 state letters + 4 year digits + 3 type letters + 6 sequence
CIN_RE = re.compile(r"\b[LUU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b")
#: generic registration number near a labelling keyword
REG_NO_RE = re.compile(r"(?i)\b(?:regn|regd|registration)\s*(?:no\.?|number)?\s*[:#.\- ]*([A-Z0-9]{4,22})")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")

_VALIDITY_KEYWORDS = re.compile(r"\b(?:valid\s+till|valid\s+up\s+to|valid\s+through|validity|expires?\s+on|expiry)\b", re.IGNORECASE)
_INCORP_KEYWORDS = re.compile(r"\b(?:date\s+of\s+incorporation|incorporated\s+on|incorporated\s+at)\b", re.IGNORECASE)
#: financial year + amount on the same (multi-rendered) line, Indian formats
FY_AMOUNT_RE = re.compile(
    r"(?:(?:F\.?\s?Y\.?|Financial\s+Year)\s*[:.\- ]?\s*)?"
    r"(\d{4})\s*[-–/]\s*(\d{2,4})"
    r"\D{0,70}?"
    r"(?:(?:Rs\.?|INR|₹)\s*)?([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?",
    re.IGNORECASE,
)

_LIMITS = {"lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "cr": 10_000_000}


def _to_float(value: str, multiplier: str | None) -> float:
    return float(str(value).replace(",", "")) * _LIMITS.get((multiplier or "").lower(), 1)


def _span(page_no: int, start: int, end: int) -> dict:
    return {"page": page_no, "start": start, "end": end}


# --------------------------------------------------------------------------
# Field extractors (each returns entity + optional kv pair + source span)
# --------------------------------------------------------------------------
def _gstin(page_no: int, text: str) -> list[dict]:
    out = []
    for match in GSTIN_RE.finditer(text):
        out.append({
            "entity": "GSTIN", "value": match.group(0), "normalized_value": match.group(0),
            "confidence": 1.0, "source_span": _span(page_no, match.start(), match.end()),
        })
    return out


def _pan(page_no: int, text: str) -> list[dict]:
    masked = GSTIN_RE.sub(" " * 15, text)  # strip GSTINs so PAN scan never double-hits
    out = []
    for match in PAN_RE.finditer(masked):
        out.append({
            "entity": "PAN", "value": match.group(0), "normalized_value": match.group(0),
            "confidence": 1.0, "source_span": _span(page_no, match.start(), match.end()),
        })
    return out


def _cin_and_regno(page_no: int, text: str) -> list[dict]:
    out = []
    for match in CIN_RE.finditer(text):
        out.append({
            "entity": "CIN", "value": match.group(0), "normalized_value": match.group(0),
            "confidence": 1.0, "source_span": _span(page_no, match.start(), match.end()),
        })
    for match in REG_NO_RE.finditer(text):
        raw = match.group(1)
        if CIN_RE.search(raw) or len(raw) < 4:
            continue
        out.append({
            "entity": "COMPANY_REGISTRATION_NUMBER", "value": raw,
            "normalized_value": raw, "confidence": 0.85,
            "source_span": _span(page_no, match.start(), match.end()),
        })
    return out


def _near_keyword(page_no: int, text: str, keyword_re: re.Pattern, pattern_re: re.Pattern,
                  entity_name: str, window: int = 220) -> list[dict]:
    """Dates appearing shortly after a labelling keyword (validity / incorporation)."""
    out = []
    for kw in keyword_re.finditer(text):
        chunk = text[kw.start():kw.end() + window]
        match = pattern_re.search(chunk)
        if not match:
            continue
        start = kw.start() + match.start()
        out.append({
            "entity": entity_name, "value": match.group(0),
            "normalized_value": match.group(0), "confidence": 0.9,
            "source_span": _span(page_no, start, kw.start() + match.end()),
        })
    return out


def _turnovers(page_no: int, text: str) -> list[dict]:
    out = []
    for match in FY_AMOUNT_RE.finditer(text):
        year = int(match.group(1))
        fy = f"TURNOVER_{year}-{str(year + 1)[2:]}"
        amount = _to_float(match.group(3), match.group(4))
        out.append({
            "entity": fy, "value": match.group(0),
            "normalized_value": amount, "confidence": 0.85,
            "source_span": _span(page_no, match.start(), match.end()),
        })
    return out


# --------------------------------------------------------------------------
# Document assembler
# --------------------------------------------------------------------------
def _extract_document(document: dict, sections: list[dict]) -> dict:
    file_id = document.get("file_id")
    doc_role = document.get("doc_role")
    entities: list[dict] = []

    for page in document.get("pages", []):
        page_no = page.get("page_no", 1)
        text = page.get("full_text", "")
        if not text:
            continue
        entities.extend(_gstin(page_no, text))
        entities.extend(_pan(page_no, text))
        entities.extend(_cin_and_regno(page_no, text))
        entities.extend(_near_keyword(page_no, text, _VALIDITY_KEYWORDS, DATE_RE, "CERT_VALIDITY"))
        entities.extend(_near_keyword(page_no, text, _INCORP_KEYWORDS, DATE_RE, "INCORPORATION_DATE"))
        entities.extend(_turnovers(page_no, text))

    # key-value pairs: one per distinct entity kind, first occurrence
    key_value_pairs: list[dict] = []
    seen_keys: set[str] = set()
    for entity in entities:
        key = entity["entity"]
        kind = key.split("_", 1)[0] if key.startswith("TURNOVER_") else key
        if kind in seen_keys:
            continue
        seen_keys.add(kind)
        key_value_pairs.append({
            "key": kind,
            "value": entity["value"],
            "confidence": entity["confidence"],
            "source_span": entity["source_span"],
        })

    # normalized tables from detected table blocks
    tables_normalized: list[dict] = []
    for page in document.get("pages", []):
        for table in page.get("tables", []):
            rows = table.get("rows", [])
            columns = rows[0] if rows else []
            body = rows[1:] if len(rows) > 1 else []
            tables_normalized.append({
                "table_id": table.get("table_id"),
                "columns": columns,
                "rows": body,
            })

    confidence = round(min(0.97, 0.75 + 0.05 * len(entities)), 2) if entities else 0.65
    summary = (f"{doc_role}: {len(sections)} section(s), "
               f"{len(entities)} entity/field(s), {len(tables_normalized)} table(s) detected")

    return {
        "file_id": file_id,
        "doc_role": doc_role,
        "sections": sections,
        "key_value_pairs": key_value_pairs,
        "entities": entities,
        "tables_normalized": tables_normalized,
        "summary": summary,
        "confidence": confidence,
    }


def to_parsed_document(extraction: dict, request_id: str, tender_id: str, bid_id: str) -> dict:
    """Build a full parsed_document bundle (contract 3) from an ocr_extraction."""
    sections_map = segment_sections(extraction)
    documents: list[dict] = []
    for document in extraction.get("documents", []):
        file_id = document.get("file_id")
        documents.append(_extract_document(document, sections_map.get(file_id, [])))

    return {
        "request_id": request_id,
        "tender_id": tender_id,
        "bid_id": bid_id,
        "status": extraction.get("status", "completed"),
        "documents": documents,
    }