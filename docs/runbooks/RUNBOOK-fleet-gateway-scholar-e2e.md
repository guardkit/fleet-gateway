# Runbook: Fleet Gateway Scholar E2E

**Status:** Ready for execution (first authoring, wave 1 of three; Bridge and OpenWebUI mirror this shape under TASK-FG-008 / TASK-FG-009).
**Purpose:** Prove `query_student_model` returns real Graphiti data for `student-lilymay` and that Gemini Live narrates that data inside the Scholar profile, end-to-end on the operator's MacBook.
**Machines:** MacBook (runs Pollen + Scholar profile + the standalone probes) and `whitestocks` (Synology NAS hosting FalkorDB at `:6379`); both joined to the Tailscale mesh. **No NATS, no Jarvis, no GB10 traffic on this path.**
**Predecessors:** FEAT-FG-001 merged on `main` (TASK-FG-001…006 completed); strategy doc [`docs/FEAT-FG-001-e2e-test-strategy.md`](../FEAT-FG-001-e2e-test-strategy.md) accepted; bundle README [`tasks/backlog/feat-fg-001-e2e-runbooks/README.md`](../../tasks/backlog/feat-fg-001-e2e-runbooks/README.md).
**Expected wall-clock:** ≤45 minutes for a clean run (Phase 0–6 ≈30 min, Phase 7 RESULTS write ≈15 min).
**Outputs:**
- `docs/runbooks/RESULTS-feat-fg-001-scholar-{YYYY-MM-DD}.md` — dated per-run RESULTS doc (§7.1 of the strategy doc)
- `docs/runbooks/evidence/{YYYY-MM-DD}-scholar/` — raw probe stdout, voice transcripts, screenshots if any

