"""Scholar's student model query tool — reads from Graphiti.

Subclasses ``core_tools.Tool`` from ``reachy_mini_conversation_app`` to
provide the Scholar profile with access to the shared Graphiti student
model. The study-tutor writes session data (topic confidence, XP, streaks,
achievements) during tutoring sessions; this tool reads it.

The tool returns a plain dict which Gemini Live narrates in character per
the Scholar persona in ``instructions.txt``.

Dependencies:
    - graphiti-core (for Graphiti client)
    - The Graphiti/FalkorDB instance must be reachable (Synology via Tailscale)

Environment variables:
    - GRAPHITI_URI: FalkorDB connection URI (default: bolt://localhost:7687)
    - GRAPHITI_GROUP_ID: Group ID for student data (default: study_tutor__student_model)
    - STUDENT_NAME: Student name to query (default: lilymay)

TODO: This is a skeleton. The actual Graphiti query needs to be wired
once the student model schema is confirmed and the Graphiti client
import path works inside the Pollen tool framework. The conversation
starter at study-tutor/docs/research/ideas/reachy-integration-conversation-starter.md
has the detailed integration architecture.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Default configuration
_DEFAULT_GRAPHITI_URI = "bolt://localhost:7687"
_DEFAULT_GROUP_ID = "study_tutor__student_model"
_DEFAULT_STUDENT_NAME = "lilymay"


async def _fetch_student_progress(student_name: str) -> dict[str, Any]:
    """Query Graphiti for the student's current progress.

    Reads from the shared student model written by the study-tutor agent.
    Returns a dict with the fields Scholar needs to narrate a progress report.

    This is the integration point. The query shape depends on how the
    study-tutor writes session data to Graphiti — topic confidence nodes,
    gamification state entities, session episode metadata.

    Args:
        student_name: The student to query (e.g. "lilymay").

    Returns:
        Dict with progress fields, or a dict with "error" key on failure.
    """
    graphiti_uri = os.environ.get("GRAPHITI_URI", _DEFAULT_GRAPHITI_URI)
    group_id = os.environ.get("GRAPHITI_GROUP_ID", _DEFAULT_GROUP_ID)

    try:
        # TODO: Wire the actual Graphiti client here.
        #
        # The pattern is:
        #   from graphiti_core import Graphiti
        #   client = Graphiti(graphiti_uri, ...)
        #   nodes = await client.search(
        #       query=f"{student_name} study progress",
        #       group_ids=[group_id],
        #       num_results=10,
        #   )
        #
        # Then extract and structure the progress data from the returned
        # nodes/edges. The student model schema includes:
        #   - Topic confidence scores (per text, per AO)
        #   - XP total and recent session XP
        #   - Current level (from the 15-level progression)
        #   - Streak count (consecutive study days)
        #   - Achievement progress (unlocked + near-unlockable)
        #   - Session history (recent sessions, duration, topics)
        #
        # For the hackathon demo, a subset is sufficient:
        #   streak_days, level_name, recent_xp, near_achievements

        logger.warning(
            "query_student_model: Graphiti client not yet wired — "
            "returning placeholder data for %s",
            student_name,
        )

        # Placeholder until Graphiti is wired
        return {
            "student_name": student_name,
            "streak_days": 0,
            "level_name": "Unknown",
            "recent_xp": 0,
            "near_achievements": [],
            "topic_confidence": {},
            "data_available": False,
        }

    except Exception as exc:
        logger.exception("Failed to query student model for %s", student_name)
        return {
            "error": str(exc),
            "student_name": student_name,
            "data_available": False,
        }


# ---------------------------------------------------------------------------
# Pollen core_tools.Tool subclass
# ---------------------------------------------------------------------------
#
# This try/except allows the module to be tested standalone without the
# Pollen SDK installed. When running inside reachy_mini_conversation_app,
# the import succeeds and the class is registered as a custom tool.

try:
    from reachy_mini_conversation_app.tools.core_tools import Tool

    class QueryStudentModelTool(Tool):
        """Look up a student's current study progress from the knowledge graph.

        Call this whenever someone asks how revision is going, what
        achievements are close to being unlocked, or what topic to study next.
        """

        name = "query_student_model"
        description = (
            "Look up the student's current study progress: streak, level, "
            "recent XP, topic confidence, nearest unlockable achievements. "
            "Call this whenever someone asks how revision is going or what "
            "to study next."
        )

        async def run(self, args: dict, deps: Any) -> dict[str, Any]:
            """Execute the student model query.

            Args:
                args: Tool call arguments from Gemini Live.
                    Optional key: "student_name" (default from env).
                deps: Pollen dependency injection container (provides
                    daemon connection, etc. — not used by this tool).

            Returns:
                Dict with student progress fields for Gemini to narrate.
            """
            student_name = args.get(
                "student_name",
                os.environ.get("STUDENT_NAME", _DEFAULT_STUDENT_NAME),
            )
            return await _fetch_student_progress(student_name)

except ImportError:
    # Running outside reachy_mini_conversation_app (e.g. standalone test)
    logger.debug(
        "reachy_mini_conversation_app not installed — "
        "QueryStudentModelTool not registered"
    )
