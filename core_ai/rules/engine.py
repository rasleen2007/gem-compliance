"""Deterministic rule engine (Stage 3). Emits contract 5 (validation_result).

Consumes a **parsed_document** bundle (contract 3) produced by the NLP stage,
evolving the Phase P0 EMD baseline into four operator families:

  Rule-DATE  -> date_after / date_before : extracted document date vs a target
                tender deadline (e.g. certificate validity, incorporation date).
  Rule-DOC   -> exists / not_exists      : mandatory attachment presence via
                entity tokens, table refs, or keyword groupings.
  Rule-FIN   -> numeric compare on target `TURNOVER` (multi-line financial
                year turnover parse from the NLP entity index or text scan).
  Rule-XCHK  -> cross_check              : multi-document identity reconciliation
                (GSTIN/PAN/CIN/COMPANY_NAME/... must agree across files); the
                bundle's `cross_checks` conflicts become fail verdicts with the
                per-file discrepancy arrays as evidence.

Server-level resilience is preserved: per-rule exceptions degrade to `error`
status and never abort the batch. All operators run locally — LLM judge remains
opt-in (skipped when disabled).
"""

import re
from datetime import date, datetime
from typing import Any

from core_ai.rules.rule_registry import RuleRegistry, get_registry

# --------------------------------------------------------------------------
# Amount / date / entity vocab (shared with NLP where sensible)
# --------------------------------------------------------------------------
EMD_KEYWORDS = ("EMD", "Earnest Money Deposit", "Earnest Money")

_CURRENCY_RE = re.compile(r"(?:INR|Rs\.?|₹)\s*([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?", re.IGNORECASE)
_NUMBER_RE = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")
#: financial-year + amount lines (Year-YY + amount), Indian formats
_FY_AMOUNT_RE = re.compile(
    r"(?:(?:F\.?\s?Y\.?|Financial\s+Year)\s*[:.\- ]?\s*)?"
    r"(\d{4})\s*[-–/]\s*(\d{2,4})"
    r"\D{0,70}?"
    r"(?:(?:Rs\.?|INR|₹)\s*)?([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?",
    re.IGNORECASE,
)

_LIMITS = {"lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "cr": 10_000_000}

#: date-capable entity names (resolution precedence for date rules)
DATE_ENTITIES = {
    "CERT_VALIDITY": ("CERT_VALIDITY", "VALIDITY_DATE"),
    "VALIDITY_DATE": ("CERT_VALIDITY", "VALIDITY_DATE"),
    "INCORPORATION_DATE": ("INCORPORATION_DATE",),
}

#: table-presence target -> fallback keyword groupings
TABLE_TARGETS = {
    "PRICE_BREAKUP": ("price breakup", "price schedule", "itemized price", "pricing table"),
}

_SIGNATURE_LIKE = ("signature", "authorized signatory", "stamp")


def _to_float(value: str | float, multiplier: str | None) -> float:
    number = float(str(value).replace(",", ""))
    return number * _LIMITS.get((multiplier or "").lower(), 1)


def _pick_amount(window: str) -> re.Match | None:
    """First amount in `window`; currency-prefixed preferred, bare number fallback.

    Bare numbers inside `%` contexts are treated as percentages and skipped.
    """
    match = _CURRENCY_RE.search(window)
    if match:
        return match
    for candidate in _NUMBER_RE.finditer(window):
        if window[candidate.end():candidate.end() + 4].lstrip().startswith("%"):
            continue
        return candidate
    return None


def _parse_date_string(raw: Any) -> date | None:
    if isinstance(raw, date):
        return raw
    try:
        raw_str = str(raw or "").strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_str):
            return date.fromisoformat(raw_str)
        day, month, year = re.split(r"[/-]", raw_str)
        year = int(year)
        if year < 100:
            year += 2000 if year < 50 else 1900
        return date(year, int(day), int(month))
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# Corpus helpers
# --------------------------------------------------------------------------
def _iter_documents(parsed: dict):
    yield from parsed.get("documents", [])


def _corpus_chunks(parsed: dict):
    """Yield searchable text chunks with page/offset provenance.

    Accepts either an `ocr_extraction` (pages) or `parsed_document` (sections)
    shaped input so the engine tolerates both pipeline stages.
    """
    for document in _iter_documents(parsed):
        for page in document.get("pages", []):
            yield {"file_id": document.get("file_id"), "page": page.get("page_no", 1),
                   "text": page.get("full_text", "")}
        for section in document.get("sections", []):
            text = (section.get("heading", "") or "") + " " + (section.get("body", "") or "")
            yield {"file_id": document.get("file_id"), "page": section.get("page", 1), "text": text}


