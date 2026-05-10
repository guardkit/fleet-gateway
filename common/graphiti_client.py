"""Graphiti client over ``graphiti-core`` direct to FalkorDB.

Used by Scholar's ``query_student_model`` tool (TASK-FG-005). Connect-per-call
pattern mirroring :class:`common.jarvis_client.JarvisClient` — each method
opens a fresh ``graphiti-core`` client, runs the search and closes it. This
sidesteps the asyncio loop-ownership pitfalls seen in long-lived async
clients invoked from Pollen's per-request loops.

This replaces the originally-scoped HTTP-REST design (per scope §7 Q1 /
§6 A1): the deployed Graphiti is the **MCP server** that does NOT expose
a REST endpoint. The cleanest client is ``graphiti-core`` direct to
FalkorDB, mirroring ``guardkit.knowledge.graphiti_client``.

**Graceful degradation contract** (scope §5.2 #2 — Scholar must never crash
the conversation): both :meth:`GraphitiClient.search` and
:meth:`GraphitiClient.search_student_progress` swallow all errors. The
former returns ``[]``, the latter returns
``{"data_available": False, "error": "<reason>: <details>"}``.

**Error classification** (per ASSUM-004 — auth failures must be
distinguishable from unreachable failures):

* ``ConnectionRefusedError``, ``ConnectionResetError``, ``OSError``,
  :class:`asyncio.TimeoutError` → ``"unreachable"``.
* Anything whose type name or message mentions ``auth`` / ``WRONGPASS`` /
  ``NOAUTH`` → ``"auth-failed"``.
* Everything else falls back to ``"unreachable"`` so callers always see a
  classified error rather than a leaked traceback.

The mapping uses string heuristics rather than ``isinstance`` so the module
does not have to import ``redis-py`` purely for an exception check — the
``graphiti-core`` package owns that dependency.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_FALKORDB_URI",
    "DEFAULT_GROUP_IDS",
    "GraphitiClient",
    "parse_falkordb_uri",
]

#: Default FalkorDB URI (Synology NAS via Tailscale, scope §6 A1 corrected).
DEFAULT_FALKORDB_URI = "redis://whitestocks:6379"

#: Default group_id list — ``student-lilymay`` per scope §6 A6 (corrected:
#: dash form, not the rejected ``study_tutor__student_model`` double-
#: underscore form).
DEFAULT_GROUP_IDS: tuple[str, ...] = ("student-lilymay",)

#: Per-call timeout for graphiti-core searches. Mirrors ASSUM-004 in scope.
DEFAULT_TIMEOUT_SECONDS = 5.0

#: Substrings that strongly imply an authentication failure regardless of the
#: concrete exception type. Lower-cased before comparison.
_AUTH_FAILURE_MARKERS: tuple[str, ...] = (
    "authentication",
    "wrongpass",
    "noauth",
    "invalid password",
    "auth-failed",
    "auth failed",
)


def parse_falkordb_uri(uri: str) -> tuple[str, int]:
    """Parse a ``redis://host:port`` URI into a ``(host, port)`` pair.

    Args:
        uri: FalkorDB Redis-protocol URI.

    Returns:
        Tuple of ``(host, port)``.

    Raises:
        ValueError: If the URI is missing a scheme, host, or port, or uses a
            scheme other than ``redis://``.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "redis":
        msg = f"falkordb_uri must use redis:// scheme, got: {uri!r}"
        raise ValueError(msg)
    host = parsed.hostname
    if not host:
        msg = f"falkordb_uri missing host, got: {uri!r}"
        raise ValueError(msg)
    if parsed.port is None:
        msg = f"falkordb_uri must include explicit port, got: {uri!r}"
        raise ValueError(msg)
    return host, parsed.port


async def _create_graphiti_instance(host: str, port: int) -> Any:
    """Lazily construct a ``graphiti-core`` ``Graphiti`` client.

    Imports are deferred so the module loads even when ``graphiti-core`` is
    not installed (mirrors the lazy-import pattern in
    ``guardkit.knowledge.graphiti_client``). This function is the canonical
    seam used by tests — they monkey-patch it to inject a fake client and
    avoid touching FalkorDB.

    Args:
        host: FalkorDB host.
        port: FalkorDB port.

    Returns:
        An initialised ``graphiti_core.Graphiti`` instance bound to a
        ``FalkorDriver``.
    """
    from graphiti_core import Graphiti  # noqa: PLC0415 — lazy on purpose
    from graphiti_core.driver.falkordb_driver import FalkorDriver  # noqa: PLC0415

    driver = FalkorDriver(host=host, port=port)
    return Graphiti(graph_driver=driver)


def _edge_to_dict(edge: Any) -> dict[str, Any]:
    """Normalise a ``graphiti-core`` ``EntityEdge`` to a JSON-friendly dict."""
    created_at = getattr(edge, "created_at", None)
    if created_at is not None:
        created_at = str(created_at)
    return {
        "uuid": getattr(edge, "uuid", None),
        "fact": getattr(edge, "fact", None),
        "name": getattr(edge, "name", None),
        "created_at": created_at,
    }


