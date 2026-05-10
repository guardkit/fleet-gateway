# FEAT-FG-001 Autobuild Stall — Diagnostic Review

- **Review task:** [TASK-REV-8413](../../tasks/backlog/TASK-REV-8413-analyse-autobuild-feat-fg-001-stall.md)
- **Feature:** [FEAT-FG-001 Fleet Gateway Common + Gateway Interfaces](../../.guardkit/features/FEAT-FG-001.yaml)
- **Worktree:** `.guardkit/worktrees/FEAT-FG-001`
- **Failure log:** [docs/history/autobuild-FEAT-FG-001-fail-run-1.md](autobuild-FEAT-FG-001-fail-run-1.md)
- **Verdict:** **Infrastructure / oracle misconfiguration.** Player implementation is correct;
  Coach feedback was non-actionable; `common` package not importable to the BDD subprocess.
- **Recommendation:** **REVISE** — fix the BDD-runner environment and Coach feedback fidelity,
  then resume. Do not let any retry overwrite the existing implementation.

---

## TL;DR

Both Wave-2 tasks (TASK-FG-002 Jarvis NATS client, TASK-FG-003 Graphiti client) finished
their implementation correctly:

- 11/11 (FG-002) and 10/10 (FG-003) acceptance criteria verified by Coach.
- 13/21 unit tests pass in the worktree's `.venv` (0.05 s, no I/O).
- ruff / mypy clean on every modified file.

But the Coach's BDD oracle failed every turn for the same non-Gherkin reason:

```
ImportError while importing test module
features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces.py:41
    from common.jarvis_client import JARVIS_TOPIC, JarvisClient
ModuleNotFoundError: No module named 'common'
```

That import error is a **pytest collection failure**, not an assertion failure on a Gherkin step.
The Coach surfaced it to the Player as the prose string *"BDD oracle: 1 scenario(s) failed during
pytest-bdd execution. Implementation does not satisfy the Gherkin specification"* — losing every
line of the actual traceback. The Player therefore had nothing actionable to fix; it kept editing
the implementation, which kept passing every other gate, which produced an identical Coach
feedback signature (`47fb7107`) for five turns, which fired the feedback-stall guard.

---

## 1. Failing scenario / failing step / failing assertion

| Source | Reported failing step | Reported failing reason |
|---|---|---|
| `coach_turn_5.json` (FG-002 & FG-003) | `step: collection failure` | `collection failure` |
| `task_work_results.json` → `bdd_results.failures[0]` | `failing_step: "collection failure"` | `reason: "collection failure"` |
| `coach_feedback_for_turn_4.json` | (no step) | *"BDD oracle: 1 scenario(s) failed during pytest-bdd execution. Implementation does not satisfy the Gherkin specification."* |
| `.guardkit/bdd/TASK-FG-002_junit.xml` (and FG-003) | **(real cause)** `<error message="collection failure">ImportError ... ModuleNotFoundError: No module named 'common'</error>` | Python import error at `test_*.py:41` |

So there is **no** failing Gherkin scenario or failing Gherkin step. The "1 scenario failed"
counter is the bdd-runner's synthetic representation of pytest exit code = collection error: it
emits a `BDDFailure(scenario_name=<feature path>, failing_step="collection failure",
reason="collection failure")` whenever the junit XML reports `errors > 0` with no parsable
`<failure>` block. The full traceback **is** in `.guardkit/bdd/TASK-FG-00{2,3}_junit.xml` but
never reaches the Coach feedback channel.

Reproduced today from `cd .guardkit/worktrees/FEAT-FG-001`:

```bash
pytest --gherkin-terminal-reporter --junitxml=/tmp/repro.xml \
       -m task_TASK_FG_002 \
       features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feature
# → 1 error in 0.13s
# → ModuleNotFoundError: No module named 'common'  (test file line 41)
```

The same import error reproduces for `-m task_TASK_FG_003`.

## 2. Root cause categorisation

**Primary class — Environment / infrastructure (oracle subprocess Python).**

