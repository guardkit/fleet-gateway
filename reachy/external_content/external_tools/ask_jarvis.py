"""Route questions through Jarvis — the fleet's intent router.

Subclasses ``core_tools.Tool`` from ``reachy_mini_conversation_app`` to
give the Scholar and Bridge profiles access to the full Jarvis agent fleet
(study-tutor, architect, forge, product-owner) via NATS.

The tool uses :class:`common.jarvis_client.JarvisClient` — the same
shared client that powers the OpenWebUI pipe function. A single
``send_command`` call builds the envelope, publishes to
``agents.command.jarvis`` via NATS request-reply, and returns the parsed
response text.

Design notes:
    - **Voice-optimised**: The tool returns plain text (not JSON) that
      Gemini Live / OpenAI Realtime narrates directly. No post-processing.
    - **Connect-per-call**: JarvisClient opens a fresh NATS connection per
      invocation, avoiding event loop conflicts with Pollen's audio loop.
    - **Graceful degradation**: On NATS timeout or unreachable, returns a
      narration-friendly error string — never crashes the conversation.
    - **Adapter identity**: Envelope source_id is ``reachy-scholar-gateway``
      or ``reachy-bridge-gateway`` so Jarvis can distinguish the source.

Environment variables:
    NATS_URL: NATS server URL (default: ``nats://promaxgb10-41b1:4222``).
    REACHY_MINI_CUSTOM_PROFILE: Used as adapter suffix (scholar or bridge).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from common.jarvis_client import JarvisClient

logger = logging.getLogger(__name__)

#: Default NATS URL — GB10 via Tailscale hostname.
_DEFAULT_NATS_URL = "nats://promaxgb10-41b1:4222"

#: Request timeout in seconds — generous for LLM inference chains.
_DEFAULT_TIMEOUT = 120

#: Narration hint when Jarvis is unreachable.
_NARRATION_HINT_OFFLINE = (
    "I can't reach the study tutor right now — the NATS connection to the "
    "GB10 isn't responding. Let's try again in a moment."
)


# ---------------------------------------------------------------------------
# Pollen core_tools.Tool subclass (with fallback for non-Pollen envs)
# ---------------------------------------------------------------------------

try:
    from reachy_mini_conversation_app.tools.core_tools import (  # type: ignore[import-not-found]
        Tool as _PollenTool,
    )
except ImportError:  # pragma: no cover
    logger.debug(
        "reachy_mini_conversation_app not installed — using fallback Tool base"
    )

    class _PollenTool:  # type: ignore[no-redef]
        """Minimal stand-in so the tool class is importable standalone."""

        name: str = ""
        description: str = ""
        parameters: dict[str, Any] = {}


class AskJarvisTool(_PollenTool):  # type: ignore[misc]
    """Send a question or command to Jarvis, the fleet's AI supervisor.

    Jarvis routes your message to the right specialist agent:
    - Study tutor: for GCSE revision, Socratic tutoring, topic explanation
    - Architect: for software architecture questions and ADR review
    - Forge: for queuing and checking software builds
    - Product owner: for feature planning and roadmap questions

    Use this tool for any question that needs a specialist agent's help.
    The response comes back as natural text ready to speak aloud.
    """

    name = "ask_jarvis"
    description = (
        "Send a question to Jarvis, the Ship's Computer. Jarvis routes it "
        "to the right specialist agent — study tutor for revision help, "
        "architect for technical decisions, forge for build status. Use "
        "this for any question that needs an expert answer. Returns text "
        "you can speak directly."
    )
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "The question or command to send to Jarvis. Write it "
                    "as natural language — Jarvis will figure out which "
                    "agent should handle it."
                ),
            },
        },
        "required": ["message"],
    }

    async def __call__(self, deps: Any = None, **kwargs: Any) -> dict[str, Any]:
        """Send message to Jarvis via NATS and return the response.

        Args:
            deps: ToolDependencies (unused, required by Pollen interface).
            **kwargs: Must contain 'message' key with the question text.

        Returns:
            Dict with 'response' key containing Jarvis's text, or 'error'.
        """
        message = kwargs.get("message", "")
        if not message:
            return {"error": "No message provided"}

        nats_url = os.environ.get("NATS_URL", _DEFAULT_NATS_URL)
        profile = os.environ.get("REACHY_MINI_CUSTOM_PROFILE", "scholar")
        adapter = f"reachy-{profile}"

        client = JarvisClient(
            nats_url=nats_url,
            timeout=_DEFAULT_TIMEOUT,
            adapter=adapter,
        )

        try:
            response = await client.send_command(message)
            logger.info(
                "AskJarvisTool: Jarvis responded (%d chars) for adapter=%s",
                len(response),
                adapter,
            )
            return {"response": response}
        except TimeoutError:
            logger.warning("AskJarvisTool: Jarvis timeout after %ds", _DEFAULT_TIMEOUT)
            return {"response": _NARRATION_HINT_OFFLINE}
        except ConnectionError as exc:
            logger.warning("AskJarvisTool: NATS connection error: %s", exc)
            return {"response": _NARRATION_HINT_OFFLINE}
        except Exception as exc:  # noqa: BLE001 — must never bubble out of tool
            logger.exception("AskJarvisTool: unexpected failure")
            return {"response": f"Something went wrong talking to Jarvis: {exc}. Let's try that again."}


__all__ = ["AskJarvisTool"]
