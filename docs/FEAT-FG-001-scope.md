# Feature Spec: Fleet Gateway Common + Gateway Interfaces

## FEAT-FG-001: Shared Gateway Client & Dual Interface Build-Out

**Status:** Draft
**Date:** 9 May 2026
**Repo:** `guardkit/fleet-gateway`
**Predecessor:** Demo strategy v4 (7 May), Reachy Jarvis Bridge design doc (8 May)
**Deadline:** Hackathon video shoot 11–13 May; DDD Southwest 16 May

---

## 1. Problem Statement

The fleet-gateway repo has two gateways (OpenWebUI pipe, Reachy Scholar) that
both need to talk to Jarvis via NATS. The OpenWebUI pipe already has a working
implementation with the NATS envelope/request-reply pattern inlined. The Reachy
Scholar tool has a skeleton with a `TODO: Wire the actual Graphiti client here`.

Both gateways duplicate (or will duplicate) the same wire protocol code:
building `CommandPayload` envelopes, NATS request-reply to Jarvis, parsing
`ResultPayload` responses. This should be a shared module.

Additionally, Scholar's hackathon shortcut (direct Graphiti read) needs to
actually work — the tool skeleton returns placeholder data.

---

## 2. Scope

### In Scope

1. **`common/` module** — shared gateway client library:
   - `envelope.py`: `build_command_envelope()`, `parse_result_payload()`
   - `jarvis_client.py`: `JarvisClient` class wrapping NATS connect → request → close
   - `graphiti_client.py`: `GraphitiClient` class wrapping Graphiti search queries
   - Consistent error handling, timeout, reconnection patterns

2. **OpenWebUI Pipe Function** — refactor `nats_fleet_pipe.py`:
   - Import from `common/` instead of inline envelope construction
   - Preserve existing Valve configuration (NATS_URL, REQUEST_TIMEOUT)
   - Maintain backward compatibility with Open WebUI Pipe interface

3. **Reachy Scholar tools** — wire the working implementations:
   - `query_student_model.py`: Replace placeholder with real Graphiti client
   - `celebrate_achievement.py`: New tool triggering celebration dances/emotions
   - Scholar profile (`instructions.txt`, `tools.txt`, `voice.txt`): Finalise
   - Bridge profile: Create with `agent_status` tool using shared JarvisClient

4. **Tests** — pytest suite covering:
   - Common module unit tests (envelope building, response parsing)
   - Integration tests with mock NATS (or real NATS if available)
   - Reachy tool tests (standalone, without Pollen SDK)

### Out of Scope

- **Phase 2 NATS backend swap** — replacing OpenAI Realtime with Parakeet/Kokoro
  is post-DDD work. Phase 1 uses cloud voice.
- **Jarvis serve-nats implementation** — Jarvis receiving and routing commands
  is a separate feature (FEAT-JARVIS-006). We build the client side here.
- **nats-core package changes** — we consume nats-core patterns but the shared
  module is gateway-specific. No changes to the wire contract.
- **Reachy hardware integration** — app deployment to Pi, Tailscale setup,
  daemon connection. That's hands-on-hardware work, not this feature.
- **Open WebUI deployment** — already deployed as Docker container on GB10.
- **Telegram / REST adapters** — future gateways. The common module is designed
  for them but we don't build them now.

### Decisions Already Made

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | All gateways route through Jarvis | Architecture doc: no gateway calls agents directly |
| D2 | Scholar's direct Graphiti read is a hackathon shortcut | Will become NATS-routed post-hackathon |
| D3 | nats-core MessageEnvelope is the wire format | Established contract, 97% test coverage |
| D4 | External profiles pattern for Reachy (not scaffolded clone) | April decision confirmed by fleet-gateway repo structure |
| D5 | Gemini Live backend for Scholar Phase 1 | Already configured in Reachy README |
| D6 | OpenAI Realtime or Gemini Live for voice (Phase 1) | Cloud voice acceptable for hackathon |