def _classify_exception(exc: BaseException) -> str:
    """Classify ``exc`` as ``"auth-failed"`` or ``"unreachable"``.

    The check inspects both the exception type name and its message in
    lowercase form, so a ``redis.exceptions.AuthenticationError`` and a
    raw ``RuntimeError("WRONGPASS ...")`` both map to ``auth-failed``.
    """
    type_name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "auth" in type_name and "authentic" not in type_name and "auth" not in msg:
        # Avoid mis-classifying e.g. ``AuthorityError`` from an unrelated
        # subsystem — fall through if the message has no auth marker.
        return "unreachable"
    if "auth" in type_name or any(marker in msg for marker in _AUTH_FAILURE_MARKERS):
        return "auth-failed"
    return "unreachable"


class GraphitiClient:
    """Async client for the Graphiti knowledge graph backed by FalkorDB.

    The client owns no long-lived state: each call to :meth:`search` or
    :meth:`search_student_progress` constructs a new ``graphiti-core``
    instance, performs the search and closes it. This is the same loop-
    ownership-safe pattern used by :class:`common.jarvis_client.JarvisClient`
    and is critical for callers running inside Pollen's per-request asyncio
    loops where a long-lived client would bind to the wrong loop.

    All public methods degrade gracefully — see the module docstring for the
    full error-classification contract.

    Example:
        >>> client = GraphitiClient(falkordb_uri="redis://whitestocks:6379")
        >>> facts = await client.search("english progress")  # doctest: +SKIP
        >>> progress = await client.search_student_progress("lilymay")  # doctest: +SKIP
    """

    def __init__(
        self,
        falkordb_uri: str = DEFAULT_FALKORDB_URI,
        default_group_ids: list[str] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Construct the client.

        Args:
            falkordb_uri: FalkorDB Redis-protocol URI: ``redis://host:port``.
                Defaults to the Synology NAS Tailscale endpoint.
            default_group_ids: Group IDs used when callers omit ``group_ids``.
                Defaults to ``["student-lilymay"]`` per scope §6 A6
                (corrected dash form).
            timeout_seconds: Per-call timeout passed to
                :func:`asyncio.wait_for`. Defaults to
                :data:`DEFAULT_TIMEOUT_SECONDS`.

        Raises:
            ValueError: If ``falkordb_uri`` is malformed.
        """
        self._host, self._port = parse_falkordb_uri(falkordb_uri)
        self._falkordb_uri = falkordb_uri
        self._default_group_ids: list[str] = (
            list(DEFAULT_GROUP_IDS) if default_group_ids is None else list(default_group_ids)
        )
        self._timeout_seconds = timeout_seconds

    @property
    def default_group_ids(self) -> list[str]:
        """Return a copy of the configured default group IDs."""
        return list(self._default_group_ids)

    @property
    def falkordb_uri(self) -> str:
        """Return the configured FalkorDB URI (read-only)."""
        return self._falkordb_uri

    async def search(
        self,
        query: str,
        group_ids: list[str] | None = None,
        num_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search Graphiti for facts matching ``query``.

        Never raises — on any error returns an empty list and logs a warning
        with the classified error type. See module docstring for the
        unreachable / auth-failed classification contract.

        Args:
            query: Natural-language search query.
            group_ids: Group IDs to scope the search. Falls back to
                :attr:`default_group_ids` when ``None``.
            num_results: Maximum number of facts ``graphiti-core`` should
                return. Defaults to 10.

        Returns:
            List of fact dicts with keys ``uuid``, ``fact``, ``name`` and
            ``created_at``. Empty list on connection / auth failures or
            timeouts.
        """
        ids = list(group_ids) if group_ids is not None else list(self._default_group_ids)
        graphiti: Any | None = None
        try:
            graphiti = await _create_graphiti_instance(self._host, self._port)
            raw = await asyncio.wait_for(
                graphiti.search(query, group_ids=ids, num_results=num_results),
                timeout=self._timeout_seconds,
            )
            return [_edge_to_dict(edge) for edge in (raw or [])]
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            kind = _classify_exception(exc)
            logger.warning(
                "GraphitiClient.search degraded (%s) for query=%r at %s: %s",
                kind,
                query,
                self._falkordb_uri,
                exc,
            )
            return []
        finally:
            if graphiti is not None:
                await self._safe_close(graphiti)

    async def search_student_progress(
        self,
        student_name: str = "lilymay",
        subject: str = "english",
    ) -> dict[str, Any]:
        """Return a structured snapshot of student progress for the LLM.

        Composes three internal :meth:`search` calls (streak/level, near
        achievements, topic confidence) and assembles the structured dict
        Scholar narrates back to the learner. The ``group_id`` is derived
        as ``f"student-{student_name}"`` per scope §6 A6 (correction).

        Never raises — unreachable / auth-failed errors return
        ``{"data_available": False, "error": "<reason>: <details>"}``.

        Args:
            student_name: Student identifier (without prefix). Defaults to
                ``"lilymay"``.
            subject: Subject domain narrative is being shaped for. Defaults
                to ``"english"``.

        Returns:
            Dict with keys ``student_name`` (str), ``streak_days`` (int),
            ``level_name`` (str), ``recent_xp`` (int), ``near_achievements``
            (list[str]), ``topic_confidence`` (dict[str, float]) and
            ``data_available`` (bool). On failure the dict only contains
            ``data_available=False`` and ``error``.
        """
        group_ids = [f"student-{student_name}"]
        graphiti: Any | None = None
        try:
            graphiti = await _create_graphiti_instance(self._host, self._port)
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            kind = _classify_exception(exc)
            logger.warning(
                "GraphitiClient.search_student_progress connect failed (%s) at %s: %s",
                kind,
                self._falkordb_uri,
                exc,
            )
            return {"data_available": False, "error": f"{kind}: {exc}"}

        try:
            queries = (
                f"current streak and level for {student_name} in {subject}",
                f"near achievements for {student_name} in {subject}",
                f"topic confidence for {student_name} in {subject}",
            )
            collected: list[list[dict[str, Any]]] = []
            for query in queries:
                raw = await asyncio.wait_for(
                    graphiti.search(query, group_ids=group_ids, num_results=10),
                    timeout=self._timeout_seconds,
                )
                collected.append([_edge_to_dict(edge) for edge in (raw or [])])
            streak_facts, achievement_facts, topic_facts = collected
            return {
                "student_name": student_name,
                "streak_days": _extract_streak_days(streak_facts),
                "level_name": _extract_level_name(streak_facts),
                "recent_xp": _extract_recent_xp(streak_facts),
                "near_achievements": _extract_near_achievements(achievement_facts),
                "topic_confidence": _extract_topic_confidence(topic_facts),
                "data_available": True,
            }
        except Exception as exc:  # noqa: BLE001 — graceful degradation
            kind = _classify_exception(exc)
            logger.warning(
                "GraphitiClient.search_student_progress degraded (%s) for %s/%s: %s",
                kind,
                student_name,
                subject,
                exc,
            )
            return {"data_available": False, "error": f"{kind}: {exc}"}
        finally:
            await self._safe_close(graphiti)

    @staticmethod
    async def _safe_close(graphiti: Any) -> None:
        """Close a Graphiti instance, swallowing and logging any errors."""
        close = getattr(graphiti, "close", None)
        if close is None:
            return
        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # noqa: BLE001 — best-effort cleanup
            logger.debug("GraphitiClient close error suppressed: %s", exc)


# ---------------------------------------------------------------------------
# Fact-shape extractors used by search_student_progress
# ---------------------------------------------------------------------------


def _extract_streak_days(facts: list[dict[str, Any]]) -> int:
    """Pick the first integer adjacent to the word ``streak`` in any fact."""
    for fact in facts:
        text = (fact.get("fact") or "").lower()
        match = re.search(r"streak[^0-9]{0,40}(\d+)", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:  # pragma: no cover — regex guarantees digits
                continue
    return 0


def _extract_level_name(facts: list[dict[str, Any]]) -> str:
    """Find a level identifier (e.g. ``Bronze 3``) in streak/level facts."""
    for fact in facts:
        text = fact.get("fact") or ""
        match = re.search(r"level[: ]+([A-Za-z]+(?:\s+\d+)?)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "unknown"


def _extract_recent_xp(facts: list[dict[str, Any]]) -> int:
    """Pick the first integer immediately preceding ``xp`` in any fact."""
    for fact in facts:
        text = (fact.get("fact") or "").lower()
        match = re.search(r"(\d+)\s*xp\b", text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:  # pragma: no cover — regex guarantees digits
                continue
    return 0


def _extract_near_achievements(facts: list[dict[str, Any]]) -> list[str]:
    """Return the raw fact texts as the achievement summaries."""
    achievements: list[str] = []
    for fact in facts:
        text = fact.get("fact")
        if isinstance(text, str) and text:
            achievements.append(text)
    return achievements


def _extract_topic_confidence(facts: list[dict[str, Any]]) -> dict[str, float]:
    """Parse ``topic <name> confidence: 0.82``-style facts into a dict."""
    confidence: dict[str, float] = {}
    pattern = re.compile(
        r"(?:topic|skill|area)\s+(?:of\s+|on\s+)?"
        r"([A-Za-z][A-Za-z0-9 _-]{0,40}?)\s+"
        r"(?:confidence|score|level)[: =]+([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    for fact in facts:
        text = fact.get("fact") or ""
        match = pattern.search(text)
        if match:
            try:
                confidence[match.group(1).strip().lower()] = float(match.group(2))
            except ValueError:  # pragma: no cover — regex guarantees digits
                continue
    return confidence
