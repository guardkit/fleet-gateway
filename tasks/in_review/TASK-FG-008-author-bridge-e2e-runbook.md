---
id: TASK-FG-008
title: Author RUNBOOK-fleet-gateway-bridge-e2e.md
task_type: feature
parent_review: TASK-REV-3078
feature_id: FEAT-FG-001
wave: 2
implementation_mode: direct
complexity: 4
estimated_minutes: 150
dependencies:
  - TASK-REV-3078
  - TASK-FG-007
domain_tags:
  - runbook
  - bridge
  - e2e
  - nats
  - jarvis
  - documentation
status: in_review
created: 2026-05-10
updated: 2026-05-10
previous_state: in_progress
state_transition_reason: "Authoring complete; all 16 acceptance criteria mechanically verified during /task-work — every numbered step ends with **Pass:**, zero TODOs, query_status appears exactly once (the load-bearing scope §7 Q3 disambiguation note), destructive steps carry confirm-with-operator notes, no substantive prose copied from precedent runbooks (iterative rewrite passes against Scholar wave-1 and Jarvis FEAT-JARVIS-INTERNAL-001), ruff clean on the bridge-probe script."
deliverables:
  - docs/runbooks/RUNBOOK-fleet-gateway-bridge-e2e.md
  - scripts/bridge-probe.py
context_files:
  - docs/FEAT-FG-001-e2e-test-strategy.md
  - docs/FEAT-FG-001-scope.md
  - tasks/completed/TASK-FG-006-bridge-profile-agent-status.md
external_references:
  - /home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
---

# TASK-FG-008: Author RUNBOOK-fleet-gateway-bridge-e2e.md

## Goal

Materialise the Bridge e2e runbook decided in TASK-REV-3078 as a shippable
markdown file at `docs/runbooks/RUNBOOK-fleet-gateway-bridge-e2e.md`. The
runbook proves end-to-end that `agent_status` returns a Jarvis-narrated
fleet status text (with the wire envelope visible on `agents.command.jarvis`)
and that the tool degrades cleanly when NATS is unreachable.

**Wave 2** — depends on Wave 1 (TASK-FG-007) for the runbook *shape* (header
format, known-issues block, RESULTS-write phase). No file conflicts with
TASK-FG-009; the two can author in parallel.

## File to create

- `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-bridge-e2e.md`

## Files NOT to touch

- `common/`, `openwebui/`, `reachy/`
- `docs/FEAT-FG-001-e2e-test-strategy.md`
- The Scholar or OpenWebUI runbooks (separate tasks)

## Inputs (read in order)

1. **Wave-1 output** — `RUNBOOK-fleet-gateway-scholar-e2e.md` (shape reference; mirror the header / phase numbering / `**Pass:**` discipline)
2. **Strategy doc §4.2** — phase outline (8 phases including a *paired* side-terminal envelope-capture phase)
3. **Strategy doc §6.2** — Bridge probe spec (Python snippet — `JarvisClient.send_command("what's the fleet status?")` and the wire-envelope assertion)
4. **Strategy doc §3** — surface map rows for NATS, Jarvis subscriber, llama-swap, Tailscale, `nats-py` in Pollen venv
5. **Strategy doc §7** — RESULTS convention; gap-back-fill rule
6. **Strategy doc §9** — voice transcription HUMAN step (Phase 5)
7. **Scope §7 Q3** — `JarvisClient.query_status()` does not exist; Bridge calls `send_command` on `agents.command.jarvis`. The runbook MUST encode this — any call to a non-existent topic is itself a gap.
8. **TASK-FG-006** — completed task that wired the tool; its acceptance criteria are the e2e re-confirmation target
9. **Reference runbook (shape only):** `jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — multi-terminal `nats sub` envelope-capture pattern in Phase 5 / Phase 7

## Acceptance criteria

- [ ] File lands at `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-bridge-e2e.md`
- [ ] Header includes: purpose (one sentence), machines (MacBook + GB10 via Tailscale), predecessors, expected wall-clock (≤60 min for a clean run), outputs
- [ ] `Known issues / forward-references` block exists (initially empty)
- [ ] Phase 0 covers: Tailscale up, NATS reachable from MacBook, `nats sub agents.status.jarvis` heartbeat captured, llama-swap on `:9000` returning models including `JARVIS_SUPERVISOR_MODEL`, `nats-py` in Pollen venv, fleet-gateway editable-installed in Pollen venv
- [ ] Phase 1 (standalone JarvisClient probe) inlines the Python snippet from strategy §6.2 — either as `python -c "..."` or as a referenced `scripts/bridge-probe.py`
- [ ] Phase 2 (paired side-terminal envelope capture) explicitly numbers the `nats sub agents.command.jarvis --count 1` BEFORE Phase 1's publish — the runbook MUST clarify which terminal runs which command and the order of operations
- [ ] Phase 3 (standalone tool wrapper probe) calls `AgentStatusTool` directly with no Pollen
- [ ] Phase 4 (Pollen launch) wraps in `tmux`
- [ ] Phase 5 marked HUMAN: operator says "Computer, fleet status?", listens for LCARS-style narration mentioning ≥1 fleet agent, transcribes into RESULTS, notes voice tone is distinct from Scholar
- [ ] Phase 6 (graceful degradation) stops NATS via `docker stop ships-computer-nats` and re-runs Phase 1; asserts the tool returns text containing "NATS unreachable" / "fleet offline" / equivalent and **no** Python traceback
- [ ] Phase 7 (restore + teardown) restarts NATS, kills tmux, runs one final `send_command("ping")` to confirm green again
- [ ] Phase 8 (RESULTS write) instructs the operator to land `docs/runbooks/RESULTS-feat-fg-001-bridge-{date}.md`
- [ ] Every numbered step ends with `**Pass:**` — no TODO
- [ ] Destructive steps (`docker stop ships-computer-nats`, `tmux kill-session`) carry "confirm with user before running" notes
- [ ] Runbook explicitly references scope §7 Q3: `JarvisClient.query_status()` does NOT exist; Bridge MUST use `send_command`. A grep for `query_status` in the runbook returns ≤1 match (the disambiguation note itself)
- [ ] No content copied from precedent runbooks — only shape

## Out of scope

- Authoring Scholar (TASK-FG-007) or OpenWebUI (TASK-FG-009) runbooks.
- Executing the runbook.
- Modifying `common/jarvis_client.py` or any code (the runbook tests existing code; gaps fold per strategy §7.3).
- Drafting fleet-status query phrasing alternatives — the strategy doc fixes the phrase as `"what's the fleet status?"` per scope §7 Q3.
