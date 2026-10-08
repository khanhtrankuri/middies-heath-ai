"""Process-local admission limits, applied before JSON parsing or inference.

Multi-worker/public deployments also need a shared quota at their gateway.
Client addresses come from ASGI, never directly from forwarding headers.
"""
from __future__ import annotations

import asyncio
import math
import os
import time
from collections import OrderedDict, deque

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def _positive(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


class RequestLimitsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.max_bytes = _positive("MEDDIES_MAX_REQUEST_BYTES", 262144)
        self.body_timeout = _positive("MEDDIES_BODY_TIMEOUT_SECONDS", 15)
        self.window = _positive("MEDDIES_RATE_WINDOW_SECONDS", 60)
        self.global_limit = _positive("MEDDIES_RATE_GLOBAL", 120)
        self.max_clients = _positive("MEDDIES_RATE_MAX_CLIENTS", 4096)
        self.max_inflight = _positive("MEDDIES_MAX_INFLIGHT_REQUESTS", 8)
        self.limits = {
            "/api/v1/triage": _positive("MEDDIES_RATE_TRIAGE", 120),
            "/api/v1/consultation": _positive("MEDDIES_RATE_CONSULTATION", 20),
            "/api/v1/rag/search": _positive("MEDDIES_RATE_RAG_SEARCH", 60),
        }
        self.global_hits: deque[float] = deque()
        self.clients: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self.inflight = 0

    def _admit(self, peer: str, path: str) -> int:
        now = time.monotonic()
        cutoff = now - self.window
        while self.global_hits and self.global_hits[0] <= cutoff:
            self.global_hits.popleft()
        # Ordered by last accepted request; active entries are never evicted.
        while self.clients and next(iter(self.clients.values()))[-1] <= cutoff:
            self.clients.popitem(last=False)
        key = (peer, path)
        hits = self.clients.get(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(self.global_hits) >= self.global_limit:
            return max(1, math.ceil(self.global_hits[0] + self.window - now))
        if len(hits) >= self.limits[path]:
            return max(1, math.ceil(hits[0] + self.window - now))
        if key not in self.clients and len(self.clients) >= self.max_clients:
            return self.window
        hits.append(now)
        self.clients[key] = hits
        self.clients.move_to_end(key)
        self.global_hits.append(now)
        return 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "").rstrip("/")
        if scope["type"] != "http" or scope.get("method") != "POST" or path not in self.limits:
            await self.app(scope, receive, send)
            return

        async def reject(status: int, detail: str, retry: int = 0) -> None:
            headers = {"Retry-After": str(retry)} if retry else None
            await JSONResponse({"detail": detail}, status_code=status, headers=headers)(scope, receive, send)

        peer = (scope.get("client") or ("unknown", 0))[0]
        retry = self._admit(peer, path)
        if retry:
            await reject(429, "Request rate limit exceeded", retry)
            return
        if self.inflight >= self.max_inflight:
            await reject(503, "Service is busy", 1)
            return

        self.inflight += 1
        try:
            lengths = [value for name, value in scope.get("headers", []) if name == b"content-length"]
            if lengths:
                if len(lengths) != 1 or len(lengths[0]) > 20 or not lengths[0].isdigit():
                    await reject(400, "Invalid Content-Length")
                    return
                if int(lengths[0]) > self.max_bytes:
                    await reject(413, "Request body too large")
                    return
            if any(name == b"content-encoding" and value.lower() != b"identity"
                   for name, value in scope.get("headers", [])):
                await reject(415, "Compressed request bodies are not supported")
                return

            body = bytearray()
            deadline = time.monotonic() + self.body_timeout
            while True:
                try:
                    message = await asyncio.wait_for(receive(), max(0, deadline - time.monotonic()))
                except asyncio.TimeoutError:
                    await reject(408, "Request body timed out")
                    return
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > self.max_bytes:
                    await reject(413, "Request body too large")
                    return
                body.extend(chunk)
                if not message.get("more_body", False):
                    break

            async def replay() -> dict:
                nonlocal body
                if body is not None:
                    data, body = bytes(body), None
                    return {"type": "http.request", "body": data, "more_body": False}
                return await receive()

            await self.app(scope, replay, send)
        finally:
            self.inflight -= 1
