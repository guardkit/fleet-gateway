"""Unit + seam tests for the Bridge ``agent_status`` tool.

Mocks ``common.jarvis_client.JarvisClient.send_command`` so no real NATS
server is required. Covers the acceptance criteria from TASK-FG-006:

    * happy path — Jarvis text is returned verbatim
    * NATS unreachable (``ConnectionError``) — graceful "Fleet offline:"
      string, never re-raised
    * Jarvis timeout (``TimeoutError``) — graceful "Fleet offline:" string
    * agent parameter forwarding — "all" vs a specific agent name
    * seam test against TASK-FG-002's
      ``JarvisClient.send_command`` contract (per scope §7 Q3 — proves
      Bridge does NOT reach for a ``query_status`` method)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from reachy.external_content.external_tools.agent_status import AgentStatusTool

# ---------------------------------------------------------------------------
# Tool metadata
# ---------------------------------------------------------------------------


def test_agent_status_tool_has_expected_name_and_description() -> None:
    """The Pollen tool registry keys off ``name`` and ``description``."""
    tool = AgentStatusTool()
    assert tool.name == "agent_status"
    assert isinstance(tool.description, str) and tool.description, (
        "description must be a non-empty string"
    )


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------


async def test_run_returns_jarvis_response_text_on_happy_path() -> None:
    """``run`` returns whatever ``send_command`` returns, verbatim."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = "All systems nominal. Build green."

        tool = AgentStatusTool()
        result = await tool.run(agent="all")

    assert result == "All systems nominal. Build green."
    mock_send.assert_awaited_once()


async def test_run_phrases_request_as_fleet_status_query_when_agent_is_all() -> None:
    """``agent='all'`` produces a fleet-wide status question for Jarvis."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = "ok"

        tool = AgentStatusTool()
        await tool.run(agent="all")

    args, kwargs = mock_send.call_args
    message = args[0] if args else kwargs.get("message", "")
    assert "fleet" in message.lower(), (
        "fleet-wide query must mention the fleet to Jarvis"
    )
    assert "status" in message.lower(), (
        "fleet-wide query must mention status"
    )


async def test_run_default_agent_is_all() -> None:
    """Calling ``run()`` with no args defaults ``agent`` to ``'all'``."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = "ok"

        tool = AgentStatusTool()
        await tool.run()

    args, kwargs = mock_send.call_args
    message = args[0] if args else kwargs.get("message", "")
    assert "fleet" in message.lower()


# ---------------------------------------------------------------------------
# run() — agent parameter forwarding
# ---------------------------------------------------------------------------


async def test_run_forwards_specific_agent_name_into_message() -> None:
    """A non-``all`` agent argument is mentioned in the question to Jarvis."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = "Scholar is online."

        tool = AgentStatusTool()
        result = await tool.run(agent="scholar")

    args, kwargs = mock_send.call_args
    message = args[0] if args else kwargs.get("message", "")
    assert "scholar" in message.lower(), (
        "specific-agent query must reference the agent name"
    )
    # And the response is still passed through verbatim
    assert result == "Scholar is online."


async def test_run_uses_reachy_bridge_adapter() -> None:
    """JarvisClient is constructed with adapter='reachy-bridge'.

    The envelope ``source_id`` derives from the adapter name (see scope §4.2),
    and the Bridge identity must be visible to Jarvis.
    """
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = "ok"

        with patch(
            "reachy.external_content.external_tools.agent_status.JarvisClient",
            wraps=__import__(
                "common.jarvis_client", fromlist=["JarvisClient"]
            ).JarvisClient,
        ) as mock_client_cls:
            tool = AgentStatusTool()
            await tool.run(agent="all")

    # JarvisClient was constructed with adapter="reachy-bridge"
    assert mock_client_cls.called, "JarvisClient must be constructed in run()"
    _, ctor_kwargs = mock_client_cls.call_args
    assert ctor_kwargs.get("adapter") == "reachy-bridge"
    mock_send.assert_awaited_once()


# ---------------------------------------------------------------------------
# run() — graceful error paths
# ---------------------------------------------------------------------------


async def test_run_returns_fleet_offline_when_nats_unreachable() -> None:
    """``ConnectionError`` from ``send_command`` becomes a graceful string."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.side_effect = ConnectionError(
            "Could not reach NATS server at nats://localhost:4222"
        )

        tool = AgentStatusTool()
        result = await tool.run(agent="all")

    assert result.startswith("Fleet offline:"), (
        "graceful error string must begin with 'Fleet offline:'"
    )


async def test_run_returns_fleet_offline_when_jarvis_times_out() -> None:
    """``TimeoutError`` from ``send_command`` becomes a graceful string."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.side_effect = TimeoutError(
            "No reply on 'agents.command.jarvis' within 120s"
        )

        tool = AgentStatusTool()
        result = await tool.run(agent="all")

    assert result.startswith("Fleet offline:")


async def test_run_does_not_raise_on_connection_error() -> None:
    """The tool must NEVER raise — Bridge conversations must not crash."""
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.side_effect = ConnectionError("boom")

        tool = AgentStatusTool()
        # No pytest.raises wrapper — must return cleanly.
        result = await tool.run(agent="all")

    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Seam test — TASK-FG-002 JarvisClient.send_command contract
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("JarvisClient.send_command")
async def test_agent_status_calls_send_command_with_status_query() -> None:
    """Verify Bridge agent_status uses send_command, not the dropped query_status.

    Contract: send_command(message: str) -> str on agents.command.jarvis
    Producer: TASK-FG-002 (JarvisClient)
    Reference: scope §7 Q3 — query_status was dropped because the
    jarvis.status.query topic does not exist in nats-core.
    """
    with patch(
        "common.jarvis_client.JarvisClient.send_command",
        new_callable=AsyncMock,
    ) as mock_send:
        mock_send.return_value = "All agents nominal. Build green."

        tool = AgentStatusTool()
        result = await tool.run(agent="all")

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        message = args[0] if args else kwargs.get("message", "")
        assert "status" in message.lower() or "fleet" in message.lower(), (
            "Bridge must phrase the request as a status/fleet query"
        )
        assert "All agents nominal" in result, (
            "Bridge must return Jarvis's narrated text"
        )
