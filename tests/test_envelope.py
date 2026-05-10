"""Unit tests for ``common.envelope``."""

from __future__ import annotations

import json
import uuid

import pytest

from common import (
    CommandPayload,
    MessageEnvelope,
    build_command_envelope,
    parse_result_payload,
)
from tests.conftest import make_result_bytes

# ---------------------------------------------------------------------------
# build_command_envelope
# ---------------------------------------------------------------------------


def test_build_command_envelope_happy_path() -> None:
    """Default call produces a structurally correct envelope (scope §4.1)."""
    envelope = build_command_envelope("hello", "openwebui")

    assert envelope["version"] == "1.0"
    assert envelope["event_type"] == "command"
    assert envelope["source_id"] == "openwebui-gateway"

    # correlation_id is a parseable UUID
    cid = envelope["correlation_id"]
    assert isinstance(cid, str)
    uuid.UUID(cid)  # raises if not a valid UUID

    payload = envelope["payload"]
    assert payload["command"] == "chat"
    assert payload["correlation_id"] == cid
    args = payload["args"]
    assert args["message"] == "hello"
    assert args["adapter"] == "openwebui"
    # default history is single-turn
    assert args["conversation_history"] == [{"role": "user", "content": "hello"}]


def test_build_command_envelope_with_history() -> None:
    """Caller-supplied conversation_history is preserved verbatim."""
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "back"},
        {"role": "user", "content": "second"},
    ]
    envelope = build_command_envelope("second", "openwebui", conversation_history=history)
    assert envelope["payload"]["args"]["conversation_history"] == history


def test_build_command_envelope_with_custom_correlation_id() -> None:
    """Caller-supplied correlation_id flows to both envelope and payload."""
    cid = "11111111-2222-3333-4444-555555555555"
    envelope = build_command_envelope("ping", "reachy-bridge", correlation_id=cid)
    assert envelope["correlation_id"] == cid
    assert envelope["payload"]["correlation_id"] == cid
    assert envelope["source_id"] == "reachy-bridge-gateway"


def test_build_command_envelope_round_trips_through_models() -> None:
    """The dict produced is accepted by the Pydantic models — no drift."""
    envelope = build_command_envelope("hi", "openwebui")
    msg_model = MessageEnvelope.model_validate(envelope)
    cmd_model = CommandPayload.model_validate(envelope["payload"])
    assert msg_model.source_id == "openwebui-gateway"
    assert cmd_model.command == "chat"


# ---------------------------------------------------------------------------
# parse_result_payload — happy path across the 4 key conventions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("response", "hi"),
        ("text", "All good"),
        ("reply", "ack"),
        ("output", "done"),
    ],
)
def test_parse_result_payload_response_keys(key: str, value: str) -> None:
    """Each of the 4 supported response keys is honoured."""
    data = make_result_bytes(result={key: value})
    assert parse_result_payload(data) == value


def test_parse_result_payload_minimal_shape() -> None:
    """Doc-string example: ``{"payload":{"result":{"response":"hi"}}}``."""
    raw = b'{"payload":{"result":{"response":"hi"}}}'
    assert parse_result_payload(raw) == "hi"


def test_parse_result_payload_priority_order() -> None:
    """When several keys are present, ``response`` wins."""
    data = make_result_bytes(
        result={"response": "first", "text": "second", "reply": "third", "output": "fourth"}
    )
    assert parse_result_payload(data) == "first"


def test_parse_result_payload_falls_back_to_json_dump() -> None:
    """No known text key → pretty-printed JSON of the result dict."""
    data = make_result_bytes(result={"facts": ["a", "b"], "count": 2})
    out = parse_result_payload(data)
    parsed = json.loads(out)
    assert parsed == {"facts": ["a", "b"], "count": 2}


def test_parse_result_payload_tolerates_envelope_without_payload_wrapper() -> None:
    """Some senders flatten the payload — accept both shapes."""
    raw = json.dumps({"success": True, "result": {"response": "flat"}}).encode("utf-8")
    assert parse_result_payload(raw) == "flat"


# ---------------------------------------------------------------------------
# parse_result_payload — error / malformed
# ---------------------------------------------------------------------------


def test_parse_result_payload_raises_on_failure() -> None:
    """``success=false`` surfaces the upstream error text in the ValueError."""
    data = make_result_bytes(success=False, result={"error": "Agent not found"})
    with pytest.raises(ValueError, match="Agent not found"):
        parse_result_payload(data)


def test_parse_result_payload_raises_on_failure_with_top_level_error() -> None:
    """Failure with error at the payload top level is also surfaced."""
    raw = json.dumps({"payload": {"success": False, "error": "Timeout talking to agent"}}).encode(
        "utf-8"
    )
    with pytest.raises(ValueError, match="Timeout talking to agent"):
        parse_result_payload(raw)


def test_parse_result_payload_raises_on_malformed_json() -> None:
    """Non-JSON bytes raise ValueError, not JSONDecodeError leakage."""
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_result_payload(b"this is not json {{{")


def test_parse_result_payload_raises_on_invalid_utf8() -> None:
    """Invalid UTF-8 raises a clear ValueError."""
    with pytest.raises(ValueError, match="not valid UTF-8"):
        parse_result_payload(b"\xff\xfe\xfd")


def test_parse_result_payload_raises_on_non_object_json() -> None:
    """Top-level JSON arrays/scalars are rejected."""
    with pytest.raises(ValueError, match="must be an object"):
        parse_result_payload(b"[1, 2, 3]")
