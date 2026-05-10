"""pytest-bdd glue for ``fleet-gateway-common-and-interfaces.feature`` (TASK-FG-005).

Per-task glue (TASK-AB-004) that binds the four ``@task:TASK-FG-005``
scenarios in the FEAT-FG-001 feature file. The conftest at
``features/conftest.py`` selects this module when
``GUARDKIT_BDD_TASK_ID=TASK-FG-005`` is exported, mirroring the
TASK-FG-002 / TASK-FG-003 glue beside it.

Step-definition discipline:

* Background steps are implemented unconditionally — every scenario in
  the file runs them regardless of ``@task`` tag.
* Scenario steps for ``@task:TASK-FG-005`` (.feature lines 70, 92, 219,
  317) are fully implemented here using the same factory-patch seam
  exploited by the unit test suite — no real FalkorDB or Pollen daemon
  is required.
* Steps unique to sibling tasks (``@task:TASK-FG-001``,
  ``@task:TASK-FG-002``, ``@task:TASK-FG-003``, ``@task:TASK-FG-004``,
  ``@task:TASK-FG-006``) are NOT bound here. The bdd_runner invocation
  for TASK-FG-005 uses ``-m task_TASK_FG_005`` which deselects every
  other scenario at collection time, so unbound steps for those
  scenarios are never resolved at test-run time and the BDD oracle
  passes (``scenarios_failed == 0``).
"""

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from reachy.external_content.external_tools import (
    celebrate_achievement as ca_mod,
)
from reachy.external_content.external_tools import (
    query_student_model as qsm_mod,
)
from reachy.external_content.external_tools.celebrate_achievement import (
    CelebrateAchievementTool,
)
from reachy.external_content.external_tools.query_student_model import (
    QueryStudentModelTool,
)

_FEATURE_PATH = str(Path(__file__).with_name("fleet-gateway-common-and-interfaces.feature"))


# ---------------------------------------------------------------------------
# Mock GraphitiClient seam — mirrors tests/test_query_student_model.py
# ---------------------------------------------------------------------------