def _entities_index(parsed: dict) -> list[dict]:
    return [entity for document in _iter_documents(parsed) for entity in document.get("entities", [])]


def _tables_index(parsed: dict) -> list[dict]:
    return [table for document in _iter_documents(parsed) for table in document.get("tables_normalized", [])]


class RuleEngine:
    """Evaluates a tender's rule pack against a parsed_document bundle."""

    def __init__(self, registry: RuleRegistry | None = None,
                 llm_enabled: bool = False, llm_client: Any = None) -> None:
        self.registry = registry or get_registry()
        self.llm_enabled = llm_enabled
        self.llm_client = llm_client

    # -- public entry point ------------------------------------------------
    def evaluate(self, parsed: dict, tender_id: str) -> dict:
        rules = [r for r in self.registry.for_tender(tender_id) if r.get("enabled", True)]
        results = [self._apply(rule, parsed) for rule in rules]
        return self._aggregate(results, rules, parsed, tender_id)

    # -- per-rule -----------------------------------------------------------
    def _apply(self, rule: dict, parsed: dict) -> dict:
        operator = rule.get("operator")
        verdict = {"rule_id": rule.get("rule_id"), "status": "skip",
                   "evidence": {}, "reason": "", "confidence": 1.0,
                   "suggested_action": "none"}
        try:
            if operator in (">=", "<=", "==", "!=", ">", "<"):
                verdict = self._eval_numeric(rule, parsed)
            elif operator in ("exists", "not_exists"):
                verdict = self._eval_presence(rule, parsed)
            elif operator in ("date_after", "date_before"):
                verdict = self._eval_date(rule, parsed)
            elif operator == "contains":
                verdict = self._eval_contains(rule, parsed)
            elif operator == "regex":
                verdict = self._eval_regex(rule, parsed)
            elif operator == "cross_check":
                verdict = self._eval_cross_check(rule, parsed)
            elif operator == "llm_judge" and self.llm_enabled:
                verdict = self._eval_llm(rule, parsed)
            else:
                verdict["reason"] = (f"operator {operator!r} not enabled{'' if self.llm_enabled else ' (LLM disabled)'}"
                                     if operator == "llm_judge" else f"operator {operator!r} not implemented")
        except Exception as exc:  # noqa: BLE001 — batch isolation
            verdict.update({"status": "error", "reason": f"{type(exc).__name__}: {exc}",
                            "confidence": 0.0, "suggested_action": "manual_review"})
        return verdict

    # -- Rule-FIN / Rule-EMD: numeric comparisons --------------------------
    def _eval_numeric(self, rule: dict, parsed: dict) -> dict:
        target = rule.get("target", "")
        hit: dict | None = None
        if target in ("EMD_AMOUNT", "EMD_PERCENTAGE"):
            hit = self._scan_amount(parsed)
        elif target == "TURNOVER" or str(target).startswith("TURNOVER"):
            turnover = self._turnover_best(parsed)
            if turnover:
                hit = turnover["hit"]
        else:
            hit = self._first_number(parsed)

        if hit is None:
            return {"rule_id": rule.get("rule_id"), "status": "warn", "evidence": {},
                    "reason": f"No numeric value found for target {target!r}",
                    "confidence": 0.4, "suggested_action": "manual_review"}

        lhs = hit["value"]
        rhs = _to_float(rule.get("expected_value"), None)
        operator = rule.get("operator")
        outcome = {
            ">=": lhs >= rhs, "<=": lhs <= rhs, "==": lhs == rhs,
            "!=": lhs != rhs, ">": lhs > rhs, "<": lhs < rhs,
        }[operator]

        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if outcome else "fail",
            "evidence": self._evidence(hit),
            "reason": f"Extracted {lhs:g} {operator} required {rhs:g}",
            "confidence": 0.95 if outcome else 0.9,
            "suggested_action": "none" if outcome else ("attach_missing_doc" if lhs < rhs else "manual_review"),
        }

    # -- Rule-DOC: presence / absence --------------------------------------
    def _eval_presence(self, rule: dict, parsed: dict) -> dict:
        target = str(rule.get("target", ""))
        expected = rule.get("expected_value")
        corpus = "\n".join(chunk["text"] for chunk in _corpus_chunks(parsed))
        corpus_lower = corpus.lower()
        keyword_group: list[str] = [target]
        evidence: dict = {}
        present = False

        if target.startswith("table:") or target in TABLE_TARGETS:
            name = target.removeprefix("table:")
            def _table_fingerprint(t: dict) -> str:
                cols = t.get("columns") or []
                if isinstance(cols, bool):
                    cols = [str(c) for c in cols] if cols else []
                return f"{str(t.get('table_id',''))} " + " ".join(str(c) for c in cols).lower()
            table_present = any(name.lower() in _table_fingerprint(t) for t in _tables_index(parsed))
            keywords = TABLE_TARGETS.get(name, (name,))
            text_present = any(kw.lower() in corpus_lower for kw in keywords)
            present = table_present or text_present
            evidence = {"found": "detected" if present else None, "source_span": None,
                        "file_id": None, "table_id": None}
        else:
            entity_present = any(
                e.get("entity") == target or e.get("entity", "").startswith(target + "_")
                for e in _entities_index(parsed)
            )
            keyword_group = [k.strip() for k in re.split(r"[|,]", str(expected or ""))]
            keyword_group = [k for k in keyword_group if k] or [target]
            text_present = any(kw.lower() in corpus_lower for kw in keyword_group)
            present = entity_present or text_present
            if entity_present:
                entity = next(
                    (e for e in _entities_index(parsed)
                     if e.get("entity") == target or e.get("entity", "").startswith(target + "_")), None)
                evidence = self._evidence({
                    "value": entity.get("value"), "page": (entity.get("source_span") or {}).get("page", 1),
                    "file_id": None, "context": entity.get("value", ""),
                    "start": (entity.get("source_span") or {}).get("start"),
                    "end": (entity.get("source_span") or {}).get("end"),
                })
            else:
                for kw in keyword_group:
                    idx = corpus_lower.find(kw.lower())
                    if idx != -1:
                        evidence = {"found": kw, "source_span": {"page": None, "start": idx, "end": idx + len(kw)},
                                    "file_id": None, "table_id": None}
                        break

        op = rule.get("operator")
        outcome = present if op == "exists" else not present
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if outcome else "fail",
            "evidence": evidence,
            "reason": f"{target}: '{keyword_group if op == 'exists' else target}' "
                      f"{'present' if present else 'not found'} in parsed document",
            "confidence": 0.9,
            "suggested_action": "none" if outcome else "attach_missing_doc",
        }

    # -- Rule-DATE: before/after a deadline ---------------------------------
    def _eval_date(self, rule: dict, parsed: dict) -> dict:
        target = str(rule.get("target", ""))
        required = _parse_date_string(rule.get("expected_value"))
        hit = self._resolve_date(parsed, target)
        op = rule.get("operator")

        if required is None or hit is None:
            return {"rule_id": rule.get("rule_id"), "status": "skip", "evidence": {},
                    "reason": "No comparable date available", "confidence": 0.5,
                    "suggested_action": "manual_review"}

        extracted = hit["value"]
        outcome = extracted > required if op == "date_after" else extracted < required
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if outcome else "fail",
            "evidence": self._evidence(hit),
            "reason": f"{target} {extracted.isoformat()} {op} deadline {required.isoformat()}",
            "confidence": 0.9,
            "suggested_action": "none" if outcome else "attach_missing_doc",
        }

    # -- Text operators ------------------------------------------------------
    def _eval_contains(self, rule: dict, parsed: dict) -> dict:
        needle = str(rule.get("expected_value", "")).lower()
        corpus = "\n".join(chunk["text"] for chunk in _corpus_chunks(parsed))
        idx = corpus.lower().find(needle) if needle else -1
        found = idx >= 0
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if found else "fail",
            "evidence": {"found": needle if found else None,
                         "source_span": {"start": idx, "end": idx + len(needle)} if found else None},
            "reason": f"Text contains {needle!r}: {'yes' if found else 'no'}",
            "confidence": 0.9,
            "suggested_action": "none" if found else "attach_missing_doc",
        }

    def _eval_cross_check(self, rule: dict, parsed: dict) -> dict:
        """cross_check: fail when an identity field disagrees across files.

        `rule.target` selects the field (GSTIN | PAN | CIN | COMPANY_NAME |
        COMPANY_REGISTRATION_NUMBER | INCORPORATION_DATE). The parsed bundle's
        `cross_checks` / `has_cross_check_conflict` entries are filtered to
        that field; any conflicting record yields a `fail` verdict carrying the
        per-file discrepancy arrays as evidence for the review panel.
        """
        target = str(rule.get("target", "")).upper().replace(" ", "_")
        conflicts = [
            record for record in parsed.get("cross_checks", [])
            if str(record.get("field", "")).upper() == target
        ]
        document_count = len(parsed.get("documents", []))
        base = {"rule_id": rule.get("rule_id"), "source_span": None,
                "file_id": None, "table_id": None}

        if not conflicts:
            return {**base, "status": "pass",
                    "evidence": {"found": f"{target} consistent across all documents",
                                 "source_span": None, "file_id": None, "table_id": None,
                                 "distinct_values": None, "conflict_records": [],
                                 "cross_check_conflict": False},
                    "reason": f"{target} consistent across {document_count} document(s)",
                    "confidence": 0.9, "suggested_action": "none"}

        conflict = conflicts[0]
        distinct = conflict.get("distinct_values", [])
        return {**base, "status": "fail",
                "evidence": {"found": conflict.get(
                        "note", f"{target} differs across documents"),
                             "source_span": None, "file_id": None, "table_id": None,
                             "distinct_values": distinct,
                             "conflict_records": conflicts,
                             "cross_check_conflict": True},
                "reason": conflict.get(
                        "note", f"{target} differs across documents"),
                "confidence": 0.95, "suggested_action": "manual_review"}

    def _eval_regex(self, rule: dict, parsed: dict) -> dict:
        pattern = rule.get("expected_value", "")
        corpus = "\n".join(chunk["text"] for chunk in _corpus_chunks(parsed))
        if not pattern:
            return {"rule_id": rule.get("rule_id"), "status": "error", "evidence": {},
                    "reason": "regex rule missing pattern", "confidence": 0.0,
                    "suggested_action": "manual_review"}
        match = re.search(pattern, corpus) if corpus else None
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if match else "fail",
            "evidence": {"found": match.group(0)} if match else {},
            "reason": f"regex {pattern!r} {'matched' if match else 'no match'}",
            "confidence": 0.9 if match else 0.6,
            "suggested_action": "none" if match else "manual_review",
        }

    def _eval_llm(self, rule: dict, parsed: dict) -> dict:
        instruction = rule.get("expected_value") or rule.get("description", "")
        evidence_text = self._corpus_text(parsed)
        verdict = self.llm_client.judge(str(instruction), evidence_text) if self.llm_client else {}
        return {
            "rule_id": rule.get("rule_id"),
            "status": verdict.get("verdict", "skip"),
            "evidence": {"found": verdict.get("reason")},
            "reason": verdict.get("reason", "llm judge returned no verdict"),
            "confidence": float(verdict.get("confidence", 0.5)),
            "suggested_action": "manual_review" if verdict.get("verdict") != "pass" else "none",
        }

    # -- extraction helpers --------------------------------------------------
    @staticmethod
    def _corpus_text(parsed: dict) -> str:
        return "\n".join(chunk["text"] for chunk in _corpus_chunks(parsed))

    @staticmethod
    def _scan_amount(parsed: dict) -> dict | None:
        """EMD keyword -> amount on the same/multi-line neighbourhood."""
        for chunk in _corpus_chunks(parsed):
            text = chunk["text"]
            for keyword in EMD_KEYWORDS:
                idx = text.find(keyword)
                if idx == -1:
                    continue
                window = text[idx: idx + 300]
                match = _pick_amount(window)
                if match:
                    return {"value": _to_float(match.group(1), match.group(2)),
                            "page": chunk["page"], "file_id": chunk["file_id"],
                            "start": idx + match.start(), "end": idx + match.end(),
                            "context": window.strip()[:300]}
        return None

    @staticmethod
    def _turnover_best(parsed: dict) -> dict | None:
        """Best (max) turnover found via entity index, else FY-line text scan."""
        values: list[dict] = []
        for entity in _entities_index(parsed):
            name = str(entity.get("entity", ""))
            if not name.startswith("TURNOVER"):
                continue
            normalized = entity.get("normalized_value")
            if normalized is None:
                normalized = _to_float(str(entity.get("value", "")), None)
            values.append({"value": float(normalized), "page": (entity.get("source_span") or {}).get("page", 1),
                           "file_id": None, "start": (entity.get("source_span") or {}).get("start"),
                           "end": (entity.get("source_span") or {}).get("end"),
                           "context": entity.get("value", "")})

        if not values:
            for chunk in _corpus_chunks(parsed):
                for match in _FY_AMOUNT_RE.finditer(chunk["text"]):
                    values.append({"value": _to_float(match.group(3), match.group(4)),
                                   "page": chunk["page"], "file_id": chunk["file_id"],
                                   "start": match.start(), "end": match.end(),
                                   "context": match.group(0)})
        if not values:
            return None
        best = max(values, key=lambda item: item["value"])
        return {"max": best["value"], "hit": best}

    @staticmethod
    def _first_number(parsed: dict) -> dict | None:
        for chunk in _corpus_chunks(parsed):
            match = _pick_amount(chunk["text"])
            if match:
                return {"value": _to_float(match.group(1), match.group(2)),
                        "page": chunk["page"], "file_id": chunk["file_id"],
                        "start": match.start(), "end": match.end(), "context": chunk["text"]}
        return None

    @staticmethod
    def _resolve_date(parsed: dict, target: str) -> dict | None:
        candidates = DATE_ENTITIES.get(target, (target,))
        for entity in _entities_index(parsed):
            if entity.get("entity") not in candidates:
                continue
            parsed_date = _parse_date_string(entity.get("normalized_value") or entity.get("value"))
            if parsed_date:
                return {"value": parsed_date, "page": (entity.get("source_span") or {}).get("page", 1),
                        "file_id": None,
                        "start": (entity.get("source_span") or {}).get("start"),
                        "end": (entity.get("source_span") or {}).get("end"),
                        "context": entity.get("value", "")}
        for chunk in _corpus_chunks(parsed):
            match = _DATE_RE.search(chunk["text"])
            if match:
                parsed_date = _parse_date_string(match.group(1))
                if parsed_date:
                    return {"value": parsed_date, "page": chunk["page"], "file_id": chunk["file_id"],
                            "start": match.start(), "end": match.end(), "context": chunk["text"]}
        return None

    @staticmethod
    def _evidence(hit: dict) -> dict:
        if not hit:
            return {}
        span: dict = {"page": hit.get("page")}
        if hit.get("start") is not None:
            span["start"] = hit["start"]
            span["end"] = hit["end"]
        return {"found": hit.get("context", ""), "source_span": span, "file_id": hit.get("file_id")}

    # -- aggregation ----------------------------------------------------------
    @staticmethod
    def _aggregate(results: list[dict], rules: list[dict], parsed: dict, tender_id: str) -> dict:
        severity = {r.get("rule_id"): r.get("severity") for r in rules}
        num_fail = sum(1 for r in results if r["status"] == "fail")
        num_blocking_fail = sum(
            1 for r in results if r["status"] == "fail" and severity.get(r.get("rule_id")) == "blocking")
        num_mandatory_fail = sum(
            1 for r in results if r["status"] == "fail" and severity.get(r.get("rule_id")) == "mandatory")
        num_pass = sum(1 for r in results if r["status"] == "pass")
        total = len(results)

        if num_blocking_fail:
            overall = "DISCREPANT"
        elif num_mandatory_fail or any(r["status"] in ("warn", "skip") for r in results):
            overall = "NEEDS_REVIEW"
        else:
            overall = "COMPLIANT"

        return {
            "request_id": parsed.get("request_id"),
            "tender_id": parsed.get("tender_id") or tender_id,
            "bid_id": parsed.get("bid_id"),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "engine_version": "1.2",
            "results": results,
            "overall_status": overall,
            "score": {
                "blocking": sum(1 for r in rules if severity.get(r.get("rule_id")) == "blocking"),
                "mandatory": sum(1 for r in rules if severity.get(r.get("rule_id")) == "mandatory"),
                "advisory": sum(1 for r in rules if severity.get(r.get("rule_id")) == "advisory"),
                "pass": num_pass, "fail": num_fail,
                "warn": sum(1 for r in results if r["status"] == "warn"),
                "skip": sum(1 for r in results if r["status"] == "skip"),
                "error": sum(1 for r in results if r["status"] == "error"),
                "total": total,
                "compliance_pct": round(num_pass / total * 100, 1) if total else 0.0,
            },
        }