from fastapi import APIRouter
from sqlmodel import SQLModel, Session

from app.database import engine
from app.services.diagnosis_service import memory_service

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset():
    with Session(engine) as session:
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.exec(table.delete())
        session.commit()
    memory_service.reset()
    return {"status": "reset"}
