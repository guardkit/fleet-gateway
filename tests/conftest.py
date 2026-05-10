"""Shared test factories for fleet-gateway tests.

Uses the factory function pattern (see .claude/rules/patterns/factory.md):
mock dataclasses + ``make_*`` factories with **overrides — not pytest
fixtures with mutable state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


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
