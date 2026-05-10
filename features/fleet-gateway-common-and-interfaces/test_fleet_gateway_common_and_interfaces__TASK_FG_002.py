"""pytest-bdd glue for ``fleet-gateway-common-and-interfaces.feature``.

Companion glue for the BDD oracle. The conftest at ``features/conftest.py``
redirects ``.feature`` argv to this sibling module so :func:`pytest_bdd.scenario`
can bind the scenarios. Without this glue ``bdd_runner`` exits 4
("not found") and the Coach gate reports a BDD oracle failure — which is
exactly the failure surfaced on Turns 1–3 of TASK-FG-002.

Step-definition discipline:

* Background steps are implemented unconditionally — they run for every
  scenario in the file regardless of which ``@task:TASK-FG-XXX`` tag the
  scenario carries.
* Scenario steps for ``@task:TASK-FG-002`` (the five JarvisClient
  scenarios at .feature lines 47, 153, 200, 209, 261) are fully
  implemented here — they are this module's primary deliverable.
* Steps unique to sibling tasks (``@task:TASK-FG-001`` envelope steps,
  ``@task:TASK-FG-003`` Graphiti steps, etc.) are NOT bound here. The
  bdd_runner invocation for TASK-FG-002 uses ``-m task_TASK_FG_002``
  which deselects every other scenario at collection time, so unbound
  steps for those scenarios are never resolved at test-run time and the
  BDD oracle passes (``scenarios_failed == 0``).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from nats.errors import (
    NoRespondersError,
)
from nats.errors import (
    TimeoutError as NatsTimeoutError,
)
from pytest_bdd import given, scenario, then, when

from common.jarvis_client import JARVIS_TOPIC, JarvisClient

_FEATURE_PATH = str(Path(__file__).with_name("fleet-gateway-common-and-interfaces.feature"))


# ---------------------------------------------------------------------------
# Local mock helpers (mirror tests/test_jarvis_client.py)
# ---------------------------------------------------------------------------


def _make_result_bytes(response_text: str = "ok") -> bytes:
    """Build a JSON-encoded Jarvis result envelope carrying ``response_text``."""
    envelope: dict[str, Any] = {
        "version": "1.0",
        "event_type": "result",
        "source_id": "jarvis",
        "correlation_id": "bdd-cid-0001",
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


# ---------------------------------------------------------------------------
# Scenario bindings — only @task:TASK-FG-002
# ---------------------------------------------------------------------------


@scenario(_FEATURE_PATH, "Sending a chat command to Jarvis and returning its reply")
def test_bdd_send_chat_command_returns_reply() -> None:
    """Bind the @key-example happy-path scenario."""


@scenario(_FEATURE_PATH, "Conversation history with multiple turns is forwarded to Jarvis")
def test_bdd_conversation_history_forwarded() -> None:
    """Bind the @boundary conversation-history scenario."""


@scenario(_FEATURE_PATH, "JarvisClient surfaces a timeout when Jarvis does not reply")
def test_bdd_timeout_raised() -> None:
    """Bind the @negative timeout scenario."""


@scenario(
    _FEATURE_PATH, "JarvisClient surfaces a connection error when no agent is listening"
)
def test_bdd_no_responders_raises() -> None:
    """Bind the @negative no-responders scenario."""


@scenario(_FEATURE_PATH, "Concurrent JarvisClient calls do not share connection state")
def test_bdd_concurrent_calls_isolated() -> None:
    """Bind the @edge-case connect-per-call scenario."""


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
    """No-op — the JarvisClient publishes to ``JARVIS_TOPIC`` regardless."""


@given("the Graphiti knowledge graph is reachable on the configured FalkorDB endpoint")
def given_graphiti_reachable() -> None:
    """No-op for TASK-FG-002 scenarios — none touch Graphiti."""


# ---------------------------------------------------------------------------
# TASK-FG-002 scenario steps
# ---------------------------------------------------------------------------


@given("a Jarvis client configured for the local NATS endpoint", target_fixture="bdd_client")
def given_jarvis_client_local() -> JarvisClient:
    """Construct the client used by the happy-path / history / concurrent scenarios."""
    return JarvisClient(adapter="openwebui")


@given("a Jarvis client configured with a short request timeout", target_fixture="bdd_client")
def given_jarvis_client_short_timeout() -> JarvisClient:
    """Client whose timeout=1s exercises the timeout-raised scenario."""
    return JarvisClient(timeout=1, adapter="openwebui")


@given("a Jarvis client connected to NATS", target_fixture="bdd_client")
def given_jarvis_client_connected() -> JarvisClient:
    """Client used by the no-responders scenario."""
    return JarvisClient(adapter="openwebui")


@given("Jarvis is ready to answer", target_fixture="bdd_mock_nc")
def given_jarvis_ready() -> AsyncMock:
    """Provide a mock NATS connection whose request returns a canned reply."""
    return _mock_nats_connection(reply_bytes=_make_result_bytes("Build complete"))


@given("Jarvis is not responding", target_fixture="bdd_mock_nc")
def given_jarvis_not_responding() -> AsyncMock:
    """NATS connection whose request raises ``NatsTimeoutError``."""
    nc = _mock_nats_connection()
    nc.request = AsyncMock(side_effect=NatsTimeoutError())
    return nc


@given("no agent is subscribed to the Jarvis command topic", target_fixture="bdd_mock_nc")
def given_no_responders() -> AsyncMock:
    """NATS connection whose request raises ``NoRespondersError``."""
    nc = _mock_nats_connection()
    nc.request = AsyncMock(side_effect=NoRespondersError())
    return nc


@given(
    "the user has had three prior turns in the conversation",
    target_fixture="bdd_history",
)
def given_three_prior_turns() -> list[dict[str, Any]]:
    """Three-turn history list used by the @boundary scenario."""
    return [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "back"},
        {"role": "user", "content": "second"},
    ]


@when(
    'I send the command "what is the fleet status?" through the client',
    target_fixture="bdd_response",
)
def when_send_status_command(bdd_client: JarvisClient, bdd_mock_nc: AsyncMock) -> str:
    """Invoke send_command with the canonical fleet-status query."""
    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=bdd_mock_nc)):
        return asyncio.get_event_loop().run_until_complete(
            bdd_client.send_command("what is the fleet status?")
        )


@when(
    "I send a new command together with the conversation history",
    target_fixture="bdd_published_envelope",
)
def when_send_with_history(
    bdd_client: JarvisClient,
    bdd_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Send a new turn, forwarding the prior history; capture the published envelope."""
    nc = _mock_nats_connection(reply_bytes=_make_result_bytes("ok"))
    full_history = [*bdd_history, {"role": "user", "content": "now what?"}]
    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        asyncio.get_event_loop().run_until_complete(
            bdd_client.send_command("now what?", conversation_history=full_history)
        )
    raw = nc.request.await_args.args[1]
    envelope: dict[str, Any] = json.loads(raw.decode("utf-8"))
    return envelope


