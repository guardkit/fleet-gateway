---
id: TASK-AB-005
title: "Resume FEAT-FG-001 autobuild and verify TASK-FG-002/003 complete"
task_type: feature
parent_review: TASK-REV-8413
feature_id: FEAT-AB-FIX
wave: 2
implementation_mode: task-work
complexity: 2
estimated_minutes: 30
dependencies:
  - TASK-AB-001
  - TASK-AB-002
  - TASK-AB-003
  - TASK-AB-004
working_dir: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway
domain_tags:
  - autobuild
  - resume
  - verification
status: in_review
verified_at: '2026-05-10T07:38:00Z'
verification_notes: |
  Wave 2 (FG-002, FG-003) approved. All six acceptance criteria satisfied.
  See docs/history/autobuild-FEAT-FG-001-resume-run-2.md.
  Wave 3 surfaced a new failure mode (FG-004 AC-linter stall) — tracked in TASK-AB-006.
---

# TASK-AB-005: Resume FEAT-FG-001 autobuild and verify completion

## Repository

**Working directory:** this repo (`fleet-gateway`).

## Pre-flight (must be true before starting)

- [ ] TASK-AB-001 merged in guardkit (orchestrator passes `python_executable`).
- [ ] TASK-AB-002 merged here (`pytest-bdd>=8.0` in dev extras).
- [ ] TASK-AB-003 merged in guardkit (junit error in feedback).
- [ ] TASK-AB-004 merged in guardkit + fleet-gateway conftest updated (per-task glue).
- [ ] Worktree's `.venv` re-installed: `cd .guardkit/worktrees/FEAT-FG-001 && .venv/bin/pip install -e ".[dev]"` and `.venv/bin/python -c "import pytest_bdd; import common.jarvis_client"` succeeds.

## Scope

1. **Migrate the existing shared test module to its task-specific name** so Edit D (per-task glue)
   works for the resume:
   ```bash
   cd .guardkit/worktrees/FEAT-FG-001
   git mv features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces.py \
          features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces__TASK_FG_002.py
   ```
   Note: the task ID sanitisation drops the hyphen between `TASK` and `FG` (per AB-004
   contract). Verify the actual sanitised form before running.

2. **Pre-flight smoke test** the BDD oracle locally for both tasks:
   ```bash
   cd .guardkit/worktrees/FEAT-FG-001
   GUARDKIT_BDD_TASK_ID=TASK-FG-002 \
     .venv/bin/pytest --gherkin-terminal-reporter \
       -m task_TASK_FG_002 \
       features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feature
   # Expected: 5 scenarios passed.

   GUARDKIT_BDD_TASK_ID=TASK-FG-003 \
     .venv/bin/pytest --gherkin-terminal-reporter \
       -m task_TASK_FG_003 \
       features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feature
   # Expected: 0 scenarios collected initially (Player will write the FG-003 glue on resume).
   # OR: error explicitly stating the per-task glue file is missing.
   ```

3. **Resume the autobuild**:
   ```bash
   cd /home/richardwoollcott/Projects/appmilla_github/fleet-gateway
   guardkit autobuild feature FEAT-FG-001 --resume
   ```
   Do **not** pass any flag that discards the existing worktree state. The `common/`
   implementation files must be preserved.

4. **Monitor and verify**: watch the run log; confirm:
   - TASK-FG-002 reaches `final_decision: approved`.
   - TASK-FG-003 reaches `final_decision: approved` (the Player will write the
     `test_<slug>__TASK_FG_003.py` glue on its first turn now that AB-004 is in place).
   - No `unrecoverable_stall`, no `feedback_stall`.
   - Wave 3 tasks (FG-004/005/006) start once Wave 2 completes.

## Acceptance Criteria

- [ ] FEAT-FG-001 reaches `status: completed` (or at least Wave 2 tasks reach `approved`).
- [ ] No turn produces `BDDFailure(reason="collection failure")` — confirms AB-001 + AB-002 fixed the import.
- [ ] The Coach feedback for any remaining BDD failure carries the actual error string from junit XML — confirms AB-003 is wired up.
- [ ] Both `test_fleet_gateway_common_and_interfaces__TASK_FG_002.py` and `..._TASK_FG_003.py` exist in the worktree at the end of the run — confirms AB-004 unblocks parallel writes.
- [ ] No regressions in the implementation: 51+ unit tests still pass; ruff + mypy clean.
- [ ] If the resume fails, root cause is *not* one of the four issues fixed in Wave 1 (capture the new failure mode for follow-up).

## Out of Scope

- Wave 3 task implementation (FG-004 OpenWebUI refactor, FG-005 Scholar, FG-006 Bridge) — those
  run on their own but are not the verification target of this task.
- Reverting the implementation files in `common/` — they are intact and should stay.

## Verification

After autobuild completes:
```bash
cat .guardkit/features/FEAT-FG-001.yaml | grep -E "status|final_decision"
ls .guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/test_*.py
.venv/bin/pytest tests/ -v
```
