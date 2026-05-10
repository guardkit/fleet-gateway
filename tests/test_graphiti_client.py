"""Unit and seam tests for ``common.graphiti_client``.

These tests mock ``graphiti_core.Graphiti`` via the ``_create_graphiti_instance``
seam — no real FalkorDB is required (TASK-FG-003 AC).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from common import graphiti_client as gc_mod
from common.graphiti_client import GraphitiClient, parse_falkordb_uri

# ---------------------------------------------------------------------------
# Mock data classes + factories (factory pattern per .claude/rules)
# ---------------------------------------------------------------------------


@dataclass
class MockEdge:
    """In-memory mock of a ``graphiti-core`` ``EntityEdge``."""

    uuid: str = "edge-uuid"
    fact: str = "default fact"
    name: str = "RELATES_TO"
    created_at: str | None = None


def make_edge(**overrides: Any) -> MockEdge:
    """Build a :class:`MockEdge` with sensible defaults."""
    defaults: dict[str, Any] = {
        "uuid": "edge-uuid",
        "fact": "default fact",
        "name": "RELATES_TO",
        "created_at": None,
    }
    defaults.update(overrides)
    return MockEdge(**defaults)


@dataclass
class MockGraphiti:
    """Stand-in for ``graphiti_core.Graphiti``.

    ``results`` may be a list of edges (returned for every search) or a
    callable accepting the query string for per-query routing.
    """

    results: list[MockEdge] | Callable[[str], list[MockEdge]] = field(default_factory=list)
    raise_on_search: BaseException | None = None
    search_calls: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False

    async def search(
        self,
        query: str,
        group_ids: list[str] | None = None,
        num_results: int = 10,
    ) -> list[MockEdge]:
        self.search_calls.append(
            {"query": query, "group_ids": group_ids, "num_results": num_results}
        )
        if self.raise_on_search is not None:
            raise self.raise_on_search
        if callable(self.results):
            return self.results(query)
        return list(self.results)

    async def close(self) -> None:
        self.closed = True


def make_factory(
    *,
    results: list[MockEdge] | Callable[[str], list[MockEdge]] | None = None,
    raise_on_search: BaseException | None = None,
    raise_on_construct: BaseException | None = None,
) -> Callable[[str, int], Any]:
    """Return an async ``_create_graphiti_instance`` replacement.

    The returned callable carries an ``instances`` attribute listing every
    :class:`MockGraphiti` it produced, so tests can assert on the recorded
    ``search_calls`` and ``closed`` flag without juggling globals.
    """
    instances: list[MockGraphiti] = []

    async def factory(host: str, port: int) -> Any:
        if raise_on_construct is not None:
            raise raise_on_construct
        instance = MockGraphiti(results=results or [], raise_on_search=raise_on_search)
        instances.append(instance)
        return instance

    # Attach for inspection — cast keeps mypy quiet about the dynamic attr.
    cast(Any, factory).instances = instances
    return factory


def _instances(factory: Callable[..., Any]) -> list[MockGraphiti]:
    """Return the recorded :class:`MockGraphiti` instances for ``factory``."""
    return cast(list[MockGraphiti], cast(Any, factory).instances)


# ---------------------------------------------------------------------------
# Default fixture: every test gets a no-op factory unless it overrides.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_graphiti(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Any]]:
    """Replace ``_create_graphiti_instance`` with a no-result factory."""
    factory = make_factory(results=[])
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    yield factory


# ---------------------------------------------------------------------------
# parse_falkordb_uri
# ---------------------------------------------------------------------------


def test_parse_falkordb_uri_happy_path() -> None:
    """``redis://host:port`` parses to (host, port)."""
    assert parse_falkordb_uri("redis://whitestocks:6379") == ("whitestocks", 6379)


@pytest.mark.parametrize(
    "uri",
    ["http://whitestocks:6379", "whitestocks:6379", "redis://whitestocks", "redis://:6379"],
)
def test_parse_falkordb_uri_rejects_malformed(uri: str) -> None:
    """Non-redis schemes / missing host / missing port all raise ``ValueError``."""
    with pytest.raises(ValueError):
        parse_falkordb_uri(uri)


