---
id: TASK-FG-003
title: Graphiti client (graphiti-core direct to FalkorDB)
task_type: feature
parent_review: TASK-REV-CB98
feature_id: FEAT-FG-001
wave: 2
implementation_mode: task-work
complexity: 5
estimated_minutes: 75
dependencies:
- TASK-FG-001
domain_tags:
- graphiti
- falkordb
- student-model
status: completed
consumer_context:
- task: TASK-FG-001
  consumes: common package import path
  framework: common (in-process Python)
  driver: in-process import
  format_note: Import GraphitiClient via `from common.graphiti_client import GraphitiClient`.
    The package is installed editably (`pip install -e .`) into the test venv and
    the Reachy Pollen venv.
- task: OPERATOR_CONFIG
  consumes: FALKORDB_URI
  framework: graphiti-core (async)
  driver: FalkorDB Python client
  format_note: "URI must be `redis://{host}:{port}` (e.g. redis://whitestocks:6379\
    \ \u2014 Synology NAS via Tailscale). graphiti-core wraps FalkorDB; do NOT speak\
    \ MCP-over-HTTP to :8004 (rejected by scope \xA77 Q1)."
autobuild_state:
  current_turn: 4
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001
  base_branch: main
  started_at: '2026-05-10T07:47:13.461273'
  last_updated: '2026-05-10T08:14:15.844738'
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
    timestamp: '2026-05-10T07:47:13.461273'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: '- Advisory (non-blocking): task-work produced a report with 2 of 3
      expected agent invocations. Missing phases: 3 (Implementation). Consider invoking
      these agents via the Task tool to strengthen stack-specific quality:

      - Phase 3: `the stack-specific Phase-3 specialist` (Implementation)

      - BDD oracle: 1 scenario(s) failed during pytest-bdd execution.

      Per-failure details:

      - pytest_runner_error: pytest_runner_error: exit=4; ERROR: not found: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feat...'
    timestamp: '2026-05-10T07:53:26.091921'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 3
    decision: feedback
    feedback: '- Advisory (non-blocking): task-work produced a report with 2 of 3
      expected agent invocations. Missing phases: 3 (Implementation). Consider invoking
      these agents via the Task tool to strengthen stack-specific quality:

      - Phase 3: `the stack-specific Phase-3 specialist` (Implementation)

      - BDD oracle: 1 scenario(s) failed during pytest-bdd execution.

      Per-failure details:

      - pytest_runner_error: pytest_runner_error: exit=4; ERROR: not found: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feat...'
    timestamp: '2026-05-10T07:59:42.376206'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 4
    decision: approve
    feedback: null
    timestamp: '2026-05-10T08:05:15.374112'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# TASK-FG-003: Graphiti Client

## Goal

Implement `common/graphiti_client.py` — a `graphiti-core`-backed client
that searches the Graphiti knowledge graph stored in FalkorDB. Used by
Scholar's `query_student_model` tool (TASK-FG-005).

**This replaces the original aiohttp + REST `/search` design.** Per scope
§7 Q1 / §6 A1, the deployed Graphiti is the **MCP server** (not REST) and
the cleanest client is `graphiti-core` direct to FalkorDB — matching the
proven pattern in `guardkit/guardkit/knowledge/graphiti_client.py`.

## Files to create

- `common/graphiti_client.py`
- `tests/test_graphiti_client.py`

## Files NOT to touch

- `openwebui/`, `reachy/`, `common/envelope.py`, `common/jarvis_client.py`

## Inputs

- Scope §4.3 — `GraphitiClient` API (revised 9 May for graphiti-core)
- Scope §6 A6 (corrected) — group_id is `student-{name}` (dash form), default `student-lilymay`
- Scope §6 A1 (rejected) — graphiti-mcp speaks MCP-over-HTTP at `:8004`, NOT REST `/search`. Use graphiti-core directly.
- Reference pattern: `guardkit/guardkit/knowledge/graphiti_client.py` (in another repo on this host — review for connection lifecycle, error handling)

## Acceptance criteria

- [ ] `GraphitiClient(falkordb_uri="redis://whitestocks:6379", default_group_ids=None)` constructor accepts config; if `default_group_ids` is None, defaults to `["student-lilymay"]`
- [ ] `async def search(query, group_ids=None, num_results=10) -> list[dict]` queries Graphiti via `graphiti-core` and returns a list of fact dicts
- [ ] `async def search_student_progress(student_name="lilymay", subject="english") -> dict` returns a structured progress dict containing keys: `student_name`, `streak_days` (int), `level_name` (str), `recent_xp` (int), `near_achievements` (list), `topic_confidence` (dict), `data_available` (bool)
- [ ] When Graphiti is unreachable (FalkorDB connection error, timeout, auth failure), `search` and `search_student_progress` **never raise** — they return `[]` and `{"data_available": False, "error": "<reason>"}` respectively
- [ ] Auth failures are **distinguishable** from unreachable failures in the error message (per ASSUM-004) — e.g. `"unreachable: <details>"` vs `"auth-failed: <details>"`
- [ ] The group_id used for `search_student_progress` follows the pattern `student-{student_name}` (per A6 correction; not the rejected `study_tutor__student_model`)
- [ ] All public methods have Google-style docstrings
- [ ] Module starts with `from __future__ import annotations`
- [ ] `pytest tests/test_graphiti_client.py -v` passes with ≥7 tests: search happy path, search empty result, search_student_progress happy path, search_student_progress unreachable, search_student_progress auth-failed, group_id default, group_id override
- [ ] Tests mock `graphiti_core.Graphiti` (or the equivalent connection class) — no real FalkorDB required
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation notes

- `graphiti-core` exposes an async `Graphiti` client. Construct it lazily on first call, close it after each call (mirror the connect-per-call pattern from JarvisClient — same loop-ownership concern in Pollen).
- The `search_student_progress` method should compose `search()` calls and shape the result — e.g. one search for current streak/level, one for near-achievements, one for topic confidence — then assemble the structured dict for the LLM to narrate.
- For graceful degradation, wrap the entire `Graphiti` interaction in `try/except` and return the empty/error sentinel. The Scholar tool MUST never crash the conversation (per Scenario 5.2 #2 in scope).
- Distinguish auth failures from connection failures by inspecting the exception type from `graphiti-core` / FalkorDB (e.g. `ConnectionRefusedError` → unreachable, `AuthenticationError` → auth-failed). Document the mapping in a module-level comment if non-obvious.

## Seam Tests

```python
"""Seam test: verify FALKORDB_URI contract from operator config."""
from __future__ import annotations

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("FALKORDB_URI")
def test_falkordb_uri_format():
    """Verify the FalkorDB URI passed to GraphitiClient matches expected format.

    Contract: redis://{host}:{port}
    Producer: operator config / Reachy launch script
    """
    import os

    uri = os.environ.get("FALKORDB_URI", "redis://whitestocks:6379")

    assert uri.startswith("redis://"), (
        f"FALKORDB_URI must use redis:// scheme, got: {uri}"
    )
    assert ":" in uri.split("://", 1)[1], (
        f"FALKORDB_URI must include explicit port, got: {uri}"
    )
```

## Coach validation

Coach should verify:
- `pytest tests/test_graphiti_client.py -v` exits 0 with ≥7 tests
- `pytest tests/test_graphiti_client.py -m seam` passes the seam test
- ruff and mypy pass on `common/graphiti_client.py`
- No reference to `aiohttp` or REST `/search` exists in the new code
- The default group_id is `student-lilymay` (dash, not double-underscore)
