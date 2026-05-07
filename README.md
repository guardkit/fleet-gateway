# Fleet Gateway

UI surfaces onto the GuardKit NATS message bus. Each gateway connects a different modality — chat UI, physical robot, future adapters — to the same fleet of agents.

## Gateways

### `openwebui/` — Open WebUI NATS Pipe Function

A Python Pipe Function that registers fleet agents as selectable models in Open WebUI. User messages are published to the agent's NATS command topic; responses stream back. No MCP, no intermediary routing model — NATS is the only transport.

Agents exposed: Architect Agent, Product Owner, GCSE Study Tutor, Forge Build Pipeline.

**Deployment:** Paste into Open WebUI Admin → Workspace → Functions, or drop into the Pipelines container's `/pipelines/` directory.

### `reachy/` — Reachy Mini "Scholar" Profile

A custom profile for Pollen Robotics' `reachy_mini_conversation_app` that turns Scholar (Reachy Mini #1) into a gamification companion for the GCSE Study Tutor. Scholar reads from the Graphiti student model and verbally reports progress, achievements, and session suggestions.

Uses the `external_content/` pattern — no forking of Pollen's upstream repo. Pointed at via `REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY` and `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY` env vars.

**Deployment:** Clone this repo on the MacBook, set env vars in `.env`, run `reachy_mini_conversation_app` with `REACHY_MINI_CUSTOM_PROFILE=scholar`.

## Architecture

See `docs/architecture.md` for the gateway patterns and how they connect to the NATS bus.

## Related repos

| Repo | Role |
|---|---|
| `nats-core` | Shared Pydantic models, NATSClient, Topics registry |
| `nats-infrastructure` | NATS server deployment, JetStream streams, KV config |
| `specialist-agent` | Architect + Product Owner agents (NATS subscribers) |
| `study-tutor` | GCSE Study Tutor agent (NATS subscriber, Phase 1 in progress) |
| `guardkitfactory` / `forge` | Build pipeline orchestrator |
