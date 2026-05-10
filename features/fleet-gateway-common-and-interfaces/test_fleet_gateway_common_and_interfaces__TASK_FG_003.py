"""pytest-bdd glue for ``fleet-gateway-common-and-interfaces.feature`` (TASK-FG-003).

Per-task glue (TASK-AB-004) that binds the seven ``@task:TASK-FG-003``
scenarios in the FEAT-FG-001 feature file. The conftest at
``features/conftest.py`` selects this module when
``GUARDKIT_BDD_TASK_ID=TASK-FG-003`` is exported, mirroring the
TASK-FG-002 glue beside it.

Step-definition discipline:

* Background steps are implemented unconditionally — every scenario in
  the file runs them regardless of ``@task`` tag.
* Scenario steps for ``@task:TASK-FG-003`` (.feature lines 58, 164,
  179, 271, 291, 355, 367) are fully implemented here using the same
  ``_create_graphiti_instance`` seam exploited by the unit test suite —
  no real FalkorDB is required.
* Steps unique to sibling tasks (``@task:TASK-FG-001``,
  ``@task:TASK-FG-002`` etc.) are NOT bound here. The bdd_runner
  invocation for TASK-FG-003 uses ``-m task_TASK_FG_003`` which
  deselects every other scenario at collection time, so unbound steps
  never need to resolve.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from common import graphiti_client as gc_mod
from common.graphiti_client import GraphitiClient

_FEATURE_PATH = str(Path(__file__).with_name("fleet-gateway-common-and-interfaces.feature"))


# ---------------------------------------------------------------------------
# Mock graphiti-core seam (mirrors tests/test_graphiti_client.py)
# ---------------------------------------------------------------------------


@dataclass
class _MockEdge:
    """Minimal ``EntityEdge`` stand-in used for BDD glue."""

    uuid: str = "edge"
    fact: str = ""
    name: str = "RELATES_TO"
    created_at: str | None = None


@dataclass
class _MockGraphiti:
    """In-memory ``graphiti_core.Graphiti`` substitute."""

    results: list[_MockEdge] | Callable[[str], list[_MockEdge]] = field(default_factory=list)
    raise_on_search: BaseException | None = None
    search_calls: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    async def search(
        self,
        query: str,
        group_ids: list[str] | None = None,
        num_results: int = 10,
    ) -> list[_MockEdge]:
        self.search_calls.append(
            {"query": query, "group_ids": group_ids, "num_results": num_results}
        )
        if self.raise_on_search is not None:
            raise self.raise_on_search
        if callable(self.results):
            facts = self.results(query)
        else:
            facts = list(self.results)
        return facts[:num_results]

    async def close(self) -> None:
        self.closed = True


def _install_factory(
    monkeypatch: pytest.MonkeyPatch,
    *,
    results: list[_MockEdge] | Callable[[str], list[_MockEdge]] | None = None,
    raise_on_search: BaseException | None = None,
    raise_on_construct: BaseException | None = None,
) -> Callable[..., Any]:
    """Patch ``_create_graphiti_instance`` and return the factory.

    The factory carries an ``instances`` attribute listing every
    :class:`_MockGraphiti` it produced — enabling ``then``-step
    assertions on per-call ``search_calls`` and the ``closed`` flag.
    """
    instances: list[_MockGraphiti] = []

    async def factory(host: str, port: int) -> Any:
        if raise_on_construct is not None:
            raise raise_on_construct
        instance = _MockGraphiti(results=results or [], raise_on_search=raise_on_search)
        instances.append(instance)
        return instance

    cast(Any, factory).instances = instances
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    return factory


def _instances(factory: Callable[..., Any]) -> list[_MockGraphiti]:
    """Return the recorded :class:`_MockGraphiti` instances for ``factory``."""
    return cast(list[_MockGraphiti], cast(Any, factory).instances)


def _three_query_router(query: str) -> list[_MockEdge]:
    """Route the three sub-queries of ``search_student_progress``."""
    if "streak" in query:
        return [
            _MockEdge(
                uuid="streak-1",
                fact="lilymay has a streak of 5 days at level Bronze 2 with 180 xp earned",
            )
        ]
    if "achievements" in query:
        return [_MockEdge(uuid="ach-1", fact="lilymay near achievement: Word Wizard")]
    if "topic confidence" in query:
        return [
            _MockEdge(uuid="topic-1", fact="topic verbs confidence: 0.81"),
            _MockEdge(uuid="topic-2", fact="topic spelling confidence: 0.62"),
        ]
    return []


def _no_streak_router(query: str) -> list[_MockEdge]:
    """Variant: streak fact omits the ``streak ... N`` numeric pattern."""
    if "streak" in query:
        return [_MockEdge(uuid="lvl-1", fact="lilymay is at level Silver 1")]
    if "achievements" in query:
        return []
    if "topic confidence" in query:
        return [_MockEdge(uuid="topic-1", fact="topic verbs confidence: 0.4")]
    return []


# ---------------------------------------------------------------------------
# Scenario bindings — only @task:TASK-FG-003
# ---------------------------------------------------------------------------


@scenario(_FEATURE_PATH, "Looking up a student's current study progress")
def test_bdd_lookup_student_progress() -> None:
    """Bind the @key-example happy-path scenario."""


@scenario(_FEATURE_PATH, "Graphiti search respects the requested result count")
def test_bdd_search_respects_num_results() -> None:
    """Bind the @boundary num_results scenario outline."""


@scenario(_FEATURE_PATH, "Graphiti search uses the student-named group identifier")
def test_bdd_search_uses_dash_group_id() -> None:
    """Bind the @boundary group_id scenario."""


@scenario(_FEATURE_PATH, "Graphiti search returns an empty progress result for an unseen student")
def test_bdd_unseen_student_returns_empty_progress() -> None:
    """Bind the @edge-case unseen-student scenario."""


@scenario(_FEATURE_PATH, "Graphiti client classifies a backend failure as unavailable")
def test_bdd_unreachable_classifies_unavailable() -> None:
    """Bind the @edge-case unreachable-backend scenario."""


@scenario(
    _FEATURE_PATH,
    "Graphiti client returns partial progress when some fields are missing",
)
def test_bdd_partial_progress_returns_known_fields() -> None:
    """Bind the @edge-case partial-data scenario."""


@scenario(
    _FEATURE_PATH,
    "Graphiti client distinguishes an authentication failure from an unreachable backend",
)
def test_bdd_auth_failure_classified() -> None:
    """Bind the @edge-case authentication-failure scenario."""


# ---------------------------------------------------------------------------
# Background steps
# ---------------------------------------------------------------------------


@given("the Fleet Gateway common module is available")
def given_common_module_available() -> None:
    """Smoke-import the common modules to verify packaging."""
    import common.envelope  # noqa: F401
    import common.graphiti_client  # noqa: F401


@given("Jarvis listens on the agents.command.jarvis topic")
def given_jarvis_listens() -> None:
    """No-op for TASK-FG-003 scenarios — none touch Jarvis."""


@given("the Graphiti knowledge graph is reachable on the configured FalkorDB endpoint")
def given_graphiti_reachable() -> None:
    """No-op — per-scenario Given steps install the appropriate mock factory."""


# ---------------------------------------------------------------------------
# TASK-FG-003 Given steps
# ---------------------------------------------------------------------------


@given(
    parsers.parse('the Graphiti knowledge graph holds progress for student "{student}"'),
    target_fixture="bdd_student_name",
)
def given_graphiti_holds_progress(
    student: str, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Install the three-query-router factory returning full progress facts."""
    _install_factory(monkeypatch, results=_three_query_router)
    return student