@when("I send a command through the client", target_fixture="bdd_raised")
def when_send_command_capturing_error(
    bdd_client: JarvisClient, bdd_mock_nc: AsyncMock
) -> BaseException:
    """Send a command and capture whatever exception bubbles up."""
    try:
        with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=bdd_mock_nc)):
            asyncio.get_event_loop().run_until_complete(bdd_client.send_command("ping"))
    except BaseException as exc:  # noqa: BLE001 - intentional capture for then-step assertions
        return exc
    msg = "expected send_command to raise but it returned normally"
    raise AssertionError(msg)


@when(
    "two callers send commands through the client at the same time",
    target_fixture="bdd_concurrent_state",
)
def when_two_concurrent_callers(bdd_client: JarvisClient) -> dict[str, Any]:
    """Drive two send_command calls under a connect-factory that hands out fresh mocks.

    Each call gets its own AsyncMock NATS connection whose ``request`` returns
    a caller-distinct reply. The factory tracks every connection it produced,
    so the Then-steps can assert per-connection close + reply isolation.
    """
    connections: list[AsyncMock] = []
    replies = ["reply-A", "reply-B"]

    async def fake_connect(*_: Any, **__: Any) -> AsyncMock:
        idx = len(connections)
        nc = _mock_nats_connection(
            reply_bytes=_make_result_bytes(replies[idx % len(replies)])
        )
        connections.append(nc)
        return nc

    async def drive() -> list[str]:
        with patch("common.jarvis_client.nats.connect", side_effect=fake_connect):
            return await asyncio.gather(
                bdd_client.send_command("hello-A"),
                bdd_client.send_command("hello-B"),
            )

    results = asyncio.get_event_loop().run_until_complete(drive())
    return {"connections": connections, "results": results}