---

## 3. Architecture

### 3.1 Current State

```
fleet-gateway/
├── openwebui/
│   └── nats_fleet_pipe.py      # Inline envelope construction, working
├── reachy/
│   └── external_content/
│       └── external_tools/
│           └── query_student_model.py  # Skeleton, returns placeholder
└── docs/
    └── architecture.md          # Design principles documented
```

### 3.2 Target State

```
fleet-gateway/
├── common/                      # NEW: shared gateway library
│   ├── __init__.py
│   ├── envelope.py              # build_command_envelope(), parse_result_payload()
│   ├── jarvis_client.py         # JarvisClient: NATS request-reply to Jarvis
│   └── graphiti_client.py       # GraphitiClient: search queries to Graphiti
├── openwebui/
│   ├── README.md
│   └── nats_fleet_pipe.py       # REFACTORED: imports from common/
├── reachy/
│   ├── README.md                # UPDATED: reflects working tools
│   └── external_content/
│       ├── external_profiles/
│       │   ├── scholar/
│       │   │   ├── instructions.txt   # FINALISED: GCSE tutor persona
│       │   │   ├── tools.txt          # UPDATED: lists working tools
│       │   │   └── voice.txt          # Gemini voice pin
│       │   └── bridge/                # NEW
│       │       ├── instructions.txt   # Ship's Computer persona
│       │       ├── tools.txt          # agent_status, build_status
│       │       └── voice.txt          # Different voice to Scholar
│       └── external_tools/
│           ├── query_student_model.py    # WIRED: real Graphiti queries
│           ├── celebrate_achievement.py  # NEW: celebration animations
│           └── agent_status.py           # NEW: NATS fleet status query
├── tests/
│   ├── __init__.py
│   ├── test_envelope.py
│   ├── test_jarvis_client.py
│   ├── test_graphiti_client.py
│   └── test_query_student_model.py
├── pyproject.toml               # NEW: package definition
└── docs/
    └── architecture.md          # Existing (minor update)
```

### 3.3 Dependency Graph

> Updated 9 May per Q1: drop `aiohttp` (no REST API to call), add `graphiti-core` (talks to FalkorDB directly via `redis://whitestocks:6379`).

```
fleet-gateway/common/
    ├── nats-py (>=2.9.0)         # NATS client
    ├── pydantic (>=2.0)          # Envelope models
    └── graphiti-core             # Direct FalkorDB read for Scholar
                                  # (the deployed graphiti-mcp:8004 speaks MCP,
                                  #  not REST — see §7 Q1)

fleet-gateway/openwebui/
    └── common/                   # Imports envelope + JarvisClient
                                  # NOTE: cannot pip-install at runtime — the
                                  # deployable .py must be self-contained.
                                  # See §7 Q4.

fleet-gateway/reachy/external_tools/
    └── common/                   # Imports GraphitiClient (Scholar)
    └── common/                   # Imports JarvisClient (Bridge)
```

### 3.4 Import Strategy for Reachy Tools

Reachy external tools run inside `reachy_mini_conversation_app` which doesn't
know about fleet-gateway. The tools need to import from `common/` without
fleet-gateway being pip-installed in the Pollen venv.

Solution: add fleet-gateway to `PYTHONPATH` via the launch script:

```bash
export PYTHONPATH="/path/to/fleet-gateway:$PYTHONPATH"
```

Or install fleet-gateway as editable in the Pollen venv:

```bash
pip install -e /path/to/fleet-gateway
```

---

## 4. API Contracts

### 4.1 common/envelope.py

