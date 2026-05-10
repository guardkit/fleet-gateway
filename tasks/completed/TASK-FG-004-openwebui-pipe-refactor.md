---
id: TASK-FG-004
title: OpenWebUI Pipe Function refactor (self-contained deploy)
task_type: refactor
parent_review: TASK-REV-CB98
feature_id: FEAT-FG-001
wave: 3
implementation_mode: task-work
complexity: 4
estimated_minutes: 60
dependencies: [TASK-FG-002]
domain_tags: [openwebui, pipe-function, integration]
status: completed
consumer_context:
  - task: TASK-FG-002
    consumes: JarvisClient API
    framework: "common.jarvis_client (in-process Python at test time)"
    driver: "in-process import in tests; flattened/inlined in deploy"
    format_note: "Tests import `from common.jarvis_client import JarvisClient`. The deployable `nats_fleet_pipe.py` must remain self-contained per scope §7 Q4 — Open WebUI pipes execute inside the Open WebUI container which does NOT ship nats-py and cannot pip-install dependencies."
---

# TASK-FG-004: OpenWebUI Pipe Function Refactor

## Goal

Refactor `openwebui/nats_fleet_pipe.py` so that:
1. The shared envelope/parse logic from `common/` is the source of truth
   for tests.
2. The deployable file remains **self-contained** (single `.py` paste-able
   into the Open WebUI Workspace Functions admin UI) — because Open WebUI's
   Python interpreter does not ship `nats-py` and cannot pip-install
   `fleet-gateway-common`.

Per scope §7 Q4 (REJECTED A1 / confirmed by `docker exec` against the running
container), Approach A: **self-contained file with source-level reuse**. The
file will (a) import from `common/` so tests exercise the shared code, and
(b) ship a flattened/inlined version for Open WebUI deployment. A small
build script (or annotated inline copies) handles the flatten step.

## Files to modify

- `openwebui/nats_fleet_pipe.py` — replace inline envelope construction with
  calls into `common/`, preserving the Pipe class signature
- `openwebui/README.md` — document the source-vs-deploy divergence and the
  flatten step (build script command or manual inlining instructions)

## Files to create

- `openwebui/build_pipe.py` (or `openwebui/Makefile` / shell script) —
  one-shot build step that flattens `common/envelope.py` + `common/jarvis_client.py`
  into the deployable `nats_fleet_pipe.py`. Optional: inline by hand if the
  build step is judged disproportionate for ~60 LOC.
- `tests/test_openwebui_pipe.py` — pytest suite verifying the Pipe class

## Files NOT to touch

- `reachy/`, `common/` (consume only)

## Inputs

- Current working pipe: `openwebui/nats_fleet_pipe.py` (preserve `Valve`, `pipe()`, `pipes()` signatures)
- JarvisClient API from TASK-FG-002
- Scope §7 Q4 — Approach A confirmation; the file MUST be paste-able into Open WebUI

## Acceptance criteria

- [ ] `nats_fleet_pipe.py` (test-time) imports `JarvisClient` from `common.jarvis_client` — verifiable by `grep "from common" openwebui/nats_fleet_pipe.py`
- [ ] Inline envelope construction (the lines previously at 68–88) is removed; envelope/parse logic lives in `common/`
- [ ] `Pipe.pipes()` still returns `[{"id": "jarvis", "name": "Jarvis"}]`
- [ ] `Pipe.pipe(body)` still accepts an Open WebUI request body (with `messages` list) and returns a response string
- [ ] `Pipe.Valves` still exposes `NATS_URL` and `REQUEST_TIMEOUT` with the same defaults as before the refactor
- [ ] Error messages preserved: timeout error message and no-responders error message read identically (or better) to the pre-refactor versions, so existing Open WebUI users see consistent behaviour
- [ ] **Deployable file is self-contained**: a flattened version (either committed alongside the source file, or produced by `python openwebui/build_pipe.py`, or maintained inline with `# BEGIN INLINED` markers) imports nothing from `common/` at runtime — Open WebUI can paste it directly
- [ ] `openwebui/README.md` documents: (a) why the file is self-contained (Open WebUI pipe isolation), (b) how to regenerate the flattened version after `common/` changes, (c) the test command (`pytest tests/test_openwebui_pipe.py`)
- [ ] `pytest tests/test_openwebui_pipe.py -v` passes with ≥4 tests: pipes() shape, pipe() happy path (mocked JarvisClient), pipe() timeout error formatting, pipe() no-responders error formatting
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation notes

- The cleanest "self-contained at deploy" pattern is a small `build_pipe.py`
  that:
  1. Reads `common/envelope.py` and `common/jarvis_client.py`.
  2. Strips their `from __future__` and module-level imports.
  3. Concatenates them into the top of `nats_fleet_pipe.py` between
     `# BEGIN INLINED` / `# END INLINED` markers.
  4. Writes a sibling file like `nats_fleet_pipe.deploy.py` (kept in git so
     reviewers can diff it).
- Alternative for Phase 1 hackathon: maintain the inlined block by hand
  inside `nats_fleet_pipe.py` itself, with a clear comment block explaining
  the rule. Document the chosen approach in `openwebui/README.md`.
- Do NOT add `pip install` instructions to the README that imply Open WebUI
  can install `fleet-gateway-common` — confirmed impossible (scope §7 Q4).

## Seam Tests

```python
"""Seam test: verify JarvisClient API contract is honoured by the pipe."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("JarvisClient.send_command")
@pytest.mark.asyncio
async def test_pipe_calls_send_command_with_message():
    """Verify Pipe.pipe forwards the Open WebUI message into JarvisClient.send_command.

    Contract: send_command(message: str, conversation_history: list[dict] | None) -> str
    Producer: TASK-FG-002 (JarvisClient)
    """
    with patch("common.jarvis_client.JarvisClient.send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = "Build complete"

        from openwebui.nats_fleet_pipe import Pipe

        pipe = Pipe()
        body = {"messages": [{"role": "user", "content": "How's the build going?"}]}
        result = await pipe.pipe(body) if hasattr(pipe.pipe, "__await__") else pipe.pipe(body)

        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        # message text must be first positional or 'message' kwarg
        assert "How's the build going?" in (args[0] if args else kwargs.get("message", "")), (
            "Pipe must forward the user's latest message into send_command"
        )
        assert "Build complete" in str(result), "Pipe must return JarvisClient response text"
```

## Coach validation

Coach should verify:
- `pytest tests/test_openwebui_pipe.py -v` exits 0 with ≥4 tests
- `grep -c "from common" openwebui/nats_fleet_pipe.py` returns ≥1 (test-time import present)
- The deployable variant (flattened file or inlined block) contains the envelope/parse logic verbatim — no `from common` at deploy time
- `openwebui/README.md` mentions the self-contained constraint and the regeneration step
- ruff and mypy pass on `openwebui/`