The bdd-runner spawns pytest as a subprocess with `cwd=<worktree>` and **does not pass
`python_executable=<worktree>/.venv/bin/python3`** ([guardkit/orchestrator/quality_gates/bdd_runner.py:382-405](../../../guardkit/guardkit/orchestrator/quality_gates/bdd_runner.py)).
That subprocess therefore runs whichever `pytest` is on the orchestrator's `PATH` — on this
machine `~/.local/bin/pytest`, which has shebang `#!/usr/bin/python3`. That interpreter has
user-installed `pytest_bdd`, `nats-py`, `graphiti-core`, etc. — but **not** the worktree's
editable-installed `fleet-gateway` distribution (which is what exposes the `common` package).
Result: pytest-bdd's collection bridge ([features/conftest.py](../../.guardkit/worktrees/FEAT-FG-001/features/conftest.py))
imports the test module, which fails on its `from common.jarvis_client import …` line.

The worktree's own `.venv` has `fleet-gateway 0.1.0` editable-installed, so `python -c "import
common.jarvis_client"` succeeds there — but the BDD oracle never invokes that interpreter.

**Aggravating factor — pytest-bdd missing from the project's dev extras.** Even if the bdd-runner
*were* taught to pin to `<worktree>/.venv/bin/python3`, that interpreter still cannot collect
this test file because [pyproject.toml](../../.guardkit/worktrees/FEAT-FG-001/pyproject.toml)
lists only `pytest`, `pytest-asyncio`, `ruff`, `mypy` under `[project.optional-dependencies].dev`
— pytest-bdd is absent. The autobuild infrastructure expects pytest-bdd to be importable from the
worktree env (`bdd_runner.has_pytest_bdd` probe), but the pyproject doesn't declare it as a
dependency, so a fresh venv would not have it.

**Aggravating factor — Coach feedback drops the diagnostic payload.** The bdd-runner extracts a
faithful representation of the failure into `BDDResult.failures[i].reason`, but the orchestrator's
feedback summariser reduces every BDD failure to the same prose: *"BDD oracle: 1 scenario(s)
failed during pytest-bdd execution. Implementation does not satisfy the Gherkin specification."*
The Player never sees `ModuleNotFoundError: No module named 'common'`. The actual traceback lives
in `.guardkit/bdd/TASK-FG-002_junit.xml` but is never injected into the Player prompt.

**Aggravating factor — Wave-2 sibling-task collision in shared worktree.** TASK-FG-002 and
TASK-FG-003 ran in parallel against the same `.guardkit/worktrees/FEAT-FG-001/` tree. They share a
single `features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces.py`.
Each Player rewrites that file for *its* task only. The current file binds five
`@scenario(...)` decorators — all `@task:TASK-FG-002` scenarios. Even after the import bug is
fixed, **TASK-FG-003's BDD oracle would still collect zero scenarios** because no
`@scenario(...)` decorator targets a `@task:TASK-FG-003` scenario, and the marker `-m
task_TASK_FG_003` would deselect everything that *is* bound. The two tasks need either separate
test modules per task tag, or a single coordinated module that binds both task tags.

**Implementation bug?** No. Read on.

## 3. Why the implementation is *not* the cause

The Coach's own structured outputs validate this directly:

- All eleven AC entries for TASK-FG-002 are `verified` with concrete file/line evidence, and the
  thirteen unit tests under `tests/test_jarvis_client.py` pass deterministically (no NATS server
  required). [coach_turn_5.json](../../.guardkit/worktrees/FEAT-FG-001/.guardkit/autobuild/TASK-FG-002/coach_turn_5.json)
- All ten AC entries for TASK-FG-003 are `verified`; twenty-one unit tests under
  `tests/test_graphiti_client.py` pass (mocked Graphiti). [coach_turn_5.json](../../.guardkit/worktrees/FEAT-FG-001/.guardkit/autobuild/TASK-FG-003/coach_turn_5.json)
- `phase_4_summary.json`: *"pytest: 51 passed, 0 failed in 0.20s; coverage 95% (jarvis_client
  100%, envelope 94%, graphiti_client 94%)"*.
- `quality_gates`: `tests_passed=true, coverage_met=true, arch_review_passed=true,
  plan_audit_passed=true, all_gates_passed=true` on every multi-turn turn.

The hand-written code in
[`.guardkit/worktrees/FEAT-FG-001/common/jarvis_client.py`](../../.guardkit/worktrees/FEAT-FG-001/common/jarvis_client.py),
[`graphiti_client.py`](../../.guardkit/worktrees/FEAT-FG-001/common/graphiti_client.py), and
[`features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces.py`](../../.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces.py)
is consistent with the Gherkin scenarios for `@task:TASK-FG-002`. The BDD step definitions
themselves are well-formed — every `@given` / `@when` / `@then` referenced by the five FG-002
scenarios has a matching binding in the test module.

