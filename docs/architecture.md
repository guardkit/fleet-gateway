# Fleet Gateway — Architecture

**Status:** Active
**Date:** 7 May 2026

---

## Purpose

Fleet Gateway is the collection of UI surfaces onto the GuardKit NATS message bus. Each gateway connects a different modality to the same fleet of agents. The gateways are thin transport adapters — they don't contain agent logic, orchestration, or business rules. All intelligence lives in the agents.

---

## Gateway inventory

| Gateway | Modality | Transport to agents | Status |
|---|---|---|---|
| **Open WebUI Pipe Function** | Web chat (browser) | NATS request/reply | Phase 1 in progress |
| **Reachy Mini "Scholar"** | Physical robot (voice) | Direct Graphiti read (hackathon); NATS (post-hackathon) | Profile created, tool skeleton ready |
| *(future)* Telegram adapter | Mobile messaging | NATS request/reply | Deferred |
| *(future)* REST API facade | HTTP clients | NATS request/reply | Not scoped |

---

## Open WebUI Pipe Function

```
Browser ──► Open WebUI ──► NATS Pipe Function ──► NATS ──► Agent ──► llama-swap
                                                              │
                                                              ▼
                                                          Graphiti
```

The Pipe Function registers agents as selectable models via the `pipes()` manifold. The `pipe()` method publishes a `CommandPayload` to the agent's NATS command topic and returns the `ResultPayload`. No intermediary LLM routes the request — the user's model selection determines the NATS topic deterministically.

Wire format: nats-core `MessageEnvelope` → `CommandPayload` / `ResultPayload`.

NATS topics:
- Publish: `agents.command.{agent_id}` (via `Topics.resolve()`)
- Subscribe (for response): NATS request/reply inbox (automatic)

---

## Reachy Mini "Scholar"

### Hackathon path (direct Graphiti read)

```
Voice ──► Reachy Mini ──► Gemini Live ──► query_student_model tool ──► Graphiti
```

Scholar is a Pollen `reachy_mini_conversation_app` custom profile. Gemini Live handles the conversation. When the user asks about study progress, Gemini calls the `query_student_model` tool, which reads directly from Graphiti. No NATS, no tutor agent involved — Scholar is a read-only consumer of the student model.

### Post-hackathon path (NATS gateway)

```
Voice ──► Reachy Mini ──► NATS adapter ──► NATS ──► Agents
```

Scholar becomes a NATS publisher, like the Open WebUI Pipe Function. Voice input is transcribed (Whisper on GB10 or Gemini Live STT), published to agent command topics, and responses are spoken via TTS. This is the "Ship's Computer" pattern documented in `jarvis/docs/research/ideas/reachy-mini-integration.md`.

---

## Design principles

1. **Gateways are thin.** No business logic in the gateway. If you're writing an if/else that decides how to tutor, it belongs in the agent, not the gateway.

2. **NATS is the only internal transport.** Gateways translate from their modality (HTTP, voice, WebSocket) to NATS. Agents only speak NATS. This means adding a new UI surface doesn't require changes to any agent.

3. **nats-core is the wire contract.** All NATS messages use the shared Pydantic models from nats-core. The gateway and the agent must agree on `MessageEnvelope`, `CommandPayload`, `ResultPayload`. If the contract changes, it changes in nats-core and both sides update.

4. **One gateway per modality, not per agent.** The Open WebUI Pipe Function exposes ALL agents via a manifold. A Telegram adapter would do the same. Don't build one gateway per agent — build one gateway per modality that routes to all agents.

---

## Related decisions

| Decision | Location |
|---|---|
| Open WebUI + NATS replaces Claude Desktop | `study-tutor/docs/talks/openwebui-nats-pipe-architecture.md` |
| Everything on GB10 (dark factory topology) | Same doc, "Architecture" section |
| NATS everywhere, no MCP in production path | Same doc, "What this replaces" section |
| Embeddings via llama-swap, not Ollama | `ddd-southwest-demo-strategy.md` v3, decisions table |
| ChromaDB PersistentClient on GB10 | Same |
