from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryMode(str, Enum):
    off = "off"
    on = "on"
    full_context = "full_context"


class Confidence(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Hypothesis(BaseModel):
    cause: str
    current_evidence: list[str] = Field(default_factory=list)
    supporting_incident_ids: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    action: str
    reason: str
    requires_approval: Literal[True] = True


class AvoidedApproach(BaseModel):
    approach: str
    reason: str


class DiagnosisOutput(BaseModel):
    summary: str
    confidence: Confidence
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    approaches_to_avoid: list[AvoidedApproach] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class MemoryEvidence(BaseModel):
    fact_id: str
    document_id: str | None = None
    incident_id: str | None = None
    text: str
    type: Literal["world", "experience", "observation", "unknown"] = "unknown"
    occurred_start: str | None = None
    occurred_end: str | None = None


class MemoryDocument(BaseModel):
    document_id: str
    content: str
    timestamp: str
    metadata: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class Metric(BaseModel):
    name: str
    before: float | int | None = None
    during: float | int | None = None
    unit: str | None = None


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


class Deployment(BaseModel):
    deployment_id: str
    service: str
    retry_attempts: int | None = None
    retry_budget: int | None = None
    timeout_seconds: float | None = None
    connection_pool_size: int | None = None
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    previous_retry_attempts: int | None = None
    change_summary: str | None = None


class Incident(BaseModel):
    model_config = ConfigDict(extra="allow")

    incident_id: str
    service: str
    environment: str
    severity: Literal["SEV1", "SEV2", "SEV3"]
    status: str = "OPEN"
    started_at: str
    resolved_at: str | None = None
    summary: str
    symptoms: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)
    deployment: Deployment | None = None


class DiagnosisResult(BaseModel):
    output: DiagnosisOutput
    memory_evidence: list[MemoryEvidence] = Field(default_factory=list)
    recalled_fact_ids: list[str] = Field(default_factory=list)
    source_incident_ids: list[str] = Field(default_factory=list)
    mode: MemoryMode
    model_id: str
    validation_status: Literal["valid", "validation_failed"]
    latency_ms: int = Field(ge=0)


class ResolutionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    root_cause: str = Field(min_length=5)
    action_taken: str = Field(min_length=5)
    outcome: Literal["succeeded", "failed", "partial"]
    verification_evidence: list[str] = Field(min_length=1)
    applicability_conditions: list[str] = Field(default_factory=list)
    contradiction_conditions: list[str] = Field(default_factory=list)
    proposed_rule: RuleExpression | None = None


class CorrectionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=200)
    wrong_hypothesis: str = Field(min_length=3)
    corrected_fact: str = Field(min_length=5)
    supporting_evidence: list[str] = Field(min_length=1)
    engineer_confidence: Confidence
    supersedes: bool = False


ALLOWED_FIELDS = {
    "service",
    "retry_attempts",
    "retry_budget",
    "timeout_seconds",
    "connection_pool_size",
    "feature_flags.batch_retries",
}
ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "exists", "not_exists"}


class RuleCondition(BaseModel):
    field: str
    operator: str
    value: str | int | float | bool | None = None

    @model_validator(mode="after")
    def validate_rule_parts(self) -> RuleCondition:
        if self.field not in ALLOWED_FIELDS:
            raise ValueError(f"Unknown rule field: {self.field}")
        if self.operator not in ALLOWED_OPERATORS:
            raise ValueError(f"Unknown rule operator: {self.operator}")
        if self.operator in {"exists", "not_exists"} and self.value is not None:
            raise ValueError(f"{self.operator} does not accept a value")
        return self


class RuleExpression(BaseModel):
    all: list[RuleCondition] = Field(min_length=1, max_length=10)


class PreventiveRule(BaseModel):
    rule_id: str
    name: str
    description: str = ""
    expression: RuleExpression
    source_incident_ids: list[str] = Field(min_length=1)
    status: Literal["proposed", "active", "rejected", "disabled"] = "proposed"
    approved_by: str | None = None
    approved_at: str | None = None


class ApprovalRequest(BaseModel):
    approver: str = Field(min_length=1, max_length=200)


class RuleStatusRequest(BaseModel):
    status: Literal["rejected", "disabled"]
    actor: str = Field(min_length=1, max_length=200)


class DeploymentEvaluationRequest(BaseModel):
    deployment: dict[str, Any]


class MemoryService(Protocol):
    def recall(self, incident: Incident) -> list[MemoryEvidence]: ...
    def retain(self, doc: MemoryDocument) -> str: ...
    def list_memories(self, incident_id: str | None = None) -> list[MemoryEvidence]: ...
    def reset(self) -> None: ...


class DiagnosisService(Protocol):
    def diagnose(self, incident: Incident, mode: MemoryMode) -> DiagnosisResult: ...


class MemoryUnavailable(Exception):
    pass


class ModelUnavailable(Exception):
    pass


class ModelOutputInvalid(Exception):
    pass


class CitationValidationFailed(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


class NotFoundError(Exception):
    pass


class InvalidStateTransition(Exception):
    pass
