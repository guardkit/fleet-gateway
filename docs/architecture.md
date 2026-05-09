# Fleet Gateway — Architecture

**Status:** Active
**Date:** 7 May 2026

---

## Purpose

Fleet Gateway holds the UI surfaces onto the GuardKit NATS message bus. All gateways route through **Jarvis** — the fleet's intent router and supervisor. Jarvis receives natural language, decides which specialist agent can handle it, constructs structured requests, and dispatches via NATS.

Gateways are thin transport adapters. They translate from their modality (HTTP chat, voice) to NATS and back. All routing intelligence lives in Jarvis; all specialist intelligence lives in the agents.

---

## Architecture

```
Gateway (Open WebUI / Reachy / future)
    │
    │ NATS request/reply
    ▼
Jarvis (Qwen3.6-35B-A3B, 3B active)
    │ supervisor decides: dispatch_by_capability / queue_build
    │ constructs structured CommandPayload
    │
    ├──► specialist-agent (architect / product-owner)
    ├──► study-tutor
    └──► forge
```

**Exception — hackathon path:** Reachy Mini Scholar reads directly from Graphiti (no Jarvis, no NATS). This is a temporary shortcut for Scenario 1 ("How's her revision going?"). Post-hackathon, Scholar becomes a full NATS gateway routing through Jarvis.

---

## Gateway inventory

| Gateway | Modality | Transport | Status |
|---|---|---|---|
| **Open WebUI Pipe Function** | Web chat (browser) | NATS → Jarvis → agents | Pipe Function written; Jarvis serve-nats in progress |
| **Reachy Mini "Scholar"** | Physical robot (voice) | Direct Graphiti read (hackathon); NATS → Jarvis (post-hackathon) | Profile created, tool skeleton ready |
| *(future)* Telegram adapter | Mobile messaging | NATS → Jarvis | Deferred |
| *(future)* REST API facade | HTTP clients | NATS → Jarvis | Not scoped |

---

## Design principles

1. **All gateways route through Jarvis.** No gateway calls a specialist agent directly (except Scholar's hackathon shortcut, which is temporary). Jarvis handles intent classification and argument extraction so specialist agents receive clean structured commands.

2. **Gateways are thin.** If you're writing an if/else that decides how to tutor or review architecture, it belongs in an agent, not a gateway. The Open WebUI Pipe Function is ~60 lines. Scholar's tool is ~80 lines.

3. **One gateway per modality, not per agent.** The Pipe Function doesn't need a separate entry per agent. It sends everything to Jarvis. Adding a new agent means registering it in the fleet; no gateway changes needed.

4. **nats-core is the wire contract.** `MessageEnvelope`, `CommandPayload`, `ResultPayload`. Same models between the Pipe Function and Jarvis, between Jarvis and agents, between any future gateway and Jarvis.

---

## Related decisions

| Decision | Location |
|---|---|
| Open WebUI + NATS via Jarvis (full rationale) | `study-tutor/docs/talks/openwebui-nats-pipe-architecture.md` |
| Jarvis serve-nats scope | `jarvis/features/feat-jarvis-006-nats-chat-gateway/` |
| Study-tutor serve-nats scope | `study-tutor/features/nats-fleet-integration/` |
| Everything on GB10 (dark factory topology) | Demo strategy v4 |
| DECISION-DF-001 (no cloud on critical path) | `guardkit/docs/decisions/` |
