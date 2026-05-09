"""NATS Fleet Gateway — Open WebUI Pipe Function.

Sends all user messages to Jarvis, the fleet's intent router and supervisor.
Jarvis uses its reasoning model (Qwen3.6-35B-A3B, 3B active params via
llama-swap) to understand the user's intent, then dispatches to the right
specialist agent (architect, product-owner, study-tutor, forge) via NATS
using structured CommandPayload messages.

The Pipe Function is deliberately thin — it's a transport adapter between
Open WebUI's chat protocol and the NATS message bus. All routing intelligence
lives in Jarvis; all specialist intelligence lives in the agents.

Deployment:
    - Paste into Open WebUI Admin → Workspace → Functions, OR
    - Drop into Pipelines container /pipelines/ directory

Dependencies:
    - nats-py (``pip install nats-py``)
    - pydantic (already in Open WebUI)

Architecture decision: study-tutor/docs/talks/openwebui-nats-pipe-architecture.md
"""

from __future__ import annotations

import json
import logging
import uuid

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jarvis NATS configuration
# ---------------------------------------------------------------------------

_JARVIS_AGENT_ID = "jarvis"
_JARVIS_COMMAND = "chat"


class Pipe:
    """NATS Fleet Gateway — routes all user messages through Jarvis.

    Jarvis is the fleet's intent router. It receives natural language,
    decides which specialist agent can answer, constructs the right
    structured request, dispatches via NATS, and returns the response.

    The Open WebUI dropdown shows one model: "Jarvis". The audience sees
    a clean chat interface backed by the full agent fleet.

    Valves (configurable via Open WebUI admin):
        NATS_URL: NATS server URL (default: nats://localhost:4222)
        REQUEST_TIMEOUT: NATS request timeout in seconds (default: 120)
    """

    class Valves(BaseModel):
        NATS_URL: str = Field(
            default="nats://localhost:4222",
            description="NATS server URL (localhost on GB10)",
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="NATS request timeout in seconds",
        )

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        """Register Jarvis as the single selectable model in Open WebUI."""
        return [{"id": "jarvis", "name": "Jarvis"}]

    async def pipe(self, body: dict) -> str:
        """Send user message to Jarvis via NATS and return the response.

        Steps:
            1. Extract the user's latest message from the conversation
            2. Build a CommandPayload with the message and history
            3. Publish to agents.command.jarvis via NATS request
            4. Parse the ResultPayload and return the response text

        Args:
            body: Open WebUI request body containing model, messages, etc.

        Returns:
            Jarvis's response text, or an error message.
        """
        import nats as nats_py  # lazy import — must be installed

        # 1. Extract conversation
        messages = body.get("messages", [])
        if not messages:
            return "No message provided."

        user_message = messages[-1].get("content", "")

        # 2. Build CommandPayload (nats-core wire format)
        correlation_id = str(uuid.uuid4())

        command_payload = {
            "command": _JARVIS_COMMAND,
            "args": {
                "message": user_message,
                "conversation_history": [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                ],
                "adapter": "openwebui",
            },
            "correlation_id": correlation_id,
        }

        envelope = {
            "version": "1.0",
            "event_type": "command",
            "source_id": "openwebui-gateway",
            "correlation_id": correlation_id,
            "payload": command_payload,
        }

        # 3. Publish to Jarvis via NATS request/reply
        nats_topic = f"agents.command.{_JARVIS_AGENT_ID}"

        try:
            nc = await nats_py.connect(self.valves.NATS_URL)
            try:
                response = await nc.request(
                    nats_topic,
                    json.dumps(envelope).encode("utf-8"),
                    timeout=self.valves.REQUEST_TIMEOUT,
                )
            finally:
                await nc.close()
        except nats_py.errors.TimeoutError:
            return (
                f"Jarvis did not respond within {self.valves.REQUEST_TIMEOUT}s. "
                f"Is it running? Start with: jarvis serve-nats --nats {self.valves.NATS_URL}"
            )
        except nats_py.errors.NoRespondersError:
            return (
                f"No agent is listening on '{nats_topic}'. "
                f"Start Jarvis with: jarvis serve-nats --nats {self.valves.NATS_URL}"
            )
        except Exception as exc:
            logger.exception("NATS request failed for %s", nats_topic)
            return f"NATS error: {exc}"

        # 4. Parse response
        try:
            result_envelope = json.loads(response.data.decode("utf-8"))
            result_payload = result_envelope.get("payload", result_envelope)

            if not result_payload.get("success", True):
                error = result_payload.get("result", {}).get("error", "Unknown error")
                return f"Error: {error}"

            result = result_payload.get("result", {})

            # Return the response text from Jarvis
            for key in ("response", "text", "reply", "output"):
                if key in result and isinstance(result[key], str):
                    return result[key]

            # Fallback: return the full result as formatted JSON
            return json.dumps(result, indent=2, default=str)

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse Jarvis response: %s", exc)
            return response.data.decode("utf-8")