## 4. The self-reinforcing feedback-stall loop

The five turns produced one stable feedback signature (`sig=47fb7107`):

```
1. Advisory (non-blocking): task-work produced a report with 2 of 3 expected agent
   invocations. Missing phases: 3 (Implementation). …
2. BDD oracle: 1 scenario(s) failed during pytest-bdd execution.
   Implementation does not satisfy the Gherkin specification.
```

Trace, per turn:

1. Coach runs bdd-runner → import error → collection failure → synthetic
   `BDDFailure(reason="collection failure")`.
2. Coach feedback summariser strips the traceback, emits the prose `BDD oracle: …` line.
3. Player reads "implementation does not satisfy the Gherkin spec", but every AC is verified and
   every unit test passes. The Player has no signal about *what* to change — it cannot see the
   `ModuleNotFoundError`. Pre-Phase-3 specialist invocation is also flagged advisory, so it
   tinkers with implementation files instead of investigating the oracle.
4. Player makes cosmetic / refactoring edits (turn 5: 3 created, 42 modified across both tasks)
   and re-submits.
5. The shared worktree state, the test file, and the collection error are all unchanged → Coach
   re-runs bdd-runner → identical collection failure → identical feedback signature
   `47fb7107`.

The feedback-stall guard fires after five identical signatures with ≥10 verified criteria,
treating it as "partial progress with stuck feedback" and aborting both tasks as
`unrecoverable_stall`. The guard did exactly what it should have done — the diagnostic gap is
upstream of it.

A second, less-visible stall driver: when the Coach also runs `pytest
features/.../test_fleet_gateway_common_and_interfaces.py -v --tb=short` as the
`independent_tests` probe and reports `5 passed, 11 warnings in 0.09s`, this *cannot be true* in
the same environment that the bdd-runner uses — re-running that exact command today reproduces
the same `ModuleNotFoundError`. Either the independent-tests subprocess inherits a
`PYTHONPATH=.`-style environment that bdd-runner does not, or the result was generated from a
prior session and reused. Whichever, it gave the Coach false confidence that the test file
imports cleanly, which is why the Coach kept marking every AC `verified` and never escalated the
import error itself.

## 5. Concrete remediation plan

Three edits unblock the feature. They should land in this order so a `--resume` (or fresh run)
sees a green oracle:

### Edit A — Pin bdd-runner subprocess to the worktree venv (guardkit fix)

In [`guardkit/orchestrator/quality_gates/bdd_runner.py:435`](../../../guardkit/guardkit/orchestrator/quality_gates/bdd_runner.py)
the orchestrator must always invoke `run_bdd_for_task` with
`python_executable=<worktree>/.venv/bin/python3` (or whichever venv `pip install -e ".[dev]"`
populated). The runner already plumbs `python_executable` through `_invoke_pytest_bdd` — it
just isn't being filled in by the caller. Locate the orchestrator's bdd-runner caller and pass
the worktree-resolved interpreter. Without this, the collection bridge in `features/conftest.py`
will keep importing the test module under the wrong interpreter and the same
`ModuleNotFoundError` will recur on every retry.

### Edit B — Add pytest-bdd to the project's dev extras

Add `"pytest-bdd>=8.0"` to [`pyproject.toml`](../../.guardkit/worktrees/FEAT-FG-001/pyproject.toml)
under `[project.optional-dependencies].dev`, then re-run `pip install -e ".[dev]"` inside
`<worktree>/.venv` so the runner's `has_pytest_bdd` probe succeeds against the same interpreter
that imports `common`. (The repo-root pyproject also needs the same edit so non-worktree
local runs work.) Once Edit A is in place, the *worktree* venv must contain pytest-bdd or the
runner falls back to the synthetic "pytest_bdd_not_importable" failure.

### Edit C — Enrich Coach feedback with the junit traceback

Independently of A/B, the bdd-runner's `BDDFailure.reason` for collection errors should carry
the first `<error>` `message` and inner traceback line from junit XML rather than the literal
string `"collection failure"`. The orchestrator's feedback summariser should pass that string
through verbatim. This turns "Implementation does not satisfy the Gherkin specification" (which
mis-describes what happened) into something like:

```
BDD oracle collection error in test_fleet_gateway_common_and_interfaces.py:41:
ModuleNotFoundError: No module named 'common'
```

