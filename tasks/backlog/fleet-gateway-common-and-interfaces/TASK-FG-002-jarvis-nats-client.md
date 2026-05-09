---
id: TASK-FG-002
title: Jarvis NATS client
task_type: feature
parent_review: TASK-REV-CB98
feature_id: FEAT-FG-001
wave: 2
implementation_mode: task-work
complexity: 5
estimated_minutes: 75
dependencies: [TASK-FG-001]
domain_tags: [nats, async, client]
status: pending
consumer_context:
  - task: TASK-FG-001
    consumes: CommandPayload envelope
    framework: "common.envelope (Pydantic v2)"
    driver: "in-process Python import"
    format_note: "Must call build_command_envelope() and parse_result_payload() — never construct envelope dicts inline. Wire format is JSON-encoded bytes published to agents.command.jarvis."
  - task: OPERATOR_CONFIG
    consumes: NATS_URL
    framework: "nats-py >=2.9 (async)"
    driver: "asyncio"
    format_note: "URL must be nats:// scheme (e.g. nats://localhost:4222 in dev, nats://promaxgb10-41b1:4222 on the GB10). No TLS in Phase 1."
---

# TASK-FG-002: Jarvis NATS Client

## Goal

Implement `common/jarvis_client.py` — a connect-per-call NATS client that
sends commands to Jarvis on `agents.command.jarvis` and parses the
response. Used by both OpenWebUI (TASK-FG-004) and Reachy Bridge
(TASK-FG-006).

## Files to create

- `common/jarvis_client.py`
- `tests/test_jarvis_client.py`

## Files NOT to touch

- `openwebui/`, `reachy/`, `common/envelope.py`

## Inputs

- Existing reference implementation: `openwebui/nats_fleet_pipe.py` (lines 98–117 — request-reply pattern)
- Scope §4.2 — JarvisClient API
- Scope §7 Q3 — `query_status()` is **dropped** (no `jarvis.status.query` topic exists)
- Scope §6 A5 — connect-per-call pattern (no shared long-lived connection across Pollen turns)

## Acceptance criteria

- [ ] `JarvisClient(nats_url="nats://localhost:4222", timeout=120, adapter="unknown")` constructor accepts config (kwargs only, no positional after `nats_url`)
- [ ] `send_command(message, conversation_history=None)` is `async`, builds envelope via `common.envelope.build_command_envelope`, opens a NATS connection, publishes a request to `agents.command.jarvis`, awaits the reply, parses via `common.envelope.parse_result_payload`, closes the connection, and returns the response text
- [ ] `query_status` method is **NOT** present (per scope §7 Q3 — Bridge calls `send_command("what's the fleet status?")` instead)
- [ ] `TimeoutError` is raised with a helpful message when the configured `timeout` elapses without a reply (message names the topic and the timeout value)
- [ ] `ConnectionError` is raised with a "no responders" message that suggests starting Jarvis (`uv run jarvis serve-nats` or equivalent) when NATS reports no listeners on `agents.command.jarvis`
- [ ] `ConnectionError` is raised when the NATS server itself is unreachable (e.g. wrong URL), distinct from the no-responders case (different message)
- [ ] Connection is always closed (try/finally) — verified by a test that asserts `nc.close()` was called even when the request times out
- [ ] All public methods have Google-style docstrings
- [ ] Module starts with `from __future__ import annotations`
- [ ] `pytest tests/test_jarvis_client.py -v` passes with ≥6 tests: happy path, timeout, no-responders, server-unreachable, conversation-history forwarding, correlation_id propagation
- [ ] Tests use `unittest.mock` (or `pytest-mock`) on `nats.connect` — no real NATS server required
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation notes

- Use the `nats-py` library: `import nats`, `nc = await nats.connect(self.nats_url)`, `msg = await nc.request(topic, data, timeout=self.timeout)`.
- The connect-per-call pattern (per scope §6 A5) avoids loop-ownership issues when this client is used inside Pollen's conversation loop.
- Translate `nats.errors.TimeoutError` → Python's built-in `TimeoutError` with a fleet-gateway-specific message.
- Translate `nats.errors.NoRespondersError` → `ConnectionError` with start instructions.
- Pass `adapter` through to `build_command_envelope` so the envelope's `source_id` carries the gateway identity (e.g. `openwebui-gateway`, `reachy-bridge-gateway`).

## Seam Tests

The following seam test validates the integration contract with the
producer task (TASK-FG-001). Implement this test to verify the boundary
before integration.

```python
"""Seam test: verify CommandPayload envelope contract from TASK-FG-001."""
from __future__ import annotations

import json

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("CommandPayload")
def test_command_payload_envelope_format():
    """Verify the envelope JarvisClient publishes matches §4.1 wire format.

    Contract: dict with version="1.0", event_type="command",
    source_id="{adapter}-gateway", correlation_id (UUID), payload (with message text)
    Producer: TASK-FG-001 (build_command_envelope)
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
```

## Coach validation

Coach should verify:
- `pytest tests/test_jarvis_client.py -v` exits 0 with ≥6 tests
- `pytest tests/test_jarvis_client.py -m seam` passes the seam test
- ruff and mypy pass on `common/jarvis_client.py`
- No reference to `query_status` or `jarvis.status.query` exists in the new code