**Probe convention used by this runbook:** the Phase 1 / Phase 5 graphiti-core probe is committed at [`scripts/scholar-probe.py`](../../scripts/scholar-probe.py). The runbook invokes it verbatim; the snippet from strategy §6.1 is the body of that file. (Author's choice per the bundle IMPLEMENTATION-GUIDE — kept as a script rather than a `python -c` block because the assert messages stay readable in failure output.)

---

## Known issues / forward-references

(no known issues at first authoring — populated via the strategy §7.3 gap-back-fill rule on first execution)

---

## Phase 0: Pre-flight

Goal of this phase is to surface infrastructure drift before any code path runs. If any sub-step fails, stop here and treat the failure as a runbook gap to fold in (strategy §7.3) rather than improvising around it.

### 0.1 Tailscale mesh reachable from MacBook

```bash
tailscale status | grep -E 'whitestocks'
```

**Pass:** the line for `whitestocks` shows `idle` or `active`, not `-` or `offline`. (If absent: `tailscale up` and re-check; if the row is missing entirely, this is a runbook gap — Tailscale device list drift.)

### 0.2 FalkorDB on `whitestocks` answers ping

```bash
redis-cli -h whitestocks -p 6379 ping
```

**Pass:** stdout is exactly `PONG`. Any other output (timeout, connection refused, ACL error) is a hard fail — Phases 1–5 cannot run without this gate green.

### 0.3 `graphiti-core` importable inside the Pollen venv

Activate the Pollen venv first (path is operator-specific; the runbook assumes the operator knows their Pollen install location), then:

```bash
python -c "import graphiti_core; print(graphiti_core.__version__)"
```

**Pass:** prints a version string ≥ `0.29` (the version the Scholar tool wraps; see scope §3.3 for the dependency pin). Any import error means the venv is missing the lib — re-run the fleet-gateway editable install (`pip install -e .` from the repo root) inside the Pollen venv.

### 0.4 fleet-gateway editable-installed in the Pollen venv

```bash
python -c "from common.graphiti_client import GraphitiClient; print(GraphitiClient)"
```

**Pass:** prints `<class 'common.graphiti_client.GraphitiClient'>` (or equivalent class repr). `ModuleNotFoundError` here means the editable install is absent or shadowed — fix before continuing; the standalone probe in Phase 1 imports through this module path.

### 0.5 Scholar profile files present

```bash
ls reachy/external_content/external_profiles/scholar/
```

**Pass:** all three of `instructions.txt`, `tools.txt`, `voice.txt` are listed and non-empty. (Absent files indicate FEAT-FG-001 / TASK-FG-005 did not land cleanly; abort and reconcile against `tasks/completed/TASK-FG-005-scholar-tools-and-profile.md` acceptance criteria.)

---

## Phase 1: Standalone graphiti-core probe

Hits FalkorDB through `GraphitiClient.search_student_progress` directly, with no Pollen, no Reachy daemon, no LLM. This isolates graphiti-core / FalkorDB / Tailscale drift from the tool-wrapper layer above it.

### 1.1 Run the probe against `student-lilymay`

```bash
python scripts/scholar-probe.py --student lilymay --subject english
```

The probe prints the returned dict as JSON (default=str for non-serialisable values), then runs the three asserts from strategy §6.1.

**Pass:** the script exits 0 and stdout contains a JSON object with `"data_available": true`, an integer `streak_days`, and a non-empty `topic_confidence` mapping. Paste the exact stdout into `evidence/{YYYY-MM-DD}-scholar/phase-1-probe.json`.

### 1.2 Capture the probe output for the RESULTS doc

```bash
mkdir -p docs/runbooks/evidence/$(date +%F)-scholar
python scripts/scholar-probe.py --student lilymay --subject english \
    > docs/runbooks/evidence/$(date +%F)-scholar/phase-1-probe.json
```

**Pass:** the evidence file exists and is non-empty; its content is a JSON object that round-trips through `python -m json.tool`.

---

## Phase 2: Standalone tool-wrapper probe

Calls `QueryStudentModelTool` directly so any failure is the wrapper layer (parameter defaults, group_id construction, narration-friendly fallback shaping per TASK-FG-005), not graphiti-core. Pollen is still not in the loop.

### 2.1 Invoke the tool class with default parameters

```bash
python -c "
import asyncio, json
from reachy.external_content.external_tools.query_student_model import QueryStudentModelTool

async def main():
    tool = QueryStudentModelTool()
    result = await tool.run(subject='english', student_name='lilymay')
    print(json.dumps(result, indent=2, default=str))

asyncio.run(main())
"
```

**Pass:** stdout is a JSON object that contains `data_available: true` plus the keys defined by the TASK-FG-005 contract (`student_name`, `streak_days`, `level_name`, `recent_xp`, `near_achievements`, `topic_confidence`). Save the stdout into `evidence/{YYYY-MM-DD}-scholar/phase-2-tool-wrapper.json`.

### 2.2 Confirm the wrapper builds the expected group_id

The tool must construct `student-lilymay` (dash form, per scope §6 A6), not `study_tutor__student_model` or `student:lilymay`. Easiest live check is to read it back from the tool instance:

```bash
python -c "
from reachy.external_content.external_tools.query_student_model import QueryStudentModelTool
tool = QueryStudentModelTool()
# Inspect the tool's resolved group_id without re-running the query.
# (Implementation detail: TASK-FG-005 stores the constructed list on the
# GraphitiClient instance the tool builds; if your local code surfaces it
# under a different attribute name, update this line and fold a runbook gap.)
print(tool)
"
```

**Pass:** no exceptions raised; the printed repr (or any attribute trace the operator does add) shows the dash-form `student-lilymay` group id. If the printed shape doesn't expose group_ids in this form, that is itself a runbook gap — fold via §7.3 and proceed (the dict shape from 2.1 is the load-bearing contract; this step is a belt-and-braces check).

---

## Phase 3: Pollen launch

Bring up `reachy_mini_conversation_app` with the Scholar profile, wrapped in `tmux` so the long-running session survives the voice-test phase below without losing scrollback. The operator detaches from tmux to interact with Reachy and re-attaches after the voice probe to grep the Pollen log.

### 3.1 Start Pollen in a detached tmux session

```bash
tmux new-session -d -s scholar-pollen \
    "reachy_mini_conversation_app --profile scholar 2>&1 | tee /tmp/scholar-pollen.log"
```

(Adjust the binary path / launch command to match the operator's Pollen install — the strategy doc and the Reachy README are the source of truth for the exact entry point on this host.)

**Pass:** the `tmux new-session` command exits 0 and a follow-up `tmux ls` lists `scholar-pollen` as an active session. (A non-zero exit usually means the binary path is wrong or a stale `scholar-pollen` session already exists; reconcile and re-run.)

### 3.2 Confirm the session is alive and the tool registered

```bash
tmux ls | grep scholar-pollen
sleep 5  # let Pollen complete its first boot pass
grep -E 'query_student_model|gemini.*connected|tool.*register' /tmp/scholar-pollen.log
```

**Pass:** `tmux ls` shows `scholar-pollen` with at least one window, and the grep returns at least one line confirming `query_student_model` registered AND one line indicating the Gemini Live connection is up. If neither line is present after a 5-second settle, attach (`tmux attach -t scholar-pollen`) and capture the actual error — that's the gap to fold.

---

## Phase 4: In-Pollen voice probe (HUMAN)

⚠️  **HUMAN step — no shell command.** This is the only phase whose evidence is a voice transcription, not a stdout capture. The runbook cannot automate cloud-voice audio; the operator's verbatim transcript is the receipt (per strategy §9).

### 4.1 Speak the magic phrase to Reachy

The operator stands in front of Reachy (or whatever audio path the Scholar profile uses on this host) and says, audibly:

> **How's Lily May's revision going?**

Listen to the full Gemini Live narration. Do not interrupt. If Reachy asks a clarifying question instead of answering, that is itself the result — capture it.

**Pass:** Reachy produced *some* audible response within the Scholar profile's normal latency window (silence after ~30 s is itself a gap — capture it, fold via §7.3, and skip 4.2's transcription). The substantive content check (data-bearing narration) lives in 4.2 below.

### 4.2 Transcribe the narration verbatim

Open the RESULTS doc (created in Phase 7) and transcribe the spoken response word-for-word into a fenced block under the Phase 4 row. Mark filler/uhms with `[…]` rather than omitting them — small narrations are evidence the wire path worked even when the framing is hesitant.

**Pass:** the transcript mentions at least one of (a) a number that maps to `streak_days` from the Phase 1 dict, (b) a level name string that appears under `level_name`, or (c) a topic key from `topic_confidence`. Any of those three is sufficient; explicitly note which in the Phase 4 outcome row. If none surface, that is a real gap in the tool↔LLM integration path, even if Phases 1–3 were green — fold and stop before Phase 5.

---

## Phase 5: Graceful degradation

⚠️  **Destructive — confirm with the operator before running.** The strategy doc allows either of two methods to take FalkorDB out of reach: a surgical `pfctl` block on port 6379, or a wholesale `tailscale down`. This runbook prefers the `pfctl` route because it is narrower (the rest of the Tailscale mesh stays up; only Scholar's read path is affected). The `tailscale down` route is documented as a fallback for hosts where `pfctl` is unavailable.

### 5.1 Block FalkorDB at the network layer (macOS, primary path)

⚠️  **Destructive — confirm with the operator before running.** Requires `sudo`; will modify the host firewall.

```bash
sudo pfctl -e -f - <<'EOF'
block out proto tcp from any to any port 6379
EOF
```

(If the operator is not on macOS, skip this step and use 5.1-alt below instead.)

**Pass:** the command exits 0 and `redis-cli -h whitestocks -p 6379 ping` now hangs / returns a connection error within a few seconds. (If the ping still returns `PONG`, the rule did not take effect — abort Phase 5, restore state via Phase 6, fold the discrepancy as a runbook gap.)

### 5.1-alt Drop the Tailscale interface (fallback path)

⚠️  **Destructive — confirm with the operator before running.** Brings down the entire Tailscale mesh on this host; everything else mesh-routed will also stop until Phase 6 restores it.

```bash
sudo tailscale down
```

**Pass:** `tailscale status` shows the interface as `Stopped` and `redis-cli -h whitestocks -p 6379 ping` fails to resolve / connect.

### 5.2 Re-run the standalone probe with degradation expected

```bash
python scripts/scholar-probe.py --student lilymay --subject english --allow-no-data
```

The `--allow-no-data` flag suppresses the happy-path asserts so the script captures the structured fallback dict instead of exiting non-zero on the first miss.

**Pass:** the script exits 0 and stdout is a JSON object containing `data_available: false`, an `error` string describing the unreachability (rather than a Python traceback dumped to stderr), and a `narration_hint` field consistent with the TASK-FG-005 graceful-fallback contract. Save the stdout to `evidence/{YYYY-MM-DD}-scholar/phase-5-degradation.json`. **No traceback may appear on stderr** — if one does, the GraphitiClient layer is leaking exceptions through the tool's degraded path; that is the gap to fold.

---

## Phase 6: Teardown

⚠️  **Destructive — confirm with the operator before running each step.** Restores network state and shuts down the long-running Pollen session.

### 6.1 Restore FalkorDB reachability

⚠️  **Destructive — confirm with the operator before running.**

If Phase 5.1 ran:

```bash
sudo pfctl -d
```

If Phase 5.1-alt ran:

```bash
sudo tailscale up
```

**Pass:** `redis-cli -h whitestocks -p 6379 ping` returns `PONG` again, mirroring Phase 0.2.

### 6.2 Kill the Pollen tmux session

⚠️  **Destructive — confirm with the operator before running.** Terminates Pollen; in-memory conversation state is lost.

```bash
tmux kill-session -t scholar-pollen
```

**Pass:** `tmux ls` no longer lists `scholar-pollen` (or, if it was the only session, returns `no server running on /tmp/tmux-…`). The Pollen log file at `/tmp/scholar-pollen.log` survives — leave it on disk; Phase 7 references it.

### 6.3 Confirm the host is back to its pre-runbook posture

```bash
tailscale status | grep -E 'whitestocks'
redis-cli -h whitestocks -p 6379 ping
tmux ls 2>&1 || true
```

**Pass:** Tailscale row reads `idle`/`active`, FalkorDB ping returns `PONG`, no `scholar-pollen` session listed.

---

## Phase 7: RESULTS write

Author the dated RESULTS companion doc; this is the artefact that closes the run. The runbook itself never declares pass/fail — the RESULTS doc does, with one outcome row per phase above.

### 7.1 Create the RESULTS file at the strategy-§7.1 path

```bash
DATE=$(date +%F)
RESULTS_FILE="docs/runbooks/RESULTS-feat-fg-001-scholar-${DATE}.md"
cp /dev/null "$RESULTS_FILE"  # touch + truncate; safe to re-run
echo "$RESULTS_FILE"
```

(For multiple same-day re-runs, append `-followup-a`, `-fresh`, `-post-fix` etc. before the `.md`, mirroring the convention in strategy §7.1.)

**Pass:** the file path printed exists on disk and is empty (or has been freshly truncated). The operator now hand-writes the RESULTS body — there is no template to fill in below this point, by deliberate strategy choice; the RESULTS doc is a narrative receipt, not a generated artefact.

### 7.2 Populate the RESULTS body — required sections

Author the file with these sections, in this order, exactly as strategy §7.1 prescribes:

1. **Header** — date, operator, machines (MacBook + `whitestocks`), runbook driven (this file), `fleet-gateway` HEAD commit (`git rev-parse --short HEAD`), Pollen version if known.
2. **Outcome** — one of `✅ PASS` / `⏸ BLOCKED` / `❌ FAIL`, followed by one paragraph naming the gap if not PASS.
3. **Per-phase outcomes table** — one row per phase number above, with columns `Phase / Gate / Outcome / Evidence`. The `Evidence` column points at the relevant file under `evidence/{YYYY-MM-DD}-scholar/` (Phase 1 stdout, Phase 2 stdout, Phase 4 voice transcript, Phase 5 degradation stdout) or at the in-line transcript for Phase 4.
4. **Gaps discovered (if any)** — for each gap a numbered `GAP-<SHORT-ID>` block with the four fields from strategy §7.3 (operator-visible symptom, log-level symptom, root cause, runbook section to fold into, follow-up task ID).
5. **Evidence pointers** — paths to all files under `docs/runbooks/evidence/{YYYY-MM-DD}-scholar/`, including the Phase 1/2/5 JSON captures and any Pollen log excerpt extracted from `/tmp/scholar-pollen.log`.
6. **Close criterion** — one sentence stating what would need to change before this runbook can re-run green (for a PASS run, this is "no changes — re-runnable as-is").

**Pass:** the RESULTS file exists at the §7.1 path, all six sections are present and non-empty, and the per-phase outcomes table has exactly one row per phase number 0 through 6 above (Phase 7 itself does not get a row — the RESULTS doc is its own evidence).

### 7.3 Move evidence captures into the dated subdirectory

If any Phase 1 / 2 / 5 stdout was redirected to `/tmp` rather than directly into `docs/runbooks/evidence/{YYYY-MM-DD}-scholar/`, move it now:

```bash
mv /tmp/scholar-pollen.log docs/runbooks/evidence/$(date +%F)-scholar/ 2>/dev/null || true
ls docs/runbooks/evidence/$(date +%F)-scholar/
```

**Pass:** the evidence subdirectory contains, at minimum, the Phase 1 probe JSON, the Phase 2 tool-wrapper JSON, the Phase 5 degradation JSON, and (if grepped during Phase 3.2) a Pollen log excerpt or the full `/tmp/scholar-pollen.log`. Every path referenced in the RESULTS doc's "Evidence pointers" section actually resolves on disk.

### 7.4 If any phase failed, file the follow-up task

If the RESULTS outcome is `⏸ BLOCKED` or `❌ FAIL`, create a follow-up code or runbook task per strategy §7.3:

```text
/task-create "Fix GAP-<SHORT-ID>: <one-line summary>" feature_id:FEAT-FG-001
```

Link the new task back to the RESULTS doc path, and add a row to this runbook's `Known issues / forward-references` block at the top, summarising the gap and pointing at the new task. Do not edit the failed phase's bash itself in this run — the gap is the receipt.

**Pass:** for a BLOCKED/FAIL run, a new task exists in `tasks/backlog/` whose body links to the RESULTS doc, and the `Known issues / forward-references` block at the top of this file has gained a row referencing it. For a PASS run, this step is a no-op.
