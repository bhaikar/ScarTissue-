from fastapi import APIRouter, HTTPException

from app.services.diagnosis_service import load_incidents

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.get("")
def incidents():
    return load_incidents()


@router.get("/{incident_id}")
def incident(incident_id: str):
    item = next((x for x in load_incidents() if x.incident_id == incident_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "INCIDENT_NOT_FOUND", "message": "Incident not found"})
    return item
