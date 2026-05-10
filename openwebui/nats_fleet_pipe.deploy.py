"""NATS Fleet Gateway Open WebUI Pipe — DEPLOYABLE (auto-generated).

DO NOT EDIT BY HAND. Regenerate after any change to ``common/`` or to
``openwebui/nats_fleet_pipe.py`` with::

    python openwebui/build_pipe.py

Source files (concatenated in order):
    * common/envelope.py
    * common/jarvis_client.py
    * openwebui/nats_fleet_pipe.py

This file is paste-ready for Open WebUI Admin → Workspace → Functions:
the Open WebUI Python interpreter does not ship ``nats-py`` and cannot
``pip install fleet-gateway-common``, so the shared envelope and
JarvisClient code is inlined below between the BEGIN/END markers.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import nats
from nats.errors import (
    NoRespondersError,
    NoServersError,
)
from nats.errors import (
    TimeoutError as NatsTimeoutError,
)
from pydantic import BaseModel, Field

# === BEGIN INLINED FROM common/ ===
# --- inlined from common/envelope.py ---
logger = logging.getLogger(__name__)

__all__ = [
    "CommandPayload",
    "MessageEnvelope",
    "build_command_envelope",
    "parse_result_payload",
]

# Response key conventions Jarvis (or the agent it dispatches to) may use to
# carry the answer text. Order matters — first match wins.
_RESPONSE_KEYS: tuple[str, ...] = ("response", "text", "reply", "output")


class CommandPayload(BaseModel):
    """Wire-format command body sent to Jarvis.

    Attributes:
        command: Logical command name. Defaults to ``"chat"``.
        args: Free-form argument dict — typically contains ``message``,
            ``conversation_history`` and ``adapter`` for chat commands.
        correlation_id: UUID tying request to reply. Auto-generated if absent.
    """

    command: str = Field(default="chat", description="Logical command name.")
    args: dict[str, Any] = Field(
        default_factory=dict, description="Command arguments (e.g. message, history)."
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID correlating request to reply.",
    )


class MessageEnvelope(BaseModel):
    """Standard fleet-gateway envelope wrapping all messages.

    Every NATS message exchanged between gateways and Jarvis is serialised
    from this envelope. The ``payload`` field holds the command/result body
    (typically a serialised :class:`CommandPayload` or a result payload).

    Attributes:
        version: Wire-format version. Pinned to ``"1.0"``.
        event_type: ``"command"`` for outbound, ``"result"`` for inbound.
        source_id: Originating adapter id (e.g. ``"openwebui-gateway"``).
        correlation_id: UUID matching the originating command.
        payload: Command or result body as a dict.
    """

    version: str = Field(default="1.0", description="Wire-format version (pinned).")
    event_type: str = Field(default="command", description="Envelope kind.")
    source_id: str = Field(description="Originating adapter identifier.")
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID matching the originating command.",
    )
    payload: dict[str, Any] = Field(default_factory=dict, description="Command or result body.")


def _source_id_for(adapter: str) -> str:
    """Return the canonical ``source_id`` for an adapter name.

    Convention is ``{adapter}-gateway`` (see TASK-FG-001 implementation
    notes / scope §4.1). For example ``adapter="openwebui"`` →
    ``"openwebui-gateway"``.
    """
    return f"{adapter}-gateway"


def build_command_envelope(
    message: str,
    adapter: str,
    conversation_history: list[dict[str, Any]] | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Build a Jarvis-bound command envelope as a JSON-ready dict.

    The envelope wraps a :class:`CommandPayload` for the canonical ``chat``
    command. ``source_id`` is computed from ``adapter`` using the
    ``{adapter}-gateway`` convention — for ``adapter="openwebui"`` the
    returned envelope has ``source_id="openwebui-gateway"``. Downstream tasks
    (FG-004 OpenWebUI, FG-005 Scholar, FG-006 Bridge) consume this contract.

    Args:
        message: The user's latest message text.
        adapter: Gateway identifier (e.g. ``"openwebui"``,
            ``"reachy-scholar"``, ``"reachy-bridge"``).
        conversation_history: Optional list of ``{role, content}`` dicts.
            Defaults to a single-turn history containing only ``message``.
        correlation_id: Optional UUID string. Auto-generated if omitted.
            The same value is used for both the envelope and inner payload
            so downstream consumers can match request to reply.

    Returns:
        Dict ready for ``json.dumps`` and NATS publish. Top-level keys are
        ``version``, ``event_type``, ``source_id``, ``correlation_id`` and
        ``payload``.
    """
    cid = correlation_id if correlation_id is not None else str(uuid.uuid4())

    history: list[dict[str, Any]]
    if conversation_history is None:
        history = [{"role": "user", "content": message}]
    else:
        history = list(conversation_history)

    payload = CommandPayload(
        command="chat",
        args={
            "message": message,
            "conversation_history": history,
            "adapter": adapter,
        },
        correlation_id=cid,
    )

    envelope = MessageEnvelope(
        version="1.0",
        event_type="command",
        source_id=_source_id_for(adapter),
        correlation_id=cid,
        payload=payload.model_dump(),
    )
    return envelope.model_dump()


