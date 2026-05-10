# Runbook: Fleet Gateway Bridge E2E

**Status:** Ready for execution (first authoring, wave 2 of three; mirrors the wave-1 Scholar runbook for shape — header layout, known-issues block, RESULTS-write phase — with no content copied, since the wire path is different).
**Purpose:** Prove `agent_status` returns a Jarvis-narrated fleet-status text inside the Bridge profile, with the request envelope visible on `agents.command.jarvis`, and that the tool degrades cleanly when NATS is unreachable.
**Machines:** MacBook (runs Pollen + Bridge profile + the standalone probes + the side-terminal NATS subscriber) and `promaxgb10-41b1` (GB10 hosting NATS, Jarvis subscriber, llama-swap supervisor); both joined to the Tailscale mesh. **No FalkorDB, no Scholar code path on this runbook.**
**Predecessors:** FEAT-FG-001 merged on `main` (TASK-FG-001…006 completed; TASK-FG-006 is the Bridge tool whose acceptance criteria this runbook re-confirms end-to-end); strategy doc [`docs/FEAT-FG-001-e2e-test-strategy.md`](../FEAT-FG-001-e2e-test-strategy.md) accepted; bundle README [`tasks/backlog/feat-fg-001-e2e-runbooks/README.md`](../../tasks/backlog/feat-fg-001-e2e-runbooks/README.md); Scholar wave-1 runbook [`RUNBOOK-fleet-gateway-scholar-e2e.md`](RUNBOOK-fleet-gateway-scholar-e2e.md) (shape reference only — no commands shared).
**Expected wall-clock:** ≤60 minutes for a clean run (Phase 0–7 ≈45 min, Phase 8 RESULTS write ≈15 min). Bridge runs longer than Scholar because of the paired-terminal envelope capture in Phase 1/2 and the docker-stop / docker-start cycle in Phase 6/7.
**Outputs:**
- `docs/runbooks/RESULTS-feat-fg-001-bridge-{YYYY-MM-DD}.md` — dated per-run RESULTS doc (§7.1 of the strategy doc)
- `docs/runbooks/evidence/{YYYY-MM-DD}-bridge/` — raw probe stdout, captured `agents.command.jarvis` envelope JSON, voice transcripts, Pollen log excerpts

**Probe convention used by this runbook:** the Phase 1 / Phase 6 `JarvisClient` probe is committed at [`scripts/bridge-probe.py`](../../scripts/bridge-probe.py). The runbook invokes it verbatim; the snippet body is the strategy-§6.2 Bridge probe. The `--allow-connection-error` flag suppresses the happy-path asserts so Phase 6 can capture a clean `ConnectionError` signature without exiting non-zero.

**Wire-path scope-disambiguation note (load-bearing — see scope §7 Q3):** the Bridge `agent_status` tool calls `JarvisClient.send_command("what's the fleet status?")` on `agents.command.jarvis`. The originally-proposed `JarvisClient.query_status()` method on a `jarvis.status.query` topic was dropped at scope §7 Q3 because that topic does not exist in `nats-core`. **Any phase below that appears to publish on a `jarvis.status.*` subject, or any probe that imports a `query_status`-named callable, is itself a runbook gap to fold per §7.3 — do not improvise.**

---

## Known issues / forward-references

(none recorded yet — this block stays empty until first execution discovers something. The §7.3 gap-back-fill rule is what populates it: each `GAP-<SHORT-ID>` from a RESULTS doc lands here as a one-line forward-reference plus a pointer to the follow-up task that fixes it.)

---

## Phase 0: Pre-flight

Goal of this phase is to surface infrastructure drift before any wire path runs. If any sub-step fails, stop here and treat the failure as a runbook gap to fold in (strategy §7.3) rather than improvising around it. Bridge fans out to two hosts (MacBook + GB10) via Tailscale, so this Phase 0 is wider than Scholar's.

### 0.1 Tailscale mesh reachable from MacBook

```bash
tailscale status | grep -E 'promaxgb10-41b1'
```

