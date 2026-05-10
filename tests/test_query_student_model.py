"""Tests for ``reachy.external_content.external_tools.query_student_model``.

All tests mock ``common.graphiti_client.GraphitiClient`` — no real FalkorDB
required (TASK-FG-005 AC). The seam test that verifies the
producer/consumer contract for ``GraphitiClient.search_student_progress``
is also defined here, marked with ``seam`` and ``integration_contract``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from reachy.external_content.external_tools import query_student_model as qsm_mod
from reachy.external_content.external_tools.query_student_model import (
    DEFAULT_STUDENT_NAME,
    DEFAULT_SUBJECT,
    QueryStudentModelTool,
)

# ---------------------------------------------------------------------------
# Mock data classes + factory functions (factory pattern per .claude/rules)
# ---------------------------------------------------------------------------


@dataclass
class MockProgress:
    """In-memory mock of a ``GraphitiClient.search_student_progress`` reply."""

    student_name: str = "lilymay"
    streak_days: int = 5
    level_name: str = "Knight"
    recent_xp: int = 240
    near_achievements: list[str] = field(default_factory=lambda: ["7-day streak"])
    topic_confidence: dict[str, float] = field(
        default_factory=lambda: {"reading": 0.7, "writing": 0.55}
    )
    data_available: bool = True


def make_progress(**overrides: Any) -> dict[str, Any]:
    """Build a happy-path progress dict with sensible defaults."""
    defaults: dict[str, Any] = {
        "student_name": "lilymay",
        "streak_days": 5,
        "level_name": "Knight",
        "recent_xp": 240,
        "near_achievements": ["7-day streak"],
        "topic_confidence": {"reading": 0.7, "writing": 0.55},
        "data_available": True,
    }
    defaults.update(overrides)
    return defaults


def make_unreachable_progress(**overrides: Any) -> dict[str, Any]:
    """Build a degraded progress dict matching ``GraphitiClient`` contract."""
    defaults: dict[str, Any] = {
        "data_available": False,
        "error": "unreachable: connection refused",
    }
    defaults.update(overrides)
    return defaults


@dataclass
class MockGraphitiClient:
    """Stand-in for :class:`common.graphiti_client.GraphitiClient`.

    Records constructor kwargs and method invocations so tests can assert
    on the group_id construction and the args forwarded to
    ``search_student_progress`` without touching FalkorDB.
    """

    init_kwargs: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, Any] = field(default_factory=make_progress)
    raise_on_call: BaseException | None = None
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    async def search_student_progress(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        self.calls.append((args, kwargs))
        if self.raise_on_call is not None:
            raise self.raise_on_call
        return self.progress


def make_mock_client(**overrides: Any) -> MockGraphitiClient:
    """Build a :class:`MockGraphitiClient` with sensible defaults."""
    defaults: dict[str, Any] = {
        "progress": make_progress(),
        "raise_on_call": None,
    }
    defaults.update(overrides)
    return MockGraphitiClient(**defaults)


def install_client_factory(
    monkeypatch: pytest.MonkeyPatch, mock_client: MockGraphitiClient
) -> list[dict[str, Any]]:
    """Patch ``GraphitiClient`` to return ``mock_client`` and capture init kwargs.

    Returns a list that will be appended to once per construction with the
    keyword arguments the tool used. Tests assert on this to verify the
    ``default_group_ids`` group_id construction.
    """
    captured: list[dict[str, Any]] = []

    def factory(*args: Any, **kwargs: Any) -> MockGraphitiClient:
        captured.append(kwargs)
        mock_client.init_kwargs = kwargs
        return mock_client

    monkeypatch.setattr(qsm_mod, "GraphitiClient", factory)
    return captured


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_run_happy_path_returns_progress_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: GraphitiClient returns data, tool returns it unchanged."""
    mock_client = make_mock_client()
    install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    result = await tool.run(subject="english", student_name="lilymay")

    assert result["data_available"] is True
    assert result["streak_days"] == 5
    assert result["level_name"] == "Knight"
    assert result["recent_xp"] == 240
    assert result["near_achievements"] == ["7-day streak"]
    assert "narration_hint" not in result, (
        "happy path must not inject narration_hint"
    )


