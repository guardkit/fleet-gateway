"""Tests for ``reachy.external_content.external_tools.ask_tutor``.

Network is replaced by an ``httpx.MockTransport`` (see ``conftest`` and the
handler factory in ``test_tutor_client``). Seam tests pin the R06 subject
default, the ``resume_if_active`` flag, verbatim subject forwarding, and the
single-offline-string mapping for every failure mode (AC-R07-3/4).
"""

from __future__ import annotations

import json

import httpx
import pytest

from common.subject import DEFAULT_SUBJECT
from reachy.external_content.external_tools.ask_tutor import (
    TUTOR_OFFLINE_MESSAGE,
    AskTutorTool,
)
from tests.conftest import install_mock_transport
from tests.test_tutor_client import make_tutor_handler


def _paths(record: list[httpx.Request]) -> list[str]:
    return [r.url.path for r in record]


# ---------------------------------------------------------------------------
# ABC conformance (AC-R07-1)
# ---------------------------------------------------------------------------


def test_ask_tutor_conforms_to_tool_abc() -> None:
    tool = AskTutorTool()
    assert hasattr(tool, "parameters_schema"), "must expose parameters_schema"
    assert not hasattr(tool, "parameters"), "must not use rejected 'parameters'"
    assert callable(getattr(tool, "__call__", None)), "must implement async __call__"
    assert not hasattr(tool, "run"), "must not use the rejected 'run' method"
    assert tool.name == "ask_tutor"
    assert "message" in tool.parameters_schema["properties"]
    assert tool.parameters_schema["required"] == ["message"]


# ---------------------------------------------------------------------------
# Happy path + session lifecycle (AC-R07-2)
# ---------------------------------------------------------------------------


async def test_first_call_starts_session_then_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(
        monkeypatch, make_tutor_handler(record=record, tutor_response="Let's begin.")
    )
    tool = AskTutorTool()

    result = await tool(message="Help me plan a Macbeth essay")

    assert result == {"response": "Let's begin."}
    assert _paths(record) == ["/api/sessions/start", "/api/sessions/sess-1/turn"]


async def test_session_is_reused_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record))
    tool = AskTutorTool()

    await tool(message="first question")
    await tool(message="second question")

    # One /start, two /turn — the session is created once and reused.
    assert _paths(record).count("/api/sessions/start") == 1
    assert _paths(record).count("/api/sessions/sess-1/turn") == 2


async def test_empty_message_is_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record))
    tool = AskTutorTool()

    result = await tool(message="   ")

    assert "error" in result
    assert record == [], "must not call the tutor for an empty message"


# ---------------------------------------------------------------------------
# Subject default + forwarding — R06 seam (AC-R07-3)
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("SUBJECT_DEFAULT")
async def test_ask_tutor_sends_subject_default_and_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitted subject → shared default (never empty); resume flag set."""
    assert DEFAULT_SUBJECT == "english"

    # (a) No subject arg → falls back to the shared default, resume=true.
    record_a: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record_a))
    await AskTutorTool()(message="how do I open this essay?")
    start_a = json.loads(record_a[0].content)
    assert start_a["subject"] == DEFAULT_SUBJECT
    assert start_a["subject"] != ""
    assert start_a["resume_if_active"] is True

    # (b) Explicit subject → forwarded verbatim (multi-subject path).
    record_b: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record_b))
    await AskTutorTool()(message="analyse this poem", subject="literature")
    assert json.loads(record_b[0].content)["subject"] == "literature"


async def test_blank_subject_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(monkeypatch, make_tutor_handler(record=record))
    await AskTutorTool()(message="hi", subject="   ")
    assert json.loads(record[0].content)["subject"] == DEFAULT_SUBJECT


# ---------------------------------------------------------------------------
# Graceful offline — one string for every failure mode (AC-R07-4)
# ---------------------------------------------------------------------------


async def test_start_5xx_returns_offline_string(monkeypatch: pytest.MonkeyPatch) -> None:
    install_mock_transport(monkeypatch, make_tutor_handler(start_status=500))
    result = await AskTutorTool()(message="hello")
    assert result == {"response": TUTOR_OFFLINE_MESSAGE}


async def test_rejected_bearer_returns_same_offline_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 401 must collapse to the identical string — no auth detail leaks."""
    install_mock_transport(monkeypatch, make_tutor_handler(start_status=401))
    result = await AskTutorTool()(message="hello")
    assert result == {"response": TUTOR_OFFLINE_MESSAGE}


async def test_turn_failure_returns_offline_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_mock_transport(monkeypatch, make_tutor_handler(turn_status=503))
    result = await AskTutorTool()(message="hello")
    assert result == {"response": TUTOR_OFFLINE_MESSAGE}


async def test_connection_error_returns_offline_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_mock_transport(monkeypatch, make_tutor_handler(raise_exc=httpx.ConnectError("down")))
    result = await AskTutorTool()(message="hello")
    assert result == {"response": TUTOR_OFFLINE_MESSAGE}
    # The offline string carries no network / auth / status detail.
    assert "401" not in TUTOR_OFFLINE_MESSAGE
    assert "http" not in TUTOR_OFFLINE_MESSAGE.lower()
