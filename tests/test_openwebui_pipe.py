"""Tests for ``openwebui.nats_fleet_pipe``.

The Open WebUI Pipe Function is a thin transport adapter: extract the
user's latest message, hand it to ``common.jarvis_client.JarvisClient``,
return the response text. These tests pin:

    * ``Pipe.pipes()`` shape (single "Jarvis" model in the dropdown)
    * ``Pipe.Valves`` defaults preserved across the refactor
    * ``Pipe.pipe()`` happy path — JarvisClient.send_command is awaited
      with the user's message and the conversation history
    * ``Pipe.pipe()`` timeout error message — preserves pre-refactor text
      so existing Open WebUI users see consistent behaviour
    * ``Pipe.pipe()`` no-responders error message — same preservation
    * Seam test against TASK-FG-002's JarvisClient.send_command contract
    * Empty-messages guard returns a helpful string

All tests mock ``JarvisClient`` — zero network calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from openwebui.nats_fleet_pipe import Pipe  # noqa: I001

# ---------------------------------------------------------------------------
# pipes() and Valves shape
# ---------------------------------------------------------------------------


def test_pipes_returns_single_jarvis_model() -> None:
    """Open WebUI dropdown shows exactly one model — Jarvis."""
    pipe = Pipe()
    assert pipe.pipes() == [{"id": "jarvis", "name": "Jarvis"}]


def test_valves_defaults_preserved() -> None:
    """Refactor must not change Valve defaults — operators rely on them."""
    pipe = Pipe()
    assert pipe.valves.NATS_URL == "nats://localhost:4222"
    assert pipe.valves.REQUEST_TIMEOUT == 120


def test_valves_fields_exposed() -> None:
    """Both Valve fields exist on the model after refactor."""
    fields = Pipe.Valves.model_fields
    assert "NATS_URL" in fields
    assert "REQUEST_TIMEOUT" in fields


# ---------------------------------------------------------------------------
# pipe() — happy path
# ---------------------------------------------------------------------------


async def test_pipe_happy_path_returns_jarvis_response() -> None:
    """Successful round-trip returns the JarvisClient response text."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.send_command = AsyncMock(return_value="hello from jarvis")

        pipe = Pipe()
        body = {"messages": [{"role": "user", "content": "hi"}]}
        result = await pipe.pipe(body)

    assert result == "hello from jarvis"
    mock_client.send_command.assert_awaited_once()


async def test_pipe_forwards_user_message_and_history_to_client() -> None:
    """The user's latest message + full history reach JarvisClient.send_command."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.send_command = AsyncMock(return_value="ok")

        pipe = Pipe()
        body = {
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "back"},
                {"role": "user", "content": "second"},
            ]
        }
        await pipe.pipe(body)

    args, kwargs = mock_client.send_command.call_args
    sent_message = args[0] if args else kwargs.get("message")
    assert sent_message == "second", "latest user message must be the send_command arg"
    history = kwargs.get("conversation_history") or (args[1] if len(args) > 1 else None)
    assert history == body["messages"], "full history must be forwarded verbatim"


async def test_pipe_constructs_client_with_valve_config() -> None:
    """JarvisClient is built from the configured Valves and adapter='openwebui'."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_cls.return_value.send_command = AsyncMock(return_value="ok")

        pipe = Pipe()
        pipe.valves.NATS_URL = "nats://example:4222"
        pipe.valves.REQUEST_TIMEOUT = 17
        await pipe.pipe({"messages": [{"role": "user", "content": "hi"}]})

    # The client is constructed with valve config + the openwebui adapter id.
    _, kwargs = mock_cls.call_args
    args = mock_cls.call_args.args
    nats_url = kwargs.get("nats_url") or (args[0] if args else None)
    assert nats_url == "nats://example:4222"
    assert kwargs.get("timeout") == 17
    assert kwargs.get("adapter") == "openwebui"


# ---------------------------------------------------------------------------
# pipe() — guards and errors
# ---------------------------------------------------------------------------