# ---------------------------------------------------------------------------
# Construction defaults
# ---------------------------------------------------------------------------


def test_default_group_ids_is_student_lilymay() -> None:
    """Default group_ids honours scope §6 A6 corrected dash form."""
    client = GraphitiClient()
    assert client.default_group_ids == ["student-lilymay"]


def test_default_group_ids_override() -> None:
    """Caller-supplied default_group_ids replaces the built-in default."""
    client = GraphitiClient(default_group_ids=["alpha", "beta"])
    assert client.default_group_ids == ["alpha", "beta"]


def test_default_group_ids_returns_copy() -> None:
    """The default_group_ids property returns a copy — list cannot be mutated."""
    client = GraphitiClient()
    client.default_group_ids.append("intruder")
    assert client.default_group_ids == ["student-lilymay"]


# ---------------------------------------------------------------------------
# search()
# ---------------------------------------------------------------------------


async def test_search_happy_path_normalises_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each EntityEdge becomes a {uuid, fact, name, created_at} dict."""
    factory = make_factory(
        results=[
            make_edge(uuid="u-1", fact="lilymay studies english"),
            make_edge(uuid="u-2", fact="lilymay loves verbs", created_at="2026-05-01T10:00"),
        ]
    )
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    facts = await client.search("english progress")

    assert len(facts) == 2
    assert facts[0] == {
        "uuid": "u-1",
        "fact": "lilymay studies english",
        "name": "RELATES_TO",
        "created_at": None,
    }
    assert facts[1]["uuid"] == "u-2"
    assert facts[1]["created_at"] == "2026-05-01T10:00"
    # Connect-per-call: instance is closed after search.
    assert _instances(factory)[0].closed is True


async def test_search_empty_result_returns_empty_list(
    patch_graphiti: Callable[..., Any],
) -> None:
    """When graphiti-core returns no edges the client returns ``[]``."""
    client = GraphitiClient()
    assert await client.search("nothing matches") == []


async def test_search_uses_default_group_ids(patch_graphiti: Callable[..., Any]) -> None:
    """Omitting group_ids forwards the default to graphiti-core."""
    client = GraphitiClient()
    await client.search("q")
    call = _instances(patch_graphiti)[0].search_calls[0]
    assert call["group_ids"] == ["student-lilymay"]


async def test_search_group_ids_override(patch_graphiti: Callable[..., Any]) -> None:
    """Caller-supplied group_ids overrides the default."""
    client = GraphitiClient()
    await client.search("q", group_ids=["custom-group"])
    call = _instances(patch_graphiti)[0].search_calls[0]
    assert call["group_ids"] == ["custom-group"]


async def test_search_unreachable_returns_empty_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connection failures on construction degrade to ``[]`` per scope §5.2."""
    factory = make_factory(raise_on_construct=ConnectionRefusedError("connection refused"))
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()
    assert await client.search("q") == []


async def test_search_failure_during_search_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Errors raised mid-search degrade to ``[]`` and still close the client."""
    factory = make_factory(raise_on_search=OSError("boom"))
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    assert await client.search("q") == []
    assert _instances(factory)[0].closed is True


# ---------------------------------------------------------------------------
# search_student_progress()
# ---------------------------------------------------------------------------


def _three_query_router(query: str) -> list[MockEdge]:
    """Return distinct facts depending on which sub-query is being run."""
    if "streak" in query:
        return [
            make_edge(
                uuid="streak-1",
                fact="lilymay has a streak of 7 days at level Bronze 3 with 250 xp earned",
            ),
        ]
    if "achievements" in query:
        return [
            make_edge(uuid="ach-1", fact="lilymay near achievement: Word Wizard"),
            make_edge(uuid="ach-2", fact="lilymay near achievement: Verb Voyager"),
        ]
    if "topic confidence" in query:
        return [
            make_edge(uuid="topic-1", fact="topic verbs confidence: 0.82"),
            make_edge(uuid="topic-2", fact="topic spelling confidence: 0.65"),
        ]
    return []


async def test_search_student_progress_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Composes three searches and shapes the structured progress dict."""
    factory = make_factory(results=_three_query_router)
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    progress = await client.search_student_progress("lilymay", "english")

    assert progress["student_name"] == "lilymay"
    assert progress["data_available"] is True
    assert progress["streak_days"] == 7
    assert progress["recent_xp"] == 250
    assert "Bronze" in progress["level_name"]
    assert len(progress["near_achievements"]) == 2
    assert progress["topic_confidence"]["verbs"] == pytest.approx(0.82)
    assert progress["topic_confidence"]["spelling"] == pytest.approx(0.65)