```python
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime, timezone


class CommandPayload(BaseModel):
    """Wire format for commands sent to Jarvis."""
    command: str = "chat"
    args: dict
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class MessageEnvelope(BaseModel):
    """Standard fleet-gateway envelope wrapping all messages."""
    version: str = "1.0"
    event_type: str = "command"
    source_id: str
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict


def build_command_envelope(
    message: str,
    adapter: str,
    conversation_history: list[dict] | None = None,
    correlation_id: str | None = None,
) -> dict:
    """Build a CommandPayload envelope for Jarvis.

    Args:
        message: The user's latest message text.
        adapter: Gateway identifier (e.g. "openwebui", "reachy-scholar").
        conversation_history: Optional list of {role, content} dicts.
        correlation_id: Optional correlation ID (auto-generated if omitted).

    Returns:
        Dict ready for JSON serialisation and NATS publish.
    """
    ...


def parse_result_payload(response_data: bytes) -> str:
    """Extract response text from a Jarvis ResultPayload.

    Handles multiple response key conventions (response, text, reply, output).
    Returns formatted JSON as fallback if no text key found.

    Args:
        response_data: Raw bytes from NATS response.

    Returns:
        Response text string.

    Raises:
        ValueError: If response cannot be parsed.
    """
    ...
```

### 4.2 common/jarvis_client.py

```python
class JarvisClient:
    """Async NATS client for sending commands to Jarvis.

    Handles connection lifecycle, request-reply, timeout, and reconnection.
    Used by both OpenWebUI pipe and Reachy Bridge tools.
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        timeout: int = 120,
        adapter: str = "unknown",
    ):
        ...

    async def send_command(
        self,
        message: str,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """Send a chat command to Jarvis and return the response text.

        Builds envelope via build_command_envelope(), publishes to
        agents.command.jarvis via NATS request-reply, parses response
        via parse_result_payload().

        Args:
            message: User's message text.
            conversation_history: Optional conversation context.

        Returns:
            Jarvis response text.

        Raises:
            TimeoutError: Jarvis didn't respond within timeout.
            ConnectionError: NATS server unreachable.
        """
        ...

    # NOTE (9 May, §7 Q3): `query_status()` is dropped. There is no
    # `jarvis.status.query` topic in nats-core; the Bridge `agent_status`
    # tool now calls `send_command("what's the fleet status?")` and lets
    # Jarvis narrate. Removing this method keeps JarvisClient as a single
    # request-reply primitive over `agents.command.jarvis`.
```

### 4.3 common/graphiti_client.py

> Revised 9 May per §7 Q1 / §6 A1. The deployed Graphiti is the **MCP server** at
> `http://promaxgb10-41b1:8004/mcp/`, not a REST `/search` server. Rather than
> implement an MCP-over-HTTP client inside a Pollen tool, GraphitiClient wraps
> `graphiti-core` and connects to FalkorDB directly (matches the proven pattern
> in [`guardkit/guardkit/knowledge/graphiti_client.py`](../../guardkit/guardkit/knowledge/graphiti_client.py)).

```python
class GraphitiClient:
    """Async client for querying the Graphiti knowledge graph via graphiti-core.

    Used by Scholar's query_student_model tool for direct reads
    (hackathon shortcut). Post-hackathon, this gets replaced by
    routing through Jarvis via JarvisClient.
    """

    def __init__(
        self,
        falkordb_uri: str = "redis://whitestocks:6379",  # Synology via Tailscale
        default_group_ids: list[str] | None = None,      # e.g. ["student-lilymay"]
    ):
        ...

    async def search(
        self,
        query: str,
        group_ids: list[str] | None = None,
        num_results: int = 10,
    ) -> list[dict]:
        """Search Graphiti for relevant facts.

        Args:
            query: Natural language search query.
            group_ids: Override default group IDs.
            num_results: Max results to return.

        Returns:
            List of fact dicts from Graphiti.
        """
        ...

    async def search_student_progress(
        self,
        student_name: str = "lilymay",
        subject: str = "english",
    ) -> dict:
        """Convenience method for student progress queries.

        Searches the study_tutor__student_model group for the student's
        current progress state: streak, level, XP, topic confidence,
        near-achievements.

        Args:
            student_name: Student to query.
            subject: Subject filter.

        Returns:
            Structured progress dict for the LLM to narrate.
        """
        ...
```

