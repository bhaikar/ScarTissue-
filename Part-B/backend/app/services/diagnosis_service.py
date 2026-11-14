from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from app.config import settings
from app.contracts import (
    AvoidedApproach,
    Confidence,
    DiagnosisOutput,
    DiagnosisResult,
    DiagnosisService,
    Hypothesis,
    Incident,
    MemoryEvidence,
    MemoryMode,
    RecommendedAction,
    CitationValidationFailed,
)


class FakeMemoryService:
    def __init__(self) -> None:
        self._evidence: list[MemoryEvidence] = [
            MemoryEvidence(
                fact_id="fact-inc-017-root",
                document_id="seed:INC-017:postmortem",
                incident_id="INC-017",
                text="Retry amplification saturated checkout database. Increasing the connection pool failed; disabling batch retries resolved the incident.",
                type="experience",
            ),
            MemoryEvidence(
                fact_id="fact-inc-024-retry",
                document_id="seed:INC-024:postmortem",
                incident_id="INC-024",
                text="Unbounded retries saturated payment workers. A retry budget and disabling batch retries restored service.",
                type="experience",
            ),
            MemoryEvidence(
                fact_id="fact-inc-023-lock",
                document_id="seed:INC-023:postmortem",
                incident_id="INC-023",
                text="Lock waits after a schema migration caused saturation. Retry changes were not the cause.",
                type="experience",
            ),
            MemoryEvidence(
                fact_id="fact-inc-029-cert",
                document_id="seed:INC-029:postmortem",
                incident_id="INC-029",
                text="TLS certificate validation failures caused checkout timeouts while database metrics stayed normal.",
                type="experience",
            ),
        ]

    def recall(self, incident: Incident) -> list[MemoryEvidence]:
        query = f"{incident.summary} {' '.join(incident.symptoms)}".lower()
        if "lock" in query or "migration" in query:
            return [self._evidence[1], self._evidence[0]]
        if "certificate" in query or "tls" in query:
            return [self._evidence[2], self._evidence[0]]
        return [self._evidence[0], self._evidence[1], self._evidence[2], self._evidence[3]]

    def retain(self, doc):
        evidence = MemoryEvidence(
            fact_id=f"fact-{doc.document_id}",
            document_id=doc.document_id,
            incident_id=doc.metadata.get("incident_id"),
            text=doc.content,
            type="experience",
        )
        self._evidence = [e for e in self._evidence if e.document_id != doc.document_id]
        self._evidence.append(evidence)
        return doc.document_id

    def list_memories(self, incident_id: str | None = None):
        if incident_id is None:
            return list(self._evidence)
        return [e for e in self._evidence if e.incident_id == incident_id]

    def reset(self) -> None:
        self.__init__()


class FakeDiagnosisService:
    def __init__(self, memory: FakeMemoryService | None = None) -> None:
        self.memory = memory or FakeMemoryService()

    def diagnose(self, incident: Incident, mode: MemoryMode) -> DiagnosisResult:
        started = time.perf_counter()
        evidence = self.memory.recall(incident) if mode == MemoryMode.on else []
        current = " ".join(incident.symptoms).lower()
        deployment = incident.deployment
        retry_signal = bool(deployment and deployment.retry_attempts and deployment.retry_attempts > 5)
        lock_signal = "lock" in current or "migration" in current
        cert_signal = "certificate" in current or "tls" in current

        if cert_signal:
            summary = "Certificate expiry is the leading hypothesis."
            confidence = Confidence.high
            cause = "Certificate validation failure"
            actions = [RecommendedAction(action="Verify certificate expiry and rotate the certificate", reason="TLS errors are direct current evidence.")]
        elif lock_signal:
            summary = "Lock contention is more likely than retry amplification."
            confidence = Confidence.high
            cause = "Database lock contention after migration"
            actions = [RecommendedAction(action="Inspect lock waits and migration state", reason="Lock evidence contradicts retry-based diagnosis.")]
        elif retry_signal:
            summary = "Retry amplification is the leading hypothesis."
            confidence = Confidence.high if mode == MemoryMode.on else Confidence.medium
            cause = "Retry amplification after recent deployment"
            actions = [RecommendedAction(action="Inspect retry-driven request amplification", reason="Retry attempts increased before connection saturation.")]
        else:
            summary = "Evidence is insufficient to identify a reliable root cause."
            confidence = Confidence.low
            cause = "Undetermined"
            actions = [RecommendedAction(action="Collect deployment, dependency-volume, lock-wait, and certificate evidence", reason="Current signals do not distinguish likely causes.")]

        supporting = [e.incident_id for e in evidence if e.incident_id]
        avoided = []
        if mode == MemoryMode.on and retry_signal:
            avoided.append(AvoidedApproach(approach="Increase the database connection pool immediately", reason="This worsened saturation in INC-017."))
        contradicting = []
        if lock_signal and mode == MemoryMode.on:
            contradicting.append("INC-023 shows lock waits can cause similar saturation without retry amplification.")

        output = DiagnosisOutput(
            summary=summary,
            confidence=confidence,
            hypotheses=[Hypothesis(cause=cause, current_evidence=incident.symptoms[:4], supporting_incident_ids=supporting, contradicting_evidence=contradicting)],
            recommended_actions=actions,
            approaches_to_avoid=avoided,
            missing_evidence=[] if confidence == Confidence.high else ["Database lock-wait metrics", "Dependency request volume before and after deployment"],
        )
        allowed_incidents = {incident.incident_id, *(e.incident_id for e in evidence if e.incident_id)}
        cited_incidents = {item for hypothesis in output.hypotheses for item in hypothesis.supporting_incident_ids}
        if not cited_incidents.issubset(allowed_incidents):
            raise CitationValidationFailed("Diagnosis cited an incident absent from current or recalled evidence")
        return DiagnosisResult(
            output=output,
            memory_evidence=evidence,
            recalled_fact_ids=[e.fact_id for e in evidence],
            source_incident_ids=supporting,
            mode=mode,
            model_id=settings.llm_model,
            validation_status="valid",
            latency_ms=max(1, int((time.perf_counter() - started) * 1000)),
        )


memory_service = FakeMemoryService()
diagnosis_service: DiagnosisService = FakeDiagnosisService(memory_service)


def load_incidents() -> list[Incident]:
    path = Path(__file__).parents[2] / "fixtures" / "incidents.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Incident.model_validate(item) for item in data]
