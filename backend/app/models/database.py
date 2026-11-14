from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DiagnosisRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    mode: str
    model_id: str
    payload_json: str
    created_at: datetime = Field(default_factory=utc_now)


class LearningRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    incident_id: str = Field(index=True)
    kind: str
    content_json: str
    idempotency_key: str = Field(index=True, unique=True)
    memory_status: str = "pending"
    hindsight_document_id: str | None = None
    created_by: str = "engineer"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RuleRecord(SQLModel, table=True):
    rule_id: str = Field(primary_key=True)
    payload_json: str
    status: str = "proposed"
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class DeploymentEvaluationRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    deployment_id: str
    decision: str
    payload_json: str
    created_at: datetime = Field(default_factory=utc_now)


class AuditRecord(SQLModel, table=True):
    id: str = Field(primary_key=True)
    event: str
    incident_id: str | None = None
    outcome: str
    request_id: str
    created_at: datetime = Field(default_factory=utc_now)
