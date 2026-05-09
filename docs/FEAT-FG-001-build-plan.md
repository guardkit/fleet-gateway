# Feature Plan: Fleet Gateway Common + Gateway Interfaces

## FEAT-FG-001: Build Plan

**Scope doc:** `fleet-gateway/docs/FEAT-FG-001-scope.md`
**Date:** 9 May 2026
**Target:** Hackathon video shoot 11–13 May

---

## Task Dependency Graph

```
TASK-FG-001 (pyproject.toml + common/envelope.py)
    │
    ├──► TASK-FG-002 (common/jarvis_client.py)
    │        │
    │        ├──► TASK-FG-004 (OpenWebUI pipe refactor)
    │        │
    │        └──► TASK-FG-006 (Bridge profile + agent_status tool)
    │
    └──► TASK-FG-003 (common/graphiti_client.py)
             │
             └──► TASK-FG-005 (Scholar tools + profile)
```

**Wave 1:** TASK-FG-001 (foundation)
**Wave 2:** TASK-FG-002, TASK-FG-003 (clients, parallel)
**Wave 3:** TASK-FG-004, TASK-FG-005, TASK-FG-006 (interfaces, parallel)

---

## Tasks

### TASK-FG-001: Package Setup + Common Envelope Module

- **Complexity:** Small
- **Type:** Implementation
- **Domain tags:** `packaging, wire-format, pydantic`
- **Files to create:**
  - `pyproject.toml` — package definition with deps (nats-py, pydantic, aiohttp, pytest)
  - `common/__init__.py` — public exports
  - `common/envelope.py` — `build_command_envelope()`, `parse_result_payload()`, Pydantic models
  - `tests/__init__.py`
  - `tests/test_envelope.py` — unit tests for envelope construction and parsing
- **Files NOT to touch:** `openwebui/`, `reachy/`, `docs/architecture.md`
- **Dependencies:** None (foundation task)
- **Inputs:**
  - Wire format from `openwebui/nats_fleet_pipe.py` lines 68–88 (existing inline envelope)
  - MessageEnvelope pattern from `nats-core` (version, event_type, source_id, correlation_id)
  - Distributed agent orchestration doc (topic structure, envelope schema)
- **Acceptance criteria:**
  - [ ] `pyproject.toml` exists with `name = "fleet-gateway"`, deps include nats-py>=2.9.0, pydantic>=2.0, aiohttp>=3.9.0
  - [ ] `build_command_envelope("hello", "openwebui")` returns a valid dict with version, event_type, source_id, correlation_id, and payload containing message text
  - [ ] `parse_result_payload(b'{"payload":{"result":{"response":"hi"}}}')` returns `"hi"`
  - [ ] `parse_result_payload` handles all key conventions: response, text, reply, output
  - [ ] `parse_result_payload` raises `ValueError` for failed responses (success=false)
  - [ ] `pytest tests/test_envelope.py` passes with ≥5 tests covering happy path + error cases

---

### TASK-FG-002: Jarvis NATS Client

- **Complexity:** Medium
- **Type:** Implementation
- **Domain tags:** `nats, async, client`
- **Files to create:**
  - `common/jarvis_client.py` — `JarvisClient` class
  - `tests/test_jarvis_client.py` — unit tests with mocked NATS
- **Files NOT to touch:** `openwebui/`, `reachy/`
- **Dependencies:** TASK-FG-001 (imports envelope module)
- **Inputs:**
  - NATS request-reply pattern from `openwebui/nats_fleet_pipe.py` lines 98–117
  - NATS topic: `agents.command.jarvis` (from architecture doc)
  - Status query topic: `jarvis.status.query` (from Reachy bridge design doc)
- **Acceptance criteria:**
  - [ ] `JarvisClient(nats_url, timeout, adapter)` constructor accepts config
  - [ ] `send_command(message, conversation_history)` builds envelope via `build_command_envelope`, publishes to `agents.command.jarvis`, returns parsed response text
  - [ ] `query_status(agent="all")` publishes to `jarvis.status.query`, returns status text
  - [ ] `TimeoutError` raised with helpful message when Jarvis doesn't respond
  - [ ] `ConnectionError` raised with start instructions when no responders
  - [ ] Connection lifecycle: connect on first use, close after request (stateless per call, matches pipe pattern)
  - [ ] `pytest tests/test_jarvis_client.py` passes with mocked nats.connect

