"""Pydantic mirror for contract 6: compliance_dashboard."""

from pydantic import BaseModel, Field


class ScoreView(BaseModel):
    pass_: int = Field(0, alias="pass")
    fail: int = 0
    warn: int = 0
    skip: int = 0
    error: int = 0
    total: int = 0
    compliance_pct: float = 0.0

    model_config = {"populate_by_name": True}


class CategoryBreakdown(BaseModel):
    category: str
    pass_: int = Field(0, alias="pass")
    fail: int = 0
    warn: int = 0
    total: int = 0

    model_config = {"populate_by_name": True}


class DocState(BaseModel):
    file_id: str
    file_name: str | None = None
    doc_role: str
    stage: str  # uploaded|ocr_done|parsed|validated|failed
    status: str  # ok|error|partial


class Issue(BaseModel):
    rule_id: str
    category: str
    severity: str  # blocking|mandatory|advisory
    status: str  # pass|fail|warn|skip|error
    summary: str
    evidence: str | None = None
    source_span: dict | None = None
    suggested_action: str = "none"


class TimelineItem(BaseModel):
    stage: str  # upload|ocr|nlp|validation|adjudication
    status: str  # pending|running|done|error
    ts: str | None = None
    runtime_ms: int | None = None
    message: str | None = None


class Adjudication(BaseModel):
    decision: str | None = None  # approved|rejected|rework_requested
    officer: str | None = None
    comment: str | None = None
    ts: str | None = None


class ComplianceDashboard(BaseModel):
    tender_id: str
    bid_id: str
    supplier: str
    category: str | None = None
    status: str = "IN_PROGRESS"  # COMPLIANT|DISCREPANT|NEEDS_REVIEW|IN_PROGRESS
    score: ScoreView = Field(default_factory=ScoreView)
    category_breakdown: list[CategoryBreakdown] = Field(default_factory=list)
    documents: list[DocState] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    adjudication: Adjudication | None = None