@given(
    parsers.parse(
        'the Graphiti knowledge graph holds progress for student "{student}"'
        " with no recorded streak"
    ),
    target_fixture="bdd_student_name",
)
def given_graphiti_holds_partial_progress(
    student: str, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Install a factory whose streak fact omits a parsable streak number."""
    _install_factory(monkeypatch, results=_no_streak_router)
    return student


@given("the Graphiti knowledge graph holds many matching facts")
def given_graphiti_holds_many_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide 50 mock edges so the num_results cap can be observed."""
    edges = [_MockEdge(uuid=f"u-{i}", fact=f"fact {i}") for i in range(50)]
    _install_factory(monkeypatch, results=edges)


@given(
    parsers.parse('the configured student name is "{student}"'),
    target_fixture="bdd_student_name",
)
def given_configured_student_name(
    student: str, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Empty-result factory — only the recorded group_ids matter for this scenario."""
    _install_factory(monkeypatch, results=[])
    return student


@given(
    parsers.parse('the Graphiti knowledge graph has no records for student "{student}"'),
    target_fixture="bdd_student_name",
)
def given_no_records_for_student(
    student: str, monkeypatch: pytest.MonkeyPatch
) -> str:
    """Empty-result factory — graph is reachable but knows nothing yet."""
    _install_factory(monkeypatch, results=[])
    return student


@given("the FalkorDB endpoint refuses connections")
def given_falkordb_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction raises ``ConnectionRefusedError``."""
    _install_factory(
        monkeypatch,
        raise_on_construct=ConnectionRefusedError("connection refused at whitestocks:6379"),
    )


@given("the FalkorDB endpoint accepts connections but rejects the credential")
def given_falkordb_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction raises a custom auth-shaped error per ASSUM-004."""

    class _AuthenticationError(Exception):
        """Mimic ``redis.exceptions.AuthenticationError`` for classification."""

    _install_factory(
        monkeypatch,
        raise_on_construct=_AuthenticationError(
            "WRONGPASS invalid username-password pair"
        ),
    )


# ---------------------------------------------------------------------------
# TASK-FG-003 When steps
# ---------------------------------------------------------------------------


@when(
    "I ask the Graphiti client for the student's English progress",
    target_fixture="bdd_progress",
)
def when_ask_for_english_progress(bdd_student_name: str) -> dict[str, Any]:
    """Invoke ``search_student_progress`` for the previously-named student."""
    client = GraphitiClient()
    return asyncio.get_event_loop().run_until_complete(
        client.search_student_progress(student_name=bdd_student_name, subject="english")
    )


@when(
    "I ask the Graphiti client for the student's progress",
    target_fixture="bdd_progress",
)
def when_ask_for_progress(bdd_student_name: str) -> dict[str, Any]:
    """Subject-agnostic variant for scenarios that omit the subject."""
    client = GraphitiClient()
    return asyncio.get_event_loop().run_until_complete(
        client.search_student_progress(student_name=bdd_student_name)
    )


@when(
    "I ask the Graphiti client for a student's progress",
    target_fixture="bdd_progress",
)
def when_ask_for_a_student_progress() -> dict[str, Any]:
    """Failure-path variant — no specific student fixture is required."""
    client = GraphitiClient()
    return asyncio.get_event_loop().run_until_complete(client.search_student_progress())


@when(
    parsers.parse("I ask the Graphiti client to search with a result count of {num_results:d}"),
    target_fixture="bdd_search_result",
)
def when_search_with_num_results(num_results: int) -> list[dict[str, Any]]:
    """Drive the ``search()`` API with the boundary num_results value."""
    client = GraphitiClient()
    return asyncio.get_event_loop().run_until_complete(
        client.search("english progress", num_results=num_results)
    )


# ---------------------------------------------------------------------------
# TASK-FG-003 Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse('the result should report the student\'s name as "{student}"'))
def then_result_reports_student_name(bdd_progress: dict[str, Any], student: str) -> None:
    """Assert the response carries the requested student name."""
    assert bdd_progress["student_name"] == student


@then("the result should include a numeric study streak")
def then_result_has_numeric_streak(bdd_progress: dict[str, Any]) -> None:
    """Assert the streak_days field is an int."""
    assert isinstance(bdd_progress["streak_days"], int)


@then("the result should include a level name")
def then_result_has_level_name(bdd_progress: dict[str, Any]) -> None:
    """Assert level_name is a non-empty string."""
    assert isinstance(bdd_progress["level_name"], str)
    assert bdd_progress["level_name"]


@then("the result should include topic confidence by topic")
def then_result_has_topic_confidence(bdd_progress: dict[str, Any]) -> None:
    """Assert topic_confidence is a dict (empty or populated, both legal)."""
    assert isinstance(bdd_progress["topic_confidence"], dict)


@then("the result should mark the data as available")
def then_result_data_available(bdd_progress: dict[str, Any]) -> None:
    """Assert data_available=True (graph reachable, no failure classification)."""
    assert bdd_progress["data_available"] is True


@then("the result should mark the data as unavailable")
def then_result_data_unavailable(bdd_progress: dict[str, Any]) -> None:
    """Assert data_available=False under the failure-classification contract."""
    assert bdd_progress["data_available"] is False


@then("the result should include the underlying failure reason")
def then_result_includes_failure_reason(bdd_progress: dict[str, Any]) -> None:
    """Assert the error string is non-empty and prefixed with the kind."""
    assert "error" in bdd_progress
    assert isinstance(bdd_progress["error"], str)
    assert ":" in bdd_progress["error"]


@then("the result should classify the failure as an authentication problem")
def then_result_classifies_auth_failure(bdd_progress: dict[str, Any]) -> None:
    """Assert the auth-failed prefix is set per ASSUM-004."""
    assert bdd_progress["error"].startswith("auth-failed:")


@then("the result should describe the student as having no recorded progress yet")
def then_result_describes_no_progress(bdd_progress: dict[str, Any]) -> None:
    """Assert the empty-graph defaults: 0 streak / xp, unknown level, empty lists."""
    assert bdd_progress["streak_days"] == 0
    assert bdd_progress["recent_xp"] == 0
    assert bdd_progress["level_name"] == "unknown"
    assert bdd_progress["near_achievements"] == []
    assert bdd_progress["topic_confidence"] == {}


@then("the result should mark the streak field as unavailable")
def then_result_marks_streak_unavailable(bdd_progress: dict[str, Any]) -> None:
    """Assert streak_days falls back to 0 when no parsable streak exists."""
    assert bdd_progress["streak_days"] == 0


@then("the result should still include the level name")
def then_result_still_includes_level(bdd_progress: dict[str, Any]) -> None:
    """Assert level_name was extracted from the partial fact set."""
    assert bdd_progress["level_name"] != "unknown"


@then("no exception should be raised")
def then_no_exception_raised(bdd_progress: dict[str, Any]) -> None:
    """Implicit — bdd_progress is already populated, so no exception escaped."""
    assert isinstance(bdd_progress, dict)


@then(parsers.parse("the result should contain at most {num_results:d} facts"))
def then_result_capped(bdd_search_result: list[dict[str, Any]], num_results: int) -> None:
    """Assert the search result honoured the requested num_results cap."""
    assert len(bdd_search_result) <= num_results


@then(parsers.parse('the search should be scoped to the group identifier "{group_id}"'))
def then_search_scoped_to_group_id(group_id: str) -> None:
    """Assert every recorded search call carried the dash-form group_id."""
    factory = gc_mod._create_graphiti_instance  # current patched factory
    instances = _instances(factory)
    assert instances, "expected at least one Graphiti instance to be created"
    for instance in instances:
        assert instance.search_calls, "expected search to be invoked"
        for call in instance.search_calls:
            assert call["group_ids"] == [group_id], (
                f"search must be scoped to {group_id!r}, got {call['group_ids']!r}"
            )