---

### TASK-FG-003: Graphiti Client

- **Complexity:** Medium
- **Type:** Implementation
- **Domain tags:** `graphiti, http, student-model`
- **Files to create:**
  - `common/graphiti_client.py` — `GraphitiClient` class
  - `tests/test_graphiti_client.py` — unit tests with mocked HTTP
- **Files NOT to touch:** `openwebui/`, `reachy/`
- **Dependencies:** TASK-FG-001 (imports from common)
- **Inputs:**
  - Graphiti MCP tool interface (search_memory_facts, search_nodes)
  - Group ID convention: `study_tutor__student_model` (underscore, double-underscore separator)
  - Student model fields: streak_days, level_name, recent_xp, topic_confidence, near_achievements
  - Existing tool skeleton: `reachy/external_content/external_tools/query_student_model.py`
- **Acceptance criteria:**
  - [ ] `GraphitiClient(graphiti_url, group_ids)` constructor accepts config
  - [ ] `search(query, group_ids, num_results)` posts to Graphiti HTTP API and returns list of fact dicts
  - [ ] `search_student_progress(student_name, subject)` returns structured dict with: student_name, streak_days, level_name, recent_xp, near_achievements, topic_confidence, data_available
  - [ ] Graceful degradation: returns `{"data_available": False, "error": "..."}` when Graphiti unreachable (never raises)
  - [ ] `pytest tests/test_graphiti_client.py` passes with mocked aiohttp responses
- **Open question:** Verify exact Graphiti HTTP API endpoint shape. [ASSUMPTION A1: /search with query + group_ids]. If Graphiti only exposes MCP tools, we may need to use the MCP client instead of raw HTTP. Check against running instance.

---

### TASK-FG-004: OpenWebUI Pipe Function Refactor

- **Complexity:** Small
- **Type:** Refactor
- **Domain tags:** `openwebui, pipe-function, integration`
- **Files to modify:**
  - `openwebui/nats_fleet_pipe.py` — replace inline envelope with imports from `common/`
- **Files NOT to touch:** `reachy/`, `common/` (consume only)
- **Dependencies:** TASK-FG-002 (imports JarvisClient)
- **Inputs:**
  - Current working pipe function (preserve Valve interface, Pipe interface)
  - JarvisClient API from TASK-FG-002
- **Acceptance criteria:**
  - [ ] `nats_fleet_pipe.py` imports `JarvisClient` from `common.jarvis_client`
  - [ ] Inline envelope construction (lines 68–88) replaced with `JarvisClient.send_command()`
  - [ ] `Pipe.pipes()` still returns `[{"id": "jarvis", "name": "Jarvis"}]`
  - [ ] `Pipe.pipe(body)` still accepts Open WebUI request body and returns response string
  - [ ] `Pipe.Valves` still exposes NATS_URL and REQUEST_TIMEOUT
  - [ ] Error messages preserved (timeout, no responders)
  - [ ] File is still self-contained enough to paste into Open WebUI admin (may need inline JarvisClient if import not feasible — see open question)
- **Open question:** Open WebUI Pipe Functions run in an isolated context. Can they import from `common/`? If not, keep the pipe as a standalone file that duplicates the pattern (acceptable for ~60 lines), and `common/` serves the Reachy tools + future gateways. Document the decision either way.

---

### TASK-FG-005: Scholar Tools + Profile (Hackathon Critical Path)

- **Complexity:** Medium
- **Type:** Implementation
- **Domain tags:** `reachy, scholar, graphiti, tools, profile`
- **Files to modify:**
  - `reachy/external_content/external_tools/query_student_model.py` — replace placeholder with GraphitiClient
  - `reachy/external_content/external_profiles/scholar/instructions.txt` — finalise persona
  - `reachy/external_content/external_profiles/scholar/tools.txt` — list working tools
- **Files to create:**
  - `reachy/external_content/external_tools/celebrate_achievement.py` — celebration tool
- **Files NOT to touch:** `openwebui/`, `common/` (consume only)
- **Dependencies:** TASK-FG-003 (imports GraphitiClient)
- **Inputs:**
  - Scholar persona from Reachy bridge design doc (instructions.txt draft)
  - GraphitiClient API from TASK-FG-003
  - Pollen Tool subclass pattern (from existing skeleton + video insights)
  - Tone reference: `chess_coach` built-in profile (per existing README)
