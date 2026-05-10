# FEAT-FG-001 E2E Test Strategy

**Status:** Decided (Decision-mode review TASK-REV-3078, 2026-05-10)
**Predecessor:** [`docs/FEAT-FG-001-scope.md`](FEAT-FG-001-scope.md), [`docs/FEAT-FG-001-build-plan.md`](FEAT-FG-001-build-plan.md), six completed tasks (`tasks/completed/TASK-FG-001..006*.md`)
**Successor task:** `/task-create "Author RUNBOOK-fleet-gateway-openwebui-e2e.md"` (and siblings) — see §10
**Trade-off priority (operator):** Quality over deadline. The 11-13 May video shoot is acknowledged but does not drive structure choice; highest e2e confidence per run wins.

---

## 1. Decision in one paragraph

**Three thin per-gateway runbooks, each fully self-contained with its own Phase 0 pre-flight, executed sequentially by Claude Code reading top-to-bottom and writing a dated `RESULTS-…md` companion as it goes.** Gaps discovered during execution fold back into the runbook's "Known issues / forward-references" section and spawn `TASK-FG-RUN-…` follow-ups, mirroring the v3-production / jarvis-architect-align precedent. No new tooling, no shared infra-only runbook, no mega-runbook.

The three runbooks, in order of independence and decreasing isolation:

| # | Runbook | Path under test | Infra needed |
|---|---------|-----------------|--------------|
| 1 | `RUNBOOK-fleet-gateway-scholar-e2e.md` | Pollen (Scholar) → `graphiti-core` → FalkorDB on `whitestocks` | FalkorDB + Tailscale + Pollen venv. **No NATS, no Jarvis.** |
| 2 | `RUNBOOK-fleet-gateway-bridge-e2e.md` | Pollen (Bridge) → `JarvisClient` → NATS → Jarvis on GB10 | NATS + Jarvis + Tailscale + Pollen venv. **No FalkorDB.** |
| 3 | `RUNBOOK-fleet-gateway-openwebui-e2e.md` | Open WebUI Workspace Function → `JarvisClient` → NATS → Jarvis on GB10 | NATS + Jarvis + Open WebUI container on GB10. **No FalkorDB, no MacBook/Pollen.** |

Order rationale: Scholar isolates the most code (the in-process call has no NATS hop), so it surfaces graphiti-core/FalkorDB drift fastest. Bridge then reuses the proven NATS+Jarvis path with the same client surface OpenWebUI uses. OpenWebUI runs last because it adds the deployable-flat-file build and a containerised consumer on top of an already-validated wire path.

---

## 2. Why three thin runbooks, not one or two

### Options considered

| Option | Shape | Pros | Cons | Verdict |
|---|---|---|---|---|
| A — One mega-runbook | All three gateways exercised in one phased run | Single RESULTS doc; tight narrative; no duplication of pre-flight prose | Compound failure cascade (a Scholar failure in §3 stalls discovery of Bridge gaps in §7); single FAIL signature mixes three independent failure surfaces; deviates from the precedent's *"one feature, one flow, one runbook"* discipline | Rejected |
| B — Two runbooks (`infra` + `e2e`) | One provisioning/verifier runbook + one combined exercise runbook | Centralises shared probes; matches v3-production shape | The infra is already deployed and stable on GB10/`whitestocks`; an "infra runbook" would mostly be a verifier, which the per-gateway Phase 0 already does in 5 lines. Combined-exercise runbook reintroduces the cascade problem from Option A | Rejected |
| **C — Three thin per-gateway runbooks** | Each gateway has its own self-contained runbook | Independent failure surfaces; can run in any order or in parallel terminals; each RESULTS doc is one diff against one path; matches the jarvis precedent of separate runbooks for `RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` vs `RUNBOOK-jarvis-architect-align-dddsw-demo.md` even though they share NATS+llama-swap | Pre-flight prose duplicated across three files (≤10 lines each — acceptable); three runbooks to author rather than one | **Selected** |

