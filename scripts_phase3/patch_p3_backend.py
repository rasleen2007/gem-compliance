"""P3 backend patch: multi-document cross-checking (TRUE multi-file identity
reconciliation) + surface it in the rules engine.

SCHEMA NOTE (verified before writing): jsonschema is a *runtime dependency only
in requirements.txt* — no runtime code imports it; it is exercised exclusively
in `backend/tests/test_contracts.py` against the Contract-1 / Contract-2
*fixtures* (document_upload.schema.json, validation_rule.schema.json). The
generated `parsed_document` bundle is NOT schema-validated at runtime, so
additive bundle keys are safe and the schema fixture stays untouched.

entity_extractor.py:
  - new `_company_name()` extractor producing COMPANY_NAME entities
    (label-vocabulary: "Name of Company" / "Company Name" / "M/s <name>").
  - new cross-document pass that reconciles IDENTITY fields across every
    uploaded file: GSTIN, PAN, CIN, COMPANY_REGISTRATION_NUMBER,
    INCORPORATION_DATE, and COMPANY_NAME. Each field whose normalized values
    disagree between two or more files becomes a `cross_check` conflict entry.
  - `to_parsed_document()` gains `"cross_checks"` (list of conflict records)
    and `"has_cross_check_conflict"` (bool) on the bundle.

engine.py:
  - new `cross_check` operator dispatch -> `_eval_cross_check` which reads the
    bundle's `cross_checks`/`has_cross_check_conflict` and turns the
    target-field conflicts into rule verdicts (warn|fail) with the conflicting
    values as evidence. Conflicts also surface into `_aggregate` counts.
"""

from pathlib import Path

ROOT = Path(r"D:\sih")
EE = ROOT / "core_ai" / "nlp" / "entity_extractor.py"
ENG = ROOT / "core_ai" / "rules" / "engine.py"

made: list[str] = []


def split(text: str) -> list[str]:
    return text.splitlines(keepends=True)


def join(lines: list[str]) -> str:
    return "".join(lines)


def find_once(lines: list[str], anchor: str, label: str) -> int:
    hits = [i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == anchor]
    if len(hits) != 1:
        raise SystemExit(f"ABORTED ({label}): anchor found {len(hits)}x, need 1. No writes made.\n"
                         f"anchor={anchor!r}")
    return hits[0]


def insert_after(lines: list[str], anchor: str, block: str, label: str) -> list[str]:
    idx = find_once(lines, anchor, label)
    return lines[: idx + 1] + split(block) + lines[idx + 1 :]


# ==========================================================================
# 1) entity_extractor.py
# ==========================================================================
ee_text = EE.read_text(encoding="utf-8")
ee_lines = split(ee_text)

