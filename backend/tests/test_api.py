from fastapi.testclient import TestClient

from app.main import app

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


def test_returns_reference_possibilities() -> None:
    response = client.post(
        "/api/v1/triage",
        json={"symptom": "Tôi bị đau đầu và hơi chóng mặt", "duration": "Khoảng 1–3 ngày"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["urgency"] == "routine"
    assert len(body["possibilities"]) >= 1