async def test_run_forwards_subject_and_student_to_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tool forwards both kwargs to ``search_student_progress``."""
    mock_client = make_mock_client()
    install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    await tool.run(subject="literature", student_name="alice")

    assert len(mock_client.calls) == 1
    args, kwargs = mock_client.calls[0]
    forwarded = list(args) + list(kwargs.values())
    assert "alice" in forwarded
    assert "literature" in forwarded


# ---------------------------------------------------------------------------
# Unreachable / degraded path — must never crash, must add narration hint
# ---------------------------------------------------------------------------


async def test_run_when_graphiti_unreachable_returns_narration_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per scope §5.2 #2 — unreachable Graphiti must not crash conversation."""
    mock_client = make_mock_client(progress=make_unreachable_progress())
    install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    result = await tool.run(subject="english", student_name="lilymay")

    assert result["data_available"] is False
    assert "error" in result and result["error"]
    assert "narration_hint" in result and result["narration_hint"]
    # Narration hint must instruct LLM to acknowledge missing data
    hint = result["narration_hint"].lower()
    assert "no" in hint or "data" in hint
    assert result["student_name"] == "lilymay"


async def test_run_when_client_raises_unexpected_returns_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even an unexpected exception must not bubble out of the tool."""
    mock_client = make_mock_client(raise_on_call=RuntimeError("boom"))
    install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    result = await tool.run(subject="english", student_name="lilymay")

    assert result["data_available"] is False
    assert "error" in result
    assert "narration_hint" in result


async def test_run_when_client_returns_non_dict_returns_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed (non-dict) progress payload is degraded gracefully."""
    mock_client = make_mock_client()
    mock_client.progress = "not a dict"  # type: ignore[assignment]
    install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    result = await tool.run(subject="english", student_name="lilymay")

    assert result["data_available"] is False
    assert "error" in result
    assert "narration_hint" in result


# ---------------------------------------------------------------------------
# group_id construction — must be the dash form per scope §6 A6
# ---------------------------------------------------------------------------


async def test_run_constructs_group_id_with_dash_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """default_group_ids must be ``[f"student-{student_name}"]`` (dash form)."""
    mock_client = make_mock_client()
    captured = install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    await tool.run(subject="english", student_name="lilymay")

    assert len(captured) == 1
    init_kwargs = captured[0]
    assert init_kwargs["default_group_ids"] == ["student-lilymay"]


async def test_run_group_id_uses_supplied_student_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different student names produce different group_ids."""
    mock_client = make_mock_client()
    captured = install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    await tool.run(subject="english", student_name="alice")

    assert captured[0]["default_group_ids"] == ["student-alice"]


# ---------------------------------------------------------------------------
# Parameter defaults
# ---------------------------------------------------------------------------


async def test_run_defaults_subject_and_student_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling ``run()`` with no kwargs uses the documented defaults."""
    mock_client = make_mock_client()
    captured = install_client_factory(monkeypatch, mock_client)

    tool = QueryStudentModelTool()
    await tool.run()

    assert DEFAULT_STUDENT_NAME == "lilymay"
    assert DEFAULT_SUBJECT == "english"
    assert captured[0]["default_group_ids"] == [f"student-{DEFAULT_STUDENT_NAME}"]
    assert mock_client.calls, "client must have been invoked"


def test_tool_metadata_matches_acceptance_criteria() -> None:
    """Tool name / description / parameter schema match the AC."""
    tool = QueryStudentModelTool()
    assert tool.name == "query_student_model"
    assert tool.description and "progress" in tool.description.lower()
    schema = tool.parameters
    assert schema["type"] == "object"
    properties = schema["properties"]
    assert "subject" in properties
    assert "student_name" in properties
    assert properties["student_name"]["default"] == "lilymay"


# ---------------------------------------------------------------------------
# Seam test — pinned to the contract version of the GraphitiClient
# (mirrors the canonical seam test in TASK-FG-005 spec).
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("GraphitiClient.search_student_progress")
async def test_query_student_model_consumes_progress_dict() -> None:
    """Seam: Scholar tool consumes the contract-bound progress dict.

    Contract: dict with keys ``student_name``, ``streak_days``, ``level_name``,
    ``recent_xp``, ``near_achievements``, ``topic_confidence``,
    ``data_available``. Producer: TASK-FG-003.
    """
    with patch(
        "common.graphiti_client.GraphitiClient.search_student_progress",
        new_callable=AsyncMock,
    ) as mock_progress:
        mock_progress.return_value = {
            "student_name": "lilymay",
            "streak_days": 5,
            "level_name": "Knight",
            "recent_xp": 240,
            "near_achievements": ["7-day streak"],
            "topic_confidence": {"reading": 0.7},
            "data_available": True,
        }

        tool = QueryStudentModelTool()
        result = await tool.run(subject="english", student_name="lilymay")

        mock_progress.assert_called_once()
        assert isinstance(result, dict), "tool must return a dict"
        assert result.get("data_available") is True
        assert result.get("streak_days") == 5
