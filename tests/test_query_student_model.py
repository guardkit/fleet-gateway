"""Tests for ``reachy.external_content.external_tools.query_student_model``.

Post-migration (FEAT-VOICE-004 R04 + R05): the tool conforms to the Pollen
``core_tools.Tool`` ABC (``parameters_schema`` + async ``__call__``, dict
return) and reads the durable learning record via the study-tutor ``:8100``
adapter — **not** the frozen Graphiti graph. Network is replaced by an
``httpx.MockTransport`` (see ``conftest``); no real adapter required.
"""

from __future__ import annotations

import inspect
from typing import Any

import httpx
import pytest

from common.tutor_client import STUDENT_MODEL_PATH
from reachy.external_content.external_tools import query_student_model as qsm_mod
from reachy.external_content.external_tools.query_student_model import (
    DEFAULT_STUDENT_NAME,
    DEFAULT_SUBJECT,
    QueryStudentModelTool,
)
from tests.conftest import install_mock_transport
from tests.test_tutor_client import make_tutor_handler

# Mirrors the live ``GET /api/student-model`` body (study-tutor
# ``build_student_model_response``): ``near_achievements`` is a list of
# objects, and the §2.2.1 enrichment fields ride alongside the original R05
# fields. The tool consumes the body opaquely (only ``data_available`` is
# load-bearing), so this shape exercises pass-through fidelity to the narrator.
HAPPY_RECORD = {
    "student_name": "lilymay",
    "streak_days": 5,
    "level_name": "Knight",
    "recent_xp": 240,
    "near_achievements": [
        {
            "id": "streak-7",
            "name": "7-day streak",
            "description": "Study seven days in a row",
            "progress": 5,
            "target": 7,
            "hint": "Two more days to go",
        }
    ],
    "topic_confidence": {"reading": 0.7, "writing": 0.55},
    "data_available": True,
    # -- §2.2.1 enrichment (additive; passed through untouched) --------------
    "total_xp": 1240,
    "level_number": 3,
    "longest_streak": 9,
    "recent_achievements": [
        {
            "id": "first-session",
            "name": "First session",
            "unlocked_at": "2026-07-10T09:00:00+00:00",
            "xp_awarded": 50,
        }
    ],
    "next_unlock": {"level": 4, "feature": "Custom avatar"},
}


# ---------------------------------------------------------------------------
# Happy path — reads the durable record via :8100
# ---------------------------------------------------------------------------


async def test_happy_path_returns_progress_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    install_mock_transport(monkeypatch, make_tutor_handler(student_body=HAPPY_RECORD))

    tool = QueryStudentModelTool()
    result = await tool(subject="english", student_name="lilymay")

    assert result["data_available"] is True
    assert result["streak_days"] == 5
    assert result["level_name"] == "Knight"
    assert result["recent_xp"] == 240
    assert "narration_hint" not in result, "happy path must not inject narration_hint"


async def test_forwards_subject_and_student_as_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(
        monkeypatch, make_tutor_handler(record=record, student_body=HAPPY_RECORD)
    )

    tool = QueryStudentModelTool()
    await tool(subject="literature", student_name="alice")

    req = record[0]
    assert req.method == "GET"
    assert req.url.path == STUDENT_MODEL_PATH
    params = dict(req.url.params)
    assert params["subject"] == "literature"
    assert params["student_name"] == "alice"


# ---------------------------------------------------------------------------
# Degraded / unavailable — must never crash, must add narration hint
# ---------------------------------------------------------------------------


async def test_when_tutor_unavailable_returns_narration_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-2xx read (transport error / 4xx / 5xx) degrades gracefully."""
    install_mock_transport(monkeypatch, make_tutor_handler(student_status=503))

    tool = QueryStudentModelTool()
    result = await tool(subject="english", student_name="lilymay")

    assert result["data_available"] is False
    assert result["error"]
    assert result["narration_hint"]
    hint = result["narration_hint"].lower()
    assert "no" in hint or "data" in hint
    assert result["student_name"] == "lilymay"


async def test_when_client_raises_unexpected_returns_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpected (non-TutorUnavailable) error must not bubble out."""

    async def boom(self: Any, *a: Any, **k: Any) -> dict[str, Any]:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("common.tutor_client.TutorClient.get_student_model", boom)

    tool = QueryStudentModelTool()
    result = await tool(subject="english", student_name="lilymay")

    assert result["data_available"] is False
    assert "error" in result
    assert "narration_hint" in result


