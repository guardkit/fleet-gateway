"""Tests for :mod:`common.tutor_client`.

All network is replaced by an :class:`httpx.MockTransport` injected via
``install_mock_transport`` (see ``conftest.py``). No real ``:8100`` adapter
required — the seam tests pin method, path, bearer auth and body shape.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from common.tutor_client import (
    DEFAULT_TUTOR_URL,
    STUDENT_MODEL_PATH,
    TutorClient,
    TutorUnavailableError,
)
from tests.conftest import install_mock_transport

# ---------------------------------------------------------------------------
# Handler factory
# ---------------------------------------------------------------------------


def make_tutor_handler(
    *,
    record: list[httpx.Request] | None = None,
    start_status: int = 200,
    turn_status: int = 200,
    student_status: int = 200,
    session_id: str = "sess-1",
    resumed: bool = False,
    tutor_response: str = "What do you notice about the opening line?",
    student_body: dict[str, Any] | None = None,
    turn_body: dict[str, Any] | None = None,
    raise_exc: Exception | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    """Build a MockTransport handler routing the three tutor endpoints."""

    def handler(request: httpx.Request) -> httpx.Response:
        if record is not None:
            record.append(request)
        if raise_exc is not None:
            raise raise_exc
        path = request.url.path
        if path == "/api/sessions/start":
            if start_status >= 400:
                return httpx.Response(start_status, json={"error_type": "Unauthenticated"})
            return httpx.Response(
                start_status,
                json={"session_id": session_id, "student_id": "lilymay", "resumed": resumed},
            )
        if path.endswith("/turn"):
            if turn_status >= 400:
                return httpx.Response(turn_status, json={"error": "boom"})
            body = turn_body if turn_body is not None else {"tutor_response": tutor_response}
            return httpx.Response(turn_status, json=body)
        if path == STUDENT_MODEL_PATH:
            if student_status >= 400:
                return httpx.Response(student_status, json={"error": "no endpoint"})
            body = (
                student_body
                if student_body is not None
                else {
                    "student_name": "lilymay",
                    "streak_days": 5,
                    "level_name": "Knight",
                    "data_available": True,
                }
            )
            return httpx.Response(student_status, json=body)
        return httpx.Response(404, json={"error": "unknown path"})

    return handler


# ---------------------------------------------------------------------------
# Construction / configuration
# ---------------------------------------------------------------------------


def test_defaults_to_gb10_url_and_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDY_TUTOR_HTTP_URL", raising=False)
    monkeypatch.delenv("STUDY_TUTOR_TOKEN", raising=False)
    client = TutorClient()
    assert client.base_url == DEFAULT_TUTOR_URL
    assert client.token == ""


def test_reads_base_url_and_token_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDY_TUTOR_HTTP_URL", "http://tutor.local:8100/")
    monkeypatch.setenv("STUDY_TUTOR_TOKEN", "token-lilymay")
    client = TutorClient()
    assert client.base_url == "http://tutor.local:8100"  # trailing slash stripped
    assert client.token == "token-lilymay"


# ---------------------------------------------------------------------------
# start_session
# ---------------------------------------------------------------------------


async def test_start_session_posts_start_with_resume_and_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record, resumed=True))
    client = TutorClient("http://tutor.local:8100", token="token-lilymay")

    result = await client.start_session("english", resume_if_active=True)

    assert result["session_id"] == "sess-1"
    assert result["resumed"] is True
    assert len(record) == 1
    req = record[0]
    assert req.method == "POST"
    assert req.url.path == "/api/sessions/start"
    assert req.headers["authorization"] == "Bearer token-lilymay"
    body = json.loads(req.content)
    assert body == {"subject": "english", "resume_if_active": True}


async def test_start_session_rejected_bearer_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_mock_transport(monkeypatch, make_tutor_handler(start_status=401))
    client = TutorClient("http://tutor.local:8100", token="bad")
    with pytest.raises(TutorUnavailableError):
        await client.start_session("english")


# ---------------------------------------------------------------------------
# turn
# ---------------------------------------------------------------------------


async def test_turn_posts_user_message_and_returns_tutor_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(
        monkeypatch,
        make_tutor_handler(record=record, tutor_response="Good — why does that matter?"),
    )
    client = TutorClient("http://tutor.local:8100", token="t")

    text = await client.turn("sess-1", "What is a metaphor?")

    assert text == "Good — why does that matter?"
    req = record[0]
    assert req.url.path == "/api/sessions/sess-1/turn"
    assert json.loads(req.content) == {"user_message": "What is a metaphor?"}


async def test_turn_missing_tutor_response_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_mock_transport(monkeypatch, make_tutor_handler(turn_body={"unexpected": 1}))
    client = TutorClient("http://tutor.local:8100")
    with pytest.raises(TutorUnavailableError):
        await client.turn("sess-1", "hello")


async def test_turn_transport_error_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_mock_transport(
        monkeypatch,
        make_tutor_handler(raise_exc=httpx.ConnectError("no route to host")),
    )
    client = TutorClient("http://tutor.local:8100")
    with pytest.raises(TutorUnavailableError):
        await client.turn("sess-1", "hello")


# ---------------------------------------------------------------------------
# get_student_model (R05)
# ---------------------------------------------------------------------------


async def test_get_student_model_reads_via_8100_with_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record))
    client = TutorClient("http://tutor.local:8100", token="token-lilymay")

    result = await client.get_student_model("english", "lilymay")

    assert result["data_available"] is True
    assert result["streak_days"] == 5
    req = record[0]
    assert req.method == "GET"
    assert req.url.path == STUDENT_MODEL_PATH
    assert req.headers["authorization"] == "Bearer token-lilymay"
    assert dict(req.url.params) == {"subject": "english", "student_name": "lilymay"}


async def test_get_student_model_pending_endpoint_404_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Until the adapter ships the read, a 404 degrades — never crashes."""
    install_mock_transport(monkeypatch, make_tutor_handler(student_status=404))
    client = TutorClient("http://tutor.local:8100")
    with pytest.raises(TutorUnavailableError):
        await client.get_student_model("english")