if "def _company_name" not in ee_text:
    # -- 1a. COMPANY_NAME extractor, inserted right before the assembler ----
    company_block = (
        "#: identity fields that MUST agree across all uploaded documents\n"
        "CROSS_CHECK_FIELDS = (\"GSTIN\", \"PAN\", \"CIN\", "
        "\"COMPANY_REGISTRATION_NUMBER\", \"INCORPORATION_DATE\", \"COMPANY_NAME\")\n"
        "\n"
        "#: company-name label vocabulary (financial spreadsheet vs certificate)\n"
        "_NAME_KEYWORDS = re.compile(\n"
        "    r\"(?:Name\\s+of\\s+(?:the\\s+)?(?:Company|Company\\s+Name)|"
        "Name\\s+of\\s+Company|Company\\s+Name|M/S\\.?|M\\s*s\\.?)\",\n"
        "    re.IGNORECASE,\n"
        ")\n"
        "\n"
        "\n"
        "def _company_name(page_no: int, text: str) -> list[dict]:\n"
        "    \"\"\"Company legal/business name, used for cross-document identity checks.\"\"\"\n"
        "    out: list[dict] = []\n"
        "    trimmed = text.strip()\n"
        "    for kw in _NAME_KEYWORDS.finditer(trimmed):\n"
        "        tail = trimmed[kw.end() : kw.end() + 90]\n"
        "        m = re.match(r\"\\s*[:\\-]?\\s*([A-Z][A-Za-z0-9&.,'()/ -]{4,78})?\", tail)\n"
        "        if not m or not m.group(1):\n"
        "            continue\n"
        "        raw = m.group(1).strip().rstrip(\".,;:\")\n"
        "        if len(raw) < 5:\n"
        "            continue\n"
        "        out.append({\n"
        "            \"entity\": \"COMPANY_NAME\", \"value\": raw,\n"
        "            \"normalized_value\": raw.upper(), \"confidence\": 0.86,\n"
        "            \"source_span\": _span(page_no, kw.end() + m.start(), kw.end() + m.end()),\n"
        "        })\n"
        "    return out\n"
        "\n"
        "\n"
        "def _cross_check_documents(documents: list[dict]) -> list[dict]:\n"
        "    \"\"\"Reconcile identity fields across all files; each differing\n"
        "    normalized value pair across files becomes a conflict entry.\"\"\"\n"
        "    by_field: dict[str, list[dict]] = {}\n"
        "    for doc in documents:\n"
        "        file_id = doc.get(\"file_id\")\n"
        "        role = doc.get(\"doc_role\")\n"
        "        for ent in doc.get(\"entities\", []):\n"
        "            if ent.get(\"entity\") not in CROSS_CHECK_FIELDS:\n"
        "                continue\n"
        "            by_field.setdefault(ent[\"entity\"], []).append({\n"
        "                \"file_id\": file_id, \"doc_role\": role,\n"
        "                \"value\": ent.get(\"value\"),\n"
        "                \"normalized_value\": ent.get(\"normalized_value\"),\n"
        "                \"confidence\": ent.get(\"confidence\"),\n"
        "                \"source_span\": ent.get(\"source_span\"),\n"
        "            })\n"
        "\n"
        "    cross_checks: list[dict] = []\n"
        "    for field, entries in by_field.items():\n"
        "        distinct = {e[\"normalized_value\"] for e in entries}\n"
        "        if len(distinct) <= 1:\n"
        "            continue\n"
        "        cross_checks.append({\n"
        "            \"field\": field, \"status\": \"conflict\",\n"
        "            \"values\": entries,\n"
        "            \"distinct_values\": sorted(str(v) for v in distinct),\n"
        "            \"note\": (f\"{field} disagrees across {len(distinct)} document(s) \"\n"
        "                      f\"({', '.join(str(v) for v in distinct)})\"),\n"
        "        })\n"
        "    return cross_checks\n"
        "\n"
        "\n"
    )
    anchor_asm = "def to_parsed_document(extraction: dict, request_id: str, tender_id: str, bid_id: str) -> dict:"
    ee_lines = insert_after(ee_lines, anchor_asm, company_block, "entity_assem")
    made.append("_company_name + _cross_check_documents added")
else:
    made.append("(entity_extractor already had cross-check code; skipped)")

# -- 1b. wire `_company_name` into the per-page entity assembly loop --------
if "entities.extend(_company_name(page_no, text))" not in join(ee_lines):
    anchor_page = "        entities.extend(_turnovers(page_no, text))"
    ee_lines = insert_after(ee_lines, anchor_page,
                            "        entities.extend(_company_name(page_no, text))\n",
                            "entity_pageloop")
    made.append("wired _company_name into page loop")

# -- 1c. surface cross-check pass in to_parsed_document return ---------------
old_tail = (
    '    return {\n'
    '        "request_id": request_id,\n'
    '        "tender_id": tender_id,\n'
    '        "bid_id": bid_id,\n'
    '        "status": extraction.get("status", "completed"),\n'
    '        "documents": documents,\n'
    '    }\n'
)
new_tail = (
    '    cross_checks = _cross_check_documents(documents)\n'
    '\n'
    '    return {\n'
    '        "request_id": request_id,\n'
    '        "tender_id": tender_id,\n'
    '        "bid_id": bid_id,\n'
    '        "status": extraction.get("status", "completed"),\n'
    '        "has_cross_check_conflict": bool(cross_checks),\n'
    '        "cross_checks": cross_checks,\n'
    '        "documents": documents,\n'
    '    }\n'
)
if "has_cross_check_conflict" not in join(ee_lines):
    cnt = join(ee_lines).count(old_tail)
    if cnt != 1:
        raise SystemExit(f"ABORTED (entity_tail): return-tail anchor {cnt}x. No writes made.")
    ee_lines = split(join(ee_lines).replace(old_tail, new_tail))
    made.append("added cross_check keys to parsed_document bundle")

