# Autobuild BDD-oracle infrastructure fix (FEAT-AB-FIX) — fleet-gateway slice

> Fix the four root causes of the FEAT-FG-001 unrecoverable stall, then resume the autobuild.

**Parent review:** [TASK-REV-8413](../TASK-REV-8413-analyse-autobuild-feat-fg-001-stall.md)
**Findings:** [docs/history/autobuild-FEAT-FG-001-review.md](../../../docs/history/autobuild-FEAT-FG-001-review.md)
**Sibling slice:** [`guardkit/tasks/backlog/autobuild-bdd-oracle-fix/`](../../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/)
— owns TASK-AB-001 / -003 / -004.

## Why This Exists

FEAT-FG-001's autobuild stalled with `unrecoverable_stall` on both Wave-2 tasks
(TASK-FG-002, TASK-FG-003) after 5 turns each of identical Coach feedback. The diagnostic
review proved the Player implementations were correct (all 21 ACs verified, 51 unit tests
passing, ruff/mypy clean) and isolated the failure to *oracle infrastructure*: the BDD
subprocess could not import the worktree's `common` package, the Coach feedback dropped the
real traceback, and the two parallel tasks raced on a single shared test module.

This feature fixes those four issues — three in guardkit, two here — so the autobuild can
resume cleanly.

## Subtask Summary (full feature, both repos)

| Task | Repo (location) | Wave | Mode | Complexity | Estimate | Summary |
|------|-----------------|------|------|-----------:|---------:|---------|
| [TASK-AB-001](../../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-001-pass-python-executable-to-bdd-runner.md) | **guardkit** | 1 | task-work | 3 | 30m | Orchestrator passes `python_executable=<worktree>/.venv/bin/python3` to `run_bdd_for_task`. |
| [TASK-AB-002](TASK-AB-002-add-pytest-bdd-to-dev-extras.md) | **fleet-gateway** (here) | 1 | direct | 1 | 10m | Add `pytest-bdd>=8.0` to `pyproject.toml [project.optional-dependencies].dev`. |
| [TASK-AB-003](../../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-003-surface-junit-error-in-coach-feedback.md) | **guardkit** | 1 | task-work | 4 | 60m | Surface junit `<error>` message in `BDDFailure.reason` and the Coach-to-Player feedback. |
| [TASK-AB-004](../../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-004-per-task-bdd-test-modules.md) | **guardkit** (+ fleet-gateway conftest) | 1 | task-work | 6 | 120m | bdd_runner sets `GUARDKIT_BDD_TASK_ID`; conftest collection bridge prefers per-task `test_<slug>__<TASK-ID>.py`. |
| [TASK-AB-005](../../in_review/autobuild-bdd-oracle-fix/TASK-AB-005-resume-and-verify-feat-fg-001.md) ✓ | **fleet-gateway** (here) | 2 | task-work | 2 | 30m | Migrate existing test module, run `--resume`, verify FG-002/FG-003 reach approved. **Done — in_review 2026-05-10.** |
| [TASK-AB-006](../../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/TASK-AB-006-fix-ac-linter-command-vs-path-parsing.md) | **guardkit** | 3 | task-work | 3 | 60m | AC-linter parses `pytest tests/foo.py` as a literal path; strip command prefix before existence check. New failure mode found by AB-005 resume. |

**Total:** 6 tasks · 3 waves · ~5h focused work.
**This slice:** TASK-AB-002 + TASK-AB-005 (the two fleet-gateway-side tasks).
TASK-AB-006 is in this README for traceability but is owned by the **guardkit** repo.

## Wave Layout

- **Wave 1** (parallel-safe across both repos): AB-001, AB-002, AB-003, AB-004 — no file
  overlap, no logical dependency. **Complete.**
- **Wave 2** (sequential, depends on all of Wave 1): AB-005 here in fleet-gateway —
  performs the resume and validates the fix. **Complete — see
  [autobuild-FEAT-FG-001-resume-run-2.md](../../../docs/history/autobuild-FEAT-FG-001-resume-run-2.md).**
- **Wave 3** (follow-up surfaced by AB-005): AB-006 in guardkit — fix the AC-linter
  command-vs-path parser bug that caused TASK-FG-004's `unrecoverable_stall`.

## Cross-Repo Layout

Each task lives in the repo where its work is done:

```
~/Projects/appmilla_github/
├─ guardkit/tasks/
│   ├─ backlog/autobuild-bdd-oracle-fix/
│   │   └─ TASK-AB-006-fix-ac-linter-command-vs-path-parsing.md   ← new (Wave 3)
│   └─ completed/2026-05/autobuild-bdd-oracle-fix/
│       ├─ TASK-AB-001-pass-python-executable-to-bdd-runner.md   ✓ merged 33f9db26
│       ├─ TASK-AB-003-surface-junit-error-in-coach-feedback.md  ✓ merged b0819556
│       └─ TASK-AB-004-per-task-bdd-test-modules.md              ✓ merged 00933c38
└─ fleet-gateway/tasks/
    ├─ backlog/autobuild-bdd-oracle-fix/                    ← you are here
    │   ├─ README.md
    │   └─ IMPLEMENTATION-GUIDE.md
    └─ in_review/autobuild-bdd-oracle-fix/
        └─ TASK-AB-005-resume-and-verify-feat-fg-001.md     ← completed 2026-05-10
```

(TASK-AB-002 was completed and moved out of `backlog/` here in commit `0d66b9d`.
TASK-AB-001/003/004 were completed and moved into `guardkit/tasks/completed/2026-05/`.)

Driving the work with `/task-work`:

```bash
# Guardkit slice — run from guardkit:
cd ~/Projects/appmilla_github/guardkit
/task-work TASK-AB-001
/task-work TASK-AB-003
/task-work TASK-AB-004

# Fleet-gateway slice — run from here:
cd ~/Projects/appmilla_github/fleet-gateway
/task-work TASK-AB-002
# wait for guardkit-side merges, then:
/task-work TASK-AB-005
```

## What Stays Untouched

- `common/jarvis_client.py`, `common/graphiti_client.py`, and the existing BDD test module
  in `.guardkit/worktrees/FEAT-FG-001/` are **correct and must not be regenerated**. AB-005
  only renames the test module; it does not re-author it.
- FEAT-FG-001's task graph is unchanged. AB-005's `--resume` picks up where Wave 2 stalled.

## See Also

- [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) — fleet-gateway-slice walkthrough.
- [Sibling guardkit slice README](../../../../guardkit/tasks/backlog/autobuild-bdd-oracle-fix/README.md) — TASK-AB-001 / -003 / -004.
- [docs/history/autobuild-FEAT-FG-001-fail-run-1.md](../../../docs/history/autobuild-FEAT-FG-001-fail-run-1.md) — original failure log.
- [docs/history/autobuild-FEAT-FG-001-review.md](../../../docs/history/autobuild-FEAT-FG-001-review.md) — diagnostic review report.
