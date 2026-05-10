# Implementation Guide: FEAT-FG-001 E2E Runbooks

**Source of truth:** [`docs/FEAT-FG-001-e2e-test-strategy.md`](../../../docs/FEAT-FG-001-e2e-test-strategy.md). This guide is the bridge from strategy to authoring; the strategy doc is authoritative for content, this guide is authoritative for *order and shape* of the authoring effort.

## Wave plan

```
Wave 1 (sequential)
  └── TASK-FG-007  Author Scholar runbook
                       │
                       │ (establishes shape mirrored by Wave 2)
                       ▼
Wave 2 (parallel-safe, no file conflicts)
  ├── TASK-FG-008  Author Bridge runbook
  └── TASK-FG-009  Author OpenWebUI runbook
```

Wave 1 must land first because Scholar's runbook is the smallest infrastructure surface (FalkorDB + Tailscale + Pollen — no NATS, no Jarvis), making it the cheapest place to debug the runbook *shape* itself before the higher-coupling paths land.

## Shared shape (all three runbooks)

Every runbook follows this skeleton (mirrors the jarvis precedent):

```markdown
# Runbook: Fleet Gateway {Path} E2E

**Status:** Ready for execution.
**Purpose:** {one sentence, exact path under test}
**Machines:** {GB10 / MacBook / whitestocks — only those touched by THIS path}
**Predecessors:** FEAT-FG-001 merged; reference strategy doc.
**Expected wall-clock:** ~{30-60} minutes for a clean run.
**Outputs:** `RESULTS-feat-fg-001-{path}-{date}.md` + evidence/ subdir per §7.

## Known issues / forward-references

(Initially empty. Folds in via the gap-back-fill rule — strategy §7.3.)

## Phase 0: Pre-flight
### 0.1 ...
### 0.2 ...
   ```bash
   # verbatim
   ```
   **Pass:** ...

## Phase 1: ...
   ...

## Phase N: RESULTS write
{instruction to drop the dated RESULTS file with the per-phase outcome table}
```

**Mandatory across all three:**
- A `Known issues / forward-references` block at the top, even if initially empty (the gap-back-fill rule is load-bearing).
- A `**Pass:**` line at the end of every numbered step. No `# Expected: …` placeholder may be `TODO`.
- A final phase that creates the dated RESULTS doc with the per-phase outcomes table from strategy §7.1.
- A teardown / cleanup phase before RESULTS write.

## Per-runbook content sources

| Runbook | Phase outline | Probe spec | Manual checkpoints |
|---|---|---|---|
| Scholar (TASK-FG-007) | Strategy §4.1 | Strategy §6.1 | Strategy §9 (voice transcription) |
| Bridge (TASK-FG-008)  | Strategy §4.2 | Strategy §6.2 | Strategy §9 (voice transcription) |
| OpenWebUI (TASK-FG-009) | Strategy §4.3 | Strategy §6.3 | Strategy §9 (browser screenshot, UI render) |

## Acceptance criteria (all three runbooks)

A runbook is "authoring-complete" when:

- [ ] Lands at `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-{path}-e2e.md`
- [ ] Header includes purpose, machine(s), predecessor, expected wall-clock, outputs
- [ ] `Known issues / forward-references` block exists (initially empty)
- [ ] Every phase has verbatim bash (or explicit non-shell instructions for HUMAN steps)
- [ ] Every phase has a `**Pass:**` line — no TODO, no placeholder
- [ ] Phase 0 covers every dependency listed for that path in strategy §3
- [ ] Probe spec from strategy §6.{1,2,3} is materialised verbatim in the relevant phase (the Python snippet from §6 lands in the runbook as `python -c "..."` or as a `scripts/{path}-probe.py` referenced from the runbook)
- [ ] Final phase instructs the operator to write the dated RESULTS doc per §7.1 with the per-phase outcomes table
- [ ] No content copied from precedent runbooks — only shape

## Execution-loop note

Per strategy §8: the operator instruction template is the **plain-prompt loop** ("read the runbook top-to-bottom, run each phase, paste output, decide pass/fail, write RESULTS as you go"). No new skill is needed. Each authored runbook should be self-sufficient under that prompt with no external scaffolding.

## What this guide explicitly excludes

- The `scripts/scholar-probe.py` / `scripts/bridge-probe.py` helpers referenced in strategy §6 may live as standalone files in `scripts/` *or* be inlined as `python -c` blocks in the runbook. Author's choice; document the choice in the runbook.
- Whether to add a fourth runbook (e.g. an integrated multi-gateway demo runbook for the video). That is a video-script question, not in scope here.
- Authoring effort estimates assume markdown-only output; if the author discovers code changes are needed (e.g. an envelope `source_id` clarification), that's a runbook gap → spawn a code task.
