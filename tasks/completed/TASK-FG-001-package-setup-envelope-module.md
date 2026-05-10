---
id: TASK-FG-001
title: Package setup + common envelope module
task_type: feature
parent_review: TASK-REV-CB98
feature_id: FEAT-FG-001
wave: 1
implementation_mode: direct
complexity: 3
estimated_minutes: 45
dependencies: []
domain_tags: [packaging, wire-format, pydantic]
status: completed
---

# TASK-FG-001: Package Setup + Common Envelope Module

## Goal

Create the `fleet-gateway` Python package and the shared `common/envelope.py`
module that defines the wire-format envelope every gateway speaks to Jarvis
over NATS.

This is the foundation task — every subsequent task in FEAT-FG-001 imports
from `common/envelope.py`.

## Files to create

- `pyproject.toml` — package definition
- `common/__init__.py` — public exports
- `common/envelope.py` — `build_command_envelope()`, `parse_result_payload()`, Pydantic models
- `common/py.typed` — empty file (PEP 561)
- `tests/__init__.py`
- `tests/test_envelope.py` — unit tests

## Files NOT to touch

- `openwebui/`, `reachy/` — consumers of this module live there but are wired in later tasks
- `docs/architecture.md`

## Inputs

- Wire format reference: `openwebui/nats_fleet_pipe.py` (existing inline construction; lines 68–88)
- Scope §4.1 — `CommandPayload`, `MessageEnvelope`, function signatures
- Scope §6 — A6 corrected: group_id convention is dash form (`student-lilymay`), not double-underscore

## Acceptance criteria

- [ ] `pyproject.toml` exists with `name = "fleet-gateway"`, build backend `hatchling`, src layout NOT used (top-level `common/`), Python `>=3.10`
- [ ] `pyproject.toml` declares dependencies: `nats-py>=2.9.0`, `pydantic>=2.0`, `graphiti-core` (no `aiohttp` — corrected per scope §7 Q1 / §6 A1)
- [ ] `pyproject.toml` declares dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
- [ ] `pyproject.toml` is editable-installable: `pip install -e .` succeeds in a clean venv
- [ ] `common/__init__.py` re-exports `build_command_envelope`, `parse_result_payload`, `CommandPayload`, `MessageEnvelope`
- [ ] `common/py.typed` exists (empty file, PEP 561)
- [ ] `build_command_envelope("hello", "openwebui")` returns a dict matching scope §4.1 — keys: `version="1.0"`, `event_type="command"`, `source_id` (computed from adapter), `correlation_id` (UUID), `payload` (with message text)
- [ ] `build_command_envelope` accepts optional `conversation_history` and `correlation_id` kwargs
- [ ] `parse_result_payload(b'{"payload":{"result":{"response":"hi"}}}')` returns `"hi"`
- [ ] `parse_result_payload` handles all key conventions: `response`, `text`, `reply`, `output`
- [ ] `parse_result_payload` raises `ValueError` containing the upstream error text when payload has `success=false`
- [ ] All public functions and Pydantic models have Google-style docstrings
- [ ] All modules start with `from __future__ import annotations`
- [ ] `pytest tests/test_envelope.py -v` passes with ≥7 tests covering: build happy path, build with history, build with custom correlation_id, parse happy path (×4 key conventions), parse error, malformed JSON
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation notes

- The Pydantic models (`CommandPayload`, `MessageEnvelope`) are pure data containers — no I/O.
- Use `Field(default_factory=lambda: str(uuid.uuid4()))` for `correlation_id` defaults.
- The `source_id` field convention is `{platform}-{role}-gateway`. For `adapter="openwebui"` → `source_id="openwebui-gateway"`. Document this convention in the `build_command_envelope` docstring; downstream tasks (FG-004/005/006) consume it (see §4 Integration Contracts in the IMPLEMENTATION-GUIDE).
- `parse_result_payload` walks `payload.result` first, then falls back to top-level keys. Format JSON pretty-print as final fallback when no text key found.
- **No package install at runtime in OpenWebUI**: this package is imported at *test time* and at Reachy *runtime*; the OpenWebUI deployable is flattened (TASK-FG-004).

## Coach validation

Coach should verify:
- `pip install -e .` exits 0 in a fresh venv
- `python -c "from common import build_command_envelope, parse_result_payload; print('OK')"` exits 0
- `pytest tests/test_envelope.py -v` exits 0 with ≥7 tests
- ruff and mypy pass on `common/` and `tests/`
