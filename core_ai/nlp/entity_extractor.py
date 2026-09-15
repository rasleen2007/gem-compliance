"""Entity extraction — typed entities + key-value pairs for the rules engine.

Input:  segments from text_processor (or parsed_document skeleton)
Output: entities[] and key_value_pairs[] per contract 3, each with source_span.

Target entity vocabulary (canonical, used by validation_rule.target):
  EMD_PERCENTAGE, EMD_AMOUNT, BANK_GUARANTEE_PRESENT, PAYMENT_TERMS,
  DELIVERY_PERIOD_DAYS, VALIDITY_DAYS, GSTIN, PAN, CERT_DATE,
  TECHNICAL_SPEC_VALUES, PRICE_BREAKUP, ...

TODO implement in Phase P1:
- spaCy model + gazetteer patterns (spacy.matcher) for the vocabulary above
- regex patterns for currency/percent/date/duration normalization
- assign source_span {page, start, end, bbox} from OCR blocks
"""


def extract_entities(segments: list[dict], full_pages: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (entities, key_value_pairs) per contract 3."""
    raise NotImplementedError("implement in MVP Phase P1")


def normalize_value(entity: str, raw: str) -> str | float | bool | None:
    """Normalize raw text like '2 %' -> 2.0; handle 'Rs 1,00,000'."""
    raise NotImplementedError