---

## 5. Scenarios (Gherkin)

### 5.1 Common Module

```gherkin
Feature: Gateway envelope construction and parsing

  Scenario: Build a command envelope with message and adapter
    Given a message "How's the build going?" and adapter "openwebui"
    When I call build_command_envelope
    Then the envelope has version "1.0"
    And the envelope has event_type "command"
    And the envelope has source_id "openwebui-gateway"
    And the payload contains the message text
    And the payload contains a UUID correlation_id

  Scenario: Parse a successful Jarvis response
    Given a NATS response with payload containing key "response" and value "Build complete"
    When I call parse_result_payload
    Then the result is "Build complete"

  Scenario: Parse a response with "text" key instead of "response"
    Given a NATS response with payload containing key "text" and value "All good"
    When I call parse_result_payload
    Then the result is "All good"

  Scenario: Parse a failed Jarvis response
    Given a NATS response with success=false and error "Agent not found"
    When I call parse_result_payload
    Then a ValueError is raised with message containing "Agent not found"

  Scenario: JarvisClient handles NATS timeout
    Given a JarvisClient with timeout 5 seconds
    And NATS server is not responding
    When I call send_command with "hello"
    Then a TimeoutError is raised

  Scenario: JarvisClient handles no responders
    Given a JarvisClient connected to NATS
    And no agent is listening on agents.command.jarvis
    When I call send_command with "hello"
    Then a ConnectionError is raised with helpful start instructions
```

### 5.2 Scholar Tools

```gherkin
Feature: Scholar query_student_model tool

  Scenario: Query student progress returns structured data
    Given Graphiti is reachable with student data for "lilymay"
    When the query_student_model tool is called with subject "english"
    Then the result contains streak_days as an integer
    And the result contains level_name as a string
    And the result contains topic_confidence as a dict
    And the result has data_available=true

  Scenario: Query returns graceful fallback when Graphiti unreachable
    Given Graphiti is not reachable
    When the query_student_model tool is called
    Then the result has data_available=false
    And the result contains an error message
    And no exception is raised [ASSUMPTION: tool must never crash the conversation]
```

### 5.3 Bridge Tools

> Revised 9 May per §7 Q3. `jarvis.status.query` is not a real topic; the Bridge
> reuses the existing `agents.command.jarvis` request-reply path via JarvisClient.

```gherkin
Feature: Bridge agent_status tool

  Scenario: Query fleet status via Jarvis
    Given JarvisClient is connected to NATS on GB10
    When the agent_status tool is called
    Then the tool publishes a CommandPayload to "agents.command.jarvis"
    And the request body contains a fleet-status query
    And the result is a formatted text status report

  Scenario: Graceful degradation when NATS unreachable
    Given NATS server is not reachable
    When the agent_status tool is called
    Then the result contains an error message
    And no exception is raised
```

---

## 6. Assumptions