### Why C wins under "quality over deadline"

The jarvis precedent files **two separate runbooks** for what is conceptually "one feature surface", because each runbook proves one wire path end-to-end and produces one RESULTS doc. When `RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md` discovered the `DISPATCH-STUB-RESOLVER` gap, the FEAT-JARVIS-INTERNAL-001 runbook stayed green and unaffected — the gap landed only in the demo runbook. That's the property the user is paying for here: **one gap = one RESULTS doc = one runbook update = one follow-up task**, not three coupled diagnoses.

The cost is 3× the "phase 0 pre-flight" prose (≤30 lines total across three files). That cost is far outweighed by the noise reduction during gap-back-fill iteration, which under "quality over deadline" is the single most valuable property of the strategy.

### What this is not

- Not parallelisable in the *same* terminal (each runbook is a serial script). Parallelism is offered by the operator running three terminals or three Claude Code instances; the runbooks themselves are single-threaded.
- Not a replacement for pytest — unit and BDD tests stay; this is the *integration on real infra* layer.
- Not a CI artefact. These run on the operator's MacBook + GB10 + `whitestocks` Tailscale mesh. CI cannot replicate the cloud-voice and Pollen surfaces.

---

## 3. Surface map: external dependencies and ready probes

Every external dependency touched by the three gateway interfaces, with the cheapest probe that confirms "ready". One-liners suitable for a runbook Phase 0.

| Dep | Used by | "Ready" probe |
|---|---|---|
| NATS broker (GB10 `:4222`) | OpenWebUI, Bridge | `docker exec ships-computer-nats nats-server --version` AND `nats --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" account info` returns no auth error |
| Jarvis subscriber on `agents.command.jarvis` | OpenWebUI, Bridge | `nats sub --server "nats://rich:..." agents.status.jarvis --count 1 --timeout 5s` (heartbeat present) OR a known-trivial `JarvisClient.send_command("ping")` that returns text within 30s |
| Jarvis supervisor model loaded | OpenWebUI, Bridge | `curl -s http://localhost:9000/v1/models \| jq -r '.data[].id'` includes `qwen36-workhorse` (or the `JARVIS_SUPERVISOR_MODEL` env value) |
| FalkorDB on `whitestocks` (Synology) | Scholar | `redis-cli -h whitestocks -p 6379 ping` returns `PONG` |
| `student-lilymay` group populated | Scholar | `python -c "import asyncio, graphiti_core; ..."` — see §6.1 for the standalone probe; expect `data_available=True` and a non-empty `topic_confidence` |
| `graphiti-core` lib in Pollen venv | Scholar | `python -c "import graphiti_core; print(graphiti_core.__version__)"` from inside the Pollen venv — expect ≥ 0.29 |
| `nats-py` lib in Pollen venv | Bridge | `python -c "import nats; print(nats.__version__)"` from inside the Pollen venv — expect ≥ 2.9 |
| `nats-py` lib in OpenWebUI container | OpenWebUI | `docker exec open-webui python -c "import nats; print(nats.__version__)"` — expect ≥ 2.9 (per scope §7 Q4 this needs explicit `pip install` into the running container; the image does not ship it) |
| Tailscale mesh (MacBook ↔ `whitestocks` ↔ `promaxgb10-41b1`) | Scholar (whitestocks), Bridge (GB10) | `tailscale status \| grep -E "whitestocks\|promaxgb10"` — both rows show `idle` or `active`, not `-` |
| Open WebUI container on GB10 | OpenWebUI | `docker ps --filter name=open-webui --format '{{.Status}}'` reports `Up` |
| `nats_fleet_pipe.deploy.py` registered | OpenWebUI | The Open WebUI Admin → Workspace → Functions UI lists "NATS Fleet Gateway" (or whatever pipe name is registered) and shows it enabled. **Manual check** (no API for Workspace Function listing). |
| llama-swap on `:9000` | Both NATS-routed paths (Jarvis uses it as supervisor LLM) | `curl -s http://localhost:9000/v1/models` returns 200 with non-empty `data` |
| `fleet-gateway` editable-installed in Pollen venv | Scholar, Bridge | `python -c "from common.jarvis_client import JarvisClient; from common.graphiti_client import GraphitiClient"` from inside the Pollen venv |
| Reachy MacBook conversation app | Scholar (in-Pollen probe), Bridge (in-Pollen probe) | `which reachy_mini_conversation_app` OR equivalent Pollen entry point present in venv |

