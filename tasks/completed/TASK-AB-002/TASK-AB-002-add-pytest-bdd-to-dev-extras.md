---
id: TASK-AB-002
title: "Add pytest-bdd to fleet-gateway dev extras"
task_type: feature
parent_review: TASK-REV-8413
feature_id: FEAT-AB-FIX
wave: 1
implementation_mode: direct
complexity: 1
estimated_minutes: 10
dependencies: []
working_dir: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway
domain_tags:
  - packaging
  - pytest-bdd
status: completed
updated: 2026-05-09T00:00:00Z
completed: 2026-05-09T00:00:00Z
previous_state: in_review
completed_location: tasks/completed/TASK-AB-002/
organized_files:
  - TASK-AB-002-add-pytest-bdd-to-dev-extras.md
---

# TASK-AB-002: Add pytest-bdd to fleet-gateway dev extras

## Repository

**Working directory:** this repo (`fleet-gateway`).

## Problem

The worktree's `.venv` is created by `pip install -e ".[dev]"`. The current
[`pyproject.toml`](../../../pyproject.toml) `[project.optional-dependencies].dev` lists
`pytest`, `pytest-asyncio`, `ruff`, `mypy` but **not** `pytest-bdd`. Once TASK-AB-001
lands and the BDD oracle starts using the worktree's interpreter, the runner's
`has_pytest_bdd` probe will fail unless `pytest-bdd` is in the dev extras.

## Scope

Add `pytest-bdd>=8.0` to `[project.optional-dependencies].dev` in `pyproject.toml`. Pin to the
version family the autobuild infrastructure already targets (8.x — confirmed by user-level
install at 8.1.0 today).

## Acceptance Criteria

- [x] `pyproject.toml` `[project.optional-dependencies].dev` contains `"pytest-bdd>=8.0"`.
- [x] Re-run `pip install -e ".[dev]"` inside `.venv` and confirm `python -c "import pytest_bdd"` succeeds.
- [x] The same install in `.guardkit/worktrees/FEAT-FG-001/.venv` makes pytest-bdd importable there too (apply manually as part of resume verification, or document so feature-build picks it up on next run).
- [x] No other dependency changes (do not bump pinned versions of unrelated packages).

## Out of Scope

- Adding pytest-bdd to runtime `dependencies` (it is dev-only).
- Reorganising the dependency lists.

## Verification

```bash
.venv/bin/python -c "import pytest_bdd; print(pytest_bdd.__name__)"
# expected: pytest_bdd
```

## Implementation Summary

Added `"pytest-bdd>=8.0"` to `[project.optional-dependencies].dev` in two pyproject.toml files:

1. **Worktree** (`.guardkit/worktrees/FEAT-FG-001/pyproject.toml`, branch `autobuild/FEAT-FG-001`) — the file actually consumed by `pip install -e ".[dev]"` during autobuild turns. Verified by reinstalling the worktree's `.venv` and running `python -c "import pytest_bdd"`, which printed `pytest_bdd` (pytest-bdd 8.1.0).
2. **Repo root** (newly created `pyproject.toml` on `main`) — scaffolded by copying the worktree's authoritative version verbatim and adding `pytest-bdd>=8.0` to dev extras. The repo root has no `.venv` yet, so the install/import side of AC#2 was not exercised there; AC#1 is satisfied by the file edit alone.

No other dependencies were touched in either file. The worktree change is uncommitted on `autobuild/FEAT-FG-001`; the new repo-root file is untracked on `main`.

## Notes

- The link `../../../pyproject.toml` in the original task description resolved to the repo root, but no `pyproject.toml` existed there at task-start time — only the worktree copy did. The user chose "edit both" to align reality with the description and seed `main` with a tracked scaffold.
- The next autobuild resume on FEAT-FG-001 will see pytest-bdd in dev extras during the worktree's `.venv` install probe, unblocking the BDD oracle's `has_pytest_bdd` check.