def parse_result_payload(response_data: bytes) -> str:
    """Extract the response text from a Jarvis ``ResultPayload``.

    Walks ``payload.result`` first, then falls back to top-level keys, then
    finally pretty-prints the result dict as JSON. Multiple response key
    conventions are supported in this priority order: ``response``, ``text``,
    ``reply``, ``output``.

    Args:
        response_data: Raw bytes received from a NATS request reply.

    Returns:
        The extracted response text.

    Raises:
        ValueError: If the bytes are not valid UTF-8 JSON, or if the payload
            is structurally invalid, or if the payload signals a failure
            (``success=false``) — in which case the upstream error text is
            included in the exception message.
    """
    try:
        decoded = response_data.decode("utf-8")
    except UnicodeDecodeError as exc:
        msg = f"response bytes are not valid UTF-8: {exc}"
        raise ValueError(msg) from exc

    try:
        result_envelope = json.loads(decoded)
    except json.JSONDecodeError as exc:
        msg = f"response is not valid JSON: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(result_envelope, dict):
        msg = f"response JSON must be an object, got {type(result_envelope).__name__}"
        raise ValueError(msg)

    # Envelope may have a top-level "payload" wrapper; tolerate both shapes.
    raw_payload = result_envelope.get("payload", result_envelope)
    if not isinstance(raw_payload, dict):
        msg = f"payload must be an object, got {type(raw_payload).__name__}"
        raise ValueError(msg)

    # Failure signalling — surface the upstream error text verbatim.
    if raw_payload.get("success") is False:
        result_obj = raw_payload.get("result")
        error_text: str
        if isinstance(result_obj, dict):
            err = result_obj.get("error")
            error_text = str(err) if err is not None else "Unknown error"
        else:
            err = raw_payload.get("error", "Unknown error")
            error_text = str(err)
        msg = f"Jarvis returned an error: {error_text}"
        raise ValueError(msg)

    result = raw_payload.get("result", {})
    if not isinstance(result, dict):
        # Unusual but tolerable — coerce to string.
        return str(result)

    # 1. Walk the inner result for known text keys.
    for key in _RESPONSE_KEYS:
        value = result.get(key)
        if isinstance(value, str):
            return value

    # 2. Fall back to the same keys at the payload top level.
    for key in _RESPONSE_KEYS:
        value = raw_payload.get(key)
        if isinstance(value, str):
            return value

    # 3. Final fallback — pretty-print the result dict for the LLM to narrate.
    logger.debug("No known response key found; falling back to JSON dump.")
    return json.dumps(result, indent=2, default=str)

# --- inlined from common/jarvis_client.py ---
__all__ = ["JarvisClient"]

#: NATS topic Jarvis subscribes to for command envelopes.
JARVIS_TOPIC: str = "agents.command.jarvis"


