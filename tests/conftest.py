"""Shared test factories for fleet-gateway tests.

Uses the factory function pattern (see .claude/rules/patterns/factory.md):
mock dataclasses + ``make_*`` factories with **overrides — not pytest
fixtures with mutable state.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

import httpx
import pytest


@dataclass
class MockResultPayload:
    """In-memory mock of a Jarvis result payload."""

    success: bool = True
    result: dict[str, Any] = field(default_factory=lambda: {"response": "ok"})
    error: str | None = None


def make_result_payload(**overrides: Any) -> dict[str, Any]:
    """Build a result-payload dict with sensible defaults."""
    mock = MockResultPayload(**overrides)
    payload: dict[str, Any] = {"success": mock.success, "result": mock.result}
    if mock.error is not None:
        payload["error"] = mock.error
    return payload


def make_result_envelope(**overrides: Any) -> dict[str, Any]:
    """Build a full result envelope wrapping a result payload.

    ``overrides`` are forwarded to :func:`make_result_payload`.
    """
    payload = make_result_payload(**overrides)
    return {
        "version": "1.0",
        "event_type": "result",
        "source_id": "jarvis",
        "correlation_id": "test-cid-0001",
        "payload": payload,
    }


def make_result_bytes(**overrides: Any) -> bytes:
    """Serialise :func:`make_result_envelope` to UTF-8 JSON bytes."""
    return json.dumps(make_result_envelope(**overrides)).encode("utf-8")


# ---------------------------------------------------------------------------
# study-tutor :8100 HTTP seam — inject an httpx.MockTransport into the
# connect-per-call TutorClient so seam tests never touch the network.
# ---------------------------------------------------------------------------

Handler = Callable[[httpx.Request], httpx.Response]


def install_mock_transport(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> None:
    """Route ``TutorClient``'s ``httpx.AsyncClient`` through a MockTransport.

    :class:`common.tutor_client.TutorClient` opens a fresh
    :class:`httpx.AsyncClient` per call (connect-per-call). This wraps that
    constructor so every client built inside the module is handed a
    :class:`httpx.MockTransport` around ``handler`` — ``base_url``, bearer
    headers and timeout are preserved, only the socket is replaced.

    Args:
        monkeypatch: The active monkeypatch fixture (auto-restores).
        handler: A ``(httpx.Request) -> httpx.Response`` callable. It may
            raise :class:`httpx.HTTPError` subclasses to simulate transport
            failures.
    """
    # tutor_client uses ``import httpx; httpx.AsyncClient(...)`` — the same
    # module object as here — so patching the global attribute reaches it.
    # Unwrap first so repeated installs in one test don't nest wrappers (a
    # nested factory would overwrite the inner transport).
    current = httpx.AsyncClient
    real_async_client = cast(
        "type[httpx.AsyncClient]", getattr(current, "_real_async_client", current)
    )

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_async_client(*args, **kwargs)

    factory._real_async_client = real_async_client  # type: ignore[attr-defined]
    monkeypatch.setattr(httpx, "AsyncClient", factory)
