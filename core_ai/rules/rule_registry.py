"""Rule registry — loads validation_rule entries (contract 4) for a tender.

Sources: database_schema seed tables (via app.core.db.fetch_rules) or programmatic
loads (tests, rule-pack files). Deduplicates by rule_id.
"""

from typing import Iterable


class RuleRegistry:
    def __init__(self) -> None:
        self._by_tender: dict[str, list[dict]] = {}

    def load_rules(self, rules: Iterable[dict]) -> None:
        for rule in rules:
            self.add(rule)

    def add(self, rule: dict) -> None:
        tender_id = rule.get("tender_id")
        if not tender_id:
            return
        bucket = self._by_tender.setdefault(tender_id, [])
        if all(existing.get("rule_id") != rule.get("rule_id") for existing in bucket):
            bucket.append(rule)

    def for_tender(self, tender_id: str) -> list[dict]:
        return list(self._by_tender.get(tender_id, []))

    def clear(self) -> None:
        self._by_tender.clear()


_default_registry = RuleRegistry()


def get_registry() -> RuleRegistry:
    return _default_registry