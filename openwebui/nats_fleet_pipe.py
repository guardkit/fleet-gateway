"""NATS Fleet Gateway — Open WebUI Pipe Function (test-time / source-of-truth).

This is the **source-of-truth** Pipe Function module. It imports envelope
construction and the NATS request/reply loop from
:mod:`common.jarvis_client` so unit tests exercise the shared library code
(per scope §7 Q4 / TASK-FG-004 acceptance criteria).

Open WebUI's Workspace Functions interpreter cannot ``pip install``
``fleet-gateway-common``, so the deployable file
``openwebui/nats_fleet_pipe.deploy.py`` is a flattened sibling that inlines
``common.envelope`` and ``common.jarvis_client``. Regenerate it after any
change to ``common/`` with::

    python openwebui/build_pipe.py

Sends all user messages to Jarvis, the fleet's intent router and supervisor.
Jarvis decides which specialist agent (architect, product-owner,
study-tutor, forge) should answer, dispatches via NATS using the canonical
:func:`common.envelope.build_command_envelope` envelope, and returns the
response.

Deployment:
    - Paste ``openwebui/nats_fleet_pipe.deploy.py`` into Open WebUI Admin →
      Workspace → Functions, OR
    - Drop the same deploy file into a Pipelines container ``/pipelines/``
      directory.

Runtime dependency (in the Open WebUI Python environment):
    - ``nats-py`` (``pip install nats-py``)
    - ``pydantic`` (already in Open WebUI)

See ``openwebui/README.md`` for the full deployment workflow and the
self-contained-file rationale.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from common.jarvis_client import JarvisClient

logger = logging.getLogger(__name__)

#: Adapter identifier embedded in the envelope ``source_id`` as
#: ``openwebui-gateway`` (see :func:`common.envelope.build_command_envelope`).
_ADAPTER: str = "openwebui"

#: NATS topic Jarvis subscribes on. Mirrored here purely for the
#: no-responders error message — the actual publish lives in JarvisClient.
_JARVIS_TOPIC: str = "agents.command.jarvis"


class Pipe:
    """NATS Fleet Gateway — routes all user messages through Jarvis.

    Jarvis is the fleet's intent router. It receives natural language,
    decides which specialist agent can answer, dispatches via NATS, and
    returns the response. The Open WebUI dropdown shows one model — Jarvis
    — and the audience sees a clean chat interface backed by the full
    agent fleet.

    The class is deliberately thin: ``Pipe.pipe`` extracts the user's
    latest message, hands it (plus conversation history) to a
    :class:`common.jarvis_client.JarvisClient`, and surfaces the response
    text. All envelope construction, JSON serialisation, and error
    translation lives in ``common/``.

    Attributes:
        valves: Operator-tunable configuration (see :class:`Valves`).
    """

    class Valves(BaseModel):
        """Operator configuration shown in Open WebUI Admin."""

        NATS_URL: str = Field(
            default="nats://localhost:4222",
            description="NATS server URL (localhost on GB10).",
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="NATS request timeout in seconds.",
        )

    def __init__(self) -> None:
        """Initialise the pipe with default Valve values."""
        self.valves = self.Valves()

    def pipes(self) -> list[dict[str, str]]:
        """Register Jarvis as the single selectable model in Open WebUI.

        Returns:
            A one-element list whose dict carries the model id and label
            that Open WebUI renders in the model dropdown.
        """
        return [{"id": "jarvis", "name": "Jarvis"}]

    async def pipe(self, body: dict[str, Any]) -> str:
        """Send the user's latest message to Jarvis and return the reply.

        Steps:
            1. Extract the user's latest message and conversation history
               from the Open WebUI request body.
            2. Construct a :class:`common.jarvis_client.JarvisClient`
               configured from :class:`Valves`.
            3. Await ``send_command`` and return the response text.
            4. Translate the client's typed exceptions into the
               human-readable strings Open WebUI renders in the chat
               window (preserving pre-refactor wording so existing
               operators see no behavioural change).

        Args:
            body: Open WebUI request body. Expected to contain a
                ``messages`` list of ``{role, content}`` dicts.

        Returns:
            Jarvis's response text, or a safe error string if the request
            failed. Never raises — Open WebUI surfaces the returned
            string directly to the user.
        """
        messages = body.get("messages", [])
        if not messages:
            return "No message provided."

        user_message = messages[-1].get("content", "")
        history = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ]

        client = JarvisClient(
            nats_url=self.valves.NATS_URL,
            timeout=self.valves.REQUEST_TIMEOUT,
            adapter=_ADAPTER,
        )

        try:
            return await client.send_command(
                user_message,
                conversation_history=history,
            )
        except TimeoutError:
            return (
                f"Jarvis did not respond within {self.valves.REQUEST_TIMEOUT}s. "
                f"Is it running? Start with: "
                f"jarvis serve-nats --nats {self.valves.NATS_URL}"
            )
        except ConnectionError as exc:
            # JarvisClient raises ConnectionError for both "no responders"
            # and "server unreachable". Distinguish on the message text so
            # the no-responders wording stays identical to the
            # pre-refactor pipe (per AC).
            if "No responders" in str(exc):
                return (
                    f"No agent is listening on '{_JARVIS_TOPIC}'. "
                    f"Start Jarvis with: "
                    f"jarvis serve-nats --nats {self.valves.NATS_URL}"
                )
            return f"NATS error: {exc}"
        except Exception as exc:  # noqa: BLE001 — surface any failure as text
            logger.exception("Jarvis request failed")
            return f"NATS error: {exc}"