---

## 4. Per-runbook phase outlines

Each runbook follows the precedent shape: header (purpose, machine, expected duration, predecessors), a `Known issues / forward-references` block (initially empty for these, populated as gaps fold in), then numbered phases with a clear `**Pass:**` criterion per step. Bash is verbatim; long-running commands are wrapped in `tmux` only where they're long-running (Pollen launch is the only candidate; it survives the duration of the human voice probe). The phase tables below are the **outline** — full bash gets authored in the implementation tasks (§10).

### 4.1 RUNBOOK-fleet-gateway-scholar-e2e.md

**Goal:** Prove `query_student_model` returns real Graphiti data for `student-lilymay` and that Gemini Live narrates it inside the Scholar profile.

| # | Phase | Intent | Key commands | Expected output |
|---|---|---|---|---|
| 0 | Pre-flight | Confirm Tailscale, FalkorDB, graphiti-core, fleet-gateway editable install, Scholar profile present | `tailscale status`; `redis-cli -h whitestocks -p 6379 ping`; `python -c "import graphiti_core; from common.graphiti_client import GraphitiClient"`; `ls reachy/external_content/external_profiles/scholar/` | All four checks pass; `student-` group prefix confirmed in scope §6 A6 |
| 1 | Standalone probe — graphiti-core layer | Hit FalkorDB through `GraphitiClient.search_student_progress` directly, no Pollen | `python -m fleet-gateway-scholar-probe --student lilymay --subject english` (script written by the runbook author, ≤30 lines) | Returns dict with `data_available=True`, integer `streak_days`, non-empty `topic_confidence` dict; raw stdout pasted into RESULTS |
| 2 | Standalone probe — tool wrapper | Invoke the Scholar tool class without Pollen | `python -c "from reachy.external_content.external_tools.query_student_model import QueryStudentModelTool; ..."` | Same dict shape; tool's structured-narration text non-empty |
| 3 | Pollen launch | Bring up `reachy_mini_conversation_app` with the Scholar profile | `tmux new -s scholar-pollen 'reachy_mini_conversation_app --profile scholar'` (exact command per Pollen docs) | Pollen log shows tool registered, Gemini Live connected |
| 4 | In-Pollen e2e probe (HUMAN) | Operator says "How's Lily May's revision going?" out loud; listens to Gemini Live narration | (no shell — voice + audio) | Narration mentions a streak count or level name from §1's dict; transcribe verbatim into RESULTS |
| 5 | Graceful degradation | Stop Tailscale or block port 6379, repeat §1; tool returns `data_available=False` cleanly | `sudo pfctl -e -f - <<<'block in proto tcp from any to any port 6379'` (macOS) or just `tailscale down` | Dict has `data_available=False`, `error` key set, no exception |
| 6 | Teardown | Restore network, kill tmux | `tmux kill-session -t scholar-pollen`; `tailscale up` | Clean shell |
| 7 | RESULTS write | Create dated RESULTS file; declare PASS or BLOCKED with gap | (manual write) | `RESULTS-feat-fg-001-scholar-<date>.md` lands |

### 4.2 RUNBOOK-fleet-gateway-bridge-e2e.md

**Goal:** Prove `agent_status` returns a Jarvis-narrated fleet status text and degrades cleanly when NATS is down.

