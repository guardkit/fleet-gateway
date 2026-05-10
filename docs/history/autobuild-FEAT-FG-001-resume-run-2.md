# FEAT-FG-001 Autobuild Resume — Run 2 (Wave 2 verification)

- **Verification task:** [TASK-AB-005](../../tasks/in_review/autobuild-bdd-oracle-fix/TASK-AB-005-resume-and-verify-feat-fg-001.md)
- **Feature:** [FEAT-FG-001 Fleet Gateway Common + Gateway Interfaces](../../.guardkit/features/FEAT-FG-001.yaml)
- **Worktree:** `.guardkit/worktrees/FEAT-FG-001` (preserved)
- **Prior failure:** [autobuild-FEAT-FG-001-fail-run-1.md](autobuild-FEAT-FG-001-fail-run-1.md)
- **Diagnostic review:** [autobuild-FEAT-FG-001-review.md](autobuild-FEAT-FG-001-review.md)
- **Resume started:** 2026-05-10T06:43Z
- **Resume ended:** 2026-05-10T07:38Z (~55 min wall clock; 5 of 6 tasks ran in parallel waves)
- **Verdict:** **Wave 2 verification target met.** Both Wave 1 root causes (the four AB fixes)
  are confirmed resolved. Wave 3 surfaced an unrelated AC-linter parsing bug — captured
  separately as [TASK-AB-006](../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-006-fix-ac-linter-command-vs-path-parsing.md).

---

## TL;DR

The four Wave-1 fixes (AB-001/002/003/004) work as designed. The Player keeps writing the
implementation correctly; the BDD oracle now actually executes inside the worktree's venv,
the Coach feedback now carries the actual junit error string, and parallel tasks no longer
race on a shared test module. Wave 2 (FG-002, FG-003) reached `final_decision: approved` —
the explicit "or at least Wave 2 tasks reach approved" branch of TASK-AB-005's primary AC.

The feature itself ended at `status: failed` because TASK-FG-004 stalled after 3 turns with
`unrecoverable_stall`. Root cause is **not** a Wave-1 issue: the Coach AC-linter is parsing
the AC-cited string `pytest tests/test_openwebui_pipe.py` as a single literal file path
instead of as a command-plus-argument. The actual test file *does* exist on disk (14 tests
passing in the regression run); the linter rejects every Player turn before
`run_independent_tests` can prove it.

---

## Per-task outcomes

| Task | Wave | Result | Player turns | First-turn BDD | Final BDD | Notes |
|---|---|---|---:|---|---|---|
| TASK-FG-001 | 1 | (already approved) | — | — | — | Skipped — completed before stall. |
| **TASK-FG-002** | **2** | ✅ **approved** | 1 | passed=5 failed=0 | passed=5 | First-turn pass — per-task glue migration (AB-005 step 1) plus AB-001/002 fix unblocked it cleanly. |
| **TASK-FG-003** | **2** | ✅ **approved** | 4 | passed=0 failed=1 | passed=9 failed=0 | Player took 3 turns to write `test_<slug>__TASK_FG_003.py`; stall-extender (TASK-GK-COACH-001) bought the 4th turn. |
| TASK-FG-004 | 3 | ✗ unrecoverable_stall | 3 | n/a (AC-linter short-circuit) | n/a | Out of TASK-AB-005 scope. New failure mode — see [TASK-AB-006](../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-006-fix-ac-linter-command-vs-path-parsing.md). |
| TASK-FG-005 | 3 | ✅ approved | 2 | passed=0 failed=1 | passed=4 failed=0 | Same per-task-glue recovery pattern as FG-003, faster. |
| TASK-FG-006 | 3 | ✅ approved | 2 | passed=0 failed=1 | passed=2 failed=0 | Same. |

5 of 6 tasks `approved`. Wave 3 has TASK-FG-004 to revisit, but FG-005 (Scholar) and
FG-006 (Bridge) — the hackathon critical path — are through.

---

## Wave-1 fix verification

The autobuild log was filtered for the four fix signatures. All four are confirmed working
end-to-end:

### AB-001 — orchestrator passes `python_executable` to bdd_runner

Every BDD oracle invocation logs:

```
INFO:guardkit.orchestrator.agent_invoker:BDD oracle invoking run_bdd_for_task for TASK-FG-XXX
  with python_executable=/.../.guardkit/worktrees/FEAT-FG-001/.venv/bin/python3
```

The worktree venv's interpreter is used — not the system python. ✅

### AB-002 — `pytest-bdd>=8.0` in dev extras

Pre-flight check before running the resume:

```
.venv/bin/python -c "import pytest_bdd; import common.jarvis_client" → both succeed
```

Plus pytest itself was able to collect-and-run; **zero occurrences of
`BDDFailure(reason="collection failure")` across the entire log**. ✅

### AB-003 — junit error surfaced into Coach feedback

Every BDD failure on Wave 2/3 now logs the actual stderr/stdout:

```
WARNING: BDD runner for TASK-FG-XXX: pytest exited with 4 and produced no testcases;
  surfacing as synthetic failure. First 200 chars of stderr/stdout:
  'ERROR: not found: /.../fleet-gateway-common-and-interfaces.feature'
```

