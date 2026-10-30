import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.request_limits import RequestLimitsMiddleware


PATHS = ("/api/v1/triage", "/api/v1/consultation", "/api/v1/rag/search")


def limited_client(monkeypatch, **settings):
    for name, value in settings.items():
        monkeypatch.setenv(f"MEDDIES_{name}", str(value))
    api = FastAPI()
    api.add_middleware(RequestLimitsMiddleware)
    calls = []

    async def endpoint():
        calls.append(True)
        return {"ok": True}

    for path in PATHS:
        api.post(path)(endpoint)
    api.get("/health")(endpoint)
    return TestClient(api), calls


@pytest.mark.parametrize("path", PATHS)
def test_body_rejected_before_handler(monkeypatch, path):
    client, calls = limited_client(monkeypatch, MAX_REQUEST_BYTES=16)
    assert client.post(path, content=b"x" * 17).status_code == 413
    assert not calls
    assert client.post(path, content=b"x" * 16).status_code == 200


@pytest.mark.parametrize("path,setting", list(zip(PATHS, ("RATE_TRIAGE", "RATE_CONSULTATION", "RATE_RAG_SEARCH"))))
def test_rate_limit_does_not_trust_forged_headers(monkeypatch, path, setting):
    client, calls = limited_client(monkeypatch, **{setting: 2})
    for index in range(2):
        assert client.post(path, json={}, headers={"x-forwarded-for": f"192.0.2.{index}"}).status_code == 200
    response = client.post(path + "/", json={}, headers={"x-forwarded-for": "203.0.113.9"})
    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert len(calls) == 2
    assert client.get("/health").status_code == 200


def test_global_budget_is_shared_across_endpoints(monkeypatch):
    client, calls = limited_client(monkeypatch, RATE_GLOBAL=2)
    assert client.post(PATHS[0], json={}).status_code == 200
    assert client.post(PATHS[1], json={}).status_code == 200
    assert client.post(PATHS[2], json={}).status_code == 429
    assert len(calls) == 2


def test_window_expiry_and_bounded_client_table(monkeypatch):
    from app import request_limits
    now = [100.0]
    # Do not patch the shared time module used by asyncio.
    monkeypatch.setattr(request_limits, "time", type("Clock", (), {"monotonic": lambda: now[0]}))
    monkeypatch.setenv("MEDDIES_RATE_MAX_CLIENTS", "1")
    limiter = RequestLimitsMiddleware(None)
    assert limiter._admit("a", PATHS[0]) == 0
    assert limiter._admit("b", PATHS[0]) > 0
    now[0] += 61
    assert limiter._admit("b", PATHS[0]) == 0
    assert len(limiter.clients) == 1


def test_streaming_body_limit_without_or_with_false_content_length(monkeypatch):
    monkeypatch.setenv("MEDDIES_MAX_REQUEST_BYTES", "8")

    async def run(headers):
        called, sent = [], []

        async def downstream(scope, receive, send):
            called.append(True)

        chunks = iter([
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"6789", "more_body": False},
        ])

        async def receive():
            return next(chunks)

        async def send(message):
            sent.append(message)

        limiter = RequestLimitsMiddleware(downstream)
        await limiter({"type": "http", "method": "POST", "path": PATHS[1], "headers": headers}, receive, send)
        assert sent[0]["status"] == 413
        assert not called
        assert limiter.inflight == 0

    asyncio.run(run([]))
    asyncio.run(run([(b"content-length", b"1")]))


def test_malformed_length_and_compressed_body(monkeypatch):
    client, calls = limited_client(monkeypatch)
    for length in ("-1", "bad", "9" * 100):
        assert client.post(PATHS[0], content=b"{}", headers={"content-length": length}).status_code == 400
    assert client.post(PATHS[0], content=b"x", headers={"content-encoding": "gzip"}).status_code == 415
    assert not calls


def test_inflight_limit_and_slot_release(monkeypatch):
    monkeypatch.setenv("MEDDIES_MAX_INFLIGHT_REQUESTS", "1")

    async def run():
        started, finish = asyncio.Event(), asyncio.Event()
        sent = []

        async def downstream(scope, receive, send):
            started.set()
            await finish.wait()

        async def receive():
            return {"type": "http.request", "body": b"{}"}

        async def send(message):
            sent.append(message)

        limiter = RequestLimitsMiddleware(downstream)
        scope = {"type": "http", "method": "POST", "path": PATHS[1], "headers": []}
        first = asyncio.create_task(limiter(scope, receive, send))
        await started.wait()
        await limiter(scope, receive, send)
        assert sent[0]["status"] == 503
        finish.set()
        await first
        assert limiter.inflight == 0

    asyncio.run(run())


def test_body_timeout_releases_slot(monkeypatch):
    async def run():
        sent = []

        async def receive():
            await asyncio.Event().wait()

        async def send(message):
            sent.append(message)

        limiter = RequestLimitsMiddleware(None)
        limiter.body_timeout = 0.01
        await limiter({"type": "http", "method": "POST", "path": PATHS[1], "headers": []}, receive, send)
        assert sent[0]["status"] == 408
        assert limiter.inflight == 0

    asyncio.run(run())
