"""Wire-format envelope helpers shared by all fleet gateways.

This module owns the canonical command/result envelope contract that every
gateway adapter (OpenWebUI pipe, Reachy Bridge/Scholar tools, future REST or
Telegram adapters) speaks to Jarvis over NATS.

The functions are pure data containers: they build dicts ready for JSON
serialisation and parse bytes received off the wire. No I/O, no NATS, no
asyncio — that lives in ``common.jarvis_client``.

References:
    - Scope §4.1 — wire format definition.
    - ``openwebui/nats_fleet_pipe.py`` — original inline implementation
      this module replaces (kept self-contained until TASK-FG-004 refactors
      it to import from here).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

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
