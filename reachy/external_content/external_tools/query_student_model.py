"""Scholar's student model query tool — reads the durable learning record.

Subclasses ``core_tools.Tool`` from ``reachy_mini_conversation_app`` to
provide the Scholar profile with the student's current study progress. The
study-tutor writes session data (topic confidence, XP, streaks,
achievements) during tutoring sessions; this tool reads it back.

**Data plane (recon D2 / FEAT-VOICE-004 R05).** The read now goes to the
durable Postgres-backed store **via the study-tutor HTTP adapter on
``:8100``** — the same surface :mod:`ask_tutor` uses — replacing the read of
the frozen Graphiti graph (``student-lilymay``), whose write path is being
torn down. ``student_id`` is derived server-side from the bearer token.

The tool returns a plain dict which the Realtime session narrates in
character per the Scholar persona in ``instructions.txt``.

Graceful degradation (scope §5.2 #2): when the tutor is unreachable the tool
**must never crash the conversation**. It returns a narration-friendly dict
that includes ``data_available=False``, an ``error`` message and a
``narration_hint`` field instructing the LLM to acknowledge no data is
available rather than fabricating progress. This is also the live behaviour
until the ``:8100`` adapter ships the student-model read endpoint (see
:data:`common.tutor_client.STUDENT_MODEL_PATH`).
"""

from __future__ import annotations

import logging
from typing import Any

from common.subject import DEFAULT_SUBJECT
from common.tutor_client import TutorClient, TutorUnavailableError

logger = logging.getLogger(__name__)

#: Default student name (per scope §6 A6 — Lilymay is the hackathon student).
DEFAULT_STUDENT_NAME = "lilymay"

# ``DEFAULT_SUBJECT`` is re-exported from :mod:`common.subject`, the single
# source of truth for the tutoring default subject (recon D6 / ASSUM-001).
# Both this tool and ``ask_tutor`` resolve their default from that one place,
# so ``resume_if_active``'s ``(student, subject)`` match can never miss on a
# divergent default.

#: Narration hint baked into the unreachable-degraded response so the LLM
#: knows to acknowledge missing data instead of fabricating progress.
_NARRATION_HINT_NO_DATA = (
    "No study data is available right now. Acknowledge this honestly — "
    "ask whether the tutor session has run yet — and do not invent progress, "
    "levels, streaks or achievements."
)


def _ensure_narration_friendly(progress: dict[str, Any], student_name: str) -> dict[str, Any]:
    """Augment a degraded read with narration hints.

    When the durable read is unavailable the tool returns
    ``{"data_available": False, "error": "..."}``; this layers on a
    ``narration_hint`` and a ``student_name`` so the LLM can produce a
    natural in-character apology rather than crashing.

    Args:
        progress: The learning-record dict (or a degraded stub).
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
    augmented.setdefault("error", "student model unavailable")
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
    logger.debug("reachy_mini_conversation_app not installed — using fallback Tool base")

    class _PollenTool:  # type: ignore[no-redef]
        """Minimal stand-in so the tool class is importable standalone."""

        name: str = ""
        description: str = ""
        parameters_schema: dict[str, Any] = {}


class QueryStudentModelTool(_PollenTool):  # type: ignore[misc]
    """Look up a student's current study progress from the durable store.

    Call this whenever someone asks how revision is going, what
    achievements are close to being unlocked, or what topic to study next.
    The progress dict is read live from the study-tutor adapter on ``:8100``
    via :class:`common.tutor_client.TutorClient`.
    """

    name = "query_student_model"
    description = (
        "Look up the student's current study progress: streak, level, "
        "recent XP, topic confidence, nearest unlockable achievements. "
        "Call this whenever someone asks how revision is going or what "
        "to study next."
    )
    parameters_schema: dict[str, Any] = {
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
                    "Identifier of the student. Server derives identity from "
                    "the token; this is a hint. Defaults to 'lilymay'."
                ),
                "default": DEFAULT_STUDENT_NAME,
            },
        },
        "required": [],
    }

    async def __call__(self, deps: Any = None, **kwargs: Any) -> dict[str, Any]:
        """Execute the student model query against the durable store.

        Constructs a fresh :class:`TutorClient` per call (connect-per-call,
        mirroring ``ask_jarvis``/``ask_tutor``) and reads the student's
        learning record over the ``:8100`` HTTP adapter.

        Args:
            deps: ToolDependencies (unused, required by Pollen interface).
            **kwargs: Optional 'subject' and 'student_name' keys; both
                default per the module constants.

        Returns:
            The learning-record dict. When the read is unavailable the dict
            is degraded with ``data_available=False`` and a
            ``narration_hint`` — Scholar must never crash the conversation
            (scope §5.2 #2).
        """
        subject: str = kwargs.get("subject", DEFAULT_SUBJECT)
        student_name: str = kwargs.get("student_name", DEFAULT_STUDENT_NAME)
        client = TutorClient()
        try:
            progress = await client.get_student_model(subject, student_name)
        except TutorUnavailableError as exc:
            logger.info(
                "QueryStudentModelTool: study-tutor unavailable for %s/%s: %s",
                student_name,
                subject,
                exc,
            )
            return _ensure_narration_friendly(
                {"data_available": False, "error": str(exc)},
                student_name,
            )
        except Exception as exc:  # noqa: BLE001 — must never bubble out of tool
            logger.exception(
                "QueryStudentModelTool unexpected failure for %s/%s",
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
                "QueryStudentModelTool got non-dict from TutorClient: %r",
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
