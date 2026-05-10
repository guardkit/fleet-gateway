"""Fleet-gateway shared client library.

Public exports:
    build_command_envelope: Build a Jarvis-bound command envelope dict.
    parse_result_payload: Parse a Jarvis result payload from raw NATS bytes.
    CommandPayload: Pydantic model of the command body.
    MessageEnvelope: Pydantic model of the wire envelope.
"""

from __future__ import annotations

from common.envelope import (
    CommandPayload,
    MessageEnvelope,
    build_command_envelope,
    parse_result_payload,
)

__version__ = "0.1.0"

__all__ = [
    "CommandPayload",
    "MessageEnvelope",
    "__version__",
    "build_command_envelope",
    "parse_result_payload",
]
