"""Unit + seam tests for ``common.jarvis_client``.

Mocks ``nats.connect`` so no real NATS server is required. Covers the
acceptance criteria from TASK-FG-002:

    * happy path
    * timeout (translated from ``nats.errors.TimeoutError``)
    * no-responders (translated from ``nats.errors.NoRespondersError``)
    * server-unreachable (translated from ``nats.errors.NoServersError``
      / ``OSError``)
    * conversation-history forwarding into the envelope
    * correlation_id propagation between envelope and inner payload
    * connection always closed (try/finally) — verified on the timeout
      path
    * seam test against TASK-FG-001's ``build_command_envelope`` contract
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats.errors import (
    NoRespondersError,
    NoServersError,
)
from nats.errors import (
    TimeoutError as NatsTimeoutError,
)

from common.jarvis_client import JARVIS_TOPIC, JarvisClient
from tests.conftest import make_result_bytes

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _mock_nats_connection(reply_bytes: bytes | None = None) -> AsyncMock:
    """Build an ``AsyncMock`` that mimics a connected NATS client.

    ``nc.request`` returns a ``MagicMock`` whose ``.data`` is ``reply_bytes``.
    ``nc.close`` is an awaitable no-op. Tests can override ``request`` to
    raise instead of return.
    """
    nc = AsyncMock()
    if reply_bytes is not None:
        response = MagicMock()
        response.data = reply_bytes
        nc.request.return_value = response
    nc.close = AsyncMock()
    return nc


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_jarvis_client_constructor_defaults() -> None:
    """All three config fields default sensibly and are kwargs-only after url."""
    client = JarvisClient()
    assert client.nats_url == "nats://localhost:4222"
    assert client.timeout == 120
    assert client.adapter == "unknown"


def test_jarvis_client_constructor_kwargs_only() -> None:
    """`timeout` and `adapter` are keyword-only — positional must fail."""
    with pytest.raises(TypeError):
        JarvisClient("nats://x:4222", 60, "openwebui")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# send_command — happy path
# ---------------------------------------------------------------------------


async def test_send_command_happy_path_returns_response_text() -> None:
    """Successful round-trip parses the reply and returns the text."""
    reply = make_result_bytes(result={"response": "hello from jarvis"})
    nc = _mock_nats_connection(reply_bytes=reply)

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(adapter="openwebui")
        result = await client.send_command("hi")

    assert result == "hello from jarvis"
    nc.request.assert_awaited_once()
    nc.close.assert_awaited_once()

    # Topic + timeout are correct on the request
    call = nc.request.await_args
    assert call.args[0] == JARVIS_TOPIC
    assert call.kwargs["timeout"] == 120


async def test_send_command_publishes_envelope_with_message_and_adapter() -> None:
    """The published bytes carry the message and the {adapter}-gateway source."""
    reply = make_result_bytes(result={"response": "ok"})
    nc = _mock_nats_connection(reply_bytes=reply)

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(adapter="reachy-bridge")
        await client.send_command("status?")

    raw = nc.request.await_args.args[1]
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["version"] == "1.0"
    assert envelope["event_type"] == "command"
    assert envelope["source_id"] == "reachy-bridge-gateway"
    assert envelope["payload"]["args"]["message"] == "status?"
    assert envelope["payload"]["args"]["adapter"] == "reachy-bridge"


# ---------------------------------------------------------------------------
# send_command — error translation
# ---------------------------------------------------------------------------


async def test_send_command_timeout_raises_builtin_timeout_error() -> None:
    """``nats.errors.TimeoutError`` becomes a built-in ``TimeoutError``.

    The message names the topic and the configured timeout so operators
    can tell where the deadline expired.
    """
    nc = _mock_nats_connection()
    nc.request = AsyncMock(side_effect=NatsTimeoutError())

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(timeout=7, adapter="openwebui")
        with pytest.raises(TimeoutError) as excinfo:
            await client.send_command("hi")

    msg = str(excinfo.value)
    assert "agents.command.jarvis" in msg
    assert "7s" in msg


async def test_send_command_timeout_still_closes_connection() -> None:
    """Try/finally guarantees ``nc.close`` runs even when ``request`` raises."""
    nc = _mock_nats_connection()
    nc.request = AsyncMock(side_effect=NatsTimeoutError())

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(timeout=2, adapter="openwebui")
        with pytest.raises(TimeoutError):
            await client.send_command("hi")

    nc.close.assert_awaited_once()


async def test_send_command_no_responders_raises_connection_error() -> None:
    """``NoRespondersError`` → ``ConnectionError`` with start instructions."""
    nc = _mock_nats_connection()
    nc.request = AsyncMock(side_effect=NoRespondersError())

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(adapter="openwebui")
        with pytest.raises(ConnectionError) as excinfo:
            await client.send_command("hi")

    msg = str(excinfo.value)
    assert "No responders" in msg
    assert "jarvis serve-nats" in msg
    nc.close.assert_awaited_once()


async def test_send_command_server_unreachable_raises_connection_error() -> None:
    """`NoServersError` from ``nats.connect`` → ``ConnectionError``.

    Distinct from no-responders: the message names the URL rather than
    the topic, so misconfiguration is obvious.
    """
    with patch(
        "common.jarvis_client.nats.connect",
        AsyncMock(side_effect=NoServersError()),
    ):
        client = JarvisClient(nats_url="nats://does-not-exist:4222", adapter="openwebui")
        with pytest.raises(ConnectionError) as excinfo:
            await client.send_command("hi")

    msg = str(excinfo.value)
    assert "Could not reach NATS server" in msg
    assert "nats://does-not-exist:4222" in msg
    # Crucially, this is NOT the no-responders message.
    assert "No responders" not in msg


async def test_send_command_server_unreachable_translates_oserror() -> None:
    """OS-level connect failures (e.g. refused socket) also surface as ConnectionError."""
    with patch(
        "common.jarvis_client.nats.connect",
        AsyncMock(side_effect=ConnectionRefusedError("Connection refused")),
    ):
        client = JarvisClient(nats_url="nats://127.0.0.1:65535", adapter="openwebui")
        with pytest.raises(ConnectionError) as excinfo:
            await client.send_command("hi")

    assert "Could not reach NATS server" in str(excinfo.value)


# ---------------------------------------------------------------------------
# send_command — payload semantics
# ---------------------------------------------------------------------------


async def test_send_command_forwards_conversation_history() -> None:
    """Caller-supplied conversation_history is published verbatim."""
    history: list[dict[str, Any]] = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "back"},
        {"role": "user", "content": "second"},
    ]
    reply = make_result_bytes(result={"response": "ok"})
    nc = _mock_nats_connection(reply_bytes=reply)

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(adapter="openwebui")
        await client.send_command("second", conversation_history=history)

    raw = nc.request.await_args.args[1]
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["payload"]["args"]["conversation_history"] == history


async def test_send_command_propagates_correlation_id_to_payload() -> None:
    """The same correlation_id appears on the envelope and the inner payload."""
    reply = make_result_bytes(result={"response": "ok"})
    nc = _mock_nats_connection(reply_bytes=reply)

    with patch("common.jarvis_client.nats.connect", AsyncMock(return_value=nc)):
        client = JarvisClient(adapter="openwebui")
        await client.send_command("hi")

    raw = nc.request.await_args.args[1]
    envelope = json.loads(raw.decode("utf-8"))
    assert envelope["correlation_id"] == envelope["payload"]["correlation_id"]
    # And it's a non-empty string (a UUID generated by build_command_envelope).
    assert isinstance(envelope["correlation_id"], str)
    assert envelope["correlation_id"]


# ---------------------------------------------------------------------------
# Seam test — TASK-FG-001 envelope contract
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("CommandPayload")
def test_command_payload_envelope_format() -> None:
    """Verify the envelope JarvisClient publishes matches §4.1 wire format.

    Contract: dict with version="1.0", event_type="command",
    source_id="{adapter}-gateway", correlation_id (UUID), payload (with
    message text). Producer: TASK-FG-001 (build_command_envelope).
    """
    from common.envelope import build_command_envelope

    envelope = build_command_envelope(
        message="hello",
        adapter="openwebui",
    )

    assert envelope["version"] == "1.0", "envelope must declare version 1.0"
    assert envelope["event_type"] == "command", "event_type must be 'command'"
    assert envelope["source_id"] == "openwebui-gateway", (
        "source_id must follow {adapter}-gateway convention"
    )
    assert "correlation_id" in envelope, "correlation_id must be present"
    assert isinstance(envelope["payload"], dict), "payload must be a dict"
    # Round-trip: must be JSON-serialisable for NATS publish
    raw = json.dumps(envelope).encode()
    assert json.loads(raw)["payload"], "envelope must round-trip via JSON"


# ---------------------------------------------------------------------------
# Negative: query_status must NOT exist (scope §7 Q3)
# ---------------------------------------------------------------------------


def test_jarvis_client_has_no_query_status_method() -> None:
    """`query_status` was dropped — it must not be present on the client."""
    assert not hasattr(JarvisClient, "query_status")