async def test_when_client_returns_non_dict_returns_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def not_a_dict(self: Any, *a: Any, **k: Any) -> Any:
        return "not a dict"

    monkeypatch.setattr("common.tutor_client.TutorClient.get_student_model", not_a_dict)

    tool = QueryStudentModelTool()
    result = await tool(subject="english", student_name="lilymay")

    assert result["data_available"] is False
    assert "error" in result
    assert "narration_hint" in result


# ---------------------------------------------------------------------------
# Parameter defaults
# ---------------------------------------------------------------------------


async def test_defaults_subject_and_student_name(monkeypatch: pytest.MonkeyPatch) -> None:
    record: list[httpx.Request] = []
    install_mock_transport(
        monkeypatch, make_tutor_handler(record=record, student_body=HAPPY_RECORD)
    )

    tool = QueryStudentModelTool()
    await tool()

    assert DEFAULT_STUDENT_NAME == "lilymay"
    assert DEFAULT_SUBJECT == "english"
    params = dict(record[0].url.params)
    assert params["subject"] == "english"
    assert params["student_name"] == "lilymay"


# ---------------------------------------------------------------------------
# ABC conformance (R04) + the negative that the rejected shape is gone
# ---------------------------------------------------------------------------


def test_tool_conforms_to_pollen_abc() -> None:
    """AC-R04-1/2/4: parameters_schema + async __call__ + dict return; no run/parameters."""
    tool = QueryStudentModelTool()
    assert hasattr(tool, "parameters_schema"), "must expose parameters_schema"
    assert not hasattr(tool, "parameters"), "must not use rejected 'parameters' field"
    assert callable(getattr(tool, "__call__", None)), "must implement __call__"
    assert not hasattr(tool, "run"), "must not use the rejected 'run' method"
    assert inspect.iscoroutinefunction(tool.__call__), "__call__ must be async"

    schema = tool.parameters_schema
    assert schema["type"] == "object"
    assert "subject" in schema["properties"]
    assert "student_name" in schema["properties"]
    assert schema["properties"]["student_name"]["default"] == "lilymay"


# ---------------------------------------------------------------------------
# Seam test — R05: reads via :8100, never from Graphiti
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("STUDY_TUTOR_HTTP_8100")
async def test_query_student_model_reads_via_8100_not_graphiti(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The read targets the :8100 adapter with a bearer; no Graphiti path remains.

    Contract: HTTP GET against the study-tutor adapter on :8100 (bearer).
    Producer: TASK-APP-001 (HTTP adapter).
    """
    # The frozen graph is gone from the tool's data plane entirely — no import
    # of the graphiti client module and no client construction remain. (Prose
    # in the docstring may still explain the migration away from it.)
    assert not hasattr(qsm_mod, "GraphitiClient"), "Graphiti read path must be removed"
    src = inspect.getsource(qsm_mod)
    assert "graphiti_client" not in src, "no residual graphiti_client import"
    assert "GraphitiClient" not in src, "no residual GraphitiClient construction"

    monkeypatch.setenv("STUDY_TUTOR_TOKEN", "token-lilymay")
    record: list[httpx.Request] = []
    install_mock_transport(
        monkeypatch, make_tutor_handler(record=record, student_body=HAPPY_RECORD)
    )

    tool = QueryStudentModelTool()
    result = await tool(subject="english", student_name="lilymay")

    assert isinstance(result, dict), "tool must return a dict"
    assert result["data_available"] is True
    req = record[0]
    assert req.url.path == STUDENT_MODEL_PATH
    assert req.headers["authorization"] == "Bearer token-lilymay"
