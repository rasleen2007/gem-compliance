"""Pydantic mirrors for contracts 4-5: validation_rule, validation_result."""

from pydantic import BaseModel, Field

SEVERITIES = ["blocking", "mandatory", "advisory"]
OPERATORS = [">=", "<=", "==", "!=", ">", "<", "contains", "exists", "not_exists", "regex", "date_after", "date_before", "cross_check", "llm_judge"]
RULE_STATUSES = ["pass", "fail", "warn", "skip", "error"]


# ---- Contract 4: validation_rule ----
class ValidationRule(BaseModel):
    rule_id: str
    tender_id: str
    category: str
    description: str
    severity: str  # blocking|mandatory|advisory
    element: str  # doc_role rule inspects
    target: str  # entity / kv / word('...') expression
    operator: str  # OPERATORS
    expected_value: str | float | bool | None = None
    expression: str | None = None
    notes: str | None = None
    enabled: bool = True


# ---- Contract 5: validation_result ----
class Evidence(BaseModel):
    found: str | None = None
    source_span: dict | None = None
    file_id: str | None = None
    table_id: str | None = None
    # Rule-XCHK: multi-document identity reconciliation
    distinct_values: list[str] | None = None
    conflict_records: list[dict] | None = None
    cross_check_conflict: bool = False


class RuleResult(BaseModel):
    rule_id: str
    status: str  # RULE_STATUSES
    evidence: Evidence = Field(default_factory=Evidence)
    reason: str | None = None
    confidence: float = Field(ge=0, le=1)
    suggested_action: str = "none"  # none|attach_missing_doc|correct_value|reupload|manual_review


class Score(BaseModel):
    blocking: int = 0
    mandatory: int = 0
    advisory: int = 0
    pass_: int = Field(0, alias="pass")
    fail: int = 0
    warn: int = 0
    skip: int = 0
    error: int = 0
    total: int = 0
    compliance_pct: float = 0.0

    model_config = {"populate_by_name": True}


class ValidationResult(BaseModel):
    request_id: str
    tender_id: str
    bid_id: str
    generated_at: str
    engine_version: str = "1.0"
    results: list[RuleResult]
    overall_status: str  # COMPLIANT|DISCREPANT|NEEDS_REVIEW
    score: Score