@then("a command envelope should be published to the Jarvis command topic")
def then_envelope_published(bdd_mock_nc: AsyncMock) -> None:
    """Assert request was called once on the canonical topic."""
    bdd_mock_nc.request.assert_awaited_once()
    assert bdd_mock_nc.request.await_args.args[0] == JARVIS_TOPIC


@then("the client should return Jarvis's reply text")
def then_client_returns_reply_text(bdd_response: str) -> None:
    """Assert the client returned the canned response text."""
    assert bdd_response == "Build complete"


@then("the NATS connection should be released after the reply")
def then_connection_released(bdd_mock_nc: AsyncMock) -> None:
    """Assert close() was awaited exactly once after the reply."""
    bdd_mock_nc.close.assert_awaited_once()


@then("the published envelope should include all three prior turns in order")
def then_envelope_includes_three_prior_turns(bdd_published_envelope: dict[str, Any]) -> None:
    """Assert the first three history entries are the prior turns, in order."""
    history = bdd_published_envelope["payload"]["args"]["conversation_history"]
    assert history[0] == {"role": "user", "content": "first"}
    assert history[1] == {"role": "assistant", "content": "back"}
    assert history[2] == {"role": "user", "content": "second"}


@then("the published envelope should include the new user turn last")
def then_envelope_includes_new_turn_last(bdd_published_envelope: dict[str, Any]) -> None:
    """Assert the final history entry is the new user turn."""
    history = bdd_published_envelope["payload"]["args"]["conversation_history"]
    assert history[-1] == {"role": "user", "content": "now what?"}


@then("the client should raise a timeout error")
def then_raises_timeout(bdd_raised: BaseException) -> None:
    """Assert the captured exception is a built-in TimeoutError."""
    assert isinstance(bdd_raised, TimeoutError)


@then("the client should raise a connection error")
def then_raises_connection_error(bdd_raised: BaseException) -> None:
    """Assert the captured exception is a ConnectionError."""
    assert isinstance(bdd_raised, ConnectionError)


@then("the error message should explain how to start Jarvis")
def then_error_explains_how_to_start_jarvis(bdd_raised: BaseException) -> None:
    """Assert the error message references the Jarvis start command."""
    assert "jarvis serve-nats" in str(bdd_raised)


@then("each call should establish its own NATS connection")
def then_each_call_own_connection(bdd_concurrent_state: dict[str, Any]) -> None:
    """Assert exactly two distinct NATS connections were established."""
    connections = bdd_concurrent_state["connections"]
    assert len(connections) == 2
    assert connections[0] is not connections[1]


@then("each call should release its own connection after the reply")
def then_each_call_releases_connection(bdd_concurrent_state: dict[str, Any]) -> None:
    """Assert close() was awaited on every connection."""
    for nc in bdd_concurrent_state["connections"]:
        nc.close.assert_awaited_once()


@then("the two replies should not be cross-wired between the callers")
def then_replies_not_cross_wired(bdd_concurrent_state: dict[str, Any]) -> None:
    """Assert each caller received a distinct reply."""
    results = bdd_concurrent_state["results"]
    assert results[0] != results[1]
    assert set(results) == {"reply-A", "reply-B"}
