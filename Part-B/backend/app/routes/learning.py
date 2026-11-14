from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from app.contracts import CorrectionRequest, PreventiveRule, ResolutionRequest
from app.database import engine
from app.models.database import LearningRecord
from app.services.diagnosis_service import load_incidents, memory_service
from app.services.learning_service import submit_learning
from app.services.prevention_service import create_rule

router = APIRouter(prefix="/api/incidents/{incident_id}", tags=["learning"])


def get_incident(incident_id: str):
    incident = next((x for x in load_incidents() if x.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail={"code": "INCIDENT_NOT_FOUND", "message": "Incident not found"})
    return incident


@router.post("/corrections")
def correction(incident_id: str, request: CorrectionRequest):
    incident = get_incident(incident_id)
    with Session(engine) as session:
        try:
            record = submit_learning(session, memory_service, incident, request, "correction")
        except Exception:
            raise HTTPException(status_code=503, detail={"code": "MEMORY_UNAVAILABLE", "message": "Historical memory unavailable", "retryable": True})
    return {"learning_record_id": record.id, "memory_status": record.memory_status, "hindsight_document_id": record.hindsight_document_id}


@router.post("/resolution")
def resolution(incident_id: str, request: ResolutionRequest):
    incident = get_incident(incident_id)
    with Session(engine) as session:
        try:
            record = submit_learning(session, memory_service, incident, request, "resolution")
        except Exception:
            raise HTTPException(status_code=503, detail={"code": "MEMORY_UNAVAILABLE", "message": "Historical memory unavailable", "retryable": True})
        proposed_rule = None
        if request.proposed_rule and record.memory_status == "retained":
            proposed_rule = create_rule(session, PreventiveRule(
                rule_id=f"CHK-{incident_id}-RETRY",
                name="Engineer-proposed preventive check",
                description="Proposed from a verified incident resolution.",
                expression=request.proposed_rule,
                source_incident_ids=[incident_id],
            ))
        response = {
            "learning_record_id": record.id,
            "memory_status": record.memory_status,
            "hindsight_document_id": record.hindsight_document_id,
            "proposed_rule": proposed_rule,
        }
    return response


@router.get("/learning-records")
def learning_records(incident_id: str):
    get_incident(incident_id)
    with Session(engine) as session:
        rows = session.exec(select(LearningRecord).where(LearningRecord.incident_id == incident_id)).all()
    return rows