async def test_pipe_empty_messages_returns_helpful_string() -> None:
    """Empty body → helpful guidance, no NATS call."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        pipe = Pipe()
        result = await pipe.pipe({"messages": []})

    assert "No message" in result
    mock_cls.assert_not_called()


async def test_pipe_timeout_returns_preserved_error_message() -> None:
    """Timeout text matches pre-refactor exactly so Open WebUI users see no change."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.send_command = AsyncMock(side_effect=TimeoutError("deadline"))

        pipe = Pipe()
        body = {"messages": [{"role": "user", "content": "hi"}]}
        result = await pipe.pipe(body)

    assert "Jarvis did not respond within 120s" in result
    assert "Is it running?" in result
    assert "jarvis serve-nats --nats nats://localhost:4222" in result


async def test_pipe_no_responders_returns_preserved_error_message() -> None:
    """No-responders text matches pre-refactor exactly."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.send_command = AsyncMock(
            side_effect=ConnectionError(
                "No responders on 'agents.command.jarvis'. "
                "Start Jarvis with 'uv run jarvis serve-nats --nats nats://localhost:4222'."
            )
        )

        pipe = Pipe()
        body = {"messages": [{"role": "user", "content": "hi"}]}
        result = await pipe.pipe(body)

    assert "No agent is listening on 'agents.command.jarvis'" in result
    assert "jarvis serve-nats --nats nats://localhost:4222" in result


async def test_pipe_unexpected_exception_returns_safe_string() -> None:
    """Unexpected exceptions are caught and surfaced as 'NATS error: ...'."""
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.send_command = AsyncMock(side_effect=ValueError("garbled reply"))

        pipe = Pipe()
        body = {"messages": [{"role": "user", "content": "hi"}]}
        result = await pipe.pipe(body)

    assert "garbled reply" in result


# ---------------------------------------------------------------------------
# Source-of-truth divergence: tests must use the common-importing variant
# ---------------------------------------------------------------------------


def test_source_file_imports_jarvis_client_from_common() -> None:
    """AC: ``nats_fleet_pipe.py`` (test-time) imports JarvisClient from common.

    Verifiable via grep — pinned here so the refactor cannot regress.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "openwebui" / "nats_fleet_pipe.py"
    text = src.read_text(encoding="utf-8")
    assert "from common.jarvis_client import JarvisClient" in text


def test_source_file_no_inline_envelope_construction() -> None:
    """AC: inline envelope construction (lines 68–88) is removed."""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "openwebui" / "nats_fleet_pipe.py"
    text = src.read_text(encoding="utf-8")
    # The pre-refactor file built the envelope dict by hand.
    assert '"event_type": "command"' not in text, (
        "envelope construction should live in common.envelope, not the pipe"
    )
    assert "command_payload = {" not in text


def test_deploy_file_is_self_contained() -> None:
    """AC: deployable file imports nothing from ``common`` at runtime."""
    from pathlib import Path

    deploy = (
        Path(__file__).resolve().parent.parent / "openwebui" / "nats_fleet_pipe.deploy.py"
    )
    if not deploy.exists():
        pytest.skip(
            "Deploy file not present — run `python openwebui/build_pipe.py` to generate it."
        )
    text = deploy.read_text(encoding="utf-8")
    # No runtime ``from common`` imports — the deploy file is paste-ready.
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert not stripped.startswith("from common"), (
            f"Deployable file must not import from common: {stripped!r}"
        )
        assert not stripped.startswith("import common"), (
            f"Deployable file must not import common: {stripped!r}"
        )


# ---------------------------------------------------------------------------
# Seam test — TASK-FG-002 JarvisClient.send_command contract
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("JarvisClient.send_command")
async def test_pipe_calls_send_command_with_message() -> None:
    """Verify Pipe.pipe forwards the latest message into JarvisClient.send_command.

    Contract: send_command(message: str, conversation_history: list[dict] | None) -> str
    Producer: TASK-FG-002 (JarvisClient).
    """
    with patch("openwebui.nats_fleet_pipe.JarvisClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.send_command = AsyncMock(return_value="Build complete")

        pipe = Pipe()
        body = {"messages": [{"role": "user", "content": "How's the build going?"}]}
        result = await pipe.pipe(body)

    mock_client.send_command.assert_awaited_once()
    args, kwargs = mock_client.send_command.call_args
    sent = args[0] if args else kwargs.get("message", "")
    assert "How's the build going?" in sent, (
        "Pipe must forward the user's latest message into send_command"
    )
    assert "Build complete" in str(result), "Pipe must return JarvisClient response text"
