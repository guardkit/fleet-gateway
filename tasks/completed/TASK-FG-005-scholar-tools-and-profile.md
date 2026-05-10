---
id: TASK-FG-005
title: Scholar tools + profile (hackathon critical path)
task_type: feature
parent_review: TASK-REV-CB98
feature_id: FEAT-FG-001
wave: 3
implementation_mode: task-work
complexity: 6
estimated_minutes: 110
dependencies:
- TASK-FG-003
domain_tags:
- reachy
- scholar
- graphiti
- tools
- profile
status: completed
consumer_context:
- task: TASK-FG-003
  consumes: GraphitiClient API
  framework: common.graphiti_client (in-process Python in Pollen venv)
  driver: in-process import; fleet-gateway is editable-installed in the Pollen venv
    (`pip install -e .`)
  format_note: "Scholar tool calls `GraphitiClient(default_group_ids=['student-{name}']).search_student_progress(student_name,\
    \ subject)` and narrates the returned dict. The dict is contract-bound (see TASK-FG-003\
    \ ACs) \u2014 keys: streak_days, level_name, recent_xp, near_achievements, topic_confidence,\
    \ data_available."
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001
  base_branch: main
  started_at: '2026-05-10T08:14:15.872888'
  last_updated: '2026-05-10T08:32:58.262281'
  turns:
  - turn: 1
    decision: feedback
    feedback: '- Advisory (non-blocking): task-work produced a report with 2 of 3
      expected agent invocations. Missing phases: 3 (Implementation). Consider invoking
      these agents via the Task tool to strengthen stack-specific quality:

      - Phase 3: `the stack-specific Phase-3 specialist` (Implementation)

      - BDD oracle: 1 scenario(s) failed during pytest-bdd execution.

      Per-failure details:

      - pytest_runner_error: pytest_runner_error: exit=4; ERROR: not found: /home/richardwoollcott/Projects/appmilla_github/fleet-gateway/.guardkit/worktrees/FEAT-FG-001/features/fleet-gateway-common-and-interfaces/fleet-gateway-common-and-interfaces.feat...'
    timestamp: '2026-05-10T08:14:15.872888'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-05-10T08:24:22.542854'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# TASK-FG-005: Scholar Tools + Profile

## Goal

Wire the Scholar profile end-to-end so Reachy can answer
*"How's her revision going?"* by reading real data from Graphiti and
narrating a progress report in character. **This is the hackathon
critical-path task** — TASK-FG-001 → TASK-FG-003 → TASK-FG-005 is the
minimum viable demo.

Deliverables:
1. Replace the placeholder in `query_student_model.py` with a real
   `GraphitiClient` call.
2. Add a new `celebrate_achievement.py` tool.
3. Finalise the Scholar profile (`instructions.txt`, `tools.txt`, `voice.txt`).

## Files to modify

- `reachy/external_content/external_tools/query_student_model.py`
- `reachy/external_content/external_profiles/scholar/instructions.txt`
- `reachy/external_content/external_profiles/scholar/tools.txt`
- `reachy/external_content/external_profiles/scholar/voice.txt` (if not already finalised)

## Files to create

- `reachy/external_content/external_tools/celebrate_achievement.py`
- `tests/test_query_student_model.py`
- `tests/test_celebrate_achievement.py`

## Files NOT to touch

- `openwebui/`, `common/` (consume only), Bridge profile/tools

## Inputs

- Existing skeleton: `reachy/external_content/external_tools/query_student_model.py`
- GraphitiClient API from TASK-FG-003 (default group `student-lilymay`, returns structured progress dict)
- Pollen `core_tools.Tool` subclass pattern (confirmed by A2)
- Tone reference: `chess_coach` built-in profile (per `reachy/README.md`)
- Scope §5.2 (Scholar Gherkin scenarios)

## Acceptance criteria

### query_student_model.py (rewired)