async def test_search_student_progress_uses_dash_group_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """group_id derivation uses the corrected ``student-{name}`` dash form."""
    factory = make_factory(results=[])
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    await client.search_student_progress("alex", "maths")

    instance = _instances(factory)[0]
    assert instance.search_calls, "expected search to be invoked"
    for call in instance.search_calls:
        assert call["group_ids"] == ["student-alex"], (
            "group_id must follow student-{name} (dash) per scope §6 A6"
        )
    assert "study_tutor__student_model" not in str(instance.search_calls), (
        "rejected double-underscore group_id leaked into search"
    )


async def test_search_student_progress_no_data_still_marks_available(
    patch_graphiti: Callable[..., Any],
) -> None:
    """Empty searches still report data_available=True (graph is reachable)."""
    client = GraphitiClient()
    progress = await client.search_student_progress("lilymay", "english")
    assert progress["data_available"] is True
    assert progress["streak_days"] == 0
    assert progress["level_name"] == "unknown"
    assert progress["recent_xp"] == 0
    assert progress["near_achievements"] == []
    assert progress["topic_confidence"] == {}


async def test_search_student_progress_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """ConnectionRefusedError → data_available=False, error starts ``unreachable:``."""
    factory = make_factory(raise_on_construct=ConnectionRefusedError("nope: refused"))
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    out = await client.search_student_progress()

    assert out["data_available"] is False
    assert out["error"].startswith("unreachable:")
    assert "refused" in out["error"]


async def test_search_student_progress_auth_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth failures are distinguishable per ASSUM-004."""

    class AuthenticationError(Exception):
        """Mimic ``redis.exceptions.AuthenticationError``."""

    factory = make_factory(
        raise_on_construct=AuthenticationError("WRONGPASS invalid username-password pair")
    )
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    out = await client.search_student_progress()

    assert out["data_available"] is False
    assert out["error"].startswith("auth-failed:")
    assert "WRONGPASS" in out["error"]


async def test_search_student_progress_search_error_returns_error_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Errors raised during the search calls also degrade to the error dict."""
    factory = make_factory(raise_on_search=OSError("graph offline"))
    monkeypatch.setattr(gc_mod, "_create_graphiti_instance", factory)
    client = GraphitiClient()

    out = await client.search_student_progress()

    assert out["data_available"] is False
    assert out["error"].startswith("unreachable:")
    assert _instances(factory)[0].closed is True


# ---------------------------------------------------------------------------
# Seam test (per task spec)
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("FALKORDB_URI")
def test_falkordb_uri_format() -> None:
    """Verify the FalkorDB URI passed to GraphitiClient matches expected format.

    Contract: ``redis://{host}:{port}``.
    Producer: operator config / Reachy launch script.
    """
    uri = os.environ.get("FALKORDB_URI", "redis://whitestocks:6379")

    assert uri.startswith("redis://"), f"FALKORDB_URI must use redis:// scheme, got: {uri}"
    assert ":" in uri.split("://", 1)[1], (
        f"FALKORDB_URI must include explicit port, got: {uri}"
    )
    # Use the production parser so seam covers the same code path as runtime.
    host, port = parse_falkordb_uri(uri)
    assert host
    assert port > 0
