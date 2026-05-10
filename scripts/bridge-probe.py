"""Standalone probe for the Bridge e2e runbook (Phase 1 + Phase 6).

Hits NATS on `promaxgb10-41b1:4222` through ``JarvisClient.send_command`` with
no Pollen, no Reachy daemon, no Bridge tool wrapper in the loop. The runbook
prints the returned text (or the ConnectionError signature) verbatim into the
RESULTS doc.

Per FEAT-FG-001 scope §7 Q3, this probe deliberately uses ``send_command`` on
``agents.command.jarvis``. ``JarvisClient.query_status()`` does not exist —
that method was dropped because the ``jarvis.status.query`` topic is not in
``nats-core``. Any code path that reaches for ``query_status`` is itself the
gap to fold.

Usage::

    python scripts/bridge-probe.py                              # default phrase
    python scripts/bridge-probe.py --phrase "what's the fleet status?"
    python scripts/bridge-probe.py --allow-connection-error     # Phase 6 mode

Pass criterion (Phase 1, happy path):
    - the call returns a non-empty string
    - the returned text mentions ≥1 known fleet agent
      (architect-agent / product-owner-agent / study-tutor / forge / …)

Pass criterion (Phase 6, graceful degradation):
    - the call raises ``ConnectionError`` (or a subclass of ``OSError``) cleanly
    - no nats-py / asyncio internal traceback escapes the script — the script
      prints the error class + message and exits 0 under
      ``--allow-connection-error``. Higher-layer "Fleet offline:" text is the
      ``AgentStatusTool`` contract (see Phase 3 / Phase 6.3 in the runbook).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from common.jarvis_client import JarvisClient

# Snapshot of known fleet agent ids at runbook authoring (2026-05-10).
# When the live `agent-registry` KV gains or drops members, the runbook gap-
# fold rule (strategy §7.3) applies: update this set and note the gap in the
# RESULTS table rather than improvising assertions.
KNOWN_AGENTS: frozenset[str] = frozenset(
    {
        "architect-agent",
        "product-owner-agent",
        "study-tutor",
        "forge",
        "specialist-agent",
    }
)


async def _probe(phrase: str, allow_connection_error: bool) -> int:
    client = JarvisClient(
        nats_url="nats://promaxgb10-41b1:4222",
        adapter="reachy-bridge",
    )
    try:
        response = await client.send_command(phrase)
    except (ConnectionError, OSError) as exc:
        # Phase 6 mode: NATS unreachable surfaces here as ConnectionError.
        # Print the structured error rather than letting the traceback
        # leak — the runbook treats a clean ConnectionError as a pass for
        # the lower layer; the tool-wrapper graceful contract is checked
        # one phase up via AgentStatusTool.
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 0 if allow_connection_error else 1

    print(response)

    if allow_connection_error:
        # Phase 6 mode: if NATS is somehow still reachable, treat any
        # returned text as a pass for the bare layer — the asserts below
        # belong to the happy path only.
        return 0

    # Phase 1 mode: enforce the §6.2 happy-path contract.
    assert response, "empty response from Jarvis"
    assert any(a in response.lower() for a in KNOWN_AGENTS), (
        f"no known fleet agent named in response: {response[:200]}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge e2e standalone probe")
    parser.add_argument(
        "--phrase",
        default="what's the fleet status?",
        help="Message to send to Jarvis on agents.command.jarvis",
    )
    parser.add_argument(
        "--allow-connection-error",
        action="store_true",
        help=(
            "Suppress the happy-path asserts and treat ConnectionError as a "
            "pass (use for Phase 6 graceful-degradation runs)"
        ),
    )
    args = parser.parse_args()
    return asyncio.run(_probe(args.phrase, args.allow_connection_error))


if __name__ == "__main__":
    sys.exit(main())
