# Feature Spec Summary: Fleet Gateway Common + Gateway Interfaces

**Feature ID**: FEAT-FG-001
**Stack**: python
**Generated**: 2026-05-09
**Scenarios**: 33 total (13 smoke, 4 regression)
**Assumptions**: 10 total (5 high / 5 medium / 0 low confidence)
**Review required**: No (no low-confidence assumptions)

## Scope

Specifies the behaviour of the shared `common/` gateway client library
(`envelope.py`, `jarvis_client.py`, `graphiti_client.py`) consumed by both
the OpenWebUI Pipe Function and Reachy Mini external tools (Scholar +
Bridge profiles). Covers wire-format envelope construction and parsing,
NATS request-reply semantics with Jarvis, direct Graphiti reads to
FalkorDB, graceful degradation when NATS or Graphiti is unreachable, and
the deployment-isolation invariants the OpenWebUI pipe and Reachy tools
must respect.

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (`@key-example`) | 8 |
| Boundary conditions (`@boundary`) | 6 |
| Negative cases (`@negative`) | 7 |
| Edge cases (`@edge-case`) | 12 |

## Tag Index (cross-cutting)

| Tag | Scope | Count |
|-----|-------|-------|
| `@common` | shared library (envelope/jarvis-client/graphiti-client) | 19 |
| `@openwebui` | OpenWebUI Pipe Function | 7 |
| `@scholar` | Reachy Scholar profile + tools | 4 |
| `@bridge` | Reachy Bridge profile + tools | 3 |
| `@security` | prompt-injection forwarding, log redaction | 2 |
| `@regression` | locks down behaviour the implementation must preserve | 4 |
| `@smoke` | Coach-blocking subset run on every build | 13 |

## Deferred Items

None. All four scenario groups (A/B/C/D) plus the edge-case expansion
(Y) were accepted in full.

## Open Assumptions (low confidence)

None — the spec has 5 high-confidence and 5 medium-confidence
assumptions, all `human_response: confirmed`. No `REVIEW REQUIRED`
flag is set. The medium-confidence items are listed below for
visibility; they are not blocking but are worth re-checking during
implementation:

- ASSUM-001 — Reachy adapter source_id naming (`reachy-scholar-gateway`, `reachy-bridge-gateway`)
- ASSUM-002 — Bridge `agent_status` query phrasing (`"what's the fleet status?"`)
- ASSUM-003 — Pipe log-redaction policy (no user message at INFO)
- ASSUM-004 — Graphiti auth-failure classification (distinct from unreachable)
- ASSUM-010 — Reachy `common/` import strategy (PYTHONPATH vs editable install)

## Mapping to Build-Plan Tasks

The 6 tasks in `docs/FEAT-FG-001-build-plan.md` cover the scenario
surface as follows. (Final task↔scenario binding is produced by
`/feature-plan` Step 11; this is an indicative pre-mapping.)

| Task | Primary scenario tags |
|------|------------------------|
| TASK-FG-001 (envelope module) | `@common @envelope` (Groups A, B, C, D) |
| TASK-FG-002 (JarvisClient) | `@common @jarvis-client` (Groups A, B, C, D) |
| TASK-FG-003 (GraphitiClient) | `@common @graphiti-client` (Groups A, B, C, D) |
| TASK-FG-004 (OpenWebUI pipe refactor) | `@openwebui` (Groups A, C, D) |
| TASK-FG-005 (Scholar tools + profile) | `@scholar @tools` (Groups A, C, D) |
| TASK-FG-006 (Bridge profile + agent_status) | `@bridge @tools` (Groups A, C) |

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "Fleet Gateway Common + Gateway Interfaces" \
      --context features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces_summary.md \
      --context docs/FEAT-FG-001-scope.md \
      --context docs/FEAT-FG-001-build-plan.md

The build plan in `docs/FEAT-FG-001-build-plan.md` is already
detailed; `/feature-plan` will reconcile its tasks with this
specification and run Step 11 (BDD linker) to bind each scenario to
the task that should turn it green.

## Related Documents

- Scope: `docs/FEAT-FG-001-scope.md`
- Build plan: `docs/FEAT-FG-001-build-plan.md`
- Architecture: `docs/architecture.md`
- Existing implementations referenced: `openwebui/nats_fleet_pipe.py`, `reachy/external_content/external_tools/query_student_model.py`
