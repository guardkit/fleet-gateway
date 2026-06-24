# Fleet-Gateway Slack Adapter — Jarvis-Fronted Door — Conversation Starter

## For: /feature-spec session · `fleet-gateway` (new adapter) · June 2026

---

## Purpose of this document

Context brief for a `/feature-spec` session that feeds `/feature-spec` →
`/feature-plan` → AutoBuild. **It deliberately skips `/system-arch`** — this is
a new adapter in an existing repo built on a proven, shipped pattern (the Open
WebUI pipe), not a new system. The strategic anchor is
`factory-scaling-and-output-bottleneck-findings.md`; this refines D7.

---

## What is it?

James's (and later the FinProxy founders') door into the factory. A **Slack
channel adapter** in `fleet-gateway` that puts a message into the ecosystem via
**Jarvis** (the intent router) and returns the response — the same pattern as
the Open WebUI pipe James already uses in demos.

The point, in Rich's words: James thinks in **outcomes** and drops a request in;
Jarvis routes it; James stays ignorant of which agent runs. New agent
capabilities register in the fleet and "just work" — no re-educating James or
the FinProxy founders. That outcome-level, frontier-like experience costs some
latency and compute on the entry hop, and that trade is accepted (see Warnings).

---

## The decision this captures (refines findings-doc D7)

The door is **Jarvis-fronted**. Slack adapts onto `agents.command.jarvis`, *not*
onto the Product Owner agent directly — identical to how `openwebui/` and
`reachy/` adapt onto Jarvis. D7's core holds (Slack is a thin, swappable channel
adapter); what changed is *what it adapts onto*. One canonical entry point, many
channels in front of it.

---

## The foundation: what already exists (treat as fixed)

- **`fleet-gateway` is the channel-adapter home.** Its charter: "UI surfaces onto
  the GuardKit NATS message bus… each gateway connects a different modality to
  Jarvis." `openwebui/` (chat) and `reachy/` (voice robot) already ship. Slack is
  the **third** adapter on the same pattern. This repo is the right home (Rich's
  instinct confirmed).
- **`common/` is the shared contract — reuse verbatim:**
  - `common/envelope.py` — `build_command_envelope(message, adapter,
    conversation_history)` builds a `MessageEnvelope` wrapping a
    `CommandPayload(command="chat", args={message, conversation_history,
    adapter})`; `source_id` = `{adapter}-gateway`. `parse_result_payload(bytes)`
    extracts the reply text (keys: response/text/reply/output; surfaces
    `success=false` errors verbatim).
  - `common/jarvis_client.py` — `JarvisClient(nats_url, timeout=120,
    adapter="slack").send_command(message, history)` — **connect-per-call**
    NATS request/reply to `agents.command.jarvis`. Stateless, safe across event
    loops, distinguishes Timeout / no-responders / server-unreachable / failure.
- **Jarvis** (Qwen3.6-35B-A3B supervisor) understands intent, constructs the
  structured request, and dispatches to the specialist whose manifest advertises
  the matching `IntentCapability` signals. "The pipe doesn't know what agents
  exist — Jarvis does. Adding a new agent means registering it in the fleet; the
  adapter doesn't change."
- **Mode-inference confirmation round-trip already exists** in the specialists
  ("I think you want greenfield mode — sound right?") — the built-in safety valve
  for ambiguous routing.
- **Simpler than Open WebUI:** the Workspace interpreter can't `pip install`, so
  the pipe ships a generated self-contained deploy file. The Slack adapter runs
  as a normal service/container and **imports `common/` directly** — no two-file
  dance.

---

## Key decisions (resolved — do not reopen)

| # | Decision | Resolution |
|---|----------|-----------|
| D1 | Door is Jarvis-fronted | Slack → `agents.command.jarvis` via `JarvisClient(adapter="slack")`. Refines findings-doc D7: the adapter targets Jarvis, not a named agent. |
| D2 | Reuse `common/` verbatim | No new wire contract. `build_command_envelope` / `parse_result_payload` / `JarvisClient`. Mirrors `openwebui/` and `reachy/`. |
| D3 | Outcome-level confirmations | Lean on the existing mode-inference round-trip; phrase confirmations as **outcomes** ("I'll treat this as 'what to build next' — go?") so James confirms an outcome, not an agent. He stays agent-ignorant. |
| D4 | Keep a direct path | Do not remove the ability to address an agent directly — power-user route and the fallback when routing is wrong or Jarvis is down. (Fleet-level note, not Slack-specific.) |
| D5 | Approve-to-build is a gate, shared mechanism | The conversational idea→spec is the chat round-trip. Promoting a produced spec into a **build** is side-effecting, so it is an explicit approval (a Slack action → publishes the promote/`feature-planned` event). **Same notification-and-approve mechanism as the output-side loop** — one mechanism, two seats (James at the front, Rich at the back). |
| D6 | Multi-tenant scoping | FinProxy users' Slack maps to the FINPROXY NATS account / `finproxy.>` scope (existing multi-tenancy). James/Rich see all; FinProxy sees only FinProxy. Hard-scope at the NATS layer, not just the UI. |

