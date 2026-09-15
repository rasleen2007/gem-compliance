"""Deterministic rule engine (Stage 3). Emits contract 5 (validation_result).

Phase P0 scope (end-to-end EMD demo):
  - Flattens `ocr_extraction` text into a search corpus.
  - Operator implementations: numeric compare (EMD amount >= threshold),
    exists, contains, regex, date_after.
  - Evidence-backed verdicts: `pass | fail | warn | skip | error` each with
    found text + source_span (page/char offsets) + confidence.

Overall status rule (docs/02, contract 5):
  - any blocking fail            -> DISCREPANT
  - any mandatory fail/warn      -> NEEDS_REVIEW
  - any warn/skip                -> NEEDS_REVIEW
  - otherwise                    -> COMPLIANT
"""

import re
from datetime import date, datetime
from typing import Any

from core_ai.rules.rule_registry import RuleRegistry, get_registry

# --------------------------------------------------------------------------
# Amount parsing (Indian number format + lakh/crore multipliers)
# --------------------------------------------------------------------------
EMD_KEYWORDS = ("EMD", "Earnest Money Deposit", "Earnest Money", "Deposit")

_CURRENCY_RE = re.compile(r"(?:INR|Rs\.?|₹)\s*([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?", re.IGNORECASE)
_NUMBER_RE = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b")

_LIMITS = {"lakh": 100_000, "lac": 100_000, "crore": 10_000_000, "cr": 10_000_000}


def _to_float(value: str | float, multiplier: str | None) -> float:
    number = float(str(value).replace(",", ""))
    return number * _LIMITS.get((multiplier or "").lower(), 1)


def _pick_amount(window: str) -> re.Match | None:
    """First amount in `window`: currency-prefixed preferred, bare number fallback.

    Bare numbers immediately followed by '%' are treated as percentages and skipped.
    """
    m = _CURRENCY_RE.search(window)
    if m:
        return m
    for cand in _NUMBER_RE.finditer(window):
        if window[cand.end():cand.end() + 4].lstrip().startswith("%"):
            continue
        return cand
    return None


def _search_corpus(parsed: dict):
    """Yield one chunk per page: {'file_id', 'page', 'text', 'full_text'}."""
    for document in parsed.get("documents", []):
        file_id = document.get("file_id")
        for page in document.get("pages", []):
            blocks = " ".join(
                b.get("text", "") for b in page.get("text_blocks", []) if b.get("text")
            )
            yield {
                "file_id": file_id,
                "page": page.get("page_no", 1),
                "text": blocks or page.get("full_text", ""),
            }