- [ ] Imports `GraphitiClient` from `common.graphiti_client` (Pollen venv has `fleet-gateway` editable-installed)
- [ ] Subclasses `core_tools.Tool` with name `query_student_model`, description, and parameter schema (`subject: str`, `student_name: str` defaulting to `"lilymay"`)
- [ ] `async def run(self, subject: str = "english", student_name: str = "lilymay") -> dict` calls `GraphitiClient(default_group_ids=[f"student-{student_name}"]).search_student_progress(student_name, subject)`
- [ ] Returns the structured dict from `search_student_progress` (keys: `student_name`, `streak_days`, `level_name`, `recent_xp`, `near_achievements`, `topic_confidence`, `data_available`)
- [ ] When Graphiti is unreachable (`data_available=False`), returns a graceful narration-friendly dict that includes `data_available=False`, an `error` message, and a `narration_hint` field telling the LLM to acknowledge no data is available — **never crashes the conversation** (per Scenario 5.2 #2)
- [ ] No placeholder/TODO comments remain
- [ ] `pytest tests/test_query_student_model.py -v` passes with ≥4 tests: happy path (mocked GraphitiClient), unreachable graceful path, group_id construction, parameter defaults

### celebrate_achievement.py (new)

- [ ] Subclasses `core_tools.Tool` with name `celebrate_achievement`, description, and parameter schema (`achievement_type: str` enum — at minimum `streak_milestone`, `level_up`, `topic_mastered`)
- [ ] `async def run(self, achievement_type: str) -> str` returns text that prompts the LLM to narrate a celebration (the actual motion/emotion is delegated to Reachy's built-in `dance` and `emotion` tools — this tool is a *prompt scaffold*, not a motion driver)
- [ ] `pytest tests/test_celebrate_achievement.py -v` passes with ≥3 tests: each enum value returns distinct narration scaffold

### Scholar profile

- [ ] `instructions.txt` defines a Scholar persona with: warm and encouraging tone, British English spelling, Socratic questioning style, queries `query_student_model` at the start of every session before greeting the student
- [ ] `tools.txt` lists exactly: `query_student_model`, `celebrate_achievement` (custom tools) plus the built-ins the persona uses: `camera`, `emotion`, `dance`, `head_tracking`
- [ ] `voice.txt` pins a Gemini voice (per scope §2 D5) — distinct from the Bridge voice (TASK-FG-006)

### General

- [ ] Tools are testable standalone: `python -c "from reachy.external_content.external_tools.query_student_model import QueryStudentModelTool"` succeeds when `fleet-gateway` is on `PYTHONPATH` or installed editably
- [ ] All tests mock `common.graphiti_client.GraphitiClient` — no real FalkorDB required
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Hackathon demo criterion (must hold)

Scholar can answer *"How's her revision going?"* by reading real data
from Graphiti (group `student-lilymay`) and narrating a progress report
in character — confirmed by an end-to-end smoke run on the MacBook +
Reachy daemon before the 11–13 May shoot.

## Seam Tests

```python
"""Seam test: verify GraphitiClient.search_student_progress contract."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("GraphitiClient.search_student_progress")
@pytest.mark.asyncio
async def test_query_student_model_consumes_progress_dict():
    """Verify the Scholar tool consumes the contract-bound progress dict.

    Contract: dict with keys student_name, streak_days, level_name,
    recent_xp, near_achievements, topic_confidence, data_available
    Producer: TASK-FG-003 (GraphitiClient.search_student_progress)
    """
    with patch(
        "common.graphiti_client.GraphitiClient.search_student_progress",
        new_callable=AsyncMock,
    ) as mock_progress:
        mock_progress.return_value = {
            "student_name": "lilymay",
            "streak_days": 5,
            "level_name": "Knight",
            "recent_xp": 240,
            "near_achievements": ["7-day streak"],
            "topic_confidence": {"reading": 0.7},
            "data_available": True,
        }

        from reachy.external_content.external_tools.query_student_model import (
            QueryStudentModelTool,
        )

        tool = QueryStudentModelTool()
        result = await tool.run(subject="english", student_name="lilymay")

        # Producer was called with the contract args
        mock_progress.assert_called_once()
        # Consumer returned a dict the LLM can narrate
        assert isinstance(result, dict), "tool must return a dict"
        assert result.get("data_available") is True, "happy path returns data_available=True"
        assert result.get("streak_days") == 5, "streak_days propagates from producer"
```

## Coach validation

Coach should verify:
- `pytest tests/test_query_student_model.py tests/test_celebrate_achievement.py -v` exits 0 with ≥7 tests
- `pytest -m seam` includes the contract test above
- `instructions.txt`, `tools.txt`, `voice.txt` exist and are non-empty in `reachy/external_content/external_profiles/scholar/`
- `tools.txt` lists `query_student_model` and `celebrate_achievement`
- `query_student_model.py` has no `TODO`, no `placeholder`, no `pass  # stub` in the new code
- ruff and mypy pass on `reachy/external_content/external_tools/`
