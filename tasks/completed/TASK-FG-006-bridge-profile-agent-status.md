---
id: TASK-FG-006
title: Bridge profile + agent_status tool
task_type: feature
parent_review: TASK-REV-CB98
feature_id: FEAT-FG-001
wave: 3
implementation_mode: task-work
complexity: 4
estimated_minutes: 60
dependencies:
- TASK-FG-002
domain_tags:
- reachy
- bridge
- nats
- tools
- profile
status: completed
consumer_context:
- task: TASK-FG-002
  consumes: JarvisClient.send_command
  framework: common.jarvis_client (in-process Python in Pollen venv)
  driver: in-process import; fleet-gateway is editable-installed in the Pollen venv
  format_note: "Bridge calls `JarvisClient(adapter='reachy-bridge').send_command(\"\
    what's the fleet status?\")` and narrates the returned text. Per scope \xA77 Q3,\
    \ JarvisClient.query_status() does NOT exist \u2014 Bridge must use send_command\
    \ on agents.command.jarvis."
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001
  base_branch: main
  started_at: '2026-05-10T08:14:15.876981'
  last_updated: '2026-05-10T08:31:47.544269'
  turns:
  - turn: 1
    decision: feedback
    feedback: '- Advisory (non-blocking): task-work produced a report with 2 of 3
      expected agent invocations. Missing phases: 3 (Implementation). Consider invoking
      these agents via the Task tool to strengthen stack-specific quality:

      - Phase 3: `the stack-specific Phase-3 specialist` (Implementation)

      - BDD oracle: 1 scenario(s) failed during pytest-bdd execution.

      Per-failure details:

      - pytest_runner_error: pytest_runner_error: exit=4; ERROR: not found: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feat...'
    timestamp: '2026-05-10T08:14:15.876981'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-05-10T08:23:07.402786'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# TASK-FG-006: Bridge Profile + Agent Status Tool

## Goal

Create the Reachy "Bridge" profile (Ship's Computer persona) with a working
`agent_status` tool that queries Jarvis via the existing
`agents.command.jarvis` request-reply path. Per scope §7 Q3, the originally
proposed `jarvis.status.query` topic does not exist — the Bridge instead
calls `JarvisClient.send_command("what's the fleet status?")` and lets
Jarvis narrate.

## Files to create

- `reachy/external_content/external_profiles/bridge/instructions.txt`
- `reachy/external_content/external_profiles/bridge/tools.txt`
- `reachy/external_content/external_profiles/bridge/voice.txt`
- `reachy/external_content/external_tools/agent_status.py`
- `tests/test_agent_status.py`

## Files NOT to touch

- `openwebui/`, `common/`, Scholar files

## Inputs

- Bridge persona reference: `jarvis/docs/research/ideas/reachy-nats-bridge-adapter.md`
- JarvisClient API from TASK-FG-002 (`send_command(message, conversation_history=None) -> str`)
- Pollen `core_tools.Tool` subclass pattern
- Scope §5.3 (Bridge Gherkin scenarios — note these were revised 9 May to remove the invented `jarvis.status.query` topic)

## Acceptance criteria

### agent_status.py (new)

- [ ] Subclasses `core_tools.Tool` with name `agent_status`, description, and parameter schema (`agent: str` defaulting to `"all"` — kept for forward compatibility even though Phase 1 always queries the whole fleet)
- [ ] `async def run(self, agent: str = "all") -> str` constructs a `JarvisClient(adapter="reachy-bridge")` and calls `send_command("what's the fleet status?")` (or `f"what's the status of {agent}?"` when `agent != "all"`)
- [ ] Returns the text returned by `send_command`
- [ ] When NATS is unreachable (`ConnectionError`) or Jarvis times out (`TimeoutError`), the tool returns a graceful error string starting with `"Fleet offline:"` — **never raises**, never crashes the conversation
- [ ] No reference to a `query_status` method or `jarvis.status.query` topic exists in the new code (per scope §7 Q3)
- [ ] `pytest tests/test_agent_status.py -v` passes with ≥4 tests: happy path (mocked JarvisClient), NATS unreachable graceful path, Jarvis timeout graceful path, agent parameter forwarding ("all" vs specific agent)

### Bridge profile

- [ ] `instructions.txt` defines Bridge persona: authoritative, British English, LCARS-style status-report cadence ("All systems nominal."), prefers concise reports over conversation
- [ ] `tools.txt` lists exactly: `agent_status` (custom) plus the built-ins the persona uses: `camera`, `emotion`, `head_tracking`
- [ ] `voice.txt` pins a voice **distinct from Scholar's** (TASK-FG-005) — different speaker characteristics so the personas are audibly differentiated

### General

- [ ] Tool is testable standalone: `python -c "from reachy.external_content.external_tools.agent_status import AgentStatusTool"` succeeds when `fleet-gateway` is installed editably or on PYTHONPATH
- [ ] Tests mock `common.jarvis_client.JarvisClient` — no real NATS required
- [ ] All modified files pass project-configured lint/format checks with zero errors

## DDD Southwest demo criterion

Bridge can answer *"What's the fleet status?"* by querying Jarvis via NATS
and narrating the response in Ship's Computer character — confirmed by an
end-to-end smoke run before the 16 May talk. If NATS is offline, Bridge
gracefully reports "Fleet offline" instead of crashing.

## Seam Tests

```python
"""Seam test: verify Bridge consumes JarvisClient.send_command (not query_status)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("JarvisClient.send_command")
@pytest.mark.asyncio
async def test_agent_status_calls_send_command_with_status_query():
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

        from reachy.external_content.external_tools.agent_status import (
            AgentStatusTool,
        )

        tool = AgentStatusTool()
        result = await tool.run(agent="all")

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        message = args[0] if args else kwargs.get("message", "")
        assert "status" in message.lower() or "fleet" in message.lower(), (
            "Bridge must phrase the request as a status/fleet query"
        )
        assert "All agents nominal" in result, "Bridge must return Jarvis's narrated text"
```

## Coach validation

Coach should verify:
- `pytest tests/test_agent_status.py -v` exits 0 with ≥4 tests
- `pytest -m seam` includes the contract test above
- `instructions.txt`, `tools.txt`, `voice.txt` exist and are non-empty in `reachy/external_content/external_profiles/bridge/`
- `tools.txt` lists `agent_status`
- `agent_status.py` does NOT contain `query_status` or `jarvis.status.query`
- ruff and mypy pass on `reachy/external_content/external_tools/agent_status.py`
