from fastapi import APIRouter

from app.services.diagnosis_service import memory_service

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("")
def memories(incident_id: str | None = None):
    return memory_service.list_memories(incident_id)
