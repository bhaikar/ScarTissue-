from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.contracts import Incident, MemoryMode
from app.database import engine
from app.models.database import DiagnosisRecord
from app.services.diagnosis_service import diagnosis_service, load_incidents

router = APIRouter(prefix="/api/incidents/{incident_id}", tags=["diagnosis"])


class DiagnosisRequest(BaseModel):
    mode: MemoryMode


@router.post("/diagnoses")
def diagnose(incident_id: str, request: DiagnosisRequest):
    incident = next((x for x in load_incidents() if x.incident_id == incident_id), None)
    if incident is None:
        raise HTTPException(status_code=404, detail={"code": "INCIDENT_NOT_FOUND", "message": "Incident not found"})
    result = diagnosis_service.diagnose(incident, request.mode)
    diagnosis_id = __import__("uuid").uuid4().hex
    with Session(engine) as session:
        session.add(DiagnosisRecord(id=diagnosis_id, incident_id=incident_id, mode=request.mode.value, model_id=result.model_id, payload_json=result.model_dump_json()))
        session.commit()
    return {"diagnosis_id": diagnosis_id, "incident_id": incident_id, **result.model_dump(mode="json")}


@router.get("/diagnoses/{diagnosis_id}")
def get_diagnosis(incident_id: str, diagnosis_id: str):
    with Session(engine) as session:
        record = session.get(DiagnosisRecord, diagnosis_id)
    if not record or record.incident_id != incident_id:
        raise HTTPException(status_code=404, detail={"code": "DIAGNOSIS_NOT_FOUND", "message": "Diagnosis not found"})
    return {"diagnosis_id": record.id, "incident_id": record.incident_id, **__import__("json").loads(record.payload_json)}
