---
id: TASK-FG-009
title: Author RUNBOOK-fleet-gateway-openwebui-e2e.md
task_type: feature
parent_review: TASK-REV-3078
feature_id: FEAT-FG-001
wave: 2
implementation_mode: direct
complexity: 4
estimated_minutes: 165
dependencies:
  - TASK-REV-3078
  - TASK-FG-007
domain_tags:
  - runbook
  - openwebui
  - e2e
  - nats
  - jarvis
  - documentation
status: backlog
created: 2026-05-10
context_files:
  - docs/FEAT-FG-001-e2e-test-strategy.md
  - docs/FEAT-FG-001-scope.md
  - tasks/completed/TASK-FG-004-openwebui-pipe-refactor.md
  - openwebui/nats_fleet_pipe.py
external_references:
  - /home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
---

# TASK-FG-009: Author RUNBOOK-fleet-gateway-openwebui-e2e.md

## Goal

Materialise the OpenWebUI e2e runbook decided in TASK-REV-3078 as a
shippable markdown file at
`docs/runbooks/RUNBOOK-fleet-gateway-openwebui-e2e.md`. The runbook proves
that a chat posted in the deployed Open WebUI surfaces a Jarvis response,
the wire envelope is visible on `agents.command.jarvis`, and the
correlation_id chain ties UI → container log → wire envelope.

**Wave 2** — depends on Wave 1 (TASK-FG-007) for runbook *shape* only. No
file conflicts with TASK-FG-008; parallel-safe.

## File to create

- `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-openwebui-e2e.md`

## Files NOT to touch

- `common/`, `openwebui/`, `reachy/` (the runbook tests existing code)
- `docs/FEAT-FG-001-e2e-test-strategy.md`
- The Scholar or Bridge runbooks

## Inputs (read in order)

1. **Wave-1 output** — `RUNBOOK-fleet-gateway-scholar-e2e.md` (shape reference)
2. **Strategy doc §4.3** — phase outline (8 phases, including a `cmp` of source vs deploy file in Phase 0 and a manual browser screenshot in Phase 1 + Phase 3)
3. **Strategy doc §6.3** — three-way assertion: UI rendering + wire envelope + correlation_id continuity (all three must pass for "green")
4. **Strategy doc §3** — surface map rows for NATS, Jarvis subscriber, llama-swap, Open WebUI container, **`nats-py` inside the container** (the load-bearing pre-flight item per scope §7 Q4), pipe registration in Workspace UI
5. **Strategy doc §7** — RESULTS convention; evidence subdir for browser screenshots
6. **Strategy doc §9** — manual checkpoints (browser screenshot, UI render judgement)
7. **Scope §7 Q4** — `nats-py` is NOT shipped in the Open WebUI container image; the runbook's Phase 0 MUST verify it (via `docker exec open-webui python -c "import nats"`) and the runbook MUST document the install path if missing (`docker exec open-webui pip install nats-py` or rebuild image)
8. **`openwebui/nats_fleet_pipe.py`** — source-of-truth file; the runbook needs a `cmp` against the deploy file `nats_fleet_pipe.deploy.py` (regenerated via `python openwebui/build_pipe.py` per the source-file docstring)
9. **TASK-FG-004** — completed task that wired the pipe; its acceptance criteria are the e2e re-confirmation target

## Acceptance criteria

- [ ] File lands at `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-openwebui-e2e.md`
- [ ] Header includes: purpose (one sentence), machines (GB10 only — no MacBook/Pollen), predecessors, expected wall-clock (≤60 min for a clean run), outputs (RESULTS doc + screenshots subdir)
- [ ] `Known issues / forward-references` block exists (initially empty)
- [ ] Phase 0 covers: Open WebUI container Up, **`nats-py` importable inside the container** (per scope §7 Q4 — this is load-bearing), NATS reachable, Jarvis heartbeat captured, llama-swap models endpoint green, source vs deploy `cmp` returns identical
- [ ] Phase 0 explicitly documents the install/rebuild path if `docker exec open-webui python -c "import nats"` fails (e.g. `docker exec open-webui pip install nats-py` plus a note that this does not survive container restart unless the image is rebuilt)
- [ ] Phase 1 marked HUMAN: operator confirms in browser that the pipe is registered + enabled in Admin → Workspace → Functions; screenshot lands in `docs/runbooks/evidence/openwebui-{date}/`
- [ ] Phase 2 starts the side-terminal `nats sub agents.command.jarvis --count 1` BEFORE Phase 3 — the runbook explicitly orders the side-terminal subscribe ahead of the chat post
- [ ] Phase 3 marked HUMAN: operator opens Open WebUI in browser, selects "Jarvis" model, posts the prompt; UI renders a response within `REQUEST_TIMEOUT`
- [ ] Phase 4 (correlation-id grep) extracts the `correlation_id` from `docker logs --since 2m open-webui` and the runbook asserts equality with the captured envelope's `correlation_id`
- [ ] Phase 5 (wire ↔ UI cross-check) compares the captured envelope's `payload.message` to what the operator typed; runbook documents the actual shape (raw text vs conversation-history-wrapped — whichever the implementation produces)
- [ ] Phase 6 (graceful degradation) stops NATS, posts a chat in browser; runbook asserts the UI shows the preserved error string from `nats_fleet_pipe.deploy.py`'s exception handlers (NOT a stack trace)
- [ ] Phase 7 (restore + teardown) restarts NATS, runs one more chat to confirm green
- [ ] Phase 8 (RESULTS write) lands `docs/runbooks/RESULTS-feat-fg-001-openwebui-{date}.md` with screenshot links + per-phase outcomes table
- [ ] Every numbered step ends with `**Pass:**`
- [ ] Destructive steps (`docker stop ships-computer-nats`) carry "confirm with user" notes
- [ ] No content copied from precedent runbooks — only shape

## Hackathon-fit note

This is the most layered of the three runbooks (UI + container + wire +
log) and authoring takes longer (estimate ≤2.75h). Under the operator's
"quality over deadline" priority it does not need to land before 11 May —
Scholar (TASK-FG-007) is the demo-evidence priority. OpenWebUI lands when
it lands.

## Out of scope

- Authoring Scholar (TASK-FG-007) or Bridge (TASK-FG-008) runbooks.
- Executing the runbook.
- Modifying `openwebui/nats_fleet_pipe.py`, `openwebui/build_pipe.py`, or any code.
- Migrating the OpenWebUI pipe to a Pipelines container (scope §7 Q4 path B — that is a post-hackathon deployment decision).
- Authoring a screenshot/UI-validation tool. The browser checkpoints stay manual per strategy §9.
