# Runbook: Fleet Gateway OpenWebUI E2E

**Status:** Ready for execution (first authoring, wave 2 of three; mirrors the shape established by [`RUNBOOK-fleet-gateway-scholar-e2e.md`](RUNBOOK-fleet-gateway-scholar-e2e.md) under TASK-FG-007).
**Purpose:** Prove that a chat posted in the deployed Open WebUI surfaces a Jarvis response, with the wire envelope visible on `agents.command.jarvis` and the `correlation_id` chain tying UI → container log → wire envelope.
**Machines:** GB10 only (`promaxgb10-41b1`) — Open WebUI container, NATS broker (`ships-computer-nats`), Jarvis subscriber, and llama-swap all co-resident. **No MacBook, no Pollen, no `whitestocks`, no FalkorDB on this path.**
**Predecessors:** FEAT-FG-001 merged on `main` (TASK-FG-001…006 completed); strategy doc [`docs/FEAT-FG-001-e2e-test-strategy.md`](../FEAT-FG-001-e2e-test-strategy.md) accepted; Wave-1 Scholar runbook landed (TASK-FG-007 complete) — only the *shape* is reused, none of the bash; bundle README [`tasks/backlog/feat-fg-001-e2e-runbooks/README.md`](../../tasks/backlog/feat-fg-001-e2e-runbooks/README.md).
**Expected wall-clock:** ≤60 minutes for a clean run (Phase 0–7 ≈40 min including the two manual browser interactions, Phase 8 RESULTS write ≈20 min). The OpenWebUI runbook is the most layered of the three (UI + container + wire + log) so the human-in-the-loop steps dominate the wall-clock.
**Outputs:**
- `docs/runbooks/RESULTS-feat-fg-001-openwebui-{YYYY-MM-DD}.md` — dated per-run RESULTS doc (§7.1 of the strategy doc)
- `docs/runbooks/evidence/openwebui-{YYYY-MM-DD}/` — browser screenshots from Phases 1 and 3, captured envelope JSON from Phase 2, log excerpts from Phases 4 and 6

