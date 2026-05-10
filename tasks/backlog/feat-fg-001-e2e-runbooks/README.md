# FEAT-FG-001 E2E Runbooks — Authoring Bundle

**Parent review:** [TASK-REV-3078](../TASK-REV-3078-design-e2e-test-runbook-for-feat-fg-001.md)
**Strategy doc:** [`docs/FEAT-FG-001-e2e-test-strategy.md`](../../../docs/FEAT-FG-001-e2e-test-strategy.md)
**Feature:** FEAT-FG-001 (Fleet Gateway Common + Gateway Interfaces)

## What this is

The decision-mode review TASK-REV-3078 chose **three thin per-gateway runbooks** as the e2e validation strategy for FEAT-FG-001 (Scholar / Bridge / OpenWebUI), rather than one mega-runbook or a two-runbook infra+e2e split. This subfolder contains the three authoring tasks that turn that decision into shipped runbooks.

The strategy doc is the source of truth for *what* goes in each runbook (phase tables, probe specs, evidence convention, execution loop). These tasks are *authoring* instructions — they tell the implementer to materialise each runbook against §4 of the strategy doc.

## Subtasks

| ID | Title | Wave | Mode | Output |
|---|---|---|---|---|
| [TASK-FG-007](TASK-FG-007-author-scholar-e2e-runbook.md) | Author RUNBOOK-fleet-gateway-scholar-e2e.md | 1 | direct | `docs/runbooks/RUNBOOK-fleet-gateway-scholar-e2e.md` |
| [TASK-FG-008](TASK-FG-008-author-bridge-e2e-runbook.md) | Author RUNBOOK-fleet-gateway-bridge-e2e.md | 2 | direct | `docs/runbooks/RUNBOOK-fleet-gateway-bridge-e2e.md` |
| [TASK-FG-009](TASK-FG-009-author-openwebui-e2e-runbook.md) | Author RUNBOOK-fleet-gateway-openwebui-e2e.md | 2 | direct | `docs/runbooks/RUNBOOK-fleet-gateway-openwebui-e2e.md` |

**Wave 1** ships the Scholar runbook first; it establishes the shape (header → known-issues block → numbered phases with verbatim bash and `Pass:` lines → RESULTS-write phase) that **Wave 2** (Bridge + OpenWebUI, parallel-safe — no file conflicts) mirrors. Sequencing is for shape consistency; not a hard technical dependency.

## Why three (not one)

Each gateway exercises a different infrastructure stack (FalkorDB+Tailscale only / NATS+Jarvis+Tailscale+Pollen / NATS+Jarvis+container). Coupling them in one runbook cascades failures and deviates from the user's named precedent (`jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` and `RUNBOOK-jarvis-architect-align-dddsw-demo.md` are *separate* runbooks despite sharing infra). Full rationale in strategy doc §2.

## After all three land

A fourth task captures the first execution of each runbook (one execution-task per runbook, or `/loop`-driven). Not created here — author when ready to run.

## Operator priority recorded

"Quality over deadline" (collected via `/task-review` clarification on 2026-05-10). The hackathon video shoot 11-13 May is not driving structure; highest e2e confidence per run wins.
