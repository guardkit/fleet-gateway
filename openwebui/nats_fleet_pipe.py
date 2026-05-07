"""NATS Fleet Gateway — Open WebUI Pipe Function.

Exposes fleet agents as selectable models in Open WebUI's model dropdown.
User messages are published to the selected agent's NATS command topic;
responses are returned to the chat.

This is a Pipe Function (manifold pattern): the ``pipes()`` method returns
a list of agent models, and ``pipe()`` dispatches to the selected agent
via NATS request/reply.

Wire format: nats-core Pydantic models (MessageEnvelope, CommandPayload,
ResultPayload). All payloads are JSON over NATS.

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
from typing import AsyncGenerator

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent registry — add new fleet agents here
# ---------------------------------------------------------------------------

_FLEET_AGENTS = [
    {
        "id": "architect-align",
        "name": "Architect Agent (Align)",
        "nats_agent_id": "architect-agent",
        "default_command": "align",
    },
    {
        "id": "architect-greenfield",
        "name": "Architect Agent (Greenfield)",
        "nats_agent_id": "architect-agent",
        "default_command": "greenfield",
    },
    {
        "id": "product-owner",
        "name": "Product Owner",
        "nats_agent_id": "product-owner-agent",
        "default_command": "idea",
    },
    {
        "id": "gcse-tutor",
        "name": "GCSE Study Tutor",
        "nats_agent_id": "gcse-tutor",
        "default_command": "tutor_turn",
    },
    # {
    #     "id": "forge-build",
    #     "name": "Forge Build Pipeline",
    #     "nats_agent_id": "forge",
    #     "default_command": "build",
    # },
]


class Pipe:
    """NATS Fleet Gateway — exposes fleet agents as Open WebUI models.

    Each agent in ``_FLEET_AGENTS`` appears as a selectable model in the
    Open WebUI dropdown. When the user sends a message, the Pipe Function
    publishes a ``CommandPayload`` to the agent's NATS command topic and
    awaits the ``ResultPayload`` response.

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
        """Register each fleet agent as a selectable model in Open WebUI."""
        return [
            {"id": agent["id"], "name": agent["name"]}
            for agent in _FLEET_AGENTS
        ]

    async def pipe(self, body: dict) -> str:
        """Dispatch user message to the selected agent via NATS.

        Steps:
            1. Identify which agent was selected from the model id
            2. Extract the user's latest message from the conversation
            3. Build a CommandPayload with the message as args
            4. Publish to agents.command.{agent_id} via NATS request
            5. Parse the ResultPayload and return the response text

        Args:
            body: Open WebUI request body containing model, messages, etc.

        Returns:
            The agent's response text, or an error message.
        """
        import nats as nats_py  # lazy import — must be installed

        # 1. Resolve agent from model id
        model_id = body.get("model", "")
        # Open WebUI prefixes the pipe name: "nats_fleet_pipe.architect-align"
        # Strip everything up to and including the last dot
        agent_key = model_id.split(".")[-1] if "." in model_id else model_id

        agent = next(
            (a for a in _FLEET_AGENTS if a["id"] == agent_key),
            None,
        )
        if agent is None:
            return f"Unknown agent: {agent_key}"

        # 2. Extract conversation
        messages = body.get("messages", [])
        if not messages:
            return "No message provided."

        user_message = messages[-1].get("content", "")

        # 3. Build CommandPayload (nats-core wire format)
        #
        # TODO: Import from nats_core when the dependency is available
        # in the Pipelines container. For now, build the JSON manually
        # to match the MessageEnvelope + CommandPayload shape.
        correlation_id = str(uuid.uuid4())

        command_payload = {
            "command": agent["default_command"],
            "args": {
                "user_message": user_message,
                "conversation_history": [
                    {"role": m.get("role", "user"), "content": m.get("content", "")}
                    for m in messages
                ],
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

        # 4. Publish to NATS and await response
        nats_topic = f"agents.command.{agent['nats_agent_id']}"

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
                f"Agent '{agent['name']}' did not respond within "
                f"{self.valves.REQUEST_TIMEOUT}s. Is it running in serve-nats mode?"
            )
        except nats_py.errors.NoRespondersError:
            return (
                f"No agent is listening on '{nats_topic}'. "
                f"Start the agent with: serve-nats --nats {self.valves.NATS_URL}"
            )
        except Exception as exc:
            logger.exception("NATS request failed for %s", nats_topic)
            return f"NATS error: {exc}"

        # 5. Parse response
        try:
            result_envelope = json.loads(response.data.decode("utf-8"))
            result_payload = result_envelope.get("payload", result_envelope)

            if not result_payload.get("success", True):
                error = result_payload.get("result", {}).get("error", "Unknown error")
                return f"Agent error: {error}"

            result = result_payload.get("result", {})

            # Return the most useful text from the result
            # Agents return different shapes — try common keys
            for key in ("response", "text", "judgment", "output", "summary"):
                if key in result and isinstance(result[key], str):
                    return result[key]

            # Fallback: return the full result as formatted JSON
            return json.dumps(result, indent=2, default=str)

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse agent response: %s", exc)
            return response.data.decode("utf-8")