**Pass:** the matched row for `promaxgb10-41b1` reports a live status (Tailscale prints either `idle` or `active` for a peer that is reachable; `-` and `offline` are the not-reachable signatures). If the status column reads `-`/`offline`, run `tailscale up` once and rerun this check. If the row is missing from the output entirely, the GB10 host has dropped out of the operator's tailnet — that is a runbook gap to fold via §7.3, not a setup mistake.

### 0.2 NATS broker reachable from the MacBook

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222" account info
```

**Pass:** the command exits 0 and prints an `Account Information` block (memory / streams / consumers limits). Any of: `nats: error: nats: authorization violation`, `connection refused`, `i/o timeout` is a hard fail — the rest of the runbook cannot run without the MacBook → GB10 NATS path green. Common drifts: `RICH_NATS_PASSWORD` not exported in the current shell, GB10 NATS container down, Tailscale ACL change. Diagnose before continuing.

### 0.3 Jarvis subscriber heartbeat captured on `agents.status.jarvis`

The Jarvis subscriber on GB10 publishes liveness on `agents.status.jarvis`. Capturing one heartbeat proves: (a) Jarvis is up, (b) NATS auth is correct end-to-end, (c) the side-terminal pattern that Phase 2 will use is wired correctly on this MacBook.

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222" \
    sub agents.status.jarvis --count 1 --timeout 10s
```

**Pass:** within 10 seconds, exactly one message prints to stdout (subject + payload). A `--timeout 10s` exit with no messages received means Jarvis is not publishing heartbeats — fold as a gap (Jarvis subscriber down) and stop; do not skip ahead.

### 0.4 llama-swap on GB10 returns models including `JARVIS_SUPERVISOR_MODEL`

Jarvis dispatches the supervisor LLM via llama-swap on `:9000`. If the operator's chosen `JARVIS_SUPERVISOR_MODEL` is not loaded, Jarvis will reply on the wire with a model-not-found error rather than a fleet-status narration — and the runbook would FAIL at Phase 1 with a misleading payload.

```bash
curl -s http://promaxgb10-41b1:9000/v1/models | jq -r '.data[].id'
```

**Pass:** the printed list is non-empty AND contains the value of `JARVIS_SUPERVISOR_MODEL` for this run (operator's choice per scope §7 Q3 / strategy §10.3 — typically `qwen36-workhorse` at the time of authoring; the operator picks at run-time). If the operator has not pinned a model name, the floor is "the list contains at least one entry whose name appears in the Jarvis config on GB10". An empty `data` array means llama-swap is up but no model is loaded — fold as a gap.

### 0.5 `nats-py` importable inside the Pollen venv

Source the operator's Pollen virtualenv before running the import — the activation path varies per host (the operator's Reachy README, not this runbook, owns that path). Once the venv is active in the current shell, run:

```bash
python -c "import nats; print(nats.__version__)"
```

