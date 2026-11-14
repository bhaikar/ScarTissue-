from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.contracts import Incident, MemoryDocument, ResolutionRequest, CorrectionRequest
from app.models.database import LearningRecord, utc_now


def _document_id(incident_id: str, kind: str, record_id: str) -> str:
    return f"incident:{incident_id}:{kind}:{record_id}"


def submit_learning(session: Session, memory, incident: Incident, request, kind: str) -> LearningRecord:
    existing = session.exec(select(LearningRecord).where(LearningRecord.idempotency_key == request.idempotency_key)).first()
    if existing:
        return existing

    record_id = uuid.uuid4().hex
    content = request.model_dump(mode="json")
    record = LearningRecord(
        id=record_id,
        incident_id=incident.incident_id,
        kind=kind,
        content_json=json.dumps(content),
        idempotency_key=request.idempotency_key,
        memory_status="pending",
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    document_id = _document_id(incident.incident_id, kind, record_id)
    doc = MemoryDocument(
        document_id=document_id,
        content=json.dumps({"incident_id": incident.incident_id, "kind": kind, **content}),
        timestamp=incident.resolved_at or datetime.now(timezone.utc).isoformat(),
        metadata={"incident_id": incident.incident_id, "service": incident.service, "environment": incident.environment, "record_kind": kind},
        tags=["org:demo", f"service:{incident.service}", f"env:{incident.environment}"],
    )
    try:
        memory.retain(doc)
    except Exception:
        record.memory_status = "failed"
        record.updated_at = utc_now()
        session.add(record)
        session.commit()
        raise

    record.memory_status = "retained"
    record.hindsight_document_id = document_id
    record.updated_at = utc_now()
    session.add(record)
    session.commit()
    session.refresh(record)
    return record