EE.write_text(join(ee_lines), encoding="utf-8")

# ==========================================================================
# 2) engine.py
# ==========================================================================
eng_text = ENG.read_text(encoding="utf-8")
eng_lines = split(eng_text)

if 'elif operator == "cross_check":' not in eng_text:
    # -- 2a. dispatch branch -------------------------------------------------
    anchor_regex = '            elif operator == "regex":'
    eng_lines = insert_after(eng_lines, anchor_regex,
                             '            elif operator == "cross_check":\n'
                             '                verdict = self._eval_cross_check(rule, parsed)\n',
                             "engine_dispatch")
    made.append("cross_check dispatch branch")

if "def _eval_cross_check" not in join(eng_lines):
    # -- 2b. evaluator -------------------------------------------------------
    eval_block = (
        "\n"
        "    def _eval_cross_check(self, rule: dict, parsed: dict) -> dict:\n"
        "        \"\"\"cross_check: fail when an identity field disagrees across files.\n"
        "        rule.target selects the field (GSTIN/PAN/CIN/...); the bundle's\n"
        "        `cross_checks` list is filtered to that field.\"\"\"\n"
        "        target = rule.get(\"target\", \"\")\n"
        "        field = str(target).upper().replace(\" \", \"_\")\n"
        "        conflicts = [c for c in parsed.get(\"cross_checks\", [])\n"
        "                     if str(c.get(\"field\", \"\")).upper() == field]\n"
        "        if not conflicts:\n"
        "            return {\"rule_id\": rule.get(\"rule_id\"), \"status\": \"pass\",\n"
        "                    \"evidence\": {\"field\": field,\n"
        "                                   \"documents\": len(parsed.get(\"documents\", []))},\n"
        "                    \"reason\": f\"{field} consistent across all documents\",\n"
        "                    \"confidence\": 0.9, \"suggested_action\": \"none\"}\n"
        "        distinct = conflicts[0].get(\"distinct_values\", [])\n"
        "        return {\"rule_id\": rule.get(\"rule_id\"), \"status\": \"fail\",\n"
        "                \"evidence\": {\"field\": field, \"distinct_values\": distinct,\n"
        "                               \"conflict_records\": conflicts},\n"
        "                \"reason\": conflicts[0].get(\"note\",\n"
        "                        f\"{field} differs across documents: {', '.join(distinct)}\"),\n"
        "                \"confidence\": 0.95, \"suggested_action\": \"manual_review\",\n"
        "                \"cross_check_conflict\": True}\n"
        "\n"
    )
    anchor_contains = "    def _eval_contains(self, rule: dict, parsed: dict) -> dict:"
    eng_lines = insert_after(eng_lines, anchor_contains, eval_block, "engine_eval")
    made.append("_eval_cross_check method")

ENG.write_text(join(eng_lines), encoding="utf-8")

# ==========================================================================
# 3) verify: tokenize both files + probe key markers
# ==========================================================================
import io
import tokenize

for path, label in ((EE, "entity_extractor"), (ENG, "engine")):
    src = path.read_text(encoding="utf-8")
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
        n = len(list(toks))
        print(f"[verify] {label}: tokenize OK ({n} tokens)")
    except Exception as exc:
        raise SystemExit(f"[verify] {label} TOKENIZE FAILED: {exc}")

body = EE.read_text(encoding="utf-8")
for probe in ("def _company_name", "def _cross_check_documents",
              "entities.extend(_company_name(page_no, text))",
              "has_cross_check_conflict"):
    print(f"   EE {probe!r}: {body.count(probe)}x")

body2 = ENG.read_text(encoding="utf-8")
for probe in ('operator == "cross_check"', "def _eval_cross_check",
              "cross_check_conflict"):
    print(f"   ENG {probe!r}: {body2.count(probe)}x")

print("\nedits made:")
for m in made:
    print(f"  - {m}")