- **Acceptance criteria:**
  - [ ] `query_student_model.py` uses `GraphitiClient.search_student_progress()` instead of placeholder
  - [ ] `query_student_model.py` returns structured dict the LLM can narrate (not raw JSON)
  - [ ] `query_student_model.py` handles Graphiti-unavailable gracefully (returns "no data available" message, never crashes)
  - [ ] `celebrate_achievement.py` subclasses Tool with name, description, parameter schema (achievement_type enum)
  - [ ] `celebrate_achievement.py` returns text prompting the LLM to express celebration (motion handled by built-in dance/emotion tools)
  - [ ] `instructions.txt` defines Scholar persona: warm, encouraging, British English, Socratic questioning, queries progress at session start
  - [ ] `tools.txt` lists: `query_student_model`, `celebrate_achievement` (and built-in tools: camera, emotion, dance, head_tracking)
  - [ ] Tools testable standalone: `python -c "from query_student_model import QueryStudentModelTool"` succeeds when fleet-gateway is on PYTHONPATH
- **Hackathon demo criterion:** Scholar can answer "How's her revision going?" by reading real data from Graphiti and narrating a progress report in character.

---

### TASK-FG-006: Bridge Profile + Agent Status Tool

- **Complexity:** Small
- **Type:** Implementation
- **Domain tags:** `reachy, bridge, nats, tools, profile`
- **Files to create:**
  - `reachy/external_content/external_profiles/bridge/instructions.txt` — Ship's Computer persona
  - `reachy/external_content/external_profiles/bridge/tools.txt` — tool list
  - `reachy/external_content/external_profiles/bridge/voice.txt` — voice pin (different to Scholar)
  - `reachy/external_content/external_tools/agent_status.py` — fleet status tool
- **Files NOT to touch:** `openwebui/`, `common/`, Scholar files
- **Dependencies:** TASK-FG-002 (imports JarvisClient)
- **Inputs:**
  - Bridge persona from Reachy bridge design doc (instructions.txt draft)
  - JarvisClient API from TASK-FG-002
  - Pollen Tool subclass pattern
- **Acceptance criteria:**
  - [ ] `agent_status.py` subclasses Tool with name, description, parameter schema (agent: str, default "all")
  - [ ] `agent_status.py` uses `JarvisClient.query_status()` to query NATS
  - [ ] `agent_status.py` handles NATS-unavailable gracefully (returns error message, never crashes)
  - [ ] `instructions.txt` defines Bridge persona: authoritative, British English, LCARS-style, status-report focused
  - [ ] `tools.txt` lists: `agent_status` (and built-in tools: camera, emotion, head_tracking)
  - [ ] `voice.txt` contains a different voice pin to Scholar
- **DDD demo criterion:** Bridge can answer "What's the build status?" by querying fleet state via NATS (or returning a graceful "fleet offline" message if NATS not available).

---

## Execution Notes

### For Claude Code on GB10

This is a Python-only feature in a single repo. All tasks can execute on the
MacBook via Claude Code. The GB10 is needed only for integration testing
against real NATS and Graphiti instances.

### Testing without NATS/Graphiti

All tasks include mocked tests that pass without infrastructure. Integration
tests against real services are a bonus, not a gate.

### Hackathon Critical Path

TASK-FG-001 → TASK-FG-003 → TASK-FG-005 is the minimum path to get Scholar
answering "How's her revision going?" with real Graphiti data. If time is
tight, TASK-FG-002 (JarvisClient), TASK-FG-004 (pipe refactor), and
TASK-FG-006 (Bridge) can be deferred to post-hackathon.

### Open WebUI Pipe Isolation

If TASK-FG-004 determines that Open WebUI pipes can't import external modules,
the pipe stays as a standalone file. The `common/` module still serves Reachy
tools and future gateways. Document this as an ADR in the architecture doc.

---

## Related Documents

- Scope doc: `fleet-gateway/docs/FEAT-FG-001-scope.md`
- Fleet Gateway architecture: `fleet-gateway/docs/architecture.md`
- Reachy Jarvis Bridge design: `jarvis/docs/research/ideas/reachy-nats-bridge-adapter.md`
- nats-core contracts: `nats-core/` repo
- Dev pipeline spec: project knowledge `dev-pipeline-system-spec.md`
