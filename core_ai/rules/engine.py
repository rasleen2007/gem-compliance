"""Deterministic rule engine with optional LLM judge.

Input:  parsed_document (contract 3) + validation_rule[] (contract 4)
Output: validation_result (contract 5), evidence-backed, never throws per-rule.

Operator semantics:
  >= <= > < == !=  numeric compare on normalized value
  contains        substring in extracted text
  exists          entity/pair present (not_exists inverse)
  regex           pattern match on raw text
  date_after      parsed date > expected (validity check)
  llm_judge       free-text instruction via core_ai.llm (only if enabled)

Overall status rule:
  any blocking fail  -> DISCREPANT
  else any mandatory fail/warn -> NEEDS_REVIEW
  else COMPLIANT
"""

from typing import Any

from core_ai.rules.rule_registry import RuleRegistry, get_registry


class RuleEngine:
    def __init__(self, registry: RuleRegistry | None = None,
                 llm_enabled: bool = False, llm_client: Any = None) -> None:
        self.registry = registry or get_registry()
        self.llm_enabled = llm_enabled
        self.llm_client = llm_client

    def evaluate(self, parsed: dict, tender_id: str) -> dict:
        """Return validation_result dict (contract 5)."""
        rules = self.registry.for_tender(tender_id)
        results = [self._apply(rule, parsed) for rule in rules]
        return self._aggregate(results)

    def _apply(self, rule: dict, parsed: dict) -> dict:
        raise NotImplementedError("implement in MVP Phase P1")

    def _aggregate(self, results: list[dict]) -> dict:
        raise NotImplementedError