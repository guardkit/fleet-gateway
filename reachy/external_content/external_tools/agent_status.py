"""Bridge's ``agent_status`` tool — queries Jarvis for fleet status over NATS.

Subclasses ``core_tools.Tool`` from ``reachy_mini_conversation_app`` so the
Bridge persona (Ship's Computer) can answer questions like *"What's the
fleet status?"*. Per scope §7 Q3, no dedicated status topic exists — the
tool sends a regular chat command on ``agents.command.jarvis`` via
:class:`common.jarvis_client.JarvisClient` and lets Jarvis narrate.

The tool is deliberately defensive:

    * On ``ConnectionError`` (NATS unreachable, no responders) and
      ``TimeoutError`` (Jarvis didn't reply in time) the tool returns a
      graceful string starting with ``"Fleet offline:"`` rather than
      raising. A crash inside a Gemini Live tool call would terminate the
      Bridge conversation, which is unacceptable behaviour for a
      ship's-computer persona.
    * The module is importable without the Pollen SDK (a fallback plain
      class is registered when ``reachy_mini_conversation_app`` is not
      installed), so the tool can be unit-tested standalone with
      ``fleet-gateway`` editable-installed.

Environment variables:
    NATS_URL: NATS server URL. Defaults to ``"nats://localhost:4222"``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from common.jarvis_client import JarvisClient

logger = logging.getLogger(__name__)

__all__ = ["AgentStatusTool"]

#: Default NATS URL used when ``NATS_URL`` is not set in the environment.
_DEFAULT_NATS_URL = "nats://localhost:4222"


def _build_status_message(agent: str) -> str:
    """Phrase a fleet-status question for Jarvis.

    Args:
        agent: Either ``"all"`` (whole fleet) or a specific agent name.

    Returns:
        The English question forwarded as the ``message`` to
        :meth:`common.jarvis_client.JarvisClient.send_command`.
    """
    if agent == "all":
        return "what's the fleet status?"
    return f"what's the status of {agent}?"


async def _query_fleet_status(agent: str = "all") -> str:
    """Ask Jarvis for the current fleet (or specific agent) status.

    Wraps :meth:`common.jarvis_client.JarvisClient.send_command` with the
    Bridge-specific message phrasing and the graceful-failure contract
    documented in TASK-FG-006: ``ConnectionError`` and ``TimeoutError``
    are translated to a ``"Fleet offline: ..."`` string instead of
    propagating.

    Args:
        agent: Either ``"all"`` (whole fleet) or a specific agent name.
            Defaults to ``"all"`` for forward compatibility — Phase 1
            always queries the whole fleet, but the parameter is kept so
            future Bridge skills can scope down without API churn.

    Returns:
        Jarvis's narrated text on success, or a ``"Fleet offline: ..."``
        string when NATS is unreachable or Jarvis times out.
    """
    nats_url = os.environ.get("NATS_URL", _DEFAULT_NATS_URL)
    message = _build_status_message(agent)

    client = JarvisClient(nats_url=nats_url, adapter="reachy-bridge")
    try:
        return await client.send_command(message)
    except ConnectionError as exc:
        logger.warning("agent_status: NATS unreachable: %s", exc)
        return f"Fleet offline: cannot reach Jarvis ({exc})."
    except TimeoutError as exc:
        logger.warning("agent_status: Jarvis did not reply in time: %s", exc)
        return f"Fleet offline: Jarvis did not reply in time ({exc})."


# ---------------------------------------------------------------------------
# Tool description (shared between Pollen-installed and standalone variants)
# ---------------------------------------------------------------------------

_TOOL_DESCRIPTION = (
    "Ask the fleet what's going on. Use whenever someone asks about the "
    "status of agents, the build, the fleet, or 'what's happening?'. "
    "Defaults to a whole-fleet status report; pass the 'agent' parameter "
    "to scope the question to a single agent (e.g. 'scholar')."
)

_TOOL_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "agent": {
            "type": "string",
            "description": (
                "Agent name to query, or 'all' for the whole fleet. "
                "Defaults to 'all'."
            ),
            "default": "all",
        }
    },
    "required": [],
}


# ---------------------------------------------------------------------------
# Pollen ``core_tools.Tool`` subclass (with standalone fallback)
# ---------------------------------------------------------------------------
#
# Mirrors the pattern in ``query_student_model.py``: the module remains
# importable when the Pollen SDK is absent (for tests and editable
# installs), so we register a plain class with the same surface as the
# Tool subclass when the import fails.

try:
    from reachy_mini_conversation_app.tools.core_tools import (  # type: ignore[import-not-found]
        Tool,
    )

    class AgentStatusTool(Tool):  # type: ignore[misc]
        """Ask Jarvis for the current fleet (or specific agent) status.

        Call whenever someone asks about agents, the build, the fleet, or
        what's happening. Returns Jarvis's narrated text, or a graceful
        ``"Fleet offline: ..."`` string when NATS is unreachable.
        """

        name = "agent_status"
        description = _TOOL_DESCRIPTION
        parameters = _TOOL_PARAMETERS

        async def run(self, agent: str = "all") -> str:
            """Execute the fleet-status query.

            Args:
                agent: Either ``"all"`` (whole fleet) or a specific agent
                    name. Defaults to ``"all"``.

            Returns:
                Jarvis's narrated text, or ``"Fleet offline: ..."`` on
                NATS / timeout failure (never raises).
            """
            return await _query_fleet_status(agent=agent)

except ImportError:
    logger.debug(
        "reachy_mini_conversation_app not installed — "
        "AgentStatusTool falls back to a plain class for standalone use"
    )

    class AgentStatusTool:  # type: ignore[no-redef]
        """Standalone fallback for :class:`AgentStatusTool`.

        Used when the Pollen SDK (``reachy_mini_conversation_app``) is
        not installed, e.g. during library unit tests or editable
        installs of ``fleet-gateway``. The surface mirrors the Pollen
        ``Tool`` subclass above so call-sites are interchangeable.
        """

        name: str = "agent_status"
        description: str = _TOOL_DESCRIPTION
        parameters: dict[str, Any] = _TOOL_PARAMETERS

        async def run(self, agent: str = "all") -> str:
            """Execute the fleet-status query.

            See :func:`_query_fleet_status` for behaviour.
            """
            return await _query_fleet_status(agent=agent)