The `passed=0 failed=1` synthetic failure carries the literal pytest error string into
`BDDFailure.reason` and on into the Coach-to-Player feedback — exactly the fidelity gap the
TASK-REV-8413 review called out. ✅

### AB-004 — per-task BDD glue lookup via `GUARDKIT_BDD_TASK_ID`

Both `features/conftest.py` (worktree-side, fleet-gateway slice of AB-004) and the
`bdd_runner` (guardkit slice) cooperate. After the resume:

```
.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/
├── test_fleet_gateway_common_and_interfaces__TASK_FG_002.py   (renamed by AB-005 step 1)
├── test_fleet_gateway_common_and_interfaces__TASK_FG_003.py   (created by Player turn 4)
├── test_fleet_gateway_common_and_interfaces__TASK_FG_005.py   (created by Player turn 2)
└── test_fleet_gateway_common_and_interfaces__TASK_FG_006.py   (created by Player turn 2)
```

Four parallel tasks, four distinct test modules — no shared-module race. ✅

---

## Regression check (worktree)

Run from `.guardkit/worktrees/FEAT-FG-001` after the autobuild completed:

| Check | Result |
|---|---|
| `pytest tests/ -v` | **93 passed in 0.09s** (51+ threshold met) |
| `ruff check common/ openwebui/ reachy/ tests/` | **All checks passed** (clean) |
| `mypy common/ openwebui/ reachy/` | **Success: no issues found in 10 source files** |

The 3 pre-existing ruff `UP035`/`UP006` warnings in `features/conftest.py` (`typing.List`
modernisation) are isolated to the AB-004 BDD harness; no implementation code regressed.

---

## New failure modes worth following up

These are *not* AB-001/002/003/004 regressions — they're issues TASK-AB-005 surfaced for the first time. None of them affect the Wave 2 verification target.

### 1. Coach AC-linter parses commands as paths (TASK-AB-006)

Coach decision JSON for FG-004 turn 3:

```json
{
  "issues": [{
    "severity": "must_fix",
    "category": "acceptance_criteria",
    "description": "AC names test file(s) that don't exist on disk: pytest tests/test_openwebui_pipe.py.",
    "details": { "missing_test_files": ["pytest tests/test_openwebui_pipe.py"] }
  }]
}
```

The linter (TASK-GK-PR-001 preflight check) is treating the literal string
`pytest tests/test_openwebui_pipe.py` as a single file path. It's actually a *command*
(`pytest <file>`); the file `tests/test_openwebui_pipe.py` exists in the worktree and runs
14 tests cleanly. With no passing checkpoint and the same feedback hash on every turn, the
orchestrator declares `unrecoverable_stall` after 3 turns. Tracked as
[TASK-AB-006](../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-006-fix-ac-linter-command-vs-path-parsing.md).

### 2. Documentation-level constraint violations (warning, non-blocking)

Wave 3 Players each hit:

```
WARNING: [TASK-FG-XXX] Documentation level constraint violated: created N files,
  max allowed 2 for minimal level.
```

The `--docs=minimal` cap of 2 files conflicts with tasks that legitimately need to create
multiple files (profile config + tools + tests). The orchestrator logs a warning but does
not act on it. Worth deciding whether this warning is informational or whether the
constraint should be enforced.

### 3. Recurring `SDK coach test execution failed (exit code 1)`

Every Coach validation turn logs:

```
ERROR: SDK coach test execution failed (error_class=Exception):
  Command failed with exit code 1 (exit code: 1)
```

Despite the error, Coach still produces approve/reject decisions (the BDD oracle drives the
gate). The error is emitted from `coach_validator.run_independent_tests` and appears to be
a transient internal-subprocess fault. It didn't cause any false rejections in this run,
but it's noise in the log and worth diagnosing.

---

## Acceptance-criteria summary (TASK-AB-005)

| AC | Result |
|---|---|
| FEAT-FG-001 status `completed` *or* Wave 2 tasks `approved` | ✅ Wave 2 (FG-002 + FG-003) approved. Feature `failed` due to FG-004 (out of scope). |
| No turn produces `BDDFailure(reason="collection failure")` | ✅ Zero occurrences across the entire log. |
| Coach feedback for any remaining BDD failure carries actual junit error string | ✅ All synthetic BDD failures emit `First 200 chars of stderr/stdout: '...'`. |
| Both `..._TASK_FG_002.py` and `..._TASK_FG_003.py` exist in the worktree | ✅ Both present (and `..._TASK_FG_005.py`, `..._TASK_FG_006.py`). |
| No regressions: 51+ unit tests still pass; ruff + mypy clean | ✅ 93 unit tests pass; ruff/mypy clean on implementation dirs. |
| If resume fails, root cause is *not* a Wave-1 issue | ✅ FG-004 stall = AC-linter parsing bug, distinct from AB-001/002/003/004. Captured in TASK-AB-006. |

All six acceptance criteria satisfied. TASK-AB-005 → `in_review`.
