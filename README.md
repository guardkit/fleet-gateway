# Fleet Gateway

UI surfaces onto the GuardKit NATS message bus. Each gateway connects a different modality — chat UI, physical robot, future adapters — to Jarvis, the fleet's intent router. Jarvis dispatches to specialist agents (architect, product-owner, study-tutor, forge) over NATS.

## Gateways

### `openwebui/` — Open WebUI NATS Pipe Function

A Python Pipe Function (~60 lines) that sends all user messages to **Jarvis** via NATS. One model in the Open WebUI dropdown: "Jarvis". Jarvis's supervisor (Qwen3.6-35B-A3B, 3B active params) understands intent, constructs structured requests, and dispatches to specialist agents.

The Pipe Function doesn't know what agents exist — Jarvis does. Adding a new agent means registering it in the fleet; the Pipe Function doesn't change.

**Deployment:** Paste into Open WebUI Admin → Workspace → Functions, or drop into the Pipelines container's `/pipelines/` directory.

### `reachy/` — Reachy Mini "Scholar" Profile

A custom profile for Pollen Robotics' `reachy_mini_conversation_app` that turns Scholar (Reachy Mini #1) into a gamification companion for the GCSE Study Tutor. Scholar reads from the Graphiti student model and verbally reports progress, achievements, and session suggestions.

For the hackathon, Scholar reads directly from Graphiti (no NATS, no Jarvis). Post-hackathon, Scholar becomes another NATS gateway — voice in → Jarvis → agents → voice out.

Uses the `external_content/` pattern — no forking of Pollen's upstream repo.

**Deployment:** Clone this repo, set env vars, run `reachy_mini_conversation_app` with `REACHY_MINI_CUSTOM_PROFILE=scholar`.

## Architecture

See `docs/architecture.md` for gateway patterns and how they connect to Jarvis and the NATS bus.

## Related repos

| Repo | Role |
|---|---|
| `jarvis` | Intent router + supervisor (Qwen3.6-35B-A3B); all gateway traffic goes through Jarvis |
| `nats-core` | Shared Pydantic models, NATSClient, Topics registry |
| `nats-infrastructure` | NATS server deployment, JetStream streams, KV config |
| `specialist-agent` | Architect + Product Owner agents (NATS subscribers) |
| `study-tutor` | GCSE Study Tutor agent (NATS subscriber) |
| `guardkitfactory` / `forge` | Build pipeline orchestrator |
