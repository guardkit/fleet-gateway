---
id: TASK-REV-3078
title: "Design e2e test runbook for FEAT-FG-001"
task_type: review
priority: high
status: review_complete
feature_id: FEAT-FG-001
mode: decision
depth: standard
created: 2026-05-10
review_results:
  mode: decision
  depth: standard
  decision: three-thin-per-gateway-runbooks
  strategy_doc: docs/FEAT-FG-001-e2e-test-strategy.md
  report_path: .claude/reviews/TASK-REV-3078-review-report.md
  operator_priority: quality-over-deadline
  recommendations_count: 5
  next_step: spawn three runbook-authoring tasks (see strategy §10.2)
  completed_at: 2026-05-10
tags:
  - e2e
  - testing
  - runbook
  - feat-fg-001
  - hackathon
context_files:
  - docs/FEAT-FG-001-scope.md
  - docs/FEAT-FG-001-build-plan.md
  - tasks/completed/TASK-FG-001-package-setup-envelope-module.md
  - tasks/completed/TASK-FG-002-jarvis-nats-client.md
  - tasks/completed/TASK-FG-003-graphiti-client.md
  - tasks/completed/TASK-FG-004-openwebui-pipe-refactor.md
  - tasks/completed/TASK-FG-005-scholar-tools-and-profile.md
  - tasks/completed/TASK-FG-006-bridge-profile-agent-status.md
external_references:
  - /home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/
  - /home/richardwoollcott/Projects/appmilla_github/agentic-dataset-factory/domains/architect-agent/RUNBOOK-architect-dataset-pipeline.md
  - /home/richardwoollcott/Projects/appmilla_github/guardkit/docs/guides/falkordb-nas-deployment-runbook.md
  - /home/richardwoollcott/Projects/appmilla_github/guardkit/docs/research/dgx-spark/RUNBOOK-v3-production-deployment.md
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Review: Design e2e test runbook for FEAT-FG-001

## Description

FEAT-FG-001 (Fleet Gateway Common + Gateway Interfaces) is implementation-complete:
all six wave tasks (TASK-FG-001 through TASK-FG-006) have landed in `completed/`.
Unit tests cover the `common/` module, `JarvisClient`, `GraphitiClient`, and the
Reachy tool wiring with mocks. What does **not** exist is a verified e2e path
proving that:

1. Open WebUI's `nats_fleet_pipe.py` reaches a real Jarvis over real NATS,
2. The Reachy Scholar `query_student_model` tool reads real student data from
   FalkorDB-on-`whitestocks` via `graphiti-core`,
3. The Reachy Bridge `agent_status` tool gets a sensible narrated reply
   from Jarvis through `JarvisClient.send_command()`.

This task **does not implement** any tests. It is a decision-mode review that
produces (a) a chosen e2e test strategy, (b) the structure and contents of the
runbook(s) Claude Code will execute, and (c) the success criteria / evidence
artefacts each runbook run must produce.

## Stated Preference (from request)

The user's preferred mechanism is **runbooks executed by Claude Code**, mirroring
the proven pattern from:

- `jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` and
  `RUNBOOK-jarvis-architect-align-dddsw-demo.md` — Forge/Architect e2e verification.
- `agentic-dataset-factory/domains/architect-agent/RUNBOOK-architect-dataset-pipeline.md` —
  llama-swap setup, infrastructure provisioning, OpenWebUI with per-subject
  system prompts.
- `guardkit/docs/guides/falkordb-nas-deployment-runbook.md` — Synology/FalkorDB
  deployment via Tailscale.
- `guardkit/docs/research/dgx-spark/RUNBOOK-v3-production-deployment.md` — phased
  pre-flight → execute → validate runbook with gap-back-fill from RESULTS docs.

**Common shape across those runbooks:**

