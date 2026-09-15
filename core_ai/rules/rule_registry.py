"""Rule registry — loads validation_rule entries (contract 4) for a tender.

Sources: database_schema seed tables (primary) or an uploaded rule-pack file.
"""

from typing import Iterable


class RuleRegistry:
    def __init__(self) -> None:
        self._by_tender: dict[str, list[dict]] = {}

    def load_rules(self, rules: Iterable[dict]) -> None:
        for rule in rules:
            self._by_tender.setdefault(rule["tender_id"], []).append(rule)

    def for_tender(self, tender_id: str) -> list[dict]:
        return self._by_tender.get(tender_id, [])


_default_registry = RuleRegistry()


def get_registry() -> RuleRegistry:
    return _default_registry