| # | Phase | Intent | Key commands | Expected output |
|---|---|---|---|---|
| 0 | Pre-flight | Confirm Tailscale, NATS reachable from MacBook, Jarvis on GB10, llama-swap up, nats-py in Pollen venv | `tailscale status`; `nats --server "nats://rich:$RICH_NATS_PASSWORD@promaxgb10-41b1:4222" account info`; `nats sub agents.status.jarvis --count 1 --timeout 10s`; `curl -s http://promaxgb10-41b1:9000/v1/models` | All four green; one heartbeat captured on `agents.status.jarvis` |
| 1 | Standalone probe — JarvisClient layer | `python -c "import asyncio; from common.jarvis_client import JarvisClient; print(asyncio.run(JarvisClient(adapter='reachy-bridge').send_command('ping')))"` | Returns Jarvis's text response (any non-empty string); correlation_id printable from a side `nats sub agents.command.jarvis` capture |
| 2 | Side-terminal envelope capture | In a second terminal, `nats sub --server ... agents.command.jarvis --count 1` BEFORE running §1; capture the envelope JSON | (paired with §1) | One JSON envelope captured with `version="1.0"`, `event_type="command"`, `source_id="reachy-bridge-gateway"` (or whatever the adapter resolves to per §4.1 of scope) |
| 3 | Standalone probe — tool wrapper | Invoke the Bridge tool class without Pollen | `python -c "from reachy.external_content.external_tools.agent_status import AgentStatusTool; ..."` | Returned text mentions ≥ 1 known fleet agent name (architect-agent, study-tutor, forge, …) — exact list per `agent-registry` KV at run time |
| 4 | Pollen launch | Bring up `reachy_mini_conversation_app` with the Bridge profile | `tmux new -s bridge-pollen 'reachy_mini_conversation_app --profile bridge'` | Pollen log shows `agent_status` tool registered |
| 5 | In-Pollen e2e probe (HUMAN) | Operator says "Computer, fleet status?"; listens to LCARS-style narration | (voice + audio) | Narration includes at least one fleet agent name; voice tone differs from Scholar (different `voice.txt` per scope §3.2) |
| 6 | Graceful degradation | Stop NATS on GB10 (`docker stop ships-computer-nats`); repeat §1 | (paired with side `docker logs -f`) | Tool returns text containing "NATS unreachable" / "fleet offline" / equivalent — and *no* Python traceback |
| 7 | Restore + teardown | `docker start ships-computer-nats`; kill tmux; verify §1 green again | (cleanup) | NATS back up; one final `send_command("ping")` returns text |
| 8 | RESULTS write | Dated RESULTS file | (manual write) | `RESULTS-feat-fg-001-bridge-<date>.md` lands |

### 4.3 RUNBOOK-fleet-gateway-openwebui-e2e.md

**Goal:** Prove a chat posted in the deployed Open WebUI surfaces a Jarvis response, with the envelope visible on the wire.

| # | Phase | Intent | Key commands | Expected output |
|---|---|---|---|---|
| 0 | Pre-flight | Confirm NATS, Jarvis subscriber up, llama-swap up, OpenWebUI container Up, deploy file up to date, nats-py *inside the container* | `docker ps --filter name=open-webui`; `docker exec open-webui python -c "import nats"`; `nats sub agents.status.jarvis --count 1 --timeout 10s`; `cmp openwebui/nats_fleet_pipe.deploy.py <(python openwebui/build_pipe.py --stdout)` | OpenWebUI Up; `nats` import succeeds inside container (or the runbook's §0.1b auto-installs it); `cmp` returns identical (deploy file matches source) |
| 1 | Pipe registration check (MANUAL) | Operator confirms in browser: Admin → Workspace → Functions → "NATS Fleet Gateway" enabled | (browser, no shell) | Screenshot dropped under `docs/runbooks/evidence/openwebui-<date>/` |
| 2 | Side-terminal envelope capture | `nats sub --server ... agents.command.jarvis --count 1` running BEFORE §3 | (paired with §3) | One envelope captured |
| 3 | Chat post (MANUAL) | Operator opens Open WebUI in browser, selects "Jarvis" model, posts message: "What agents do you have?" | (browser) | UI streams or block-renders a Jarvis response within REQUEST_TIMEOUT |
| 4 | Container log grep | Extract the correlation_id from `docker logs open-webui` and match it to §2's captured envelope | `docker logs --since 2m open-webui 2>&1 \| grep -i correlation` | One `correlation_id` printed; equals the one in §2 |
| 5 | Wire ↔ UI cross-check | Confirm envelope's `payload.message` matches what the operator typed in §3 | (compare §2 capture vs §3 typed text) | Exact match (or with the Open WebUI conversation-history prelude — document either way as a runbook artefact) |
| 6 | Graceful degradation | Stop NATS; post a chat in §3 again | (browser + `docker stop ships-computer-nats`) | UI shows the pipe's preserved error message ("Jarvis is taking longer than expected" or "NATS unreachable" — exact text from `nats_fleet_pipe.deploy.py`) — *not* a stack trace |
| 7 | Restore + teardown | Restart NATS; one more chat returns successfully | (cleanup) | UI green again |
| 8 | RESULTS write | Dated RESULTS file with screenshot links | (manual write) | `RESULTS-feat-fg-001-openwebui-<date>.md` lands |

---

## 5. Why these phase orderings (per runbook)

- **Scholar** runs the standalone graphiti-core probe (§4.1.1) *before* the tool wrapper (§4.1.2) so a graphiti-core API drift surfaces before tool-layer glue gets blamed. This mirrors v3-production's Phase 0 model-on-disk check before any model-loading phase.
- **Bridge** captures the wire envelope (§4.2.2) *paired* with the standalone probe (§4.2.1) — the side terminal must already be subscribed before the request fires, otherwise no envelope to capture. The runbook explicitly numbers the side-terminal subscribe ahead of the publish.
- **OpenWebUI** runs container `nats` import in pre-flight because the deployed image does *not* ship `nats-py` (scope §7 Q4); without §0 catching that, §3 fails opaquely from inside the pipe. This is the kind of gap the gap-back-fill rule is designed to capture if it slips past.

---

## 6. Probe specifications per gateway

### 6.1 Scholar — `query_student_model`

**Standalone probe** (`scripts/scholar-probe.py`, written by §10's task):

```python
import asyncio
from common.graphiti_client import GraphitiClient

async def main() -> None:
    client = GraphitiClient(
        falkordb_uri="redis://whitestocks:6379",
        default_group_ids=["student-lilymay"],
    )
    progress = await client.search_student_progress(student_name="lilymay", subject="english")
    assert progress["data_available"] is True, f"data_available is False: {progress}"
    assert isinstance(progress.get("streak_days"), int), f"streak_days not int: {progress}"
    assert progress.get("topic_confidence"), f"topic_confidence empty: {progress}"
    print(progress)

asyncio.run(main())
```

**Pass criterion:** all three asserts hold; raw stdout pasted into RESULTS.

**In-Pollen probe (HUMAN):** operator asks "How's Lily May's revision going?"; narration mentions a number from `streak_days` *or* a level name *or* a topic from `topic_confidence`. Operator transcribes the narration verbatim into RESULTS.

### 6.2 Bridge — `agent_status`

**Standalone probe** (`scripts/bridge-probe.py`):

```python
import asyncio
from common.jarvis_client import JarvisClient

async def main() -> None:
    response = await JarvisClient(adapter="reachy-bridge").send_command("what's the fleet status?")
    assert response, "empty response"
    known_agents = {"architect-agent", "product-owner-agent", "study-tutor", "forge", "specialist-agent"}
    assert any(a in response.lower() for a in known_agents), f"no known agent named: {response[:200]}"
    print(response)

asyncio.run(main())
```

**Pass criterion:** response non-empty AND contains at least one known fleet agent name. (The set is updated when the runbook is authored against the live `agent-registry` KV — see §10.)

**Wire-capture probe** (paired side terminal): `nats sub agents.command.jarvis --count 1 --timeout 30s` produces exactly one JSON envelope; captured envelope's `source_id` field equals `reachy-bridge-gateway` (or whatever the adapter resolves to per `common/envelope.py`).

**Graceful-degradation probe**: with NATS stopped, the standalone probe returns a string containing "NATS unreachable" / "fleet offline" / equivalent and **no** uncaught exception.

### 6.3 OpenWebUI — `nats_fleet_pipe.deploy.py`

**Three-way assertion** (the e2e is "green" only when all three pass):

1. **UI rendering** (manual): a Jarvis response is rendered in the Open WebUI chat pane within `REQUEST_TIMEOUT`. Screenshot.
2. **Wire envelope** (side terminal): exactly one envelope captured on `agents.command.jarvis` with the operator's typed text in `payload.message` (or wrapped in conversation-history scaffolding — document the actual shape).
3. **Correlation-id continuity**: `docker logs open-webui` shows a `correlation_id` that matches the captured envelope's `correlation_id`.

**Graceful-degradation probe**: NATS stopped → UI shows the preserved error string from `nats_fleet_pipe.deploy.py`'s exception handlers, not a stack trace.

---

## 7. Evidence convention

### 7.1 RESULTS doc

**Location:** `fleet-gateway/docs/runbooks/RESULTS-feat-fg-001-{path}-{YYYY-MM-DD}.md` (one per runbook execution, dated). Mirrors the jarvis convention (`docs/runbooks/RESULTS-...-2026-05-08.md`).

**Naming:** `{path}` is one of `scholar`, `bridge`, `openwebui`. Multiple same-day runs get a suffix: `-followup-a`, `-fresh`, `-post-fix`, mirroring the jarvis pattern (`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md`).

**Required sections** (in order):

1. **Header** — date, operator, machine(s), runbook driven, fleet-gateway HEAD commit, Pollen / OpenWebUI / Jarvis HEAD commits if relevant.
2. **Outcome** — single-line status: `✅ PASS` / `⏸ BLOCKED` / `❌ FAIL`. One paragraph naming the gap if not PASS.
3. **Per-phase outcomes table** — one row per phase number with `Phase / Gate / Outcome / Evidence` columns; mirrors the jarvis table in `RESULTS-jarvis-architect-align-...-2026-05-08.md`.
4. **Gaps discovered (if any)** — for each gap: name (`GAP-<SHORT-ID>`), symptom (operator-visible), symptom (trace/log-level), root cause, runbook section to fold into, follow-up task ID.
5. **Evidence pointers** — paths under `fleet-gateway/docs/runbooks/evidence/{date}-{path}/` (envelope captures, screenshots, log tails).
6. **Close criterion** — what's needed before this runbook can re-run green.

### 7.2 Raw evidence

**Location:** `fleet-gateway/docs/runbooks/evidence/{YYYY-MM-DD}-{path}{-suffix}/`. One subdir per RESULTS doc. Contents: envelope JSON capture (`agents-command-jarvis-capture.json`), `docker logs` excerpts, browser screenshots, transcribed voice narrations as `*.txt`.

### 7.3 Gap-back-fill rule

This is the precedent-driven mechanism. When a runbook execution discovers a gap:

1. **In the RESULTS doc**, the gap gets a numbered `GAP-<SHORT-ID>` block with the four fields above.
2. **In the runbook itself**, the `Known issues / forward-references` table at the top gains a row: `GAP-<SHORT-ID>`, summary, affects-phase, workaround-in-runbook (yes/no), follow-up task. The phase that fails gains a forward-reference comment: `# See KNOWN-ISSUES § GAP-<SHORT-ID> — expected FAIL until task TASK-FG-RUN-<ID> lands`.
3. **A follow-up task is created**: `/task-create "Fix GAP-<SHORT-ID>: <summary>"` with a link back to the RESULTS doc.
4. **The next execution** of the runbook treats the documented FAIL signature as expected; the operator (Claude Code) is expected to detect any *deviation* from the documented signature, not the FAIL itself.

This is the v3-production `TASK-RUN-D6F4` pattern (gap-fix RESULTS doc → runbook annotation → fix task) and the FEAT-JARVIS-INTERNAL-001 wave 1 → wave 2 pattern (`Known issues / forward-references` block grows over runs). The user has explicitly cited both as the model.

---

## 8. Execution loop

**Decision: plain prompt, no new tooling.** Claude Code is asked to read the runbook top-to-bottom, execute each `Pass:`-criterion'd phase, and write the RESULTS doc as it goes.

### Options considered

| Option | Description | Verdict |
|---|---|---|
| Plain prompt | "Open `RUNBOOK-…md`. For each phase: run the listed bash, paste output, decide pass/fail per the `Pass:` criterion, append a row to the in-progress RESULTS doc. Stop and ask the user before any destructive step. Stop on first FAIL and write up the gap." | **Selected.** No new code, mirrors how the jarvis runbooks have actually been executed (the RESULTS docs are the receipts). |
| `/loop` against the runbook | Use the existing `/loop` skill to repeatedly re-attempt the same runbook (e.g. after fixes) | Useful *between* runs, not within. Compatible with the plain-prompt option above. |
| New `/runbook-execute` skill | Custom skill that parses the runbook structure | Rejected for this strategy: bespoke tooling for a hackathon timeline; the plain-prompt loop is observably sufficient (precedent runbooks have shipped without it) |

### Operator instruction template (paste at run-start)

> Open `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-{path}-e2e.md`. For each numbered phase, top to bottom:
>
> 1. Run the verbatim bash listed under that phase.
> 2. Paste the output (or a representative excerpt for noisy commands).
> 3. Decide pass/fail against the `Pass:` line.
> 4. Append a row to the RESULTS doc at `docs/runbooks/RESULTS-feat-fg-001-{path}-{today}.md` (create on first phase). Use the per-phase-outcomes table from §7.1.
> 5. If FAIL: stop. Write a `GAP-<SHORT-ID>` block per §7.3. Do not proceed to the next phase. Surface the gap to the user before creating any follow-up tasks.
>
> Do not skip Phase 0. Do not improvise commands the runbook does not list (any deviation is itself a runbook gap to fold in). For destructive steps (`docker stop`, `tailscale down`, `tmux kill-session`), confirm with the user first.

---

## 9. Out of scope (manual checkpoints, human-in-the-loop)

The e2e cannot cover the following; each gets a named human checkpoint embedded in its runbook phase, and the operator's transcription/screenshot is the evidence:

| Item | Why e2e can't cover | Manual checkpoint |
|---|---|---|
| Cloud voice (OpenAI Realtime / Gemini Live) audio quality | Audio-out only renders to speakers; no programmatic capture in current setup | Operator listens, transcribes verbatim into RESULTS (Scholar §4.1.4, Bridge §4.2.5) |
| Reachy hardware emotions / dance | Physical robot output, no FEAT-FG-001 code path | Out of FEAT-FG-001 scope per scope doc §2; flagged here but not a runbook phase |
| Open WebUI deployed UI auth + chat rendering | Browser-only, no scriptable API for Workspace Function listing | Operator screenshots (OpenWebUI §4.3.1, §4.3.3) |
| Voice tone distinction Scholar vs Bridge | Subjective audio judgement | Operator notes "voices distinct" / "voices identical (gap)" in RESULTS |
| Gemini Live / OpenAI Realtime tool-calling reliability under load | Cloud-hosted, opaque, rate-limited | Out of FEAT-FG-001 scope; flag in RESULTS if observed during the in-Pollen probes |
| LCARS-style persona adherence (Bridge) | LLM behaviour judgement | Operator notes adherence quality in RESULTS; not a pass-gate (informational) |

---

## 10. Hackathon fit and next steps

### 10.1 Hackathon fit (deadline acknowledged but not driving)

The 11-13 May video shoot is two days from this review (review date 2026-05-10). Authoring three runbooks takes ~2-3h each (≈6-9h total), plus first-run execution ~1-2h each, plus gap-fold cycle for whatever surfaces. **A clean run of all three before the shoot is not guaranteed.** Under the operator's "quality over deadline" priority, the shoot can use a partial-RESULTS state: run Scholar first (highest demo value, lowest infra surface), aim for green, capture as the demo evidence; Bridge and OpenWebUI follow whenever they land. The video script can call out "OpenWebUI runbook in flight" without harming the demo narrative.

If the operator later wants to compress timeline, the trade is between authoring three runbooks now (highest confidence) vs authoring just `scholar-e2e.md` plus stub outlines for the other two (faster but introduces the cascade-failure risk Option C explicitly avoids). The strategy as written prefers the former; no compression baked in.

### 10.2 Successor tasks (to create after this review accepts)

```
/task-create "Author RUNBOOK-fleet-gateway-scholar-e2e.md"  feature_id:FEAT-FG-001
/task-create "Author RUNBOOK-fleet-gateway-bridge-e2e.md"   feature_id:FEAT-FG-001
/task-create "Author RUNBOOK-fleet-gateway-openwebui-e2e.md" feature_id:FEAT-FG-001
```

Each task's body should reference §4 of this strategy doc as the phase outline, §6 for the probe specs, §7 for the evidence convention. Acceptance criterion for each authoring task: `RUNBOOK-…md` lands at the path above, every phase has a verbatim bash block and a `Pass:` line, the `Known issues / forward-references` block exists (initially empty), no `# Expected: …` placeholder is left as `TODO`.

A fourth task captures the first execution:

```
/task-create "First execution of fleet-gateway scholar e2e runbook" feature_id:FEAT-FG-001 task_type:execution
```

(or `/loop` invocations, depending on how the operator chooses to drive the runs).

### 10.3 What this review explicitly does NOT decide

- Which model llama-swap should serve as `JARVIS_SUPERVISOR_MODEL` for the runs (operator picks at run-time per scope §7 Q3).
- Whether to add a fourth runbook for an integrated multi-gateway demo for the video. That's a video-script question, not an e2e-validation question.
- Whether to migrate the Open WebUI pipe to Pipelines container (scope §7 Q4 path B). That's a post-hackathon deployment decision; the runbook stays valid for whichever deployment shape is current.

---

## 11. Provenance

- **Decision-mode review:** TASK-REV-3078 (this doc).
- **Operator trade-off priority:** "Quality over deadline" (collected via `/task-review` clarification 2026-05-10).
- **Reference runbooks studied** (shape only, no content copied):
  - `jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — known-issues forward-reference pattern, multi-wave gap-back-fill, single-flow-per-runbook discipline.
  - `jarvis/docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md` (and `RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`) — single-flow runbook for a different demo path despite shared infra; per-phase outcomes table format.
  - `agentic-dataset-factory/domains/architect-agent/RUNBOOK-architect-dataset-pipeline.md` — `tmux` pattern for long-running phases; remote-status-file pattern.
  - `guardkit/docs/research/dgx-spark/RUNBOOK-v3-production-deployment.md` — Phase 0 pre-flight discipline; gap-back-fill via TASK-RUN-D6F4 precedent.
  - `guardkit/docs/guides/falkordb-nas-deployment-runbook.md` — Tailscale + Synology access pattern, referenced from Scholar §4.1.0.

- **Source repos read for surface mapping:** `fleet-gateway/openwebui/nats_fleet_pipe.py`, `fleet-gateway/common/*`, `fleet-gateway/reachy/external_content/external_tools/*`, `fleet-gateway/tasks/completed/TASK-FG-005,006*.md`, `study-tutor/src/study_tutor/knowledge/student_model.py:67` (group ID prefix), `nats-core/src/nats_core/topics.py` (real subjects), `guardkit/scripts/graphiti-mcp-config.yaml` (FalkorDB URI).
