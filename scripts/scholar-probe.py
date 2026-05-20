"""Standalone probe for the Scholar e2e runbook (Phase 1 + Phase 5).

Hits FalkorDB on whitestocks:6379 through ``GraphitiClient.search_student_progress``
with no Pollen, no Reachy daemon, no LLM in the loop. The runbook prints the
returned dict verbatim into the RESULTS doc.

Usage::

    python scripts/scholar-probe.py                     # defaults: lilymay / english
    python scripts/scholar-probe.py --student lilymay --subject english

Pass criterion (Phase 1, happy path):
    - ``data_available is True``
    - ``streak_days`` is an ``int``
    - ``topic_confidence`` is a non-empty mapping

Pass criterion (Phase 5, graceful degradation):
    - ``data_available is False``
    - the script exits 1 (the assert on data_available trips) but prints the
      returned dict first — no Python traceback from the GraphitiClient layer
      itself. Re-run with ``--allow-no-data`` to suppress the assert and only
      capture the structured fallback dict for the RESULTS table.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from common.graphiti_client import GraphitiClient


async def _probe(student_name: str, subject: str, allow_no_data: bool) -> int:
    client = GraphitiClient(
        falkordb_uri="redis://whitestocks:6379",
        default_group_ids=[f"student-{student_name}"],
    )
    progress = await client.search_student_progress(
        student_name=student_name, subject=subject
    )
    print(json.dumps(progress, indent=2, default=str))

    if allow_no_data:
        # Phase 5 mode: any structured dict (including data_available=False)
        # is a pass as long as the call returned cleanly.
        return 0

    # Phase 1 mode: enforce the happy-path contract.
    assert progress["data_available"] is True, (
        f"data_available is False: {progress}"
    )
    assert isinstance(progress.get("streak_days"), int), (
        f"streak_days not int: {progress}"
    )
    assert progress.get("topic_confidence"), (
        f"topic_confidence empty: {progress}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Scholar e2e standalone probe")
    parser.add_argument("--student", default="lilymay")
    parser.add_argument("--subject", default="english")
    parser.add_argument(
        "--allow-no-data",
        action="store_true",
        help="Skip happy-path asserts (use for Phase 5 degradation runs)",
    )
    args = parser.parse_args()
    return asyncio.run(
        _probe(args.student, args.subject, args.allow_no_data)
    )


if __name__ == "__main__":
    sys.exit(main())
