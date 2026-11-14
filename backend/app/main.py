from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes import demo, diagnosis, incidents, learning, memories, prevention

app = FastAPI(title="ScarTissue API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(incidents.router)
app.include_router(diagnosis.router)
app.include_router(learning.router)
app.include_router(memories.router)
app.include_router(prevention.router)
app.include_router(demo.router)

# Keep CLI imports and TestClient usage safe when lifespan is not entered.
init_db()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
