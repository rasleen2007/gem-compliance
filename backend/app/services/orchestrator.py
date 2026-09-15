"""Pipeline orchestrator — drives Stages 0-4 from docs/02_core_workflow.md.

State machine: PENDING → OCR_RUNNING → OCR_COMPLETE → NLP_RUNNING →
VALIDATION_RUNNING → VALIDATION_COMPLETE (or FAILED on all-doc errors).

TODO implement in Phase P1:
- start(request_id) -> enqueue background task
- run_stage_ocr / run_stage_nlp / run_stage_validation
- persist every transition to pipeline_events for the dashboard timeline
"""

from dataclasses import dataclass, field
from enum import Enum


class Stage(str, Enum):
    PENDING = "pending"
    OCR_RUNNING = "ocr_running"
    OCR_COMPLETE = "ocr_complete"
    NLP_RUNNING = "nlp_running"
    VALIDATION_RUNNING = "validation_running"
    VALIDATION_COMPLETE = "validation_complete"
    FAILED = "failed"


@dataclass
class PipelineEvent:
    stage: Stage
    status: str
    message: str = ""
    runtime_ms: int = 0
    ts: str = ""


@dataclass
class PipelineJob:
    request_id: str
    bid_id: str
    stage: Stage = Stage.PENDING
    events: list[PipelineEvent] = field(default_factory=list)

    def transition(self, stage: Stage, message: str = "", runtime_ms: int = 0) -> None:
        self.events.append(PipelineEvent(stage=stage, status="done", message=message, runtime_ms=runtime_ms))
        self.stage = stage