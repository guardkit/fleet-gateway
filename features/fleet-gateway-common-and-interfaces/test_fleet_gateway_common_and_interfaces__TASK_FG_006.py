"""pytest-bdd glue for ``fleet-gateway-common-and-interfaces.feature`` (TASK-FG-006).

Per-task glue (TASK-AB-004) that binds the two ``@task:TASK-FG-006``
scenarios in the FEAT-FG-001 feature file. The conftest at
``features/conftest.py`` selects this module when
``GUARDKIT_BDD_TASK_ID=TASK-FG-006`` is exported, mirroring the
TASK-FG-002 / TASK-FG-003 glue beside it.

The two bound scenarios (.feature lines 81 and 229):

1. *Bridge agent_status tool asks Jarvis to narrate the fleet state* —
   the @key-example happy path. The tool calls
   :class:`common.jarvis_client.JarvisClient`'s ``send_command`` and
   forwards Jarvis's narrated reply.

2. *Bridge agent_status tool degrades gracefully when NATS is
   unreachable* — the @negative resilience path. ``send_command`` raises
   :class:`ConnectionError`; the tool returns a ``"Fleet offline: ..."``
   string and never propagates the exception.

Step-definition discipline:

* Background steps are implemented unconditionally — every scenario in
  the file runs them regardless of ``@task`` tag.
* Scenario steps for ``@task:TASK-FG-006`` are fully implemented here.
  They mock ``common.jarvis_client.JarvisClient.send_command`` directly
  rather than the lower-level ``nats.connect`` seam, because the tool's
  contract is "what does Bridge do given send_command's behaviour?",
  not "how does send_command translate NATS errors?" (the latter is
  TASK-FG-002's responsibility, already covered by its glue).
* Steps unique to sibling tasks are NOT bound here. The bdd_runner
  invocation for TASK-FG-006 uses ``-m task_TASK_FG_006`` which
  deselects every other scenario at collection time, so unbound steps
  never need to resolve.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_bdd import given, scenario, then, when

from common.jarvis_client import JARVIS_TOPIC

_FEATURE_PATH = str(Path(__file__).with_name("fleet-gateway-common-and-interfaces.feature"))


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _make_result_bytes(response_text: str) -> bytes:
    """Serialise a Jarvis result envelope carrying ``response_text``."""
    envelope: dict[str, Any] = {
        "version": "1.0",
        "event_type": "result",
        "source_id": "jarvis",
        "correlation_id": "bdd-cid-fg006",
        "payload": {"success": True, "result": {"response": response_text}},
    }
    return json.dumps(envelope).encode("utf-8")


def _mock_nats_connection(reply_bytes: bytes | None = None) -> AsyncMock:
    """Build an ``AsyncMock`` mimicking a connected NATS client."""
    nc = AsyncMock()
    if reply_bytes is not None:
        response = MagicMock()
        response.data = reply_bytes
        nc.request.return_value = response
    nc.close = AsyncMock()
    return nc


def _run(coro: Any) -> Any:
    """Run an async coroutine on the current loop (matches sibling glue style)."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Scenario bindings — only @task:TASK-FG-006
# ---------------------------------------------------------------------------


@scenario(_FEATURE_PATH, "Bridge agent_status tool asks Jarvis to narrate the fleet state")
def test_bdd_bridge_agent_status_happy_path() -> None:
    """Bind the @key-example happy-path Bridge scenario."""


@scenario(
    _FEATURE_PATH,
    "Bridge agent_status tool degrades gracefully when NATS is unreachable",
)
def test_bdd_bridge_agent_status_degrades_gracefully() -> None:
    """Bind the @negative graceful-failure Bridge scenario."""


# ---------------------------------------------------------------------------
# Background steps
# ---------------------------------------------------------------------------


@given("the Fleet Gateway common module is available")
def given_common_module_available() -> None:
    """Smoke-import the common modules to verify packaging."""
    import common.envelope  # noqa: F401
    import common.jarvis_client  # noqa: F401


@given("Jarvis listens on the agents.command.jarvis topic")
def given_jarvis_listens() -> None:
    """No-op — JarvisClient publishes to ``JARVIS_TOPIC`` regardless."""


@given("the Graphiti knowledge graph is reachable on the configured FalkorDB endpoint")
def given_graphiti_reachable() -> None:
    """No-op for TASK-FG-006 scenarios — none touch Graphiti."""


# ---------------------------------------------------------------------------
# Scenario 1 steps — happy path
# ---------------------------------------------------------------------------


@given("the Bridge profile is loaded on Reachy")
def given_bridge_profile_loaded() -> None:
    """Verify the Bridge profile assets are on disk and non-empty.

    The Pollen runtime loads ``instructions.txt``, ``tools.txt`` and
    ``voice.txt`` from the ``external_profiles/bridge/`` folder. Asserting
    they exist here keeps the BDD oracle honest about the profile-side
    deliverable in addition to the tool-side deliverable.
    """
    base = (
        Path(__file__).resolve().parents[2]
        / "reachy"
        / "external_content"
        / "external_profiles"
        / "bridge"
    )
    for name in ("instructions.txt", "tools.txt", "voice.txt"):
        path = base / name
        assert path.is_file(), f"Bridge profile is missing {name}"
        assert path.read_text(encoding="utf-8").strip(), (
            f"Bridge profile {name} must not be empty"
        )

    tools_listed = (base / "tools.txt").read_text(encoding="utf-8").splitlines()
    assert "agent_status" in {line.strip() for line in tools_listed}, (
        "Bridge tools.txt must list the agent_status tool"
    )