**Probe convention used by this runbook:** every probe is inline bash or `docker exec`; no helper script is committed. The OpenWebUI path is short enough that the inline form stays readable, and it avoids a `scripts/openwebui-probe.py` that would partially duplicate `nats sub` / `docker logs` invocations the operator already runs by hand. (Author's choice per the bundle [`IMPLEMENTATION-GUIDE.md`](../../tasks/backlog/feat-fg-001-e2e-runbooks/IMPLEMENTATION-GUIDE.md) — Scholar's standalone-probe pattern was warranted because its three asserts wanted readable failure output; the OpenWebUI three-way assertion is split across `nats sub`, `docker logs`, and the operator's eyes, so a single probe script would not earn its keep.)

---

## Known issues / forward-references

(no known issues at first authoring — populated via the strategy §7.3 gap-back-fill rule on first execution)

---

## Phase 0: Pre-flight

This phase verifies the GB10 surface is wired up before any chat traffic flows. Six sub-steps total; if any one trips, halt at that step and route the trip as a strategy-§7.3 gap rather than papering over it with an ad-hoc workaround. All commands run on GB10 — `ssh promaxgb10-41b1` first if you started the runbook on the MacBook.

### 0.1 Open WebUI container is Up

```bash
docker ps --filter name=open-webui --format '{{.Names}}\t{{.Status}}'
```

**Pass:** stdout shows exactly one row whose `Status` column starts with `Up` (e.g. `Up 2 hours`). Anything else (`Exited`, `Restarting`, no row at all) is a hard fail — Phases 1–7 cannot run without the container live. Recovery is `docker start open-webui` if the container exists, otherwise reconcile against the deployment notes in [`openwebui/README.md`](../../openwebui/README.md).

### 0.2 `nats-py` importable inside the Open WebUI container — load-bearing per scope §7 Q4

The Open WebUI container image does **not** ship `nats-py`; the deploy file ([`openwebui/nats_fleet_pipe.deploy.py`](../../openwebui/nats_fleet_pipe.deploy.py)) imports it at runtime, so a missing import here causes the pipe to fail opaquely from inside the chat path with no useful operator-visible signal. This is the single highest-value Phase 0 check on this runbook (per scope §7 Q4); do not skip it even on a "I just ran this yesterday" basis — container restarts wipe the venv-level `pip install` (see 0.2-fix below).

```bash
docker exec open-webui python -c "import nats; print(nats.__version__)"
```

**Pass:** stdout prints a version string ≥ `2.9` (the pin the deploy file's inlined `JarvisClient` was built against). Any `ModuleNotFoundError` here means the dependency is absent — apply the recovery step in 0.2-fix below before re-running this check.

### 0.2-fix If `import nats` failed in 0.2 — install path

If 0.2 raised `ModuleNotFoundError: No module named 'nats'`, install `nats-py` directly into the running container:

```bash
docker exec open-webui pip install nats-py
docker exec open-webui python -c "import nats; print(nats.__version__)"
```

⚠️ **The `pip install` is ephemeral** — it lives in the container's filesystem layer and will be lost on the next `docker rm` or image rebuild. The durable fix is to bake `nats-py` into the Open WebUI image (extend the Dockerfile, rebuild, redeploy) or migrate the pipe to a Pipelines container that has its own venv (scope §7 Q4 path B — currently a post-hackathon decision). Document in the RESULTS Phase 0 row whether the install was needed; recurring need across runs is itself a gap to fold and motivates the durable fix.

**Pass:** the second `docker exec` line prints a version string ≥ `2.9`. If it still fails, `pip install` itself errored — check container egress, PyPI reachability, or proxy configuration before continuing.

### 0.3 NATS broker is reachable and authenticated

```bash
docker exec ships-computer-nats nats-server --version
nats --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" account info
```

**Pass:** the first command prints a `nats-server: v2.x.x` line (the broker process is alive); the second command prints an account-info block (with `User: rich` or equivalent) and exits 0 with no `nats: error: nats: Authorization Violation`. Both lines green. (`$RICH_NATS_PASSWORD` is the operator's local env var — set in `~/.zshrc` or equivalent on GB10; if unset, `export` it before running the command and document the missing-env gap in RESULTS.)

### 0.4 Jarvis subscriber heartbeat present on `agents.status.jarvis`

```bash
nats sub --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" \
    agents.status.jarvis --count 1 --timeout 10s
```

**Pass:** the command captures exactly one heartbeat message within 10s and exits 0. The captured payload typically includes a Jarvis identifier and a recent timestamp; the contents are informational — the *receipt* is the load-bearing signal. A `--timeout` exit with zero captures means Jarvis is not publishing heartbeats — start it with `jarvis serve-nats --nats nats://rich:$RICH_NATS_PASSWORD@localhost:4222` (or your local supervisor command) and re-run.

### 0.5 llama-swap models endpoint is green

The supervisor LLM Jarvis routes through must be loaded; if llama-swap is wedged, Jarvis will accept the chat envelope and then time out internally, which surfaces as a Phase 3 timeout downstream rather than a clean Phase 0 fail.

```bash
curl -fsS http://localhost:9000/v1/models | jq -r '.data[].id'
```

**Pass:** `curl` exits 0 (the `-f` flag fails on HTTP error) and the JSON contains a non-empty `data` array; the printed model IDs include `qwen36-workhorse` (or the value of `JARVIS_SUPERVISOR_MODEL` if the operator has overridden it). An empty `data` array means llama-swap is up but no model is loaded — `curl` the load endpoint (operator's local llama-swap convention) before continuing.

### 0.6 Source pipe vs deploy pipe are byte-identical

Strategy §4.3 specifies a `cmp` between `openwebui/nats_fleet_pipe.deploy.py` and the regenerated output of `python openwebui/build_pipe.py --stdout`. The actual `build_pipe.py` does not expose a `--stdout` mode (it writes to disk only — see its `main()` and the docstring's "diff-stable" property). The equivalent zero-drift assertion is to regenerate the deploy file and confirm git sees no diff — semantically identical to `cmp` returning identical, and accurate to the script's real interface. Document this deviation in RESULTS Phase 0; reconciling the strategy doc to match (or adding a `--stdout` mode to the script) is a follow-up worth a small task.

```bash
python openwebui/build_pipe.py
git diff --exit-code openwebui/nats_fleet_pipe.deploy.py
```

**Pass:** `build_pipe.py` writes its `Wrote …/openwebui/nats_fleet_pipe.deploy.py (N bytes)` line to stderr and exits 0; `git diff --exit-code` exits 0 (no changes). A non-zero exit from `git diff` means the committed deploy file is stale relative to the source-of-truth pipe and `common/` modules — commit the regenerated deploy file before continuing (the running container is serving the stale paste, so the e2e would otherwise prove a stale pipe, which is not the question this runbook asks).

---

## Phase 1: Pipe registration check (HUMAN)

⚠️ **HUMAN step — no shell command.** Open WebUI's Workspace Functions UI exposes no list-via-API endpoint, so a browser confirmation is the only way to assert the deploy file is paste-registered and toggled on (per strategy §9). The operator's screenshot is the receipt.

### 1.1 Open the Functions admin page in a browser

Navigate to: **Open WebUI → Admin → Workspace → Functions**. The exact URL depends on the local deployment (typically `http://promaxgb10-41b1:3000/admin/functions` or `http://localhost:3000/admin/functions` if browsing from GB10 itself).

**Pass:** the Functions table renders and shows at least one row whose pipe class registers the model id `jarvis` (label `Jarvis` per `Pipe.pipes()` in [`openwebui/nats_fleet_pipe.deploy.py`](../../openwebui/nats_fleet_pipe.deploy.py)). The row's enable toggle is in the **on** state. If the row is missing, the deploy file is not pasted — paste it via the **+ New Function** workflow before continuing. If the toggle is off, flip it on.

### 1.2 Drop a screenshot into the dated evidence subdirectory

Capture the Functions table state with the `Jarvis` row visible and the toggle clearly **on**. Drop the PNG into the evidence subdir (create it if absent):

```bash
mkdir -p docs/runbooks/evidence/openwebui-$(date +%F)
# then drag-drop or `mv` the screenshot into that path; suggested filename:
# phase-1-pipe-registered-{HHMM}.png
```

**Pass:** the file exists at `docs/runbooks/evidence/openwebui-{YYYY-MM-DD}/phase-1-pipe-registered-*.png` and shows the row + the enabled toggle clearly. Note the filename in the RESULTS Phase 1 row's Evidence column — the screenshot link is the only proof that survives this run.

---

## Phase 2: Side-terminal envelope capture — start BEFORE Phase 3

The `nats sub` below must be running and waiting **before** the operator posts the chat in Phase 3, otherwise the envelope publishes to no subscriber-of-record and Phases 4 and 5 lose their evidence. Open a second terminal on GB10 (or a tmux pane), run the subscribe command, then return to this runbook to do Phase 3 in the first terminal — leaving the second terminal blocking on the `--count 1` wait.

### 2.1 Open a second terminal and start the subscribe

In a second terminal on GB10:

```bash
nats sub --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" \
    agents.command.jarvis --count 1 \
    > docs/runbooks/evidence/openwebui-$(date +%F)/phase-2-envelope.json
```

The redirect captures the captured envelope JSON straight into the evidence subdir. The command will block (no timeout) until Phase 3 publishes an envelope, then exit 0 and return the prompt.

**Pass:** the command starts and shows a `Subscribing on agents.command.jarvis` confirmation line on stderr (or just blocks silently, depending on `nats` CLI version) — *before* you proceed to Phase 3. Verify by checking `ps` or just observing that the terminal has not returned a prompt. Do not move to Phase 3 until you have eyes-on confirmation that this subscribe is live.

---

## Phase 3: Chat post via Open WebUI (HUMAN)

⚠️ **HUMAN step — browser-only.** The Open WebUI chat surface has no scriptable client at the level we need (Workspace Functions are invoked via the chat UI, not via the `/api/chat/completions` endpoint that bypasses the dropdown). The operator's typed message and the streamed response are the receipts.

### 3.1 Open Open WebUI chat in the browser

Navigate to the chat UI (typically `http://promaxgb10-41b1:3000/` or `http://localhost:3000/` if browsing from GB10). Select **Jarvis** from the model dropdown — this is the model id registered by `Pipe.pipes()`.

**Pass:** the model dropdown shows `Jarvis` as a selectable option and the chat composer is enabled. If `Jarvis` is missing from the dropdown, the pipe registration in Phase 1 was confirmed via the admin page but is not surfacing in the chat picker — likely a permissions or workspace-scope issue; reconcile against [`openwebui/README.md`](../../openwebui/README.md) before continuing.

### 3.2 Post the test prompt

Type and submit the following prompt verbatim into the chat composer:

> **What agents do you have?**

(This prompt mirrors the strategy doc §6.3 example. It is intentionally one Jarvis can answer without specialist routing — the question is "did the wire path work," not "is Jarvis's intent router correct.")

**Pass:** the chat pane renders a Jarvis response within `REQUEST_TIMEOUT` (120s default per `Pipe.Valves.REQUEST_TIMEOUT`). The response is non-empty text — exact content is informational; the receipt is the *render*. A spinner that never resolves, an error toast, or a stack trace pasted into the chat are all FAILs — do not retry; capture what happened, drop a screenshot under `phase-3-chat-rendered-*.png`, and proceed to Phases 4 and 5 to diagnose (the wire envelope should already be captured by Phase 2 even on a UI-render failure if the publish reached NATS).

### 3.3 Drop a screenshot of the rendered response

```bash
# screenshot saved as phase-3-chat-rendered-{HHMM}.png in the dated evidence dir
ls docs/runbooks/evidence/openwebui-$(date +%F)/phase-3-chat-rendered-*.png
```

**Pass:** the listed file exists and the screenshot shows the prompt sent + a non-empty Jarvis response visibly rendered. Note the filename in the RESULTS Phase 3 row.

---

## Phase 4: Correlation-id continuity (UI → container log → wire envelope)

Strategy §6.3 calls this out as one of the three "green" assertions: the same `correlation_id` must be visible in the Open WebUI container's log and in the envelope captured at Phase 2. If either is absent or the values diverge, the wire path was not what the UI thought it was.

### 4.1 Extract the correlation_id from the Open WebUI container log

```bash
docker logs --since 2m open-webui 2>&1 | grep -i correlation
```

**Pass:** at least one line is printed and contains a `correlation_id` value (typically a UUID-shaped string). Capture the line and the extracted UUID into the evidence subdir for cross-reference:

```bash
docker logs --since 2m open-webui 2>&1 \
    | grep -i correlation \
    > docs/runbooks/evidence/openwebui-$(date +%F)/phase-4-container-correlation.txt
```

If `grep` returns nothing, the deploy pipe (or its inlined `JarvisClient`) is not logging a correlation id — that is itself a runbook gap to fold (Phase 4 cannot complete without the assertion target). Note in RESULTS that the e2e passed Phases 0–3 but Phase 4 surfaced a "no correlation_id in container log" gap, and create a follow-up `TASK-FG-RUN-…` to add the log line in the source pipe / shared client.

### 4.2 Cross-check against the captured envelope's correlation_id

```bash
jq -r '.correlation_id // .data.correlation_id // (.. | .correlation_id? // empty)' \
    docs/runbooks/evidence/openwebui-$(date +%F)/phase-2-envelope.json \
    | head -1
```

The `jq` form tolerates either a top-level `correlation_id`, a `data.correlation_id`, or any nested occurrence — the actual nesting depends on how `common.envelope.build_command_envelope` shapes the wire JSON; document the actual location in the RESULTS Phase 4 row.

**Pass:** the printed UUID is byte-identical to the UUID extracted in 4.1. Any mismatch is a real e2e fail — the UI reached *some* envelope publisher but not the one this runbook is trying to assert about (most plausible cause: a stale or duplicate pipe registration that's racing the new one). Stop here and capture both UUIDs in RESULTS before any retry.

---

## Phase 5: Wire ↔ UI cross-check (`payload.message` matches what the operator typed)

The third leg of the §6.3 three-way assertion: confirm the captured envelope's payload contains the operator's exact prompt from Phase 3.2. The strategy doc explicitly anticipates two possible shapes — raw text or conversation-history-wrapped — and asks the runbook to *document whichever the implementation produces* rather than assert one over the other.

### 5.1 Extract the message field from the captured envelope

```bash
jq '.payload.message // .data.payload.message // .' \
    docs/runbooks/evidence/openwebui-$(date +%F)/phase-2-envelope.json
```

The fallback chain handles: (a) an envelope where `payload` is top-level, (b) one where `payload` lives under `data`, (c) the whole envelope as a final printout if neither path resolved (that is itself the first datum to record — the actual shape).

**Pass:** the printed value either equals the literal string `"What agents do you have?"` (raw-text shape — simplest case), OR is a structured object that contains the operator's prompt as the latest entry in a conversation history list (history-wrapped shape — `Pipe.pipe` in the source-of-truth `nats_fleet_pipe.py` does pass `conversation_history=history` to the client, so this shape is plausible if the client embeds history into `payload.message`). Document which shape was observed in the RESULTS Phase 5 row, and paste the actual JSON snippet under the row. **Do not edit the runbook to "fix" the assertion to match the observed shape on first execution** — the strategy explicitly leaves this open for the runbook to discover and pin down.

### 5.2 If the shape is history-wrapped, record the latest-entry equality

```bash
# Only run this if 5.1 showed a structured payload; harmless otherwise.
jq -r '
    (.payload.message // .data.payload.message)
    | if type == "string" then .
      elif type == "array" then .[-1].content // .
      elif type == "object" then .messages[-1].content // .
      else .
      end
' docs/runbooks/evidence/openwebui-$(date +%F)/phase-2-envelope.json
```

**Pass:** the printed text equals `What agents do you have?` (modulo trailing whitespace). If it does not, either Open WebUI mutated the prompt before publish (e.g. system-prompt prepend) or the conversation history's "latest" entry is in an unexpected position — record verbatim what was found and route as a runbook gap; a Phase 5 mismatch is e2e-blocking on this runbook even if Phase 4's correlation_id matched.

---

## Phase 6: Graceful degradation (NATS down, UI shows preserved error string)

Strategy §6.3 closes the e2e with a degradation probe: stop NATS, post a chat in the browser, and assert the UI surfaces the *preserved error wording* from the deploy pipe's exception handlers — not a stack trace, not "internal server error", and not silence. The four exception strings the deploy pipe ([`openwebui/nats_fleet_pipe.deploy.py`](../../openwebui/nats_fleet_pipe.deploy.py), mirrored from the source-of-truth `Pipe.pipe`) preserves are:

- `TimeoutError` → `"Jarvis did not respond within {N}s. Is it running? Start with: jarvis serve-nats --nats {url}"`
- `ConnectionError` containing `"No responders"` → `"No agent is listening on 'agents.command.jarvis'. Start Jarvis with: jarvis serve-nats --nats {url}"`
- `ConnectionError` other → `"NATS error: {exc}"`
- generic `Exception` → `"NATS error: {exc}"`

Stopping the NATS broker outright (rather than just unsubscribing Jarvis) makes the connection itself fail, so the expected wording is one of the latter two `"NATS error: …"` variants — not the "no responders" one (which fires when NATS is up but no subscriber is on the topic).

### 6.1 Stop NATS

⚠️ **Destructive — confirm with the user before running.** Stops the shared NATS broker on GB10; every other fleet component that depends on this broker will also fail for the duration, until Phase 7 brings it back.

```bash
docker stop ships-computer-nats
docker ps --filter name=ships-computer-nats --format '{{.Status}}'
```

**Pass:** the second command prints a `Status` row beginning with `Exited` (or returns no row if `--filter name=` requires `-a` on the local docker version — confirm with `docker ps -a`). The container is down.

### 6.2 Post the same prompt in the browser

⚠️ **HUMAN step.** In the same chat session as Phase 3, post the same prompt — `What agents do you have?` — and watch the chat pane.

**Pass:** the chat pane renders one of the deploy-pipe-preserved error strings listed above (most likely the `"NATS error: …"` variant). The rendered text is **plain text**, not a stack trace, not a JSON error envelope, and not "Internal Server Error" or equivalent. Drop a screenshot under `docs/runbooks/evidence/openwebui-$(date +%F)/phase-6-degraded-ui.png` — the screenshot is the receipt.

If the chat instead shows a stack trace, an HTML error page, or silently spins forever, the deploy pipe's exception handlers are not being exercised — likely the failure is happening upstream of the pipe code (e.g. an HTTP-layer error from Open WebUI itself before the pipe even runs). Capture what was shown and route as a Phase 6 runbook gap; the e2e is BLOCKED until the deploy pipe gets a chance to surface its preserved string.

### 6.3 Confirm the container log shows the exception path was hit

```bash
docker logs --since 30s open-webui 2>&1 | grep -E -i 'jarvis|nats|connection|timeout' | tail -20
```

**Pass:** at least one line is printed and corroborates that the pipe code executed and hit one of its `except` branches (e.g. a `Jarvis request failed` log line from the `logger.exception` call in the source-of-truth pipe's generic-exception handler, or the literal message strings from one of the typed-exception branches). This is a corroborating signal, not load-bearing — the visible UI string is the actual assertion.

---

## Phase 7: Restore + final green re-run

⚠️ **Destructive — confirm with the user before running each sub-step.** Brings NATS back online and re-walks the happy path so GB10 ends the run in a known-good state.

### 7.1 Restart NATS

⚠️ **Destructive — confirm with the user before running.** Restarts the shared broker the rest of the fleet depends on.

```bash
docker start ships-computer-nats
sleep 3  # broker boot
nats --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" account info
```

**Pass:** `docker start` exits 0; the `account info` call returns a clean info block (mirrors Phase 0.3). The broker is healthy again.

### 7.2 Confirm Jarvis subscriber recovered the connection

```bash
nats sub --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" \
    agents.status.jarvis --count 1 --timeout 15s
```

**Pass:** one heartbeat captured within 15s (mirrors Phase 0.4, with a slightly more generous timeout because Jarvis's reconnect backoff may push the next heartbeat slightly past the 10s window). If no heartbeat within 15s, restart Jarvis (`jarvis serve-nats --nats nats://rich:$RICH_NATS_PASSWORD@localhost:4222` or your local supervisor command) before continuing.

### 7.3 One more chat post to confirm the wire path is green again

⚠️ **HUMAN step.** In the browser, post the same prompt — `What agents do you have?` — one more time.

**Pass:** the chat pane renders a Jarvis response (mirrors Phase 3.2). No screenshot required for this confirmation (the Phase 3 screenshot already documents the happy-path render); a one-line `Confirmed green: <YYYY-MM-DD HH:MM>` note in the RESULTS Phase 7 row is sufficient evidence.

### 7.4 Final-state check: GB10 matches the Phase-0 starting posture

```bash
docker ps --filter name=open-webui --format '{{.Names}}\t{{.Status}}'
docker ps --filter name=ships-computer-nats --format '{{.Names}}\t{{.Status}}'
nats --server "nats://rich:$RICH_NATS_PASSWORD@localhost:4222" account info > /dev/null && echo "nats: ok"
```

**Pass:** both `Status` columns show `Up`, and the third line prints `nats: ok`. If 0.2-fix's ephemeral `pip install nats-py` was applied during this run, document that the next container restart will re-surface the `import nats` failure unless the durable image-rebuild path is taken.

---

## Phase 8: RESULTS write

Compose the dated RESULTS file that closes this execution. The runbook itself does not call PASS or FAIL — its bash and `**Pass:**` lines only frame the gates. The PASS/FAIL judgement, the gap discussion, and the per-phase outcome row table all live in the RESULTS companion authored here.

### 8.1 Create the RESULTS file at the strategy-§7.1 path

```bash
DATE=$(date +%F)
RESULTS_FILE="docs/runbooks/RESULTS-feat-fg-001-openwebui-${DATE}.md"
cp /dev/null "$RESULTS_FILE"  # touch + truncate; safe to re-run
echo "$RESULTS_FILE"
```

(For multiple same-day re-runs, append `-followup-a`, `-fresh`, `-post-fix` etc. before the `.md`, mirroring the convention in strategy §7.1 and the jarvis precedent.)

**Pass:** `echo` prints a path that resolves on disk and the file is zero-length (the `cp /dev/null` truncated it). The body to come is hand-composed prose; the strategy doc deliberately chose not to template it (RESULTS is a written record of what actually happened, not a structured form filled in from a generator).

### 8.2 Populate the RESULTS body — six required sections

Build out the file with these six sections, in this exact ordering — the shape that strategy §7.1 specifies:

1. **Header** — date, operator name, machine (GB10, no others for this runbook), driving runbook (this file), `fleet-gateway` HEAD commit (`git rev-parse --short HEAD`), Open WebUI image digest from `docker inspect open-webui --format '{{.Image}}'`, plus the repo path of the deploy file so reviewers can pin down which `Pipe` shape served the run.
2. **Outcome** — pick exactly one of `✅ PASS`, `⏸ BLOCKED`, `❌ FAIL`. If not PASS, add one paragraph naming the gap. A PASS verdict requires every leg of the §6.3 three-way assertion (Phase 3 UI render + Phase 2 envelope captured + Phase 4 correlation_id matching) PLUS Phase 6 surfacing a preserved error string AND Phase 7's repeat chat rendering green.
3. **Per-phase outcomes table** — eight rows, one per phase 0 through 7, with columns `Phase / Gate / Outcome / Evidence`. Populate `Evidence` with the path of whichever file under `docs/runbooks/evidence/openwebui-{YYYY-MM-DD}/` documents the row (Phase 1 / 3 / 6 screenshots, Phase 2 envelope JSON, Phase 4 correlation log excerpt, Phase 5 jq output as inline-pasted snippet or saved file), or with the inline operator-typed prompt for the Phase 3 / 6 / 7 chat-post rows.
4. **Gaps discovered (if any)** — one numbered `GAP-<SHORT-ID>` entry per surfaced gap, each carrying the four data points strategy §7.3 mandates: how the gap looked to the operator, how it looked at the log/trace level, the underlying cause if known, which runbook section needs the fold, and the ID of the spawned follow-up task. Likely candidates given this runbook's surface: Phase 0.6 strategy-doc-vs-script `--stdout` mismatch, Phase 0.2 ephemeral `pip install` durability, Phase 4 missing `correlation_id` log line, Phase 5 envelope shape (raw vs history-wrapped) — any of these should land here on first execution if observed.
5. **Evidence pointers** — list every file deposited into `docs/runbooks/evidence/openwebui-{YYYY-MM-DD}/`. Minimum surface: `phase-1-pipe-registered-*.png`, `phase-2-envelope.json`, `phase-3-chat-rendered-*.png`, `phase-4-container-correlation.txt`, `phase-6-degraded-ui.png`. Add any extra screenshots or log tails captured during the run. Every path the per-phase Evidence column references must resolve to a real file in this list.
6. **Close criterion** — one line describing what (if anything) must change for the next execution to re-pass. For a clean PASS this is "re-runnable as-is, no changes required" — optionally annotated with whether 0.2-fix's ephemeral `pip install` was needed.

**Pass:** the RESULTS file exists at the §7.1 path, every one of the six sections above is present and non-empty, and the per-phase outcomes table carries exactly eight rows (one per Phase 0–7; Phase 8 itself does not appear in the table — the RESULTS doc *is* Phase 8's evidence).

### 8.3 Confirm every evidence path the RESULTS doc references actually exists

```bash
ls docs/runbooks/evidence/openwebui-$(date +%F)/
```

**Pass:** the listing contains, at minimum, the screenshot from Phase 1, the envelope JSON from Phase 2, the screenshot from Phase 3, the correlation log excerpt from Phase 4, and the degraded-UI screenshot from Phase 6. Every path the RESULTS doc's Evidence column points at is in this listing (or under a sibling subdirectory if the operator chose to nest further). Missing files mean the RESULTS doc is making claims it cannot back up — fix before declaring the run closed.

### 8.4 On a non-PASS outcome, spawn the follow-up task

When the RESULTS verdict is anything other than `✅ PASS`, file the gap-fix task per strategy §7.3:

```text
/task-create "Fix GAP-<SHORT-ID>: <one-line summary>" feature_id:FEAT-FG-001
```

Reference the RESULTS doc path from the new task's body, and append an entry to this runbook's `Known issues / forward-references` block above with a one-line gap summary plus the new task ID. Leave the failed phase's bash untouched in this run — the captured FAIL is the artefact; rewriting now would erase the baseline that the next execution needs to compare against.

**Pass:** for a BLOCKED/FAIL outcome, a fresh task file exists under `tasks/backlog/` whose body cross-links the RESULTS doc, and this runbook's `Known issues / forward-references` block above carries a row pointing at it. For a PASS outcome, this step is a no-op.
