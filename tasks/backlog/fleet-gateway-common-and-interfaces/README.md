# Feature: Fleet Gateway Common + Gateway Interfaces (FEAT-FG-001)

Shared `common/` gateway client library + wired-up OpenWebUI Pipe and
Reachy Mini external tools (Scholar + Bridge profiles).

## Quick reference

| | |
|---|---|
| **Feature ID** | FEAT-FG-001 |
| **Origin review** | TASK-REV-CB98 (in `tasks/in_review/`) |
| **Scope doc** | `docs/FEAT-FG-001-scope.md` |
| **Build plan (pre-reconciliation)** | `docs/FEAT-FG-001-build-plan.md` |
| **BDD spec** | `features/fleet-gateway-common-and-interfaces/` |
| **Implementation guide** | `IMPLEMENTATION-GUIDE.md` (this folder) |
| **Aggregate complexity** | 6/10 (medium) |
| **Tasks** | 6 across 3 waves |
| **Estimated effort** | 5–7h focused work |
| **Hackathon target** | 11–13 May (Scholar) / 16 May (Bridge) |

## Tasks

| ID | Title | Wave | Mode | Complexity | Depends on |
|---|---|---|---|---|---|
| TASK-FG-001 | Package setup + envelope module | 1 | direct | 3 | — |
| TASK-FG-002 | JarvisClient | 2 | task-work | 5 | TASK-FG-001 |
| TASK-FG-003 | GraphitiClient (graphiti-core) | 2 | task-work | 5 | TASK-FG-001 |
| TASK-FG-004 | OpenWebUI pipe refactor | 3 | task-work | 4 | TASK-FG-002 |
| TASK-FG-005 | Scholar tools + profile ★ critical path | 3 | task-work | 6 | TASK-FG-003 |
| TASK-FG-006 | Bridge profile + agent_status | 3 | task-work | 4 | TASK-FG-002 |

## Execution waves

```
Wave 1:  [TASK-FG-001]                                  (foundation)
Wave 2:  [TASK-FG-002, TASK-FG-003]                     (parallel — Conductor)
Wave 3:  [TASK-FG-004, TASK-FG-005, TASK-FG-006]        (parallel — Conductor)
```

## How to start

1. Read `IMPLEMENTATION-GUIDE.md` (in this folder) for the full data flow,
   integration contracts, and decision rationale.
2. `pip install -e ".[dev]"` once TASK-FG-001 is complete.
3. Run Wave 1: `/task-work TASK-FG-001`
4. Run Wave 2 in parallel via Conductor or sequentially.
5. Run Wave 3 in parallel via Conductor.
6. After completion, run `/feature-complete FEAT-FG-001` to merge and
   archive.

## Smoke-gate scenarios

13 BDD scenarios are tagged `@smoke` in
`features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feature`
— these block Coach approval per task. The feature-level smoke gate runs
between waves (see `.guardkit/features/FEAT-FG-001.yaml`).

## Reconciliation note (read before starting)

This plan is the **build plan + 5 mechanical AC corrections** from
scope §7 Q1–Q4. Do NOT implement the build-plan ACs verbatim — use the
task files in this folder which already incorporate the corrections:

- `aiohttp` is **out**, `graphiti-core` is **in**
- `JarvisClient.query_status` is **dropped** (use `send_command`)
- Group ID is **`student-lilymay`** (dash, not double-underscore)
- OpenWebUI deploy is **self-contained** (cannot pip-install in the container)
- Reachy `common/` import is **editable install** in the Pollen venv

See IMPLEMENTATION-GUIDE.md §7 for the locked-in decisions.