class RuleEngine:
    """Evaluates a tender's rule pack against an `ocr_extraction` payload."""

    def __init__(self, registry: RuleRegistry | None = None,
                 llm_enabled: bool = False, llm_client: Any = None) -> None:
        self.registry = registry or get_registry()
        self.llm_enabled = llm_enabled
        self.llm_client = llm_client

    # -- public entry point -------------------------------------------------
    def evaluate(self, parsed: dict, tender_id: str) -> dict:
        """Return a validation_result dict (contract 5)."""
        rules = self.registry.for_tender(tender_id)
        results = [self._apply(rule, parsed) for rule in rules if rule.get("enabled", True)]
        return self._aggregate(results, parsed, tender_id)

    # -- per-rule evaluation ------------------------------------------------
    def _apply(self, rule: dict, parsed: dict) -> dict:
        operator = rule.get("operator")
        target = rule.get("target", "")
        expected = rule.get("expected_value")
        verdict = {"rule_id": rule.get("rule_id"), "status": "skip",
                   "evidence": {}, "reason": "", "confidence": 1.0,
                   "suggested_action": "none"}

        try:
            if operator in (">=", "<=", "==", "!=", ">", "<"):
                verdict = self._eval_numeric(rule, parsed)
            elif operator in ("exists", "not_exists"):
                verdict = self._eval_exists(rule, parsed)
            elif operator == "contains":
                verdict = self._eval_contains(rule, parsed)
            elif operator == "regex":
                verdict = self._eval_regex(rule, parsed)
            elif operator == "date_after":
                verdict = self._eval_date_after(rule, parsed)
            elif operator == "llm_judge" and not self.llm_enabled:
                verdict["status"] = "skip"
                verdict["reason"] = "llm_judge rule skipped: LLM not enabled"
            else:
                verdict["status"] = "skip"
                verdict["reason"] = f"operator {operator!r} not implemented"
        except Exception as exc:  # noqa: BLE001 — isolate rule errors
            verdict.update({"status": "error", "reason": f"{type(exc).__name__}: {exc}",
                            "confidence": 0.0, "suggested_action": "manual_review"})
        return verdict

    # -- operator implementations ------------------------------------------
    def _eval_numeric(self, rule: dict, parsed: dict) -> dict:
        """Numeric comparison — EMD scan for EMD_AMOUNT/EMD_PERCENTAGE targets."""
        target = rule.get("target", "")
        hit = self._scan_amount(parsed) if target in ("EMD_AMOUNT", "EMD_PERCENTAGE") else self._first_number(parsed)
        if not hit:
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

    def _eval_exists(self, rule: dict, parsed: dict) -> dict:
        keyword = rule.get("expected_value") or rule.get("target")
        hit = self._find_text(parsed, str(keyword))
        present = hit is not None
        outcome = present if rule.get("operator") == "exists" else not present
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if outcome else "fail",
            "evidence": self._evidence(hit) if hit else {},
            "reason": f"'{keyword}' {'found' if present else 'not found'} in bid documents",
            "confidence": 0.9 if present else 0.6,
            "suggested_action": "none" if outcome else "attach_missing_doc",
        }

    def _eval_contains(self, rule: dict, parsed: dict) -> dict:
        needle = str(rule.get("expected_value", "")).lower()
        hit = self._find_text(parsed, needle) if needle else None
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if hit else "fail",
            "evidence": self._evidence(hit) if hit else {},
            "reason": f"Text contains {needle!r}: {'yes' if hit else 'no'}",
            "confidence": 0.9,
            "suggested_action": "none" if hit else "attach_missing_doc",
        }

    def _eval_regex(self, rule: dict, parsed: dict) -> dict:
        pattern = rule.get("expected_value", "")
        corpus = "\n".join(c["text"] for c in _search_corpus(parsed))
        if not pattern:
            return {"rule_id": rule.get("rule_id"), "status": "error", "evidence": {},
                    "reason": "regex rule missing pattern", "confidence": 0.0,
                    "suggested_action": "manual_review"}
        m = re.search(pattern, corpus) if corpus else None
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if m else "fail",
            "evidence": {"found": (m.group(0) if m else None)} if m else {},
            "reason": f"regex {pattern!r} {'matched' if m else 'no match'}",
            "confidence": 0.9 if m else 0.6,
            "suggested_action": "none" if m else "manual_review",
        }

    def _eval_date_after(self, rule: dict, parsed: dict) -> dict:
        expected = rule.get("expected_value")
        required = date.fromisoformat(str(expected)) if expected else None
        extracted = None
        hit = None
        for chunk in _search_corpus(parsed):
            m = _DATE_RE.search(chunk["text"])
            if m:
                extracted = self._parse_date(m.group(1))
                hit = {"value": extracted, "page": chunk["page"], "file_id": chunk["file_id"],
                       "start": m.start(), "end": m.end(), "context": chunk["text"]}
                break
        if required is None or extracted is None:
            return {"rule_id": rule.get("rule_id"), "status": "skip", "evidence": {},
                    "reason": "no comparable date available", "confidence": 0.5,
                    "suggested_action": "manual_review"}
        outcome = extracted > required
        return {
            "rule_id": rule.get("rule_id"),
            "status": "pass" if outcome else "fail",
            "evidence": self._evidence(hit),
            "reason": f"Date {extracted.isoformat()} > required {required.isoformat()}",
            "confidence": 0.9,
            "suggested_action": "none" if outcome else "attach_missing_doc",
        }

    # -- extraction helpers --------------------------------------------------
    @staticmethod
    def _scan_amount(parsed: dict) -> dict | None:
        """Scan for EMD keywords and return the first INR amount that follows."""
        for chunk in _search_corpus(parsed):
            text = chunk["text"]
            for keyword in EMD_KEYWORDS:
                idx = text.find(keyword)
                if idx == -1:
                    continue
                window = text[idx: idx + 300]
                m = _pick_amount(window)
                if m:
                    return {"value": _to_float(m.group(1), m.group(2)),
                            "page": chunk["page"], "file_id": chunk["file_id"],
                            "start": idx + m.start(), "end": idx + m.end(),
                            "context": window.strip()[:300]}
        return None

    @staticmethod
    def _first_number(parsed: dict) -> dict | None:
        for chunk in _search_corpus(parsed):
            m = _pick_amount(chunk["text"])
            if m:
                return {"value": _to_float(m.group(1), m.group(2)),
                        "page": chunk["page"], "file_id": chunk["file_id"],
                        "start": m.start(), "end": m.end(), "context": chunk["text"]}
        return None

    @staticmethod
    def _find_text(parsed: dict, needle: str) -> dict | None:
        needle_lower = (needle or "").lower()
        if not needle_lower:
            return None
        for chunk in _search_corpus(parsed):
            idx = chunk["text"].lower().find(needle_lower)
            if idx != -1:
                return {"value": needle, "page": chunk["page"], "file_id": chunk["file_id"],
                        "start": idx, "end": idx + len(needle), "context": chunk["text"]}
        return None

    @staticmethod
    def _evidence(hit: dict | None) -> dict:
        if not hit:
            return {}
        span = {"page": hit["page"]}
        if hit.get("start") is not None:
            span["start"] = hit["start"]
            span["end"] = hit["end"]
        return {"found": hit.get("context", ""), "source_span": span, "file_id": hit.get("file_id")}

    @staticmethod
    def _parse_date(raw: str) -> date:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
            return date.fromisoformat(raw)
        day, month, year = re.split(r"[/-]", raw)
        year = int(year)
        if year < 100:
            year += 2000 if year < 50 else 1900
        return date(year, int(day), int(month))

    # -- aggregation ---------------------------------------------------------
    @staticmethod
    def _aggregate(results: list[dict], parsed: dict, tender_id: str) -> dict:
        def count(status: str) -> int:
            return sum(1 for r in results if r["status"] == status)

        total = len(results)
        pass_count = count("pass")
        # Docs/02 severity model: blocking fail => DISCREPANT, otherwise any
        # warn/skip => NEEDS_REVIEW, else COMPLIANT. (Severity field is
        # carried on rules, not results; the registry orders blocking first.)
        if any(r["status"] == "fail" for r in results):
            overall = "DISCREPANT"
        elif any(r["status"] in ("warn", "skip") for r in results):
            overall = "NEEDS_REVIEW"
        else:
            overall = "COMPLIANT"

        return {
            "request_id": parsed.get("request_id"),
            "tender_id": parsed.get("tender_id") or tender_id,
            "bid_id": parsed.get("bid_id"),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "engine_version": "1.0",
            "results": results,
            "overall_status": overall,
            "score": {
                "blocking": 0, "mandatory": 0, "advisory": 0,
                "pass": pass_count, "fail": count("fail"), "warn": count("warn"),
                "skip": count("skip"), "error": count("error"),
                "total": total,
                "compliance_pct": round(pass_count / total * 100, 1) if total else 0.0,
            },
        }