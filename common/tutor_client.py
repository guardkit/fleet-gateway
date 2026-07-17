"""Connect-per-call HTTP client for the study-tutor adapter (``:8100``).

This is the runtime seam that lets a Reachy tool talk to the study-tutor
over the **same HTTP binding the Flutter app consumes** — bearer auth,
``student_id`` derived server-side from the token, durable Postgres-backed
sessions. Giving the robot identical session semantics to the phone is what
makes D8 cross-device pickup real (a phone-started session resumed on the
robot).

Design choices mirror :class:`common.jarvis_client.JarvisClient`:

* **Connect-per-call** — every method opens a fresh
  :class:`httpx.AsyncClient` and closes it before returning, so the client
  is safe to reuse across the different event loops a conversation app runs
  its turns on (Pollen's audio loop, etc.). No shared connection, no
  caller-visible mutable state.
* **Stateless** — the client carries only configuration (base URL, token,
  timeout). Session identity is threaded by the caller, not held here.
* **One failure surface** — every transport error, non-2xx status
  (including a *rejected bearer*), and malformed body collapses to
  :class:`TutorUnavailableError`. Callers map that single exception to one
  neutral offline string, so no network / auth / status detail can leak
  into what the robot speaks (design §7.4; FEAT-VOICE-004 AC-R07-4).

Environment variables:
    STUDY_TUTOR_HTTP_URL: Base URL of the study-tutor adapter
        (default ``http://promaxgb10-41b1:8100``).
    STUDY_TUTOR_TOKEN: Bearer token; the adapter resolves it to a
        ``student_id`` via its ``STUDY_TUTOR_HTTP_TOKENS`` table. Empty by
        default so a misconfiguration surfaces as a graceful "unavailable"
        rather than a silent wrong-student write.

References:
    - study-tutor ``docs/design/contracts/API-session-http-binding.md`` —
      ``/api/sessions/start``, ``/api/sessions/{id}/turn``, bearer auth.
    - Voice design §7.4 (``ask_tutor`` direct to the tutor).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_TUTOR_URL",
    "STUDENT_MODEL_PATH",
    "TutorClient",
    "TutorUnavailableError",
]

#: Default study-tutor adapter base URL — GB10 via Tailscale hostname.
DEFAULT_TUTOR_URL = "http://promaxgb10-41b1:8100"

#: Request timeout in seconds — generous; a tutoring turn is ~5 s+ (the
#: Player wall, design §7.5).
_DEFAULT_TIMEOUT = 120.0

#: Student-model read path (recon D2 / FEAT-VOICE-004 R05).
#:
#: .. note::
#:    **Live.** The ``:8100`` adapter serves ``GET /api/student-model`` (a
#:    bearer-authenticated read of the durable Postgres-backed learner
#:    record; study-tutor ``src/study_tutor/http/app.py`` ``student_model``).
#:    :meth:`TutorClient.get_student_model` reads it directly and still
#:    degrades gracefully (``TutorUnavailableError`` → "no data") on any
#:    transport error, non-2xx (incl. an unseeded/rejected bearer → 401), or
#:    malformed body. Kept as a single constant so the path stays a one-line
#:    source of truth.
STUDENT_MODEL_PATH = "/api/student-model"


class TutorUnavailableError(Exception):
    """The study-tutor could not be reached, or refused the request.

    Raised for **every** failure mode — connection error, timeout, any
    non-2xx status (including a rejected bearer token), and a malformed or
    missing response body. Callers collapse this to one neutral offline
    string so nothing technical can be spoken by the robot.
    """


class TutorClient:
    """Connect-per-call HTTP client for the study-tutor adapter.

    Each method opens a fresh :class:`httpx.AsyncClient`, issues one
    request against :attr:`base_url` with the bearer :attr:`token`, and
    closes the connection before returning.

    Attributes:
        base_url: Study-tutor adapter base URL (no trailing slash).
        token: Bearer token presented on every request.
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        token: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the client from explicit args or the environment.

        Args:
            base_url: Adapter base URL. Falls back to ``STUDY_TUTOR_HTTP_URL``
                then :data:`DEFAULT_TUTOR_URL`. A trailing slash is stripped.
            token: Bearer token (keyword-only). Falls back to
                ``STUDY_TUTOR_TOKEN`` then the empty string (a misconfigured
                deployment then degrades gracefully rather than writing as
                the wrong student).
            timeout: Per-request timeout in seconds (keyword-only).
        """
        resolved_url = base_url or os.environ.get("STUDY_TUTOR_HTTP_URL", DEFAULT_TUTOR_URL)
        self.base_url = resolved_url.rstrip("/")
        self.token = token if token is not None else os.environ.get("STUDY_TUTOR_TOKEN", "")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        """Build the request headers, including the bearer credential."""
        return {"Authorization": f"Bearer {self.token}"}

    async def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST ``body`` as JSON to ``path`` and return the decoded object.

        Args:
            path: Request path (e.g. ``/api/sessions/start``).
            body: JSON-serialisable request body.

        Returns:
            The decoded JSON object.

        Raises:
            TutorUnavailableError: On any transport error, non-2xx status,
                or a body that is not a JSON object.
        """
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._headers(),
            ) as client:
                response = await client.post(path, json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            # Non-2xx — including 401 rejected bearer. Log the status for
            # the operator; never let it reach the caller's speech.
            logger.warning("TutorClient %s → HTTP %s", path, exc.response.status_code)
            msg = f"study-tutor returned HTTP {exc.response.status_code}"
            raise TutorUnavailableError(msg) from exc
        except httpx.HTTPError as exc:
            logger.warning("TutorClient %s transport error: %s", path, exc)
            msg = f"study-tutor unreachable: {exc}"
            raise TutorUnavailableError(msg) from exc
        except ValueError as exc:  # json() on a non-JSON body
            logger.warning("TutorClient %s malformed body: %s", path, exc)
            msg = "study-tutor returned a malformed response"
            raise TutorUnavailableError(msg) from exc

        if not isinstance(data, dict):
            logger.warning("TutorClient %s non-object body: %r", path, data)
            msg = "study-tutor returned an unexpected response shape"
            raise TutorUnavailableError(msg)
        return data

    async def start_session(self, subject: str, *, resume_if_active: bool = True) -> dict[str, Any]:
        """Create or resume a tutoring session (``POST /api/sessions/start``).

        With ``resume_if_active=True`` the adapter returns the caller's
        currently-active ``(student, subject)`` session if one exists —
        this is the D8 pickup seam. The ``subject`` **must** be the shared
        default (or an explicit persona subject); an empty subject would
        match a parallel ``""`` session and never pick up the phone's.

        Args:
            subject: Non-empty subject string (matched on by the store).
            resume_if_active: Resume an active session when one exists
                (keyword-only, default ``True``).

        Returns:
            The decoded start payload — ``{session_id, student_id,
            resumed, turns?}`` per the binding contract §5.1.

        Raises:
            TutorUnavailableError: On any failure (see :meth:`_post_json`).
        """
        return await self._post_json(
            "/api/sessions/start",
            {"subject": subject, "resume_if_active": resume_if_active},
        )

    async def turn(self, session_id: str, user_message: str) -> str:
        """Process one tutoring turn (``POST /api/sessions/{id}/turn``).

        Args:
            session_id: The session returned by :meth:`start_session`.
            user_message: The student's message (free text).

        Returns:
            The tutor's response text (contract §5.4 ``tutor_response``).

        Raises:
            TutorUnavailableError: On any failure, or if the response omits
                the ``tutor_response`` field.
        """
        data = await self._post_json(
            f"/api/sessions/{session_id}/turn",
            {"user_message": user_message},
        )
        response_text = data.get("tutor_response")
        if not isinstance(response_text, str):
            logger.warning("TutorClient turn: no tutor_response in %r", data)
            msg = "study-tutor turn response missing tutor_response"
            raise TutorUnavailableError(msg)
        return response_text

    async def get_student_model(
        self, subject: str, student_name: str | None = None
    ) -> dict[str, Any]:
        """Read the student's durable learning record via ``:8100`` (R05).

        Reads from the durable Postgres-backed store through the adapter —
        replacing the frozen Graphiti read (recon D2). The ``student_id`` is
        derived server-side from the bearer token, so ``student_name`` is
        forwarded only as a query hint for adapters that accept one.

        Args:
            subject: Subject to scope the record around.
            student_name: Optional student hint (server derives identity
                from the token regardless).

        Returns:
            The decoded learning-record object.

        Raises:
            TutorUnavailableError: On any failure — transport error, any
                non-2xx status (incl. an unseeded/rejected bearer → 401), or
                a malformed/non-object body (see :data:`STUDENT_MODEL_PATH`).
        """
        params: dict[str, str] = {"subject": subject}
        if student_name is not None:
            params["student_name"] = student_name
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._headers(),
            ) as client:
                response = await client.get(STUDENT_MODEL_PATH, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("TutorClient student-model → HTTP %s", exc.response.status_code)
            msg = f"study-tutor returned HTTP {exc.response.status_code}"
            raise TutorUnavailableError(msg) from exc
        except httpx.HTTPError as exc:
            logger.warning("TutorClient student-model transport error: %s", exc)
            msg = f"study-tutor unreachable: {exc}"
            raise TutorUnavailableError(msg) from exc
        except ValueError as exc:
            logger.warning("TutorClient student-model malformed body: %s", exc)
            msg = "study-tutor returned a malformed response"
            raise TutorUnavailableError(msg) from exc

        if not isinstance(data, dict):
            logger.warning("TutorClient student-model non-object body: %r", data)
            msg = "study-tutor returned an unexpected response shape"
            raise TutorUnavailableError(msg)
        return data