| ID | Assumption | Confidence | Impact if Wrong | Status (9 May verification) |
|----|-----------|------------|-----------------|-----------------------------|
| A1 | Graphiti HTTP API exposes `/search` endpoint with `query` + `group_ids` params | ~~Medium~~ | Need to check actual Graphiti REST API shape. MCP tools use different interface. | **REJECTED.** The deployed `graphiti-mcp` container speaks **MCP over HTTP at `http://promaxgb10-41b1:8004/mcp/`** (JSON-RPC 2.0, not REST). The REST `graph_service` (`/search`, `/get-memory`) is in `graphiti/server/` source but is **not deployed**. Live tools are `search_nodes`, `search_memory_facts`, `add_memory`, `get_episodes`, etc. — see Q1 below for the corrected client design. |
| A2 | Pollen's `core_tools.Tool` subclass supports async `run()` method | High | Already confirmed in existing skeleton | Confirmed (no change). |
| A3 | `PYTHONPATH` extension works for importing common/ into Pollen tools | High | Standard Python mechanism, tested in similar setups | Holds for the Reachy side (Pollen runs on the MacBook). **Does not hold for Open WebUI** — see Q4. |
| A4 | Scholar's Gemini Live backend handles tool calling with custom tools | High | Confirmed by Pollen video — astronomy app demonstrates this | Confirmed (no change). |
| A5 | nats-py works in the same async context as Pollen's conversation loop | Medium | Both asyncio-native, but untested together | **Still Medium, but de-risked.** nats-py is the fleet-wide standard (jarvis, study-tutor, specialist-agent all use it on the GB10) and Pollen is asyncio-native. The remaining risk is loop ownership — mitigation is to use a **connect-per-call** pattern in Bridge tools (matches the OpenWebUI pipe at [openwebui/nats_fleet_pipe.py:126](../openwebui/nats_fleet_pipe.py#L126)), so we never share a long-lived NATS connection across Pollen's conversation turns. To be confirmed on first end-to-end run. |
| A6 | Graphiti student model group ID is `study_tutor__student_model` | ~~Medium~~ | Depends on how study-tutor seeds Graphiti; may need alignment | **REJECTED.** Actual prefix in [`study-tutor/src/study_tutor/knowledge/student_model.py:67`](../../study-tutor/src/study_tutor/knowledge/student_model.py#L67) is `STUDENT_GROUP_PREFIX = "student-"`. The student group id is **`student-lilymay`** (dash form, not double-underscore — graphiti-core 0.29 rejects `:` and the colon-form was dropped at integration). Cross-product writes go to `fleet-appmilla` (`FLEET_GROUP_ID`). Note: the `pkg__name` double-underscore convention is a **guardkit** namespace pattern (`guardkit__project_overview`), not a study-tutor pattern. Scholar must query `student-{student_name}`. |

---

## 7. Open Questions

> **Status as of 9 May 2026** — all four questions resolved by inspecting the live deployment on this GB10 host (`promaxgb10-41b1`) plus the `graphiti`, `guardkit`, `study-tutor`, `nats-core`, and `jarvis` source trees. Resolutions below; assumption corrections in §6.

| # | Question | Resolution |
|---|----------|------------|
| Q1 | What is the exact Graphiti HTTP API shape? | **MCP-over-HTTP, not REST.** Single endpoint `http://promaxgb10-41b1:8004/mcp/` (note trailing slash — `/mcp` returns 307). Streamable-HTTP transport, MCP protocol version `2024-11-05`, server identity `Graphiti Agent Memory v1.26.0`. Tool surface (verified by live `tools/list`): `add_memory`, `search_nodes`, `search_memory_facts`, `delete_entity_edge`, `delete_episode`, `get_entity_edge`, `get_episodes`, `clear_graph`, `get_status`. Both search tools accept `query: str`, `group_ids: list[str] \| None`, `max_nodes`/`max_facts: int` (and `entity_types` / `center_node_uuid` respectively). Backend DB is FalkorDB on the Synology NAS at `redis://whitestocks:6379` via Tailscale. Config (single source of truth): [`guardkit/scripts/graphiti-mcp-config.yaml`](../../guardkit/scripts/graphiti-mcp-config.yaml). **Implication for `common/graphiti_client.py`:** the original `aiohttp + POST /search` design (§3.3, §4.3) is wrong for our deployment. Choose one of: (a) use `graphiti-core` Python lib and connect to FalkorDB directly (mirrors [`guardkit/guardkit/knowledge/graphiti_client.py`](../../guardkit/guardkit/knowledge/graphiti_client.py) — proven pattern, but Scholar would need Tailscale access to `whitestocks` from the MacBook); (b) speak MCP-over-HTTP to `:8004` from a small client (matches existing `.mcp.json` wiring across the fleet). **Recommendation: option (a)** — `graphiti-core` directly. It avoids the MCP session/redirect/SSE plumbing inside a Pollen tool, gives Scholar identical read semantics to study-tutor, and the Tailscale dependency already exists in the Reachy README's prerequisites. Drop `aiohttp` from §3.3 deps; add `graphiti-core` and FalkorDB client. |
| Q2 | Does Scholar need a `get_revision_recommendations` tool for hackathon? | **No — confirmed.** Keep scope minimal; `query_student_model` covers Scenario 1. Recommendations require the study-tutor planner pipeline ([`study_tutor.planner.pipeline`](../../study-tutor/src/study_tutor/planner/pipeline.py)), not a read-only Graphiti search — that belongs behind a NATS-routed `study-tutor` agent call (FEAT-FG-002 territory). |
| Q3 | Should Bridge `agent_status` return raw NATS response or formatted text? | **Formatted text, via JarvisClient — not a separate topic.** The Gherkin in §5.3 names `jarvis.status.query`, which **does not exist in nats-core**. Real topics ([`nats-core/src/nats_core/topics.py`](../../nats-core/src/nats_core/topics.py)) are `agents.status.{agent_id}`, `agents.status.>`, `fleet.heartbeat.{agent_id}`, `fleet.heartbeat.>`, and the per-adapter `agents.command.jarvis` request-reply that the OpenWebUI pipe already uses. **Recommendation:** drop `JarvisClient.query_status()` as a distinct method (§4.2) and have the Bridge `agent_status` tool simply call `JarvisClient.send_command("what's the fleet status?")` — Jarvis already owns supervisor/status reasoning, and the LLM-on-Reachy narrates the response text directly. Update Scenario 5.3 to remove the invented topic. (If we later want a low-latency status path that bypasses Jarvis, subscribe briefly to `fleet.heartbeat.>` and aggregate — but not for FEAT-FG-001.) |
| Q4 | Can the OpenWebUI pipe use fleet-gateway as a pip dependency? | **No — confirmed by inspection of the running container.** `docker exec open-webui python -c "import nats"` raises `ModuleNotFoundError`; the Open WebUI image (`ghcr.io/open-webui/open-webui:main`) does not ship nats-py and Pipe Functions execute inside that interpreter. So neither `nats-py` nor `fleet-gateway-common` can be `import`ed from a pasted Workspace Function. Two paths: **(A) Workspace Function (current, hackathon)** — keep `nats_fleet_pipe.py` as a single self-contained file; share code with `common/` only at *source* level (the file imports from `common/` during tests but the deployable artifact is a flattened single file, generated by a small build step or maintained manually). **(B) Pipelines container (post-hackathon)** — separate image we control where `pip install -e fleet-gateway` works; the same `Pipe` class then `from common.envelope import …` cleanly. **Decision for FEAT-FG-001:** target (A). Refactor for testability (extract envelope/parse helpers into `common/`), then keep the deployable `nats_fleet_pipe.py` self-contained — either by inlining the helpers it uses, or by a one-line build script that concatenates `common/envelope.py` ahead of the `Pipe` class. Document the divergence in [`openwebui/README.md`](../openwebui/README.md). |

---

## 8. Related Documents

- Fleet Gateway architecture: `fleet-gateway/docs/architecture.md`
- Reachy Jarvis Bridge design: `jarvis/docs/research/ideas/reachy-nats-bridge-adapter.md`
- Reachy integration outline: `jarvis/docs/research/ideas/reachy-mini-integration.md`
- nats-core wire contract: `nats-core/` repo (MessageEnvelope, Topics)
- Dev pipeline spec: `dev-pipeline-system-spec.md` (CommandPayload patterns)
- Distributed agent orchestration: `distributed_agent_orchestration_architecture.md`