@dataclass
class _MockGraphitiClient:
    """Stand-in for :class:`common.graphiti_client.GraphitiClient`.

    Records constructor kwargs and method invocations so ``then``-step
    assertions can verify the dash-form group_id contract without
    touching FalkorDB.
    """

    init_kwargs: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, Any] = field(
        default_factory=lambda: {
            "student_name": "lilymay",
            "streak_days": 5,
            "level_name": "Knight",
            "recent_xp": 240,
            "near_achievements": ["7-day streak"],
            "topic_confidence": {"reading": 0.7, "writing": 0.55},
            "data_available": True,
        }
    )
    raise_on_call: BaseException | None = None
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    async def search_student_progress(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        self.calls.append((args, kwargs))
        if self.raise_on_call is not None:
            raise self.raise_on_call
        return self.progress


def _install_client_factory(
    monkeypatch: pytest.MonkeyPatch,
    *,
    progress: dict[str, Any] | None = None,
    raise_on_call: BaseException | None = None,
) -> _MockGraphitiClient:
    """Patch ``qsm_mod.GraphitiClient`` to return a recording mock.

    Returns the singleton :class:`_MockGraphitiClient` shared by every
    construction during the scenario so ``then`` steps can assert on the
    init kwargs and call records.
    """
    mock_client = _MockGraphitiClient(
        progress=progress
        if progress is not None
        else _MockGraphitiClient().progress,
        raise_on_call=raise_on_call,
    )

    def factory(*args: Any, **kwargs: Any) -> _MockGraphitiClient:
        mock_client.init_kwargs = kwargs
        return mock_client

    monkeypatch.setattr(qsm_mod, "GraphitiClient", factory)
    return mock_client


# ---------------------------------------------------------------------------
# Scenario bindings — only @task:TASK-FG-005
# ---------------------------------------------------------------------------


@scenario(
    _FEATURE_PATH,
    "Scholar's query_student_model tool returns structured progress",
)
def test_bdd_query_student_model_returns_structured_progress() -> None:
    """Bind the @key-example happy-path query_student_model scenario."""


@scenario(
    _FEATURE_PATH,
    "Scholar celebrate_achievement tool returns a celebration prompt",
)
def test_bdd_celebrate_achievement_returns_prompt() -> None:
    """Bind the @key-example celebrate_achievement scenario."""


@scenario(
    _FEATURE_PATH,
    "Scholar query_student_model tool degrades gracefully when Graphiti is unreachable",
)
def test_bdd_query_student_model_degrades_gracefully() -> None:
    """Bind the @negative graceful-degradation scenario."""


@scenario(
    _FEATURE_PATH,
    "Reachy tools import the common module without fleet-gateway being pip-published",
)
def test_bdd_reachy_tools_import_without_pip_install() -> None:
    """Bind the @edge-case import-isolation scenario."""


# ---------------------------------------------------------------------------
# Background steps — bound unconditionally
# ---------------------------------------------------------------------------


@given("the Fleet Gateway common module is available")
def given_common_module_available() -> None:
    """Smoke-import the common modules to verify packaging."""
    import common.envelope  # noqa: F401
    import common.graphiti_client  # noqa: F401


@given("Jarvis listens on the agents.command.jarvis topic")
def given_jarvis_listens() -> None:
    """No-op for TASK-FG-005 scenarios — none touch Jarvis."""


@given("the Graphiti knowledge graph is reachable on the configured FalkorDB endpoint")
def given_graphiti_reachable() -> None:
    """No-op — per-scenario Given steps install the appropriate mock factory."""


# ---------------------------------------------------------------------------
# TASK-FG-005 Given steps
# ---------------------------------------------------------------------------


@given("Scholar is in conversation with a learner")
def given_scholar_in_conversation() -> None:
    """No-op context anchor — Scholar's tools are pure functions for unit BDD."""


@given(
    "the Graphiti knowledge graph holds progress for the configured student",
    target_fixture="bdd_mock_client",
)
def given_graphiti_holds_progress_for_configured_student(
    monkeypatch: pytest.MonkeyPatch,
) -> _MockGraphitiClient:
    """Install the happy-path mock returning a structured progress dict."""
    return _install_client_factory(monkeypatch)


@given("the Graphiti knowledge graph is unreachable", target_fixture="bdd_mock_client")
def given_graphiti_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> _MockGraphitiClient:
    """Install a mock returning the GraphitiClient unreachable contract."""
    return _install_client_factory(
        monkeypatch,
        progress={
            "data_available": False,
            "error": "unreachable: connection refused",
        },
    )


@given("fleet-gateway is on the Pollen interpreter's PYTHONPATH")
def given_fleet_gateway_on_pythonpath() -> None:
    """No-op anchor — running pytest already places fleet-gateway on sys.path."""


# ---------------------------------------------------------------------------
# TASK-FG-005 When steps
# ---------------------------------------------------------------------------


@when(
    "Scholar invokes the query_student_model tool",
    target_fixture="bdd_query_result",
)
def when_scholar_invokes_query_student_model() -> dict[str, Any]:
    """Drive ``QueryStudentModelTool.run`` with the documented defaults."""
    tool = QueryStudentModelTool()
    return asyncio.get_event_loop().run_until_complete(tool.run())


@when(
    parsers.parse(
        'Scholar invokes the celebrate_achievement tool with achievement type "{achievement_type}"'
    ),
    target_fixture="bdd_celebrate_result",
)
def when_scholar_invokes_celebrate_achievement(achievement_type: str) -> str:
    """Drive ``CelebrateAchievementTool.run`` with the parametrised enum value."""
    tool = CelebrateAchievementTool()
    return asyncio.get_event_loop().run_until_complete(tool.run(achievement_type))


@when(
    "the Reachy conversation app loads the external tools",
    target_fixture="bdd_imported_tools",
)
def when_reachy_loads_tools() -> dict[str, Any]:
    """Re-import the Scholar and Bridge tool modules and capture references."""
    qsm = importlib.import_module(
        "reachy.external_content.external_tools.query_student_model"
    )
    ca = importlib.import_module(
        "reachy.external_content.external_tools.celebrate_achievement"
    )
    ag = importlib.import_module(
        "reachy.external_content.external_tools.agent_status"
    )
    return {
        "scholar_query": qsm.QueryStudentModelTool,
        "scholar_celebrate": ca.CelebrateAchievementTool,
        "bridge_agent_status": ag.AgentStatusTool,
    }


# ---------------------------------------------------------------------------
# TASK-FG-005 Then steps — query_student_model happy + degraded
# ---------------------------------------------------------------------------


@then("the tool should return a structured progress report the language model can narrate")
def then_query_returns_structured_report(bdd_query_result: dict[str, Any]) -> None:
    """Assert the dict carries every contract key the LLM needs to narrate."""
    assert isinstance(bdd_query_result, dict)
    expected_keys = {
        "student_name",
        "streak_days",
        "level_name",
        "recent_xp",
        "near_achievements",
        "topic_confidence",
        "data_available",
    }
    missing = expected_keys - bdd_query_result.keys()
    assert not missing, f"missing contract keys: {missing}"


@then("the result should mark the data as available")
def then_query_result_marks_data_available(bdd_query_result: dict[str, Any]) -> None:
    """Assert the happy-path data_available flag is True."""
    assert bdd_query_result["data_available"] is True


@then("the tool should return a result marking data as unavailable")
def then_query_result_marks_data_unavailable(
    bdd_query_result: dict[str, Any],
) -> None:
    """Assert the degraded-path data_available flag is False."""
    assert bdd_query_result["data_available"] is False


@then("the result should include a brief explanation of the failure")
def then_query_result_includes_failure_explanation(
    bdd_query_result: dict[str, Any],
) -> None:
    """Assert ``error`` carries a non-empty failure description."""
    assert "error" in bdd_query_result
    assert isinstance(bdd_query_result["error"], str)
    assert bdd_query_result["error"].strip()


@then("no exception should propagate to the conversation loop")
def then_no_exception_from_query(bdd_query_result: dict[str, Any]) -> None:
    """Implicit — bdd_query_result resolved, so no exception escaped."""
    assert isinstance(bdd_query_result, dict)


# ---------------------------------------------------------------------------
# TASK-FG-005 Then steps — celebrate_achievement
# ---------------------------------------------------------------------------


@then("the tool should return text describing the achievement to celebrate")
def then_celebrate_returns_text(bdd_celebrate_result: str) -> None:
    """Assert the scaffold is a non-empty string mentioning the milestone."""
    assert isinstance(bdd_celebrate_result, str)
    assert bdd_celebrate_result.strip()
    assert "level" in bdd_celebrate_result.lower()


@then("the language model should remain responsible for choosing the dance and emotion")
def then_celebrate_delegates_motion(bdd_celebrate_result: str) -> None:
    """Assert the scaffold names the delegate tools rather than encoding motion."""
    text = bdd_celebrate_result.lower()
    assert "emotion" in text or "dance" in text, (
        "scaffold must remind the LLM to delegate to the built-in motion tools"
    )


# ---------------------------------------------------------------------------
# TASK-FG-005 Then steps — import isolation
# ---------------------------------------------------------------------------


@then("importing the Scholar tool should succeed")
def then_scholar_import_succeeds(bdd_imported_tools: dict[str, Any]) -> None:
    """Assert the Scholar tool classes resolved during the When step."""
    assert bdd_imported_tools["scholar_query"] is QueryStudentModelTool
    assert bdd_imported_tools["scholar_celebrate"] is CelebrateAchievementTool


@then("importing the Bridge tool should succeed")
def then_bridge_import_succeeds(bdd_imported_tools: dict[str, Any]) -> None:
    """Assert the Bridge agent_status tool also resolved."""
    assert bdd_imported_tools["bridge_agent_status"] is not None
    assert bdd_imported_tools["bridge_agent_status"].name == "agent_status"


@then("neither import should require fleet-gateway to be pip-installed")
def then_imports_do_not_require_pip_install() -> None:
    """Assert ``common`` and ``reachy`` resolve via sys.path, not site-packages.

    The unit test environment for this BDD oracle has fleet-gateway on
    ``sys.path`` (pytest rootdir) but not necessarily in ``site-packages``;
    a successful import in the When step proves PYTHONPATH-only resolution.
    """
    import common.graphiti_client as gc

    # The module's __file__ must live inside the worktree, not site-packages.
    module_path = Path(gc.__file__).resolve()
    assert "site-packages" not in module_path.parts, (
        f"common.graphiti_client resolved from site-packages: {module_path}"
    )

    # Reference the module to keep ruff happy and prove the symbol is live.
    assert ca_mod is not None
    assert qsm_mod is not None
