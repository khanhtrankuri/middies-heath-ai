from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.consultation import ConsultationOrchestrator
from app.services.rag.config import DocumentMetadata, RetrievedChunk

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_requests_duration_when_missing() -> None:
    response = client.post("/api/v1/triage", json={"symptom": "Tôi bị đau đầu"})
    assert response.status_code == 200
    assert response.json()["urgency"] == "routine"
    assert response.json()["possibilities"] == []


def test_detects_unaccented_emergency_phrase() -> None:
    response = client.post(
        "/api/v1/triage",
        json={"symptom": "Toi bi kho tho va dau nguc", "duration": "10 phút"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "emergency"
    assert "khó thở" in body["matched_red_flags"]
    assert "đau ngực" in body["matched_red_flags"]


def test_does_not_treat_negated_weakness_as_an_emergency_flag() -> None:
    response = client.post(
        "/api/v1/triage",
        json={"symptom": "Tôi đau đầu nhưng không yếu liệt", "duration": "2 ngày"},
    )
    assert response.status_code == 200
    assert response.json()["urgency"] == "routine"


def test_returns_reference_possibilities() -> None:
    response = client.post(
        "/api/v1/triage",
        json={"symptom": "Tôi bị đau đầu và hơi chóng mặt", "duration": "Khoảng 1–3 ngày"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "routine"
    assert len(body["possibilities"]) >= 1


def test_consultation_uses_ci_stub_provider() -> None:
    with TestClient(app) as lifespan_client:
        response = lifespan_client.post(
            "/api/v1/consultation",
            json={"messages": [{"role": "user", "content": "Tôi bị đau bụng."}]},
        )
    assert response.status_code == 200
    assert response.json()["provider"] == "stub"
    assert response.json()["action"] == "ASK_MORE"
    assert response.json()["reply"]


def test_readiness_does_not_expose_paths() -> None:
    with TestClient(app) as lifespan_client:
        response = lifespan_client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"api": True, "model": True, "rag": False}
    assert "path" not in response.text.casefold()


def test_model_load_failure_keeps_emergency_api_available(monkeypatch):
    from app import main
    class BrokenProvider:
        def load(self):
            raise RuntimeError("model unavailable")
        def generate(self, messages):
            raise RuntimeError("model unavailable")
    monkeypatch.setattr(main, "create_provider", lambda name: BrokenProvider())
    with TestClient(app) as api:
        assert api.get("/ready").json()["model"] is False
        response = api.post("/api/v1/consultation", json={"messages": [{"role": "user", "content": "Tôi không thể thở"}]})
        assert response.status_code == 200
        assert response.json()["action"] == "EMERGENCY"


def test_rag_search_returns_503_when_index_is_disabled() -> None:
    with TestClient(app) as lifespan_client:
        response = lifespan_client.post(
            "/api/v1/rag/search", json={"query": "Migraine là gì?", "top_k": 3}
        )
    assert response.status_code == 503
    assert "data/rag_index" not in response.text


class _SpyInference:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        return "Migraine là một rối loạn đau đầu tái diễn [S1]."


class _ReadyRAG:
    def __init__(self) -> None:
        self.ready = True
        self.config = SimpleNamespace(max_context_tokens=4096)
        self.calls = 0
        self.result = RetrievedChunk(
            chunk_id="migraine-1",
            text="Migraine is a recurring headache disorder.",
            score=0.98,
            metadata=DocumentMetadata(
                source_id="fixture-migraine",
                title="Migraine overview",
                organization="Test authority",
                source_url="https://example.test/migraine",
                document_hash="a" * 64,
            ),
        )

    async def retrieve_many(self, queries, final_k=None):
        del queries, final_k
        self.calls += 1
        return [self.result]

    async def retrieve(self, query: str, top_k: int = 5):
        del query, top_k
        self.calls += 1
        return [self.result]


def test_direct_question_endpoint_retrieves_and_returns_structured_citation() -> None:
    with TestClient(app) as lifespan_client:
        inference = _SpyInference()
        rag = _ReadyRAG()
        app.state.rag = rag
        app.state.consultation = ConsultationOrchestrator(inference, rag, "spy")

        response = lifespan_client.post(
            "/api/v1/consultation",
            json={"messages": [{"role": "user", "content": "Migraine là gì?"}]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "GROUNDED_ANSWER"
    assert body["grounding_status"] == "grounded"
    assert body["citations"][0]["source_id"] == "fixture-migraine"
    assert "score" not in body["citations"][0]
    assert rag.calls == 1
    assert "NGUỒN THAM KHẢO" in inference.calls[0][1]["content"]


def test_rag_search_endpoint_exposes_debug_score_and_metadata() -> None:
    with TestClient(app) as lifespan_client:
        rag = _ReadyRAG()
        app.state.rag = rag
        response = lifespan_client.post(
            "/api/v1/rag/search",
            json={"query": "Migraine là gì?", "top_k": 1},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["score"] == 0.98
    assert body["results"][0]["source_id"] == "fixture-migraine"