@given("Jarvis is ready to answer", target_fixture="bdd_mock_nc")
def given_jarvis_ready() -> AsyncMock:
    """Provide a mock NATS connection whose request returns a canned reply.

    The tool calls ``send_command`` which goes through ``nats.connect``;
    we patch the connect site in the When-step so the mock here is the
    object the tool's underlying request will land on.
    """
    return _mock_nats_connection(
        reply_bytes=_make_result_bytes("All systems nominal. Build green.")
    )


def _invoke_happy_path(bdd_mock_nc: AsyncMock) -> dict[str, Any]:
    """Helper: run AgentStatusTool against a live mock NATS connection."""
    from reachy.external_content.external_tools.agent_status import AgentStatusTool

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=bdd_mock_nc)):
        result = _run(AgentStatusTool().run(agent="all"))
    return {"result": result, "nc": bdd_mock_nc, "raised": None}


@then("a command envelope should be published to the Jarvis command topic")
def then_envelope_published_to_jarvis(bdd_invocation: dict[str, Any]) -> None:
    """Assert the underlying NATS request hit ``JARVIS_TOPIC`` exactly once."""
    nc: AsyncMock = bdd_invocation["nc"]
    nc.request.assert_awaited_once()
    assert nc.request.await_args.args[0] == JARVIS_TOPIC


@then("the envelope should ask Jarvis for the current fleet status")
def then_envelope_asks_for_status(bdd_invocation: dict[str, Any]) -> None:
    """Assert the published message phrases the request as a fleet status query."""
    nc: AsyncMock = bdd_invocation["nc"]
    raw_bytes: bytes = nc.request.await_args.args[1]
    envelope = json.loads(raw_bytes.decode("utf-8"))
    message = envelope["payload"]["args"]["message"]
    lowered = message.lower()
    assert "fleet" in lowered or "status" in lowered, (
        f"Bridge query should mention fleet/status, got {message!r}"
    )
    # And Bridge must identify itself as the reachy-bridge gateway
    assert envelope["source_id"] == "reachy-bridge-gateway", (
        f"source_id should be 'reachy-bridge-gateway', got {envelope['source_id']!r}"
    )


@then("the tool should return Jarvis's status narration as text")
def then_tool_returns_status_text(bdd_invocation: dict[str, Any]) -> None:
    """Assert the tool returns the narrated text from Jarvis verbatim."""
    result = bdd_invocation["result"]
    assert isinstance(result, str)
    assert result == "All systems nominal. Build green."


# ---------------------------------------------------------------------------
# Scenario 2 steps — graceful degradation
# ---------------------------------------------------------------------------


@given("the NATS server is unreachable", target_fixture="bdd_mock_nc")
def given_nats_unreachable() -> AsyncMock | None:
    """Indicate NATS is offline by signalling the When-step to swap connect.

    Returning ``None`` is the convention used here to flag the unreachable
    scenario; the When-step inspects the fixture and patches
    ``nats.connect`` to raise ``ConnectionRefusedError`` (which
    JarvisClient translates to ``ConnectionError``, which AgentStatusTool
    translates to a 'Fleet offline:' string).
    """
    return None


@when(
    "the Bridge agent_status tool is invoked",
    target_fixture="bdd_invocation",
)
def when_bridge_tool_invoked(bdd_mock_nc: AsyncMock | None) -> dict[str, Any]:
    """Invoke ``AgentStatusTool().run(agent='all')`` and capture the outcome.

    Branches on the ``bdd_mock_nc`` fixture, which the upstream Given-step
    populates differently per scenario:

    * Happy path (Given "Jarvis is ready to answer") → ``bdd_mock_nc`` is
      a live ``AsyncMock`` that returns canned bytes; we patch
      ``nats.connect`` to hand it out and call the tool.
    * Unreachable path (Given "the NATS server is unreachable") →
      ``bdd_mock_nc`` is ``None``; we patch ``nats.connect`` to raise
      ``ConnectionRefusedError`` (which the JarvisClient promotes to
      ``ConnectionError`` and AgentStatusTool turns into a
      ``"Fleet offline: ..."`` string). Any leaked exception is captured
      so the Then-step can assert no propagation.

    Imports ``AgentStatusTool`` lazily so the module-level import does
    not require the Pollen SDK at collection time.
    """
    from reachy.external_content.external_tools.agent_status import AgentStatusTool

    if bdd_mock_nc is None:
        with patch(
            "common.jarvis_client.nats.connect",
            AsyncMock(side_effect=ConnectionRefusedError("Connection refused")),
        ):
            try:
                result = _run(AgentStatusTool().run(agent="all"))
                raised: BaseException | None = None
            except BaseException as exc:  # noqa: BLE001 — Then-step asserts no propagation
                result = ""
                raised = exc
        return {"result": result, "nc": None, "raised": raised}

    return _invoke_happy_path(bdd_mock_nc)


@then("the tool should return a text message explaining the fleet is offline")
def then_tool_returns_offline_message(bdd_invocation: dict[str, Any]) -> None:
    """Assert the returned string starts with the 'Fleet offline:' prefix."""
    result = bdd_invocation["result"]
    assert isinstance(result, str)
    assert result.startswith("Fleet offline:"), (
        f"Expected graceful 'Fleet offline:' prefix, got {result!r}"
    )


@then("no exception should propagate to the conversation loop")
def then_no_exception_propagates(bdd_invocation: dict[str, Any]) -> None:
    """Assert the When-step did not capture any exception."""
    raised = bdd_invocation.get("raised")
    assert raised is None, f"AgentStatusTool.run leaked exception: {raised!r}"