- Phase 0 pre-flight (env, tools, network, models on disk).
- Numbered phases with copy-paste bash + `# Expected: …` annotations.
- Long-running steps wrapped in `tmux` so the runbook survives SSH disconnect.
- Companion `RESULTS-…md` doc that captures live output and gaps; gaps fold
  back into the runbook (see `RUNBOOK-v3` → "Runbook gaps discovered while
  executing", `TASK-RUN-D6F4`).
- A clear teardown / cleanup phase.

The review must decide whether one runbook or several, what each phase looks
like, and how Claude Code executes/monitors them.

## Investigation Goals

1. **Map FEAT-FG-001 e2e surface area.** Enumerate every external dependency
   touched by the three gateway interfaces (OpenWebUI pipe, Scholar tools,
   Bridge tools): NATS broker, Jarvis agent, FalkorDB on `whitestocks`,
   `graphiti-core`, llama-swap on `:9000`, OpenWebUI container on GB10,
   Tailscale mesh, Reachy MacBook environment. For each, identify what
   "ready" means and the cheapest probe to confirm it.

2. **Decide runbook granularity.** Choose one of:
   - **One mega-runbook** covering all three gateways end-to-end in a single
     run (high signal, slow, single failure cascade).
   - **Three thin runbooks** — one per gateway path (OpenWebUI, Scholar,
     Bridge) — each independently runnable from a shared pre-flight phase.
   - **Two runbooks** — `RUNBOOK-fleet-gateway-infra.md` (provision &
     verify NATS/FalkorDB/llama-swap/Jarvis) plus `RUNBOOK-fleet-gateway-e2e.md`
     (exercise the three gateway flows once infra is up).
   - Recommend the option that best matches the v3-production / dataset-pipeline
     pattern the user has had success with, and justify the choice.

3. **Define the phases.** For the chosen structure, list each phase with:
   - Pre-flight checks (what must be true before the phase runs).
   - The exact commands Claude Code will execute (or template thereof).
   - Expected output / verification (`# Expected: …`).
   - The failure-mode dispatcher (what to do if a check fails — e.g.
     "if `nats-cli sub` returns no subjects, jump to Phase 1.4 to start
     the broker").

4. **Specify the e2e probes per gateway.** Concrete, scriptable assertions:
   - **OpenWebUI pipe:** post a chat to the deployed OpenWebUI, verify the
     pipe constructs a `CommandPayload`, NATS-publishes to
     `agents.command.jarvis`, and the response surfaces in the OpenWebUI UI.
     Verification: parse `docker logs open-webui` for the correlation_id;
     `nats sub 'agents.command.jarvis'` from a side terminal proves the
     envelope contents.
   - **Scholar `query_student_model`:** invoke the tool standalone (without
     Pollen) against `student-lilymay` in FalkorDB on `whitestocks`; assert
     the returned dict has `data_available=True`, an integer `streak_days`,
     and a non-empty `topic_confidence`. Then run inside Pollen with
     Gemini Live and confirm the LLM narrates progress.
   - **Bridge `agent_status`:** invoke the tool against a live Jarvis on
     GB10; assert the returned text mentions at least one fleet agent the
     supervisor knows about. Confirm graceful degradation when NATS is
     stopped.

5. **Decide the evidence artefact format.** Match the jarvis runbook pattern:
   each runbook execution produces a dated `RESULTS-feat-fg-001-e2e-<date>.md`
   capturing pass/fail per phase, raw output excerpts, and gaps. Decide
   where the results docs live (`fleet-gateway/docs/runbooks/results/`?
   `tasks/.../evidence/`?) and how findings flow back into the runbook.

6. **Map the Claude Code execution loop.** How will the agent actually run
   these — interactive `/loop` against the runbook? A new `/runbook-execute`
   command? A plain "read this file and execute each phase, recording
   results" prompt? Whatever is chosen, it must work without bespoke
   tooling for the hackathon timeline.

7. **Identify what e2e cannot cover.** Cloud voice (OpenAI Realtime / Gemini
   Live), Reachy hardware emotions, deployed OpenWebUI auth — flag the
   parts that stay manual and document the human-in-the-loop checkpoints.

## Acceptance Criteria

- [ ] **Surface mapped:** every external dependency for the three gateway
      paths is listed with its "ready" probe (one-liner per dep).
- [ ] **Granularity chosen:** one of {1 / 2 / 3} runbooks selected with
      explicit pros/cons and a recommendation, justified against the
      jarvis + dataset-factory + v3-production patterns the user cited.
- [ ] **Runbook outline produced:** for each chosen runbook, a phase-by-phase
      table or skeleton (Phase number, name, intent, key commands, expected
      output) — *not* the full bash, but enough that an implementation task
      can fill in the verbatim commands without re-deciding structure.
- [ ] **Probes specified:** per gateway (OpenWebUI / Scholar / Bridge),
      the exact assertion(s) that constitute "e2e green".
- [ ] **Evidence convention agreed:** `RESULTS-…md` location, naming, and
      back-fill rule (how gaps discovered during execution land back in
      the runbook — explicit reference to the v3-production gap-back-fill
      precedent).
- [ ] **Execution loop defined:** how Claude Code runs the runbook (manual
      shepherding via `/loop`, a dedicated skill, or plain prompt) with
      pros/cons; pick one for the first run.
- [ ] **Out-of-scope flagged:** the items e2e can't cover (voice, Reachy
      hardware, cloud auth) listed with their manual checkpoints.
- [ ] **Decision recorded** in `docs/FEAT-FG-001-e2e-test-strategy.md`
      (or the project's preferred location) with sufficient detail that
      `/task-create "Author RUNBOOK-fleet-gateway-e2e.md"` is the obvious
      next step.
- [ ] **Hackathon fit confirmed:** the chosen approach can plausibly run
      before the 11–13 May video shoot (deadline from FEAT-FG-001 scope).

## Decision Checkpoint

After analysis, present findings and choose:

- **[A]ccept** — Strategy approved as written; spawn implementation task to
  author the runbook(s).
- **[I]mplement** — Skip directly to writing the runbook (creates a
  follow-on `TASK-FG-RUN-…` implementation task).
- **[R]evise** — Re-run the review with deeper analysis (e.g. a dry-run of
  one phase to confirm probe correctness).
- **[C]ancel** — E2e via runbook is the wrong approach for this feature;
  fall back to expanded integration tests in pytest.

## Investigation Notes

Start here:

- Scope + build plan: `docs/FEAT-FG-001-scope.md`,
  `docs/FEAT-FG-001-build-plan.md`. Section 6 of the scope (Assumptions A1/A6)
  documents the live wiring (graphiti-core → FalkorDB on `whitestocks`,
  `student-lilymay` group id) — these are the e2e probe targets.
- Completed task acceptance criteria: `tasks/completed/TASK-FG-001..006*.md`
  — each lists a unit-level criterion that an e2e probe should be able to
  re-confirm against real infra.
- Existing pipe wire: `openwebui/nats_fleet_pipe.py:126` (connect-per-call
  pattern) — the OpenWebUI runbook phase must respect that.
- Reference runbooks (read in order, copy the shape, **do not** copy content):
  1. `RUNBOOK-v3-production-deployment.md` — for the phased pre-flight +
     gap-back-fill pattern.
  2. `RUNBOOK-architect-dataset-pipeline.md` — for the long-running tmux +
     remote-status-file pattern (relevant if the e2e run includes warming
     llama-swap or seeding Graphiti).
  3. `falkordb-nas-deployment-runbook.md` — for the Tailscale + Synology
     access pattern (the Scholar e2e needs `whitestocks` reachable).
  4. `RUNBOOK-jarvis-architect-align-dddsw-demo.md` — for the per-agent
     verification + RESULTS-doc cadence.

Key constraint: hackathon video shoot 11–13 May. The strategy must produce
*something runnable* by then, even if it is just the OpenWebUI path with
Scholar/Bridge deferred to a follow-up RESULTS doc.

## Out of Scope (for this review)

- Writing the runbook itself.
- Running the runbook.
- Implementing additional integration tests in pytest (decision Q above).
- Any change to `common/`, `openwebui/`, or `reachy/` source.
