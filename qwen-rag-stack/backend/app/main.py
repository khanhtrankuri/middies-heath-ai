import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .inference import InferenceManager, create_provider
from .request_limits import RequestLimitsMiddleware
from .models import (
    ConsultationRequest,
    ConsultationResponse,
    RAGSearchRequest,
    RAGSearchResponse,
    RAGSearchResult,
    ReadyResponse,
    TriageRequest,
    TriageResponse,
)
from .services.consultation import ConsultationOrchestrator
from .services.rag.config import RAGConfig
from .services.rag.service import RAGUnavailableError, create_rag_service
from .triage import assess

LOGGER = logging.getLogger(__name__)


def _origins() -> list[str]:
    configured = os.getenv("MEDDIES_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(application: FastAPI):
    provider_name = os.getenv(
        "MEDDIES_MODEL_PROVIDER", os.getenv("MODEL_PROVIDER", "transformers")
    ).lower()
    manager = InferenceManager(
        create_provider(provider_name),
        max_generations=int(os.getenv("MEDDIES_MAX_GENERATIONS", "1")),
    )
    try:
        manager.load()
    except (RuntimeError, OSError, ValueError) as error:
        # Keep deterministic emergency routing reachable if model setup fails.
        # Do not substitute a demo provider or advertise the model as ready.
        LOGGER.error("Model failed to load (%s): %s", type(error).__name__, error)
    application.state.inference = manager
    application.state.model_provider = provider_name
    rag = create_rag_service(RAGConfig.from_env())
    rag.load()
    application.state.rag = rag
    application.state.consultation = ConsultationOrchestrator(manager, rag, provider_name)
    yield


app = FastAPI(
    title="Meddies Health AI API",
    version="0.3.0",
    lifespan=lifespan,
    description="Backend hỗ trợ sàng lọc sức khỏe ban đầu; không cung cấp chẩn đoán y khoa.",
)

# CORS wraps admission errors too, so browser clients can read 413/429 responses.
app.add_middleware(RequestLimitsMiddleware)
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


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    inference = getattr(app.state, "inference", None)
    rag = getattr(app.state, "rag", None)
    return ReadyResponse(
        api=True,
        model=bool(getattr(inference, "loaded", False)),
        rag=bool(getattr(rag, "ready", False)),
    )


@app.post("/api/v1/triage", response_model=TriageResponse)
def triage(request: TriageRequest) -> TriageResponse:
    return assess(request)


@app.post("/api/v1/consultation", response_model=ConsultationResponse)
async def consultation(request: ConsultationRequest) -> ConsultationResponse:
    messages = [message.model_dump() for message in request.messages]
    try:
        return await app.state.consultation.respond(messages)
    except (RuntimeError, TimeoutError):
        # Never return model paths, prompts, or patient content in an API error.
        LOGGER.error("Consultation inference unavailable")
        raise HTTPException(status_code=503, detail="Consultation service is temporarily unavailable") from None


@app.post("/api/v1/rag/search", response_model=RAGSearchResponse)
async def rag_search(request: RAGSearchRequest) -> RAGSearchResponse:
    try:
        results = await app.state.rag.retrieve(request.query, top_k=request.top_k)
    except RAGUnavailableError as error:
        raise HTTPException(status_code=503, detail="RAG knowledge index is not ready") from error
    return RAGSearchResponse(
        query=request.query,
        results=[
            RAGSearchResult(
                chunk_id=item.chunk_id,
                snippet=item.text,
                score=item.score,
                source_id=item.metadata.source_id,
                title=item.metadata.title,
                organization=item.metadata.organization,
                source_url=item.metadata.source_url,
                publication_date=item.metadata.publication_date,
                section=item.metadata.section,
                page=item.metadata.page,
            )
            for item in results
        ],
    )
