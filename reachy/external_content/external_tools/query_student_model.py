"""Scholar's student model query tool — reads from Graphiti.

Subclasses ``core_tools.Tool`` from ``reachy_mini_conversation_app`` to
provide the Scholar profile with access to the shared Graphiti student
model. The study-tutor writes session data (topic confidence, XP, streaks,
achievements) during tutoring sessions; this tool reads it.

The tool returns a plain dict which Gemini Live narrates in character per
the Scholar persona in ``instructions.txt``.

Contract (TASK-FG-003 + scope §6 A6):

* The Graphiti group_id used for queries is ``f"student-{student_name}"``
  — dash form, **never** the rejected double-underscore form.
* :meth:`GraphitiClient.search_student_progress` returns a dict with keys
  ``student_name``, ``streak_days``, ``level_name``, ``recent_xp``,
  ``near_achievements``, ``topic_confidence`` and ``data_available``. On
  any failure it returns ``{"data_available": False, "error": "..."}``.

Graceful degradation (scope §5.2 #2): when Graphiti is unreachable the
tool **must never crash the conversation**. It returns a narration-friendly
dict that includes ``data_available=False``, an ``error`` message and a
``narration_hint`` field instructing the LLM to acknowledge no data is
available.
"""

from __future__ import annotations

import logging
from typing import Any

from common.graphiti_client import GraphitiClient

logger = logging.getLogger(__name__)

#: Default student name (per scope §6 A6 — Lilymay is the hackathon student).
DEFAULT_STUDENT_NAME = "lilymay"

#: Default subject for the Scholar persona (per scope §2 D5 — English).
DEFAULT_SUBJECT = "english"

#: Narration hint baked into the unreachable-degraded response so the LLM
#: knows to acknowledge missing data instead of fabricating progress.
_NARRATION_HINT_NO_DATA = (
    "No study data is available right now. Acknowledge this honestly — "
    "ask whether the tutor session has run yet — and do not invent progress, "
    "levels, streaks or achievements."
)


def _ensure_narration_friendly(
    progress: dict[str, Any], student_name: str
) -> dict[str, Any]:
    """Augment a degraded-Graphiti response with narration hints.

    The ``GraphitiClient`` already returns ``{"data_available": False,
    "error": "..."}`` on connection / auth failures. The Scholar tool layers
    on a ``narration_hint`` and a ``student_name`` so the LLM can produce a
    natural in-character apology rather than crashing.

    Args:
        progress: The dict returned by
            :meth:`GraphitiClient.search_student_progress`.
        student_name: The student name used for the query (defaulted by the
            tool when the LLM omits it).

    Returns:
        A new dict — the input is not mutated. Keys ``student_name``,
        ``error`` and ``narration_hint`` are guaranteed to be present when
        ``data_available`` is ``False``.
    """
    if progress.get("data_available", False):
        return progress

    augmented: dict[str, Any] = dict(progress)
    augmented.setdefault("student_name", student_name)
    augmented.setdefault("error", "graphiti unavailable")
    augmented["narration_hint"] = _NARRATION_HINT_NO_DATA
    augmented["data_available"] = False
    return augmented


# ---------------------------------------------------------------------------
# Pollen core_tools.Tool subclass
# ---------------------------------------------------------------------------
#
# Pollen's SDK is not available outside the Reachy daemon's Python
# environment. To keep the module importable for unit tests and editable
# installs (per AC: ``python -c "from ... import QueryStudentModelTool"``
# must succeed), we fall back to a no-op base class when the import fails.

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


class QueryStudentModelTool(_PollenTool):  # type: ignore[misc]
    """Look up a student's current study progress from the knowledge graph.

    Call this whenever someone asks how revision is going, what
    achievements are close to being unlocked, or what topic to study next.
    The progress dict is read live from Graphiti via
    :class:`common.graphiti_client.GraphitiClient`.
    """

    name = "query_student_model"
    description = (
        "Look up the student's current study progress: streak, level, "
        "recent XP, topic confidence, nearest unlockable achievements. "
        "Call this whenever someone asks how revision is going or what "
        "to study next."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": (
                    "Subject domain to scope the progress narrative around — "
                    "for the Scholar profile this is typically 'english'."
                ),
                "default": DEFAULT_SUBJECT,
            },
            "student_name": {
                "type": "string",
                "description": (
                    "Identifier of the student in the Graphiti graph "
                    "(without the 'student-' prefix). Defaults to 'lilymay'."
                ),
                "default": DEFAULT_STUDENT_NAME,
            },
        },
        "required": [],
    }

    async def run(
        self,
        subject: str = DEFAULT_SUBJECT,
        student_name: str = DEFAULT_STUDENT_NAME,
    ) -> dict[str, Any]:
        """Execute the student model query.

        Constructs a fresh :class:`GraphitiClient` per call (mirrors the
        connect-per-call pattern in ``common.graphiti_client``) with the
        per-student ``group_id`` ``f"student-{student_name}"``.

        Args:
            subject: Subject domain narrative is being shaped for. Defaults
                to ``"english"``.
            student_name: Student identifier without the ``student-``
                prefix. Defaults to ``"lilymay"``.

        Returns:
            Dict from
            :meth:`GraphitiClient.search_student_progress`. When
            ``data_available`` is ``False`` the dict is augmented with a
            ``narration_hint`` field instructing the LLM to acknowledge
            missing data — Scholar must never crash the conversation
            (scope §5.2 #2).
        """
        client = GraphitiClient(default_group_ids=[f"student-{student_name}"])
        try:
            progress = await client.search_student_progress(student_name, subject)
        except Exception as exc:  # noqa: BLE001 — must never bubble out of tool
            logger.exception(
                "QueryStudentModelTool.run unexpected failure for %s/%s",
                student_name,
                subject,
            )
            return _ensure_narration_friendly(
                {
                    "data_available": False,
                    "error": f"unexpected: {exc}",
                },
                student_name,
            )

        if not isinstance(progress, dict):
            logger.warning(
                "QueryStudentModelTool.run got non-dict from GraphitiClient: %r",
                progress,
            )
            return _ensure_narration_friendly(
                {"data_available": False, "error": "malformed progress payload"},
                student_name,
            )

        return _ensure_narration_friendly(progress, student_name)


__all__ = [
    "DEFAULT_STUDENT_NAME",
    "DEFAULT_SUBJECT",
    "QueryStudentModelTool",
]