---

## Warnings & constraints

- **Slack secrets are operator-set.** Bot token, app token, signing-secret
  verification — Rich creates the Slack app and provisions secrets; the adapter
  **never** asks James for them. (Account/credential setup is not something the
  agent performs.)
- **3-second ack vs long sessions.** Slack requires a ~3s ack, but PO greenfield
  sessions run long and the client timeout is 120s. The adapter **must ack
  immediately and post the result asynchronously** (thread reply via
  `response_url` / `chat.postMessage`), never block the event handler.
- **Keep connect-per-call.** It is deliberate (safe across event loops) — do not
  introduce a long-lived NATS connection in the Slack handler without a reason.
- **Misrouting is the failure mode.** The PO modes (impact / scope / evolve) are
  genuinely close — that's *why* the confirmation round-trip exists. Do not
  suppress it for "smoothness"; it is the safety valve.
- **Intent-surface hygiene is now a product concern.** "Add capability and it
  just works" holds *only if* each new manifest advertises clean, non-overlapping
  intents. As the fleet grows, routing quality is something FinProxy feels — the
  manifests become a surface, not just plumbing.
- **The chat reply is a summary, not the artifact.** Jarvis returns a
  conversational reply; the actual roadmap/spec lands as a **file** (output
  handler) plus a NATS result event. The artifact and the approve-to-build gate
  surface visually in the **dashboard** (cross-ref `factory-dashboard-conversation-starter.md`).
- **Latency/compute trade is accepted but bounded** — keep the Jarvis entry hop
  cheap (intent match on the local workhorse / embeddings, not a fat frontier
  call on every message). Reserve frontier for the specialist work.

---

## Interaction model (for /feature-spec to resolve)

Options: a slash command (`/factory <request>`), a DM-to-bot, or a channel
mention; threading model; Block Kit buttons for confirmations and the
approve-to-build gate. **Recommendation:** bot DM / mention for the
conversational loop + Block Kit buttons for confirm/approve, ack-immediately-
then-post-async. **Socket Mode** (not HTTP events) fits the GB10/Tailscale
local-first topology — no public ingress required.

---

## Hardware / topology

| Machine | Role |
|---|---|
| GB10 (2× DGX Spark) | Jarvis + specialists in `serve-nats`; NATS JetStream; the Slack adapter container |
| Slack (cloud) | Channel only — reached via Socket Mode so no inbound public endpoint is needed |
| Tailscale | Connects the adapter/NATS; Slack Socket Mode dials out |

---

## Repo structure (target — mirrors `openwebui/` and `reachy/`)

```
fleet-gateway/
├── common/                    ← reused verbatim (JarvisClient, envelope)
├── openwebui/                 ← existing reference adapter
├── reachy/                    ← existing reference adapter
└── slack/                     ← NEW
    ├── slack_adapter.py       ← Slack Bolt app (Socket Mode) → JarvisClient
    ├── confirm.py             ← Block Kit confirm + approve-to-build handlers
    └── ...
tests/
└── test_slack_adapter.py      ← mocks JarvisClient (zero NATS, like the pipe tests)
```

---

## Open questions for /feature-spec to resolve

1. **Interaction model** (above) — slash vs DM vs mention; threading; Block Kit.
2. **Approve-to-build event contract** — which NATS topic/payload promotes a
   produced spec → a build, and confirm it is the **same gate mechanism** the
   output-side loop uses (one approval surface for both seats).
3. **FinProxy ↔ Slack ↔ NATS-account mapping** — how a Slack workspace/user
   resolves to the FINPROXY account scope; auth/isolation boundary.
4. **Shared adapter base?** — whether to lift the Open WebUI two-file lesson into
   a small shared adapter base now, or keep adapters independent until a third
   forces it (probably the latter — exemplar before template).
5. **Socket Mode vs HTTP events** — confirm Socket Mode given local-first.

---

## What /feature-spec produces

- Slack adapter feature spec: Bolt Socket-Mode app, `common/` reuse,
  ack-then-post-async pattern, outcome-level confirmation + approve-to-build
  Block Kit, multi-tenant scoping.
- Ordered implementation tasks (AutoBuild-ready).
- Test strategy (mock `JarvisClient`, like `tests/test_openwebui_pipe.py`).
- Out of scope (e.g. the interactive PO panel — that folds into the dashboard).

---

## Key insight to carry forward

**The door is a channel, not a brain.** Slack adapts onto Jarvis exactly as Open
WebUI and Reachy do — James and the FinProxy founders get an outcome-level,
frontier-like front door, and new capabilities appear without re-educating
anyone. The conversational loop is the gateway; the side-effecting "build it"
step is an explicit gate that **shares the output-side loop's approval
mechanism**. That reuse — one approval surface for James at the front and Rich at
the back — is the thread tying this doc to the Forge output-loop doc.

---

*Prepared: 19 June 2026 | Jarvis-fronted door → Slack channel adapter*
*Use as context for /feature-spec. Companions: factory-scaling-and-output-bottleneck-findings.md, factory-dashboard-conversation-starter.md*
