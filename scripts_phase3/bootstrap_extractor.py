"""P3 bootstrap: add COMPANY_NAME extraction + multi-doc cross-check pass to
entity_extractor.py. Every insert is anchored to a line that must occur exactly
once; any ambiguity aborts before writing. Script is standalone."""

import re
from pathlib import Path

FILE = Path(r"D:\sih\core_ai\nlp\entity_extractor.py")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def split(text: str):
    return text.splitlines(keepends=True)

def join(lines):
    return "".join(lines)

def find_once(lines, anchor):
    hits = [i for i, ln in enumerate(lines) if anchor == ln.rstrip("\r\n")]
    if len(hits) != 1:
        raise SystemExit(
            f"ABORTED: anchor found {len(hits)}x (need exactly 1). No writes made.\n"
            f"anchor: {anchor!r}"
        )
    return hits[0]

def insert_after(lines, anchor, block_lines):
    idx = find_once(lines, anchor)
    new_lines = []
    new_lines.extend(lines[: idx + 1])
    new_lines.extend(block_lines)
    new_lines.extend(lines[idx + 1 :])
    return new_lines

# ---------------------------------------------------------------------------
# New code block: COMPANY_NAME extractor (inserted before _company_name call)
# ---------------------------------------------------------------------------
COMPANY_BLOCK = '''def _company_name(page_no: int, text: str) -> list[dict]:
    """Extract a legal/business company name used for cross-document identity.

    Matches on common India incorporation labels (M/s, "Name of Company",
    "Company Name", "Private Limited", "Ltd", "LLP"). Values feed the
    cross-document identity cross-check in `to_parsed_document`.
    """
    out: list[dict] = []
    trimmed = text.strip()
    # anchor label headed lines
    for m in re.finditer(
        r"(?mi)^\\s*(?:m/s|ms\\.?)\\s*[:\\-]?\\s*([A-Z][A-Za-z0-9&,'\\.() /-]{3,79})",
        trimmed,
    ):
        raw = m.group(1).strip().rstrip(".,;")
        if len(raw) >= 4:
            out.append({
                "entity": "COMPANY_NAME",
                "value": raw,
                "normalized_value": raw.upper(),
                "confidence": 0.86,
                "source_span": _span(page_no, m.start(), m.end()),
            })
    # "Name of Company" / "Company Name" value after the label
    if not out:
        for m in re.finditer(
            r"(?i)(?:name\\s+of\\s+(?:the\\s+)?company|company\\s+name)"
            r"\\s*[:\\-]?\\s*([A-Z][A-Za-z0-9&,'\\.() /-]{4,79})",
            trimmed,
        ):
            raw = m.group(1).strip().rstrip(".,;")
            if len(raw) >= 4:
                out.append({
                    "entity": "COMPANY_NAME",
                    "value": raw,
                    "normalized_value": raw.upper(),
                    "confidence": 0.8,
                    "source_span": _span(page_no, m.start(), m.end()),
                })
    # corporate-suffix windows (Pvt Ltd / Ltd / LLP) anywhere in text
    if not out:
        for m in re.finditer(
            r"(?i)\\b([A-Z][A-Za-z0-9&,'\\.() /-]{4,59})\\s+"
            r"(?:pvt\\.?\\s+ltd\\.?|private\\s+limited|ltd\\.?|llp)\\b",
            trimmed,
        ):
            raw = m.group(1).strip().rstrip(".,;")
            if len(raw) >= 4:
                out.append({
                    "entity": "COMPANY_NAME",
                    "value": raw,
                    "normalized_value": raw.upper(),
                    "confidence": 0.78,
                    "source_span": _span(page_no, m.start(), m.end()),
                })
    return out


def _cross_check_documents(documents: list[dict]) -> list[dict]:
    """Compare identity fields across all documents.

    Fields compared (normalized_value): CIN, GSTIN, PAN, COMPANY_NAME,
    COMPANY_REGISTRATION_NUMBER, INCORPORATION_DATE. Any field whose normalized
    value differs between two or more documents yields one conflict entry.
    """
    fields = {"CIN", "GSTIN", "PAN", "COMPANY_NAME",
              "COMPANY_REGISTRATION_NUMBER", "INCORPORATION_DATE"}
    by_field: dict[str, list[dict]] = {}
    for doc in documents:
        file_id = doc.get("file_id")
        role = doc.get("doc_role")
        for ent in doc.get("entities", []):
            name = ent.get("entity")
            if name not in fields:
                continue
            norm = ent.get("normalized_value")
            if not norm:
                continue
            by_field.setdefault(name, []).append({
                "file_id": file_id,
                "doc_role": role,
                "value": ent.get("value"),
                "normalized_value": norm,
                "confidence": ent.get("confidence", 0.0),
                "source_span": ent.get("source_span"),
            })

    conflicts: list[dict] = []
    for field, entries in by_field.items():
        distinct = {e["normalized_value"] for e in entries}
        if len(distinct) > 1:
            conflicts.append({
                "field": field,
                "status": "conflict",
                "values": entries,
                "evidence": sorted(str(v) for v in distinct),
                "note": f"{field} differs across {len(entries)} document(s)",
            })
    return conflicts

'''

