import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import TriageRequest, TriageResponse
from .triage import assess


def _origins() -> list[str]:
    configured = os.getenv("MEDDIES_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(
    title="Meddies Health AI API",
    version="0.1.0",
    description="Backend hỗ trợ sàng lọc sức khỏe ban đầu; không cung cấp chẩn đoán y khoa.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "meddies-health-ai-backend"}


@app.post("/api/v1/triage", response_model=TriageResponse)
def triage(request: TriageRequest) -> TriageResponse:
    return assess(request)
