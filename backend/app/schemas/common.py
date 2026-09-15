"""Shared envelope + contract loader. ApiEnvelope mirrors contracts/api_envelope.schema.json."""

import json
from pathlib import Path

from pydantic import BaseModel, Field

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"


def load_schema(name: str) -> dict:
    with (CONTRACTS_DIR / name).open("r", encoding="utf-8") as fh:
        return json.load(fh)


class ErrorInfo(BaseModel):
    code: str | None = None
    message: str | None = None
    details: list[dict] = Field(default_factory=list)


class ApiEnvelope(BaseModel):
    status: str  # ok | error | accepted
    request_id: str
    data: dict | None = None
    error: ErrorInfo | None = None