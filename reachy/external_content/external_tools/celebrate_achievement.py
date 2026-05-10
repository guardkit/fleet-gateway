"""Scholar's celebration prompt-scaffold tool.

This tool **does not move Reachy**. It returns a short narration scaffold
that the LLM (Gemini Live) wraps in its own voice when the student hits a
milestone. The actual physical celebration — facial expression, dance,
head tracking — is delegated to Reachy's built-in ``emotion``, ``dance``
and ``head_tracking`` tools, which the Scholar profile lists alongside this
one (see ``tools.txt``).

Per TASK-FG-005 ACs:

* Subclasses ``core_tools.Tool`` with name ``celebrate_achievement``.
* Parameter schema: ``achievement_type: str`` enum, at minimum
  ``streak_milestone``, ``level_up`` and ``topic_mastered``.
* ``run`` returns a string — distinct narration scaffold per enum value.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Recognised celebration types. Scholar's persona expects each to map to
#: a clearly distinct narration scaffold so Gemini can vary its wording
#: rather than collapsing every milestone into the same line.
ACHIEVEMENT_STREAK_MILESTONE = "streak_milestone"
ACHIEVEMENT_LEVEL_UP = "level_up"
ACHIEVEMENT_TOPIC_MASTERED = "topic_mastered"

ACHIEVEMENT_TYPES: tuple[str, ...] = (
    ACHIEVEMENT_STREAK_MILESTONE,
    ACHIEVEMENT_LEVEL_UP,
    ACHIEVEMENT_TOPIC_MASTERED,
)


# Mapping of achievement_type → narration scaffold the LLM should rewrite
# in character. Each scaffold names the milestone, suggests an emotional
# tone, and reminds Scholar to delegate the physical celebration to the
# built-in motion tools.
_SCAFFOLDS: dict[str, str] = {
    ACHIEVEMENT_STREAK_MILESTONE: (
        "Celebrate a study-streak milestone. Acknowledge the consistency "
        "warmly — name the streak, note that showing up daily is the hardest "
        "part of revision, and encourage one more day. Trigger a happy "
        "emotion via the 'emotion' tool and a short 'dance' move. Keep the "
        "spoken line to one or two sentences, in Scholar's warm British voice."
    ),
    ACHIEVEMENT_LEVEL_UP: (
        "Celebrate a level-up. Name the new level, frame it as proof that "
        "the recent sessions added up to real progress, and tee up the next "
        "level as something within reach. Trigger an excited 'emotion' and "
        "a celebratory 'dance'. Two sentences, in Scholar's warm British voice."
    ),
    ACHIEVEMENT_TOPIC_MASTERED: (
        "Celebrate mastering a topic. Name the topic, point out a concrete "
        "skill it unlocks for the next paper, and offer a gentle nudge "
        "toward the next weakest topic. Trigger a proud 'emotion' and a "
        "subtle 'dance' motion. Two sentences, in Scholar's warm British voice."
    ),
}


def _unknown_scaffold(achievement_type: str) -> str:
    """Fallback narration scaffold for an unrecognised ``achievement_type``.

    The Scholar tool must never crash the conversation. When Gemini sends
    an unexpected enum value we still return a usable scaffold rather than
    raising — the LLM can degrade to a generic celebration.
    """
    logger.warning(
        "celebrate_achievement: unknown achievement_type=%r — using generic scaffold",
        achievement_type,
    )
    return (
        f"Celebrate the achievement '{achievement_type}'. Acknowledge the "
        "milestone warmly, name what it represents, and encourage the next "
        "step. Trigger a happy 'emotion' and an optional 'dance'. Keep it "
        "to one or two sentences, in Scholar's warm British voice."
    )


# ---------------------------------------------------------------------------
# Pollen core_tools.Tool subclass — mirrors the import-fallback pattern in
# ``query_student_model.py`` so the module is importable for unit tests
# and editable installs even when Pollen's SDK is not available.
# ---------------------------------------------------------------------------

try:
    from reachy_mini_conversation_app.tools.core_tools import (  # type: ignore[import-not-found]
        Tool as _PollenTool,
    )
except ImportError:  # pragma: no cover — exercised only in non-Pollen envs
    logger.debug(
        "reachy_mini_conversation_app not installed — using fallback Tool base"
    )

    class _PollenTool:  # type: ignore[no-redef]
        """Minimal stand-in so the tool class is importable standalone."""

        name: str = ""
        description: str = ""
        parameters: dict[str, Any] = {}


class CelebrateAchievementTool(_PollenTool):  # type: ignore[misc]
    """Prompt scaffold for celebrating a student milestone.

    This tool is a *narration scaffold*, not a motion driver — it returns a
    short prompt that tells Gemini Live how to phrase the celebration and
    which built-in motion tools to chain. Reachy's physical celebration is
    handled by the built-in ``emotion``, ``dance`` and ``head_tracking``
    tools that the Scholar profile already lists.
    """

    name = "celebrate_achievement"
    description = (
        "Generate a short narration scaffold for celebrating a student "
        "milestone (streak, level-up, topic mastered). Returns text the "
        "LLM rewrites in character. Pair with the built-in 'emotion' and "
        "'dance' tools for the physical celebration."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "achievement_type": {
                "type": "string",
                "enum": list(ACHIEVEMENT_TYPES),
                "description": (
                    "Which kind of milestone to celebrate. "
                    "'streak_milestone' for consecutive-day streaks, "
                    "'level_up' for moving up the gamification ladder, "
                    "'topic_mastered' for clearing a topic's confidence bar."
                ),
            }
        },
        "required": ["achievement_type"],
    }

    async def run(self, achievement_type: str) -> str:
        """Return the narration scaffold for ``achievement_type``.

        Args:
            achievement_type: One of :data:`ACHIEVEMENT_TYPES`. Unknown
                values fall back to a generic scaffold rather than raising
                — Scholar must never crash the conversation.

        Returns:
            A short string the LLM rewrites in Scholar's voice. Distinct
            per recognised enum value.
        """
        scaffold = _SCAFFOLDS.get(achievement_type)
        if scaffold is None:
            return _unknown_scaffold(achievement_type)
        return scaffold


__all__ = [
    "ACHIEVEMENT_LEVEL_UP",
    "ACHIEVEMENT_STREAK_MILESTONE",
    "ACHIEVEMENT_TOPIC_MASTERED",
    "ACHIEVEMENT_TYPES",
    "CelebrateAchievementTool",
]
