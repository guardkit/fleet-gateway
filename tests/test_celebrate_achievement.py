"""Tests for ``reachy.external_content.external_tools.celebrate_achievement``.

The tool is a pure prompt scaffold — no I/O, no daemon dependencies — so
the tests are correspondingly small. We verify each enum value yields a
distinct narration scaffold (per AC), the schema advertises the correct
enum, and unknown values fall back gracefully.
"""

from __future__ import annotations

import pytest

from reachy.external_content.external_tools.celebrate_achievement import (
    ACHIEVEMENT_LEVEL_UP,
    ACHIEVEMENT_STREAK_MILESTONE,
    ACHIEVEMENT_TOPIC_MASTERED,
    ACHIEVEMENT_TYPES,
    CelebrateAchievementTool,
)


def test_tool_metadata_matches_acceptance_criteria() -> None:
    """Tool exposes the AC-required name, description and enum schema."""
    tool = CelebrateAchievementTool()
    assert tool.name == "celebrate_achievement"
    assert tool.description and "milestone" in tool.description.lower()
    schema = tool.parameters
    assert schema["type"] == "object"
    enum = schema["properties"]["achievement_type"]["enum"]
    assert ACHIEVEMENT_STREAK_MILESTONE in enum
    assert ACHIEVEMENT_LEVEL_UP in enum
    assert ACHIEVEMENT_TOPIC_MASTERED in enum
    assert schema["required"] == ["achievement_type"]


@pytest.mark.parametrize("achievement_type", list(ACHIEVEMENT_TYPES))
async def test_run_returns_string_for_each_known_type(achievement_type: str) -> None:
    """Each enum value returns a non-empty string scaffold."""
    tool = CelebrateAchievementTool()
    result = await tool.run(achievement_type)
    assert isinstance(result, str)
    assert result.strip()


async def test_run_streak_milestone_distinct_from_level_up() -> None:
    """``streak_milestone`` and ``level_up`` produce different scaffolds."""
    tool = CelebrateAchievementTool()
    streak = await tool.run(ACHIEVEMENT_STREAK_MILESTONE)
    level = await tool.run(ACHIEVEMENT_LEVEL_UP)
    assert streak != level
    assert "streak" in streak.lower()
    assert "level" in level.lower()


async def test_run_topic_mastered_distinct_from_others() -> None:
    """``topic_mastered`` is distinct from streak and level scaffolds."""
    tool = CelebrateAchievementTool()
    streak = await tool.run(ACHIEVEMENT_STREAK_MILESTONE)
    level = await tool.run(ACHIEVEMENT_LEVEL_UP)
    topic = await tool.run(ACHIEVEMENT_TOPIC_MASTERED)
    assert topic != streak
    assert topic != level
    assert "topic" in topic.lower()


async def test_run_unknown_type_returns_generic_scaffold_without_raising() -> None:
    """Unknown enum values must not crash — Scholar must keep the conversation."""
    tool = CelebrateAchievementTool()
    result = await tool.run("never_seen_before")
    assert isinstance(result, str)
    assert result.strip()
    assert "never_seen_before" in result


async def test_each_known_scaffold_mentions_emotion_or_dance_delegation() -> None:
    """Scaffolds remind the LLM to delegate physical celebration."""
    tool = CelebrateAchievementTool()
    for achievement in ACHIEVEMENT_TYPES:
        scaffold = await tool.run(achievement)
        assert "emotion" in scaffold.lower() or "dance" in scaffold.lower(), (
            f"scaffold for {achievement!r} must reference emotion/dance "
            "delegation per task spec"
        )