# ---------------------------------------------------------------------------
# Read current source
# ---------------------------------------------------------------------------
text = FILE.read_text(encoding="utf-8")
if "def _cross_check_documents" in text:
    raise SystemExit("ALREADY PATCHED: cross-check pass present. No writes made.")
lines = split(text)

# ---------------------------------------------------------------------------
# 1) insert _company_name + _cross_check_documents before the assembler header
# ---------------------------------------------------------------------------
anchor1 = "def _extract_document(document: dict, sections: list[dict]) -> dict:"
lines = insert_after(lines, anchor1, split(COMPANY_BLOCK))
print("[1] inserted COMPANY_NAME extractor + cross-check pass")

# ---------------------------------------------------------------------------
# 2) wire _company_name into per-page assembly loop
# ---------------------------------------------------------------------------
anchor_call = "        entities.extend(_turnovers(page_no, text))"
new_call = "        entities.extend(_company_name(page_no, text))"
if new_call not in join(lines):
    lines = insert_after(lines, anchor_call, split(new_call + "\n"))
    print("[2] wired _company_name() into assembly loop")

# ---------------------------------------------------------------------------
# 3) return cross-checks from to_parsed_document
# ---------------------------------------------------------------------------
old_tail = '''    return {
        "request_id": request_id,
        "tender_id": tender_id,
        "bid_id": bid_id,
        "status": extraction.get("status", "completed"),
        "documents": documents,
    }'''
if "cross_checks" not in join(lines):
    new_tail = '''    cross_checks = _cross_check_documents(documents)

    return {
        "request_id": request_id,
        "tender_id": tender_id,
        "bid_id": bid_id,
        "status": extraction.get("status", "completed"),
        "has_cross_check_conflict": bool(cross_checks),
        "cross_checks": cross_checks,
        "documents": documents,
    }'''
    cnt = join(lines).count(old_tail)
    if cnt != 1:
        raise SystemExit(f"ABORTED: return-tail anchor found {cnt}x. No writes made.")
    text2 = join(lines).replace(old_tail, new_tail)
    lines = split(text2)
    print("[3] wired cross_checks keys into parsed_document bundle")
else:
    print("[3] cross_checks already present; skipped")

# ---------------------------------------------------------------------------
# write + verify
# ---------------------------------------------------------------------------
FILE.write_text(join(lines), encoding="utf-8")

import io, tokenize
try:
    tokens = tokenize.generate_tokens(io.StringIO(FILE.read_text(encoding="utf-8")).readline)
    ntok = len(list(tokens))
    print(f"[verify] tokenize OK ({ntok} tokens)")
except Exception as exc:
    raise SystemExit(f"[verify] TOKENIZE FAILED: {exc}")

body = FILE.read_text(encoding="utf-8")
for probe in ("def _company_name", "def _cross_check_documents",
              "_company_name(page_no, text)", "(page_no, text))",
              "has_cross_check_conflict", "cross_checks"):
    print(f"   probe {probe!r}: {body.count(probe)}x")
print("lines now:", len(body.splitlines()))