**Pass:** prints a version string ≥ `2.9` (the version `JarvisClient` expects; see scope §3.3 / §7 Q4). `ModuleNotFoundError` here means the Pollen venv is missing the lib — `pip install nats-py` inside the venv before continuing. (Note: this is a different surface from the OpenWebUI container, where nats-py also has to be installed separately per scope §7 Q4 — that's a different runbook.)

### 0.6 fleet-gateway editable-installed in the Pollen venv

```bash
python -c "from common.jarvis_client import JarvisClient; print(JarvisClient)"
```

**Pass:** stdout is `<class 'common.jarvis_client.JarvisClient'>` (or whatever the local Python build prints for an importable class). A `ModuleNotFoundError` at this point indicates that fleet-gateway is not on the Pollen venv's `sys.path` — the fix is to redo the editable install (`pip install -e .` from the fleet-gateway repo root, with the Pollen venv active). Phase 1's probe loads `JarvisClient` through this same module path, so a miss here will fail Phase 1 with the identical error.

### 0.7 Bridge profile files present

```bash
ls reachy/external_content/external_profiles/bridge/
```

**Pass:** all three of `instructions.txt`, `tools.txt`, `voice.txt` are listed and non-empty, AND `tools.txt` contains the literal string `agent_status`. Absent files indicate FEAT-FG-001 / TASK-FG-006 did not land cleanly; abort and reconcile against `tasks/completed/TASK-FG-006-bridge-profile-agent-status.md` acceptance criteria.

### 0.8 `RICH_NATS_PASSWORD` exported in the current shell

A bookkeeping check — every NATS command in Phases 1, 2, 6, 7 expands `${RICH_NATS_PASSWORD}`; an unset variable produces an authorization-violation error that masks as a runbook bug rather than an environment bug.

```bash
[[ -n "${RICH_NATS_PASSWORD}" ]] && echo "RICH_NATS_PASSWORD is set" || echo "MISSING"
```

**Pass:** stdout is exactly `RICH_NATS_PASSWORD is set`. If `MISSING`, source the operator's secret store (typically `direnv` or `~/.config/fleet-gateway/secrets.env`) before proceeding — do not paste the password into the runbook.

---

## Phase 1 / Phase 2 ordering (read before running either)

Phase 1 publishes on `agents.command.jarvis`. Phase 2 captures that same publish on the wire. The capture only works if Phase 2's subscriber is **already running** when Phase 1 fires. The numbering below reflects layers (tool/probe = 1, wire = 2), not execution order. **In execution order**:

1. Open a second terminal on the MacBook ("side terminal").
2. In the side terminal, start Phase 2.1's `nats sub agents.command.jarvis --count 1` first — it blocks until one envelope arrives.
3. **Then** in the primary terminal, run Phase 1.1's `python scripts/bridge-probe.py`.
4. Phase 2.1 will print exactly one envelope and exit; Phase 1.1 will print Jarvis's reply text and exit.
5. Reconcile the two outputs in Phase 2.2.

If the side terminal is not started first, Phase 2.1 will time out with no capture — do not retry without restarting Phase 2.1 ahead of Phase 1.1 (a re-run of Phase 1.1 alone does not re-publish the same envelope; you'd be capturing a *new* publish on the second attempt, and the correlation_id will not match the first stdout).

---

## Phase 1: Standalone JarvisClient probe

Hits NATS on GB10 through `JarvisClient.send_command` directly, with no Pollen, no Reachy daemon, no Bridge tool wrapper. This isolates NATS / Jarvis / Tailscale / supervisor-LLM drift from the tool-wrapper layer above it.

### 1.1 Run the probe with the canonical fleet-status phrase

(Confirm Phase 2.1 in the side terminal is running first — see the "Phase 1 / Phase 2 ordering" note above.)

```bash
python scripts/bridge-probe.py --phrase "what's the fleet status?"
```

The probe prints Jarvis's reply text to stdout, then runs the two asserts from strategy §6.2 (response non-empty AND mentions ≥1 known fleet agent name).

**Pass:** the script exits 0 and stdout contains a non-empty string that names at least one of `architect-agent`, `product-owner-agent`, `study-tutor`, `forge`, `specialist-agent` (the snapshot set in `scripts/bridge-probe.py`'s `KNOWN_AGENTS`). The text may be longer than one sentence — Jarvis narrates rather than enumerates. Paste the exact stdout into `evidence/{YYYY-MM-DD}-bridge/phase-1-probe.txt`. If the response mentions zero known agents, that is itself a real signal (the live `agent-registry` KV may have drifted from the runbook's snapshot) — fold as a gap, update `KNOWN_AGENTS`, and rerun.

### 1.2 Capture the probe output for the RESULTS doc

```bash
mkdir -p docs/runbooks/evidence/$(date +%F)-bridge
python scripts/bridge-probe.py --phrase "what's the fleet status?" \
    > docs/runbooks/evidence/$(date +%F)-bridge/phase-1-probe.txt
```

**Pass:** the evidence file exists and is non-empty; opening it shows the same Jarvis-narrated text from 1.1.

---

## Phase 2: Paired side-terminal envelope capture

Captures the wire envelope that Phase 1.1 publishes on `agents.command.jarvis`. The `--count 1 --timeout 30s` pattern blocks the side terminal until exactly one envelope arrives, then exits — matching the multi-terminal capture pattern proven in `jarvis/docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` (Phase 7.2). This is the e2e proof that JarvisClient is publishing on the right subject with the right adapter id.

### 2.1 Subscribe to `agents.command.jarvis` (run in the side terminal BEFORE Phase 1.1)

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222" \
    sub agents.command.jarvis --count 1 --timeout 30s \
    | tee docs/runbooks/evidence/$(date +%F)-bridge/phase-2-envelope.json
```

(The `tee` writes the captured envelope straight into the evidence directory. If the directory does not yet exist, run `mkdir -p docs/runbooks/evidence/$(date +%F)-bridge` first — Phase 1.2 also creates it idempotently.)

**Pass:** within 30 seconds of Phase 1.1 firing in the primary terminal, exactly one message prints to the side terminal's stdout AND lands in the evidence file. The captured stdout includes a `Subject: agents.command.jarvis` header and a JSON payload body. A 30s timeout with zero messages means Phase 1 did not publish — abort and diagnose Phase 1 before retrying (do not increase the timeout).

### 2.2 Reconcile the captured envelope against the wire contract

Inspect the JSON payload captured in 2.1:

```bash
sed -n '/^{/,$p' docs/runbooks/evidence/$(date +%F)-bridge/phase-2-envelope.json \
    | jq '{version, event_type, source_id, payload_message: .payload.message}'
```

(The `sed` strips the human-readable subject/header lines that `nats sub` prepends, leaving the JSON body for `jq` to parse.)

**Pass:** the printed object has `version == "1.0"`, `event_type == "command"`, `source_id == "reachy-bridge-gateway"` (or whatever the `adapter="reachy-bridge"` parameter resolves to per `common/envelope.py` — if the live shape differs, document the actual `source_id` in the RESULTS doc and fold via §7.3 rather than improvising). The `payload.message` field contains the literal string `what's the fleet status?` (matching the `--phrase` argument from Phase 1.1).

---

## Phase 3: Standalone tool-wrapper probe

Calls `AgentStatusTool` directly, with no Pollen and no `JarvisClient` instance built by the operator — the tool constructs its own `JarvisClient(adapter="reachy-bridge")` per TASK-FG-006. Any failure here is the wrapper layer (parameter forwarding, graceful-error contract, `Fleet offline:` text shape), not the underlying NATS path that Phase 1 already proved.

### 3.1 Invoke the tool class with the default `agent="all"` parameter

```bash
python -c "
import asyncio

from reachy.external_content.external_tools.agent_status import AgentStatusTool


async def main() -> None:
    tool = AgentStatusTool()
    result = await tool.run(agent='all')
    print(result)


asyncio.run(main())
"
```

**Pass:** stdout is a non-empty string that mentions ≥ 1 known fleet agent name (same `architect-agent` / `product-owner-agent` / `study-tutor` / `forge` / `specialist-agent` set as Phase 1). The text does NOT start with `Fleet offline:` (that's the graceful path, asserted in Phase 6). Save the stdout into `evidence/{YYYY-MM-DD}-bridge/phase-3-tool-wrapper.txt`. If stdout is empty or the tool raises any exception (other than a `KeyboardInterrupt` from the operator), that's a wrapper-layer regression against TASK-FG-006 — fold via §7.3 and stop before Phase 4.

### 3.2 Confirm the tool forwards a non-`all` `agent` parameter into the request phrase

The TASK-FG-006 contract says when `agent != "all"` the tool calls `send_command(f"what's the status of {agent}?")`. Easiest live check is to invoke it with a known agent id and confirm the response narrates that specific agent:

```bash
python -c "
import asyncio

from reachy.external_content.external_tools.agent_status import AgentStatusTool


async def main() -> None:
    tool = AgentStatusTool()
    result = await tool.run(agent='forge')
    print(result)


asyncio.run(main())
"
```

**Pass:** stdout mentions `forge` (case-insensitive). Jarvis may answer "forge is idle" or "forge has no recent activity" — any narration that names `forge` is a pass. If the response is identical to Phase 3.1's all-fleet narration (i.e. the parameter was ignored), that's a TASK-FG-006 regression — fold via §7.3.

---

## Phase 4: Pollen launch

Launch `reachy_mini_conversation_app` against the Bridge profile inside a detached `tmux` window. `tmux` is load-bearing here for two reasons: (a) Phase 5 is voice-driven, so the operator needs to step away from this terminal to talk to Reachy; (b) Phase 6 stops NATS while Pollen is still running, and the Pollen log of that disruption is the evidence — losing it to a closed terminal would force a re-run. After the voice probe, the operator re-attaches to inspect `/tmp/bridge-pollen.log`.

### 4.1 Start Pollen in a detached tmux session

```bash
tmux new-session -d -s bridge-pollen \
    "reachy_mini_conversation_app --profile bridge 2>&1 | tee /tmp/bridge-pollen.log"
```

(Adjust the binary path / launch command to match the operator's Pollen install — the strategy doc and the Reachy README are the source of truth for the exact entry point on this host. Bridge uses a different `voice.txt` from Scholar per scope §3.2 / TASK-FG-006 AC, so the personas should be audibly distinct in Phase 5.)

**Pass:** the `tmux new-session` command exits 0 and a follow-up `tmux ls` lists `bridge-pollen` as an active session. (A non-zero exit usually means the binary path is wrong or a stale `bridge-pollen` session already exists; reconcile and re-run. Do not co-launch with `scholar-pollen` — both profiles will compete for the same audio device on the MacBook.)

### 4.2 Confirm the session is alive and the `agent_status` tool registered

```bash
tmux ls | grep bridge-pollen
sleep 5  # let Pollen complete its first boot pass
grep -E 'agent_status|gemini.*connected|tool.*register' /tmp/bridge-pollen.log
```

**Pass:** `tmux ls` shows `bridge-pollen` with at least one window, AND the grep returns at least one line confirming `agent_status` registered AND one line indicating the LLM connection (Gemini Live or whichever Bridge's `voice.txt` resolves to) is up. If neither line is present after a 5-second settle, attach (`tmux attach -t bridge-pollen`) and capture the actual error — that's the gap to fold.

---

## Phase 5: In-Pollen voice probe (HUMAN)

⚠️  **HUMAN step — no shell command available.** Audio out of Reachy lands on speakers; nothing in this runbook captures it programmatically. The receipt for this phase is therefore the operator's transcribed wording — strategy §9 explicitly carves voice transcription out of the e2e automation surface and assigns it to a manual checkpoint.

### 5.1 Speak the magic phrase to Reachy

The operator stands in front of Reachy (or whatever audio path the Bridge profile uses on this host) and says, audibly:

> **Computer, fleet status?**

Listen to the full LLM-driven narration. Bridge's persona per TASK-FG-006 is "authoritative, British English, LCARS-style status-report cadence" — expect a clipped, declarative report like *"All fleet agents nominal. Forge idle. Architect-agent ready. Specialist-agent standing by."* rather than a conversational answer. If the response is conversational (warm, hedging, multi-clause), that's an in-character drift to flag in RESULTS but not a hard fail at this phase.

**Pass:** Reachy produced *some* audible response within the Bridge profile's normal latency window (silence after ~30 s is itself a gap — capture it, fold via §7.3, and skip 5.2's transcription). The substantive content check (data-bearing narration) lives in 5.2 below.

### 5.2 Transcribe the narration verbatim AND note the voice tone

Capture Reachy's reply verbatim into the Phase 5 row of the (yet-to-be-created) Phase 8 RESULTS doc. Use a fenced block. Preserve hesitation markers — `uh`, `[pause]`, `[…]` — instead of cleaning them up; even a hesitant reply is proof that the LLM consumed the tool output, and edited transcripts hide that signal. If the operator types from memory rather than from a recording, write `(transcribed from memory)` next to the fence header.

**Pass:** **two conditions, both required.** (a) **Content:** the transcript names ≥ 1 known fleet agent (same set as Phase 1's `KNOWN_AGENTS` in the probe — `architect-agent` / `product-owner-agent` / `study-tutor` / `forge` / `specialist-agent`). If none surface, that is a real gap in the Bridge tool ↔ LLM integration path, even if Phases 1–3 were green — fold and stop before Phase 6. (b) **Voice tone:** the operator notes whether the Bridge voice is **audibly distinct** from the Scholar voice (Scholar runbook Phase 4 produced its own transcript; the operator should compare from memory or by replaying the Scholar evidence). TASK-FG-006 acceptance criterion explicitly requires Bridge's `voice.txt` to pin a different speaker from Scholar's. If the two voices are indistinguishable, fold via §7.3 against `reachy/external_content/external_profiles/bridge/voice.txt` — the e2e tooling path is green but the persona-differentiation contract is not.

---

## Phase 6: Graceful degradation

⚠️  **Destructive — confirm with the operator before running.** This phase stops the NATS container on GB10. While stopped, every process across the fleet that depends on `agents.command.jarvis`, `agents.status.>`, or `pipeline.>` will fail or queue. The phase is necessary because the TASK-FG-006 acceptance criterion mandates a graceful `Fleet offline:` text path — but the blast radius is wider than just this runbook.

### 6.1 Stop the NATS container on GB10

⚠️  **Destructive — confirm with the operator before running.** Stops the canonical NATS broker; any other agent or runbook depending on NATS will fail until Phase 7.1 restores it.

```bash
ssh promaxgb10-41b1 'docker stop ships-computer-nats'
```

**Pass:** the SSH command exits 0 and prints `ships-computer-nats` to stdout (docker's stop confirmation). A follow-up `nats --server "nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222" account info` should now fail with `connection refused` or `i/o timeout` within a few seconds. (If the account-info still succeeds, the container did not stop — abort Phase 6, restore state via Phase 7.1, fold the discrepancy as a runbook gap.)

### 6.2 Re-run the standalone JarvisClient probe with degradation expected

```bash
python scripts/bridge-probe.py --phrase "what's the fleet status?" \
    --allow-connection-error \
    2> docs/runbooks/evidence/$(date +%F)-bridge/phase-6-jarvisclient-degraded.stderr.txt
```

The `--allow-connection-error` flag suppresses the happy-path asserts so the script exits 0 on a clean `ConnectionError` rather than 1. The stderr redirect captures the `ConnectionError: ...` line for the RESULTS evidence row.

**Pass:** the script exits 0; the stderr file is non-empty and contains a single line of the form `ConnectionError: <message>` (or a subclass of `OSError` — nats-py wraps the underlying socket error). **No Python traceback may appear** — neither in stderr nor stdout; the probe's `try/except` in `scripts/bridge-probe.py` is the contract. If a traceback escapes, the JarvisClient layer is leaking exceptions through the bare-call path — that's the gap to fold (against `common/jarvis_client.py`'s send_command error handling), even though TASK-FG-006's *tool*-layer graceful contract may still be satisfied in 6.3.

### 6.3 Re-run the standalone tool-wrapper probe — assert the graceful `Fleet offline:` text

This is the load-bearing assertion for TASK-FG-006's graceful contract. With NATS still stopped from 6.1:

```bash
python -c "
import asyncio

from reachy.external_content.external_tools.agent_status import AgentStatusTool


async def main() -> None:
    tool = AgentStatusTool()
    result = await tool.run(agent='all')
    print(result)


asyncio.run(main())
" | tee docs/runbooks/evidence/$(date +%F)-bridge/phase-6-tool-degraded.txt
```

**Pass:** stdout is a non-empty string starting with the literal prefix `Fleet offline:` (per TASK-FG-006 acceptance criterion). The string may also contain `NATS unreachable` or equivalent diagnostic phrasing inside the trailing message — that's narration-friendly for the LLM and satisfies the "/equivalent" clause in the strategy §4.2 expected output. **No Python traceback** — the tool's `try/except` in `agent_status.py` must catch both `ConnectionError` and `TimeoutError`. If a traceback leaks here (rather than in 6.2), TASK-FG-006's wrapper-layer graceful contract has regressed — fold via §7.3 against `reachy/external_content/external_tools/agent_status.py`.

---

## Phase 7: Restore + teardown

⚠️  **Destructive — confirm with the operator before running each step.** Restores the NATS broker that Phase 6.1 stopped, shuts down the long-running Pollen session, and confirms the host is back to its pre-runbook posture.

### 7.1 Restart the NATS container on GB10

⚠️  **Destructive — confirm with the operator before running.** Restarts the canonical NATS broker. Subscribers across the fleet will reconnect on their own; the operator does not need to bounce other agents.

```bash
ssh promaxgb10-41b1 'docker start ships-computer-nats'
```

**Pass:** the SSH command exits 0 and prints `ships-computer-nats`. A follow-up `nats --server "nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222" account info` returns the account-info block again, mirroring Phase 0.2. Allow ~5 seconds for the Jarvis subscriber on GB10 to reconnect and start publishing on `agents.status.jarvis` again before running 7.2.

### 7.2 Confirm green again with one final `send_command("ping")`

```bash
python scripts/bridge-probe.py --phrase "ping"
```

(Note: `--phrase "ping"` deliberately uses a different message from the canonical fleet-status phrase. The probe's `KNOWN_AGENTS` assert may not be satisfied by Jarvis's reply to `"ping"` — Jarvis might just answer `"pong"` or `"acknowledged"`. The probe may exit 1 from the assert; that is acceptable for this final check. The signal here is that the *call returns at all* — i.e. NATS + Jarvis + supervisor LLM are all reachable again. Capture the stdout regardless of exit code.)

**Pass:** the script either exits 0 with stdout (Jarvis named ≥ 1 known agent), or exits 1 with stdout AND no `ConnectionError` / `TimeoutError` on stderr (Jarvis answered, but the response did not name a known agent — that's fine for `"ping"`). What is **not** acceptable: a `ConnectionError` / `TimeoutError` on stderr — that means NATS or Jarvis did not actually recover, fold via §7.3 before continuing to teardown.

### 7.3 Kill the Pollen tmux session

⚠️  **Destructive — confirm with the operator before running.** Tears down the Bridge Pollen process; any unflushed conversation state inside Pollen is gone. The on-disk log at `/tmp/bridge-pollen.log` is unaffected by `tmux kill-session` and Phase 8.3 will move it into the dated evidence directory.

```bash
tmux kill-session -t bridge-pollen
```

**Pass:** `tmux ls` no longer lists `bridge-pollen` (or, if it was the only session, returns `no server running on /tmp/tmux-…`).

### 7.4 Confirm the host is back to its pre-runbook posture

```bash
tailscale status | grep -E 'promaxgb10-41b1'
nats --server "nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222" account info | head -3
tmux ls 2>&1 || true
```

**Pass:** Tailscale row reads `idle` / `active`, NATS account-info returns the same shape as Phase 0.2, no `bridge-pollen` session listed.

---

## Phase 8: RESULTS write

Write the dated RESULTS companion doc — this file is what an outside reader will read months from now to know whether the run was green. The runbook below is execution guidance; the RESULTS doc is the verdict, and the verdict lives one row per phase.

### 8.1 Create the RESULTS file at the strategy-§7.1 path

```bash
DATE=$(date +%F)
RESULTS_FILE="docs/runbooks/RESULTS-feat-fg-001-bridge-${DATE}.md"
cp /dev/null "$RESULTS_FILE"  # touch + truncate; safe to re-run
echo "$RESULTS_FILE"
```

(Strategy §7.1 documents the suffix convention for second and third runs on the same day — typically `-followup-a` for a re-run after a quick fix, `-fresh` for a clean restart from Phase 0, and `-post-fix` after a real code landing. The jarvis precedent file `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md` shows the suffixes stacking when a single day produces several execution attempts; reuse that pattern verbatim if the Bridge run needs the same.)

**Pass:** the printed path is present on disk, with zero bytes of content. From here, the operator authors the RESULTS body by hand against the section list in 8.2 below — the strategy doc deliberately chooses not to ship a fillable template, because RESULTS docs are read as narrative receipts and a templated form encourages skim-and-fill rather than thinking.

### 8.2 Populate the RESULTS body — required sections

Strategy §7.1 fixes both the section list and the section order. Author the RESULTS body using the six sections below; do not invent additional sections, do not reorder them, do not collapse the table into a flat narrative:

1. **Header** — date, operator, machines (MacBook + `promaxgb10-41b1`), runbook driven (this file), `fleet-gateway` HEAD commit (`git rev-parse --short HEAD`), Pollen / Jarvis / nats-infrastructure HEAD commits if known.
2. **Outcome** — one of `✅ PASS` / `⏸ BLOCKED` / `❌ FAIL`, followed by one paragraph naming the gap if not PASS.
3. **Per-phase outcomes table** — one row per phase number above (Phase 0 through Phase 7), with columns `Phase / Gate / Outcome / Evidence`. The `Evidence` column points at the relevant file under `evidence/{YYYY-MM-DD}-bridge/` (Phase 1 stdout, Phase 2 envelope JSON, Phase 3 stdout, Phase 5 voice transcript, Phase 6.2 stderr, Phase 6.3 stdout) or at the in-line transcript for Phase 5.
4. **Gaps discovered (if any)** — one numbered `GAP-<SHORT-ID>` block per discovered gap. Strategy §7.3 stipulates the field set for each block: the operator-visible symptom, the trace-or-log-level symptom, the root cause, which runbook section the fix folds back into, and the follow-up task id. Use that field set verbatim — do not invent additional fields here; new gap-fold conventions belong in the strategy doc, not in a single RESULTS file.
5. **Evidence pointers** — paths to all files under `docs/runbooks/evidence/{YYYY-MM-DD}-bridge/`, including the Phase 1/3 stdout captures, the Phase 2 envelope JSON, the Phase 6 degraded-path captures, and any Pollen log excerpt extracted from `/tmp/bridge-pollen.log`.
6. **Close criterion** — one sentence stating what would need to change before this runbook can re-run green (for a PASS run, this is "no changes — re-runnable as-is").

**Pass:** the file lands at the §7.1 path, every one of the six sections above contains non-empty content, and the per-phase outcomes table is exactly eight rows long — one per phase number `0` through `7`. Phase 8 does not have a row in that table; the RESULTS doc is itself the artefact Phase 8 produces.

### 8.3 Move evidence captures into the dated subdirectory

If any Pollen log excerpt was extracted to `/tmp` rather than directly into `docs/runbooks/evidence/{YYYY-MM-DD}-bridge/`, move it now:

```bash
mv /tmp/bridge-pollen.log docs/runbooks/evidence/$(date +%F)-bridge/ 2>/dev/null || true
ls docs/runbooks/evidence/$(date +%F)-bridge/
```

**Pass:** the evidence subdirectory contains, at minimum, the Phase 1 probe stdout, the Phase 2 envelope JSON, the Phase 3 tool-wrapper stdout, the Phase 6.2 ConnectionError stderr, the Phase 6.3 graceful-tool stdout, and (if grepped during Phase 4.2) a Pollen log excerpt or the full `/tmp/bridge-pollen.log`. Every path referenced in the RESULTS doc's "Evidence pointers" section actually resolves on disk.

### 8.4 If any phase failed, file the follow-up task

If the RESULTS outcome is `⏸ BLOCKED` or `❌ FAIL`, create a follow-up code or runbook task per strategy §7.3:

```text
/task-create "Fix GAP-<SHORT-ID>: <one-line summary>" feature_id:FEAT-FG-001
```

The follow-up task body should cite the RESULTS doc path; the `Known issues / forward-references` table at the top of *this* runbook then gains a single new row naming the gap and the follow-up task id. Resist the urge to patch the failed phase's bash inline during this run — the failure itself is the artefact, and editing the runbook before the fix lands erases the diagnostic.

**Pass:** for a BLOCKED/FAIL run, a new task exists in `tasks/backlog/` whose body links to the RESULTS doc, and the `Known issues / forward-references` block at the top of this file has gained a row referencing it. For a PASS run, this step is a no-op.
