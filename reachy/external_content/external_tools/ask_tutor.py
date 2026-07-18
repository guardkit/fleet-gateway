"""Ask the study-tutor directly — no Jarvis in the tutoring loop.

Subclasses ``core_tools.Tool`` from ``reachy_mini_conversation_app`` to give
the Scholar profile a tutoring turn that goes **straight to the study-tutor**
over its HTTP adapter (``:8100``), the same binding the Flutter app consumes.
Cloned from :mod:`ask_jarvis`'s plumbing (connect-per-call, generous timeout,
one neutral offline string, Pollen ABC), swapping NATS→Jarvis for HTTP→tutor.

Why direct HTTP and not NATS (design §7.4): it gives the robot *identical*
session semantics to the phone by construction — same server-side
``student_id`` derivation, ``resume_if_active``, durable Postgres-backed
sessions — which is what makes D8 phone↔robot mid-thread pickup real.

Behaviour:
    - **First call ensures a session** via ``POST /api/sessions/start`` with
      ``resume_if_active: true`` (picks up a session the phone may have
      started); subsequent calls ``POST …/turn`` and return the tutor's text.
    - **Subject** is a tool parameter (persona-supplied for multi-subject).
      When the persona omits it, it falls back to the shared default
      :data:`common.subject.DEFAULT_SUBJECT` — **never empty**. An empty
      subject would create a parallel ``""`` session and silently defeat D8
      pickup, because ``resume_if_active`` matches on ``(student, subject)``
      (recon D6).
    - **Every failure mode** — transport error, non-2xx, or a *rejected
      bearer* — returns the *same* neutral offline string. No network / auth
      / status detail can reach the Realtime session, so a credential failure
      cannot be spoken as tutoring content by construction (AC-R07-4). The
      persona renders it warmly (``instructions.txt``, ASSUM-007).

Environment variables (see :class:`common.tutor_client.TutorClient`):
    STUDY_TUTOR_HTTP_URL: Adapter base URL (default
        ``http://promaxgb10-41b1:8100``).
    STUDY_TUTOR_TOKEN: Bearer token resolved server-side to a ``student_id``.
"""

from __future__ import annotations

import logging
from typing import Any

from common.subject import DEFAULT_SUBJECT
from common.tutor_client import TutorClient, TutorUnavailableError

logger = logging.getLogger(__name__)

#: The single neutral offline string returned for *every* failure mode. Kept
#: deliberately generic so no network / auth / status detail leaks into what
#: the robot speaks. The persona handles it warmly (R08, ASSUM-007).
TUTOR_OFFLINE_MESSAGE = "The tutor isn't reachable right now."


# ---------------------------------------------------------------------------
# Pollen core_tools.Tool subclass (with fallback for non-Pollen envs)
# ---------------------------------------------------------------------------

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


class AskTutorTool(_PollenTool):  # type: ignore[misc]
    """Ask the study-tutor a tutoring question and speak its answer.

    Use this for *tutoring* turns — GCSE English Language / Literature
    questions, working through an essay or an extract, starting a revision
    topic. Simple chat stays on the conversation model; ``ask_jarvis``
    remains for non-tutoring fleet queries.

    The tool holds the session id across calls for the life of the
    conversation: the first call resumes-or-creates a session, later calls
    add turns to it.
    """

    name = "ask_tutor"
    description = (
        "Ask the study tutor a GCSE English question or work through a "
        "revision topic. Use this for teaching turns — explaining a text, "
        "planning an essay, checking an answer. Returns the tutor's reply "
        "as text you can speak in your own voice. A turn takes a few "
        "seconds, so say a short 'let me think' line before calling it."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": ("The student's tutoring question or request, in natural language."),
            },
            "question": {
                "type": "string",
                "description": (
                    "Alias for message — models routinely reach for this name "
                    "(observed live at R-G3); provide message OR question."
                ),
            },
            "query": {
                "type": "string",
                "description": (
                    "Second alias for message (also observed live at R-G3)."
                ),
            },
            "subject": {
                "type": "string",
                "description": (
                    "Subject to tutor. Usually leave unset — it defaults to "
                    f"'{DEFAULT_SUBJECT}'. Set it only when tutoring a "
                    "different subject."
                ),
                "default": DEFAULT_SUBJECT,
            },
        },
        # message-or-question is enforced at call time; JSON-schema "required"
        # can't express the alias without anyOf, which realtime validators
        # handle inconsistently.
        "required": [],
    }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise with no session yet (created lazily on first call)."""
        super().__init__(*args, **kwargs)
        self._session_id: str | None = None

    async def __call__(self, deps: Any = None, **kwargs: Any) -> dict[str, Any]:
        """Run one tutoring turn against the study-tutor.

        Args:
            deps: ToolDependencies (unused, required by Pollen interface).
            **kwargs: ``message`` (the question — ``question`` accepted as an
                alias) and an optional ``subject`` (falls back to the shared
                default, never empty).

        Returns:
            ``{"response": <tutor text>}`` on success, or
            ``{"response": TUTOR_OFFLINE_MESSAGE}`` for *every* failure mode.
            Never raises.
        """
        message = (
            kwargs.get("message") or kwargs.get("question") or kwargs.get("query") or ""
        )
        if not isinstance(message, str) or not message.strip():
            return {"error": "No message provided"}

        # Resolve the subject, guaranteeing it is never empty (recon D6).
        raw_subject = kwargs.get("subject")
        subject = (
            raw_subject.strip()
            if isinstance(raw_subject, str) and raw_subject.strip()
            else DEFAULT_SUBJECT
        )

        client = TutorClient()
        try:
            if self._session_id is None:
                start = await client.start_session(subject, resume_if_active=True)
                session_id = start.get("session_id")
                if not isinstance(session_id, str) or not session_id:
                    msg = "study-tutor start returned no session_id"
                    raise TutorUnavailableError(msg)
                self._session_id = session_id
                logger.info(
                    "AskTutorTool: session %s (resumed=%s, subject=%s)",
                    session_id,
                    start.get("resumed"),
                    subject,
                )

            response = await client.turn(self._session_id, message)
            logger.info("AskTutorTool: tutor responded (%d chars)", len(response))
            return {"response": response}
        except TutorUnavailableError as exc:
            # Single neutral string for every failure — including a rejected
            # bearer (AC-R07-4). Detail goes to the log, never to speech.
            logger.warning("AskTutorTool: tutor unavailable: %s", exc)
            return {"response": TUTOR_OFFLINE_MESSAGE}
        except Exception:  # noqa: BLE001 — must never bubble out of the tool
            logger.exception("AskTutorTool: unexpected failure")
            return {"response": TUTOR_OFFLINE_MESSAGE}


__all__ = ["TUTOR_OFFLINE_MESSAGE", "AskTutorTool"]