class JarvisClient:
    """NATS request/reply client for the Jarvis intent router.

    Each call to :meth:`send_command` opens a fresh NATS connection,
    publishes the command envelope to ``agents.command.jarvis``, awaits
    the reply, parses it, and closes the connection. The connect-per-call
    pattern is deliberate (scope §6 A5) — it makes the client safe to
    reuse across event loops without long-lived state.

    Attributes:
        nats_url: NATS server URL, e.g. ``"nats://localhost:4222"``.
        timeout: Maximum seconds to wait for Jarvis to reply on a single
            request. Translated to ``TimeoutError`` on expiry.
        adapter: Adapter identifier used to compute the envelope's
            ``source_id`` (see :func:`common.envelope.build_command_envelope`).
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        *,
        timeout: int = 120,
        adapter: str = "unknown",
    ) -> None:
        """Initialise the client with connection and identity config.

        Args:
            nats_url: NATS server URL (positional). Defaults to local dev.
            timeout: Per-request timeout in seconds (keyword-only).
                Defaults to 120s.
            adapter: Adapter name embedded in the envelope ``source_id``
                via the ``{adapter}-gateway`` convention (keyword-only).
                Defaults to ``"unknown"`` so misconfiguration is visible.
        """
        self.nats_url = nats_url
        self.timeout = timeout
        self.adapter = adapter

    async def send_command(
        self,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send a chat command to Jarvis and return the response text.

        Steps:
            1. Build a command envelope via
               :func:`common.envelope.build_command_envelope`. The same
               ``correlation_id`` is used for envelope and inner payload.
            2. Open a NATS connection to :attr:`nats_url`.
            3. ``request`` the JSON-encoded envelope on
               :data:`JARVIS_TOPIC` with a :attr:`timeout`-second deadline.
            4. Parse the reply via
               :func:`common.envelope.parse_result_payload`.
            5. Always close the NATS connection (try/finally), even on
               timeout, no-responders, or parser errors.

        Args:
            message: Latest user message (free text).
            conversation_history: Optional list of ``{role, content}``
                dicts. Forwarded verbatim into the envelope. ``None``
                yields a single-turn history derived from ``message``.

        Returns:
            The Jarvis response text (or pretty-printed JSON if no known
            text key was present — see
            :func:`common.envelope.parse_result_payload`).

        Raises:
            TimeoutError: When the configured :attr:`timeout` elapses
                without a reply. Message names the topic and the timeout.
            ConnectionError: Distinct cases:
                * ``no responders`` — NATS is up but no agent is
                  listening on :data:`JARVIS_TOPIC`. Message suggests
                  ``uv run jarvis serve-nats`` to start Jarvis.
                * ``server unreachable`` — the NATS server itself cannot
                  be contacted (wrong URL, server down, etc.). Message
                  reports the URL so misconfiguration is obvious.
            ValueError: When the reply is structurally invalid or
                signals failure (re-raised from ``parse_result_payload``).
        """
        envelope = build_command_envelope(
            message=message,
            adapter=self.adapter,
            conversation_history=conversation_history,
        )
        request_data = json.dumps(envelope).encode("utf-8")

        # Open the connection. Server-unreachable failures must be
        # distinguishable from no-responders, so we catch the connect
        # exceptions separately and translate them here.
        try:
            nc = await nats.connect(self.nats_url)
        except NoServersError as exc:
            msg = (
                f"Could not reach NATS server at {self.nats_url}: {exc}. "
                "Check that the NATS server is running and NATS_URL is correct."
            )
            raise ConnectionError(msg) from exc
        except OSError as exc:
            # ConnectionRefusedError, socket.gaierror, etc. all derive
            # from OSError — they all mean the URL is unreachable.
            msg = (
                f"Could not reach NATS server at {self.nats_url}: {exc}. "
                "Check that the NATS server is running and NATS_URL is correct."
            )
            raise ConnectionError(msg) from exc

        try:
            try:
                response = await nc.request(
                    JARVIS_TOPIC,
                    request_data,
                    timeout=self.timeout,
                )
            except NatsTimeoutError as exc:
                msg = (
                    f"No reply on {JARVIS_TOPIC!r} within {self.timeout}s. "
                    "Is Jarvis running? Start it with "
                    f"'uv run jarvis serve-nats --nats {self.nats_url}'."
                )
                raise TimeoutError(msg) from exc
            except NoRespondersError as exc:
                msg = (
                    f"No responders on {JARVIS_TOPIC!r}. "
                    "Start Jarvis with "
                    f"'uv run jarvis serve-nats --nats {self.nats_url}'."
                )
                raise ConnectionError(msg) from exc
        finally:
            # Always close — even on timeout / no-responders / parse error.
            await nc.close()

        return parse_result_payload(response.data)