— which any future Player can act on directly. This change is what makes the system robust
against the next class of oracle misconfiguration; without it, the next infra blip will produce
exactly the same five-turn cosmetic-edit stall.

### Edit D — Plan-level fix for the Wave-2 shared-test-file collision

Even after A/B/C, parallel Wave-2 tasks each writing to a *single* shared
`test_fleet-gateway-common-and-interfaces.py` will keep racing. Two options:

1. **Per-task test modules.** Have the bdd-runner accept either `test_<slug>.py` or
   `test_<slug>__<task_id>.py` and have each task's Player write its own task-suffixed test
   module. The conftest's collection bridge would need to round-robin candidate glue paths.
2. **One coordinated test module owned by the upstream task.** Move BDD wiring out of FG-002 /
   FG-003 and into FG-001 (which already passed first-attempt), making FG-001 responsible for
   binding *every* `@task:TASK-FG-00*` scenario. FG-002 / FG-003 then deliver only the
   implementation files and unit tests, and the BDD oracle reads against the FG-001-owned
   module. This keeps the task graph but removes the shared-file race.

I recommend option 2 for this hackathon — option 1 is the longer-term design but requires
guardkit changes; option 2 only needs a feature-plan re-shape (move all `@scenario` decorators
into FG-001's deliverables) and a small task-spec amendment. Without **either** option, even
a perfectly green resume of FG-002 will leave FG-003's BDD oracle facing a "0 scenarios
collected" failure mode (the bindings written by the FG-002 Player do not satisfy the
`-m task_TASK_FG_003` filter).

## 6. Decision

| Option | Outcome |
|---|---|
| **Resume now (`autobuild feature FEAT-FG-001 --resume`)** | ❌ Will re-stall — same import error. |
| **Revise (apply Edits A + B at minimum, then resume)** | ✅ Recommended. Implementation is intact; only the oracle environment is broken. |
| **Manual completion of FG-002/003 outside autobuild** | ⚠️ Possible — the work product is already correct. But this loses the guardkit gating evidence and orphans the Wave-2 BDD coverage. |
| **Abandon the feature run** | ❌ Wasteful — none of the implementation needs redoing. |

**Recommended decision: REVISE.**

Apply Edits A and B at minimum (orchestrator caller passes `python_executable`; pytest-bdd added
to dev extras). Edit C (feedback fidelity) and Edit D (Wave-2 plan re-shape) are strongly
encouraged but not strictly required for FG-002 alone — FG-002's resume will pass once A+B are in
place because the existing test file already binds the FG-002 scenarios. FG-003 will need
Edit D before its BDD oracle can collect any scenarios.

Resume command after A + B: `guardkit autobuild feature FEAT-FG-001 --resume` (do **not** pass
flags that would discard the existing worktree state — the Player implementations in
`common/jarvis_client.py` and `common/graphiti_client.py` are correct and must be preserved).

## 7. Cross-references

- Failure log: [docs/history/autobuild-FEAT-FG-001-fail-run-1.md](autobuild-FEAT-FG-001-fail-run-1.md)
- Worktree autobuild artefacts: `.guardkit/worktrees/FEAT-FG-001/.guardkit/autobuild/TASK-FG-00{2,3}/`
  - `coach_turn_{1..5}.json`, `coach_feedback_for_turn_{2,4}.json`, `task_work_results.json`,
    `specialist_results.json`, `phase_4_summary.json`, `turn_state_turn_{1..5}.json`
- BDD junit XML (carries the *real* traceback the Coach feedback dropped):
  - `.guardkit/worktrees/FEAT-FG-001/.guardkit/bdd/TASK-FG-002_junit.xml`
  - `.guardkit/worktrees/FEAT-FG-001/.guardkit/bdd/TASK-FG-003_junit.xml`
- Implementation under review (intact, do not regenerate):
  - [`common/jarvis_client.py`](../../.guardkit/worktrees/FEAT-FG-001/common/jarvis_client.py)
  - [`common/graphiti_client.py`](../../.guardkit/worktrees/FEAT-FG-001/common/graphiti_client.py)
  - [`features/.../test_fleet_gateway_common_and_interfaces.py`](../../.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/test_fleet_gateway_common_and_interfaces.py)
- bdd-runner source: [`guardkit/guardkit/orchestrator/quality_gates/bdd_runner.py`](../../../guardkit/guardkit/orchestrator/quality_gates/bdd_runner.py)
