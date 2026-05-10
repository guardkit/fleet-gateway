---
id: TASK-FG-007
title: Author RUNBOOK-fleet-gateway-scholar-e2e.md
task_type: feature
parent_review: TASK-REV-3078
feature_id: FEAT-FG-001
wave: 1
implementation_mode: direct
complexity: 4
estimated_minutes: 150
dependencies:
  - TASK-REV-3078
domain_tags:
  - runbook
  - scholar
  - e2e
  - graphiti
  - documentation
status: completed
created: 2026-05-10
updated: 2026-05-10
completed: 2026-05-10
previous_state: in_review
state_transition_reason: "Authoring complete; all 13 acceptance criteria mechanically verified during /task-work (every sub-step has a Pass: line, destructive steps carry confirm-with-operator notes, no precedent-runbook prose copied verbatim — Python-driven check across all three precedent runbooks returned zero matches)."
deliverables:
  - docs/runbooks/RUNBOOK-fleet-gateway-scholar-e2e.md
  - scripts/scholar-probe.py
context_files:
  - docs/FEAT-FG-001-e2e-test-strategy.md
  - docs/FEAT-FG-001-scope.md
  - tasks/completed/TASK-FG-005-scholar-tools-and-profile.md
external_references:
  - /home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
  - /home/richardwoollcott/Projects/appmilla_github/guardkit/docs/research/dgx-spark/RUNBOOK-v3-production-deployment.md
---

# TASK-FG-007: Author RUNBOOK-fleet-gateway-scholar-e2e.md

## Goal

Materialise the Scholar e2e runbook decided in TASK-REV-3078 as a shippable
markdown file at `docs/runbooks/RUNBOOK-fleet-gateway-scholar-e2e.md`. The
runbook proves end-to-end that `query_student_model` returns real Graphiti
data for `student-lilymay` and that Gemini Live narrates it inside the
Scholar profile.

This runbook is **wave 1** of the three-runbook bundle — it establishes the
shape that Bridge (TASK-FG-008) and OpenWebUI (TASK-FG-009) mirror.

## File to create

- `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-scholar-e2e.md`

## Files NOT to touch

- `common/`, `openwebui/`, `reachy/` (the runbook tests existing code, does not change it)
- `docs/FEAT-FG-001-e2e-test-strategy.md` (source of truth, do not edit)
- The other two runbooks (separate tasks)

## Inputs (read in order)

1. **Strategy doc §4.1** — phase outline (8 phases, the shape to materialise)
2. **Strategy doc §6.1** — Scholar probe spec (Python snippet to inline as `python -c` or `scripts/scholar-probe.py`)
3. **Strategy doc §3** — surface map row for FalkorDB / `student-lilymay` / graphiti-core / Tailscale / Pollen venv (Phase 0 ingredients)
4. **Strategy doc §7** — RESULTS doc convention and gap-back-fill rule (final phase materials)
5. **Strategy doc §9** — voice transcription manual checkpoint (Phase 4 HUMAN step)
6. **Scope §6 A6** — group_id is `student-lilymay` (dash form), not double-underscore
7. **TASK-FG-005** — completed task that wired the tool; its acceptance criteria are what the runbook re-confirms against real infra
8. **Reference runbooks (shape only, do not copy content):**
   - `jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — header + known-issues block format
   - `guardkit/docs/research/dgx-spark/RUNBOOK-v3-production-deployment.md` — Phase 0 pre-flight discipline

## Acceptance criteria

- [ ] File lands at `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-scholar-e2e.md`
- [ ] Header has: purpose (one sentence), machines (MacBook + whitestocks via Tailscale), predecessors (FEAT-FG-001 merged + strategy doc link), expected wall-clock (≤45 min for a clean run), outputs (RESULTS doc path + evidence/ subdir)
- [ ] `Known issues / forward-references` block exists (initially empty — a placeholder header with "(no known issues at first authoring)" is acceptable)
- [ ] Phase 0 covers: Tailscale up, FalkorDB ping on `whitestocks:6379`, `graphiti-core` import in Pollen venv, fleet-gateway editable-installed in Pollen venv, Scholar profile files present
- [ ] Phase 1 (standalone graphiti-core probe) inlines the Python snippet from strategy §6.1 — either as `python -c "..."` or as a referenced `scripts/scholar-probe.py` (author's choice; document it)
- [ ] Phase 2 (standalone tool wrapper probe) calls `QueryStudentModelTool` directly with no Pollen
- [ ] Phase 3 (Pollen launch) wraps in `tmux` so the operator can voice-test without losing the session
- [ ] Phase 4 is explicitly marked HUMAN: operator says the magic phrase out loud, listens, transcribes verbatim into RESULTS
- [ ] Phase 5 (graceful degradation) blocks port 6379 / drops Tailscale and re-runs Phase 1; asserts `data_available=False` returns cleanly with no traceback
- [ ] Phase 6 (teardown) restores network and kills the tmux session
- [ ] Phase 7 (RESULTS write) instructs the operator to land `docs/runbooks/RESULTS-feat-fg-001-scholar-{date}.md` with the per-phase outcomes table from strategy §7.1
- [ ] Every numbered step ends with a `**Pass:**` line — no TODO, no `# Expected: ...` placeholder
- [ ] Destructive steps (`tailscale down`, `tmux kill-session`, `pfctl`) carry an explicit "confirm with user before running" note (matches strategy §8 operator instruction template)
- [ ] No content copied from precedent runbooks — only shape; `grep -F` of any non-trivial sentence from a precedent runbook against this file returns zero matches

## Hackathon-fit note

Authoring estimate ≤2.5h. Under the operator's "quality over deadline"
priority, this runbook is the minimum viable demo evidence for the 11-13
May video shoot — Scholar is the highest-demo-value path with the lowest
infra surface, so a green Scholar RESULTS doc covers the demo even if
Bridge and OpenWebUI runbooks land later.

## Out of scope

- Authoring Bridge or OpenWebUI runbooks (separate tasks: TASK-FG-008, TASK-FG-009).
- Executing the runbook (separate execution task — create after all three runbooks land).
- Adding new code to `common/` / `reachy/` (the runbook tests existing code; if it surfaces a code gap, fold via the strategy §7.3 gap-back-fill rule and spawn a separate code task).
- Updating the strategy doc itself (it is the source of truth — feedback to it is a TASK-REV-3078 revise, not in this task).