# === END INLINED FROM common/ ===

# --- inlined from openwebui/nats_fleet_pipe.py ---
logger = logging.getLogger(__name__)

#: Adapter identifier embedded in the envelope ``source_id`` as
#: ``openwebui-gateway`` (see :func:`common.envelope.build_command_envelope`).
_ADAPTER: str = "openwebui"

#: NATS topic Jarvis subscribes on. Mirrored here purely for the
#: no-responders error message — the actual publish lives in JarvisClient.
_JARVIS_TOPIC: str = "agents.command.jarvis"


class Pipe:
    """NATS Fleet Gateway — routes all user messages through Jarvis.

    Jarvis is the fleet's intent router. It receives natural language,
    decides which specialist agent can answer, dispatches via NATS, and
    returns the response. The Open WebUI dropdown shows one model — Jarvis
    — and the audience sees a clean chat interface backed by the full
    agent fleet.

    The class is deliberately thin: ``Pipe.pipe`` extracts the user's
    latest message, hands it (plus conversation history) to a
    :class:`common.jarvis_client.JarvisClient`, and surfaces the response
    text. All envelope construction, JSON serialisation, and error
    translation lives in ``common/``.

    Attributes:
        valves: Operator-tunable configuration (see :class:`Valves`).
    """

    class Valves(BaseModel):
        """Operator configuration shown in Open WebUI Admin."""

        NATS_URL: str = Field(
            default="nats://localhost:4222",
            description="NATS server URL (localhost on GB10).",
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="NATS request timeout in seconds.",
        )

    def __init__(self) -> None:
        """Initialise the pipe with default Valve values."""
        self.valves = self.Valves()

    def pipes(self) -> list[dict[str, str]]:
        """Register Jarvis as the single selectable model in Open WebUI.

        Returns:
            A one-element list whose dict carries the model id and label
            that Open WebUI renders in the model dropdown.
        """
        return [{"id": "jarvis", "name": "Jarvis"}]

    async def pipe(self, body: dict[str, Any]) -> str:
        """Send the user's latest message to Jarvis and return the reply.

        Steps:
            1. Extract the user's latest message and conversation history
               from the Open WebUI request body.
            2. Construct a :class:`common.jarvis_client.JarvisClient`
               configured from :class:`Valves`.
            3. Await ``send_command`` and return the response text.
            4. Translate the client's typed exceptions into the
               human-readable strings Open WebUI renders in the chat
               window (preserving pre-refactor wording so existing
               operators see no behavioural change).

        Args:
            body: Open WebUI request body. Expected to contain a
                ``messages`` list of ``{role, content}`` dicts.

        Returns:
            Jarvis's response text, or a safe error string if the request
            failed. Never raises — Open WebUI surfaces the returned
            string directly to the user.
        """
        messages = body.get("messages", [])
        if not messages:
            return "No message provided."

        user_message = messages[-1].get("content", "")
        history = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ]

        client = JarvisClient(
            nats_url=self.valves.NATS_URL,
            timeout=self.valves.REQUEST_TIMEOUT,
            adapter=_ADAPTER,
        )

        try:
            return await client.send_command(
                user_message,
                conversation_history=history,
            )
        except TimeoutError:
            return (
                f"Jarvis did not respond within {self.valves.REQUEST_TIMEOUT}s. "
                f"Is it running? Start with: "
                f"jarvis serve-nats --nats {self.valves.NATS_URL}"
            )
        except ConnectionError as exc:
            # JarvisClient raises ConnectionError for both "no responders"
            # and "server unreachable". Distinguish on the message text so
            # the no-responders wording stays identical to the
            # pre-refactor pipe (per AC).
            if "No responders" in str(exc):
                return (
                    f"No agent is listening on '{_JARVIS_TOPIC}'. "
                    f"Start Jarvis with: "
                    f"jarvis serve-nats --nats {self.valves.NATS_URL}"
                )
            return f"NATS error: {exc}"
        except Exception as exc:  # noqa: BLE001 — surface any failure as text
            logger.exception("Jarvis request failed")
            return f"NATS error: {exc}"
