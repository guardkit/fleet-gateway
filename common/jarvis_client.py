"""Connect-per-call NATS client for Jarvis.

This module owns the runtime side of the fleet gateway: a small async
client that publishes a :func:`common.envelope.build_command_envelope`
envelope to ``agents.command.jarvis`` over NATS, awaits the reply, and
returns the parsed response text via
:func:`common.envelope.parse_result_payload`.

Design choices (scope §6 A5):
    - **Connect-per-call**: every :meth:`JarvisClient.send_command`
      opens a fresh NATS connection and closes it before returning. This
      avoids loop-ownership issues when the client is invoked from
      conversation loops that run on different event loops across turns
      (e.g. Pollen, Open WebUI).
    - **Stateless**: the client carries only configuration. There is no
      shared connection, no background task, and no caller-visible
      mutable state.
    - **No status query**: ``query_status`` is intentionally absent — see
      scope §7 Q3. Bridge callers that want fleet status simply send a
      regular chat command (e.g. ``send_command("what's the fleet
      status?")``) and let Jarvis route it.

References:
    - Scope §4.2 — ``JarvisClient`` API.
    - ``openwebui/nats_fleet_pipe.py`` — original inline implementation
      that this module supersedes (TASK-FG-004 will refactor the pipe to
      delegate here).
"""

from __future__ import annotations

import json
from typing import Any

import nats
from nats.errors import (
    NoRespondersError,
    NoServersError,
)
from nats.errors import (
    TimeoutError as NatsTimeoutError,
)

from common.envelope import build_command_envelope, parse_result_payload

__all__ = ["JarvisClient"]

#: NATS topic Jarvis subscribes to for command envelopes.
JARVIS_TOPIC: str = "agents.command.jarvis"


class JarvisClient:
    """NATS request/reply client for the Jarvis intent router.

    Each call to :meth:`send_command` opens a fresh NATS connection,
    publishes the command envelope to ``agents.command.jarvis``, awaits
    the reply, parses it, and closes the connection. The connect-per-call
    pattern is deliberate (scope §6 A5) — it makes the client safe to
    reuse across event loops without long-lived state.

    Attributes:
        nats_url: NATS server URL, e.g. ``"nats://localhost:4222"``.
        timeout: Maximum seconds to wait for Jarvis to reply on a single
            request. Translated to ``TimeoutError`` on expiry.
        adapter: Adapter identifier used to compute the envelope's
            ``source_id`` (see :func:`common.envelope.build_command_envelope`).
    """

    def __init__(
        self,
        nats_url: str = "nats://localhost:4222",
        *,
        timeout: int = 120,
        adapter: str = "unknown",
    ) -> None:
        """Initialise the client with connection and identity config.

        Args:
            nats_url: NATS server URL (positional). Defaults to local dev.
            timeout: Per-request timeout in seconds (keyword-only).
                Defaults to 120s.
            adapter: Adapter name embedded in the envelope ``source_id``
                via the ``{adapter}-gateway`` convention (keyword-only).
                Defaults to ``"unknown"`` so misconfiguration is visible.
        """
        self.nats_url = nats_url
        self.timeout = timeout
        self.adapter = adapter

    async def send_command(
        self,
        message: str,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Send a chat command to Jarvis and return the response text.

        Steps:
            1. Build a command envelope via
               :func:`common.envelope.build_command_envelope`. The same
               ``correlation_id`` is used for envelope and inner payload.
            2. Open a NATS connection to :attr:`nats_url`.
            3. ``request`` the JSON-encoded envelope on
               :data:`JARVIS_TOPIC` with a :attr:`timeout`-second deadline.
            4. Parse the reply via
               :func:`common.envelope.parse_result_payload`.
            5. Always close the NATS connection (try/finally), even on
               timeout, no-responders, or parser errors.

        Args:
            message: Latest user message (free text).
            conversation_history: Optional list of ``{role, content}``
                dicts. Forwarded verbatim into the envelope. ``None``
                yields a single-turn history derived from ``message``.

        Returns:
            The Jarvis response text (or pretty-printed JSON if no known
            text key was present — see
            :func:`common.envelope.parse_result_payload`).

        Raises:
            TimeoutError: When the configured :attr:`timeout` elapses
                without a reply. Message names the topic and the timeout.
            ConnectionError: Distinct cases:
                * ``no responders`` — NATS is up but no agent is
                  listening on :data:`JARVIS_TOPIC`. Message suggests
                  ``uv run jarvis serve-nats`` to start Jarvis.
                * ``server unreachable`` — the NATS server itself cannot
                  be contacted (wrong URL, server down, etc.). Message
                  reports the URL so misconfiguration is obvious.
            ValueError: When the reply is structurally invalid or
                signals failure (re-raised from ``parse_result_payload``).
        """
        envelope = build_command_envelope(
            message=message,
            adapter=self.adapter,
            conversation_history=conversation_history,
        )
        request_data = json.dumps(envelope).encode("utf-8")

        # Open the connection. Server-unreachable failures must be
        # distinguishable from no-responders, so we catch the connect
        # exceptions separately and translate them here.
        try:
            nc = await nats.connect(self.nats_url)
        except NoServersError as exc:
            msg = (
                f"Could not reach NATS server at {self.nats_url}: {exc}. "
                "Check that the NATS server is running and NATS_URL is correct."
            )
            raise ConnectionError(msg) from exc
        except OSError as exc:
            # ConnectionRefusedError, socket.gaierror, etc. all derive
            # from OSError — they all mean the URL is unreachable.
            msg = (
                f"Could not reach NATS server at {self.nats_url}: {exc}. "
                "Check that the NATS server is running and NATS_URL is correct."
            )
            raise ConnectionError(msg) from exc

        try:
            try:
                response = await nc.request(
                    JARVIS_TOPIC,
                    request_data,
                    timeout=self.timeout,
                )
            except NatsTimeoutError as exc:
                msg = (
                    f"No reply on {JARVIS_TOPIC!r} within {self.timeout}s. "
                    "Is Jarvis running? Start it with "
                    f"'uv run jarvis serve-nats --nats {self.nats_url}'."
                )
                raise TimeoutError(msg) from exc
            except NoRespondersError as exc:
                msg = (
                    f"No responders on {JARVIS_TOPIC!r}. "
                    "Start Jarvis with "
                    f"'uv run jarvis serve-nats --nats {self.nats_url}'."
                )
                raise ConnectionError(msg) from exc
        finally:
            # Always close — even on timeout / no-responders / parse error.
            await nc.close()

        return parse_result_payload(response.data)
