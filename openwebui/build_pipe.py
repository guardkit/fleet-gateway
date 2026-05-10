"""Build a self-contained Open WebUI pipe by inlining ``common/`` modules.

Open WebUI's Workspace Functions Python interpreter does **not** ship
``nats-py`` and cannot ``pip install fleet-gateway-common`` (verified by
``docker exec`` against the running container — see scope §7 Q4). This
script flattens the source-of-truth pipe at ``openwebui/nats_fleet_pipe.py``
together with ``common/envelope.py`` and ``common/jarvis_client.py`` into
a single paste-ready file at ``openwebui/nats_fleet_pipe.deploy.py``.

Run after any change to ``common/`` or to the source pipe::

    python openwebui/build_pipe.py

The output file:
    * imports nothing from ``common`` at runtime,
    * carries the envelope/parse logic verbatim between
      ``# === BEGIN INLINED FROM common/ ===`` markers,
    * is regenerated deterministically (no timestamps in the body), so
      running the script twice produces identical bytes when the inputs
      have not changed.

The deploy file is committed to the repo so reviewers can diff it; the
Coach validates AC-007 by reading it directly.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

#: Repository root (parent of this file's parent — i.e. the worktree root).
ROOT: Path = Path(__file__).resolve().parent.parent

#: Source files concatenated into the deployable artifact, in order. The
#: order matters: ``envelope`` must be defined before ``jarvis_client``
#: references it.
SOURCES: tuple[str, ...] = (
    "common/envelope.py",
    "common/jarvis_client.py",
    "openwebui/nats_fleet_pipe.py",
)

#: Inline-block markers (used by tests + reviewers to spot the seam).
INLINE_BEGIN: str = "# === BEGIN INLINED FROM common/ ==="
INLINE_END: str = "# === END INLINED FROM common/ ==="

#: Regex for ``from common(.x)? import ...`` lines that must NOT survive
#: into the deploy file — at runtime there is no ``common`` package.
_COMMON_IMPORT_RE: re.Pattern[str] = re.compile(
    r"^\s*from\s+common(\.[\w]+)?\s+import\b.*$",
    re.MULTILINE,
)

#: Regex for ``from __future__ import annotations`` — kept exactly once at
#: the top of the deploy file.
_FUTURE_IMPORT_RE: re.Pattern[str] = re.compile(
    r"^from __future__ import annotations\s*$",
    re.MULTILINE,
)


def _read(rel: str) -> str:
    """Read a repository-relative source file as UTF-8 text."""
    return (ROOT / rel).read_text(encoding="utf-8")


def _strip_module_docstring(src: str) -> str:
    """Remove the leading triple-quoted module docstring, if any.

    The deploy file gets a single combined docstring at the top; the
    inlined sources keep their bodies but lose their per-module
    docstrings to avoid noise.
    """
    pattern = re.compile(r'^\s*(?:"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\')\s*\n', re.MULTILINE)
    match = pattern.match(src)
    if match is None:
        return src
    return src[match.end() :]


def _strip_unwanted_imports(src: str) -> str:
    """Strip ``from common`` and ``__future__`` imports from a source file."""
    src = _COMMON_IMPORT_RE.sub("", src)
    src = _FUTURE_IMPORT_RE.sub("", src)
    return src


def _normalise(src: str) -> str:
    """Trim leading/trailing whitespace and ensure exactly one trailing \\n."""
    return src.strip() + "\n"


def _split_imports_and_body(src: str) -> tuple[list[str], str]:
    """Split a source string into (top-level import statements, remaining body).

    Uses ``ast`` so we correctly detect multi-line ``from x import (\\n ...\\n)``
    blocks. Imports that target ``common`` or ``__future__`` are dropped — they
    are either inlined elsewhere or already declared once at the top of the
    deploy file.

    Args:
        src: Python source string.

    Returns:
        ``(imports, body)``. ``imports`` is a deduped list of import statement
        source segments; ``body`` is the remaining source with imports removed.
    """
    tree = ast.parse(src)
    src_lines = src.splitlines(keepends=True)

    import_segments: list[str] = []
    drop_ranges: list[tuple[int, int]] = []  # (start_line_idx, end_line_idx) inclusive

    for node in tree.body:
        if isinstance(node, ast.Import | ast.ImportFrom):
            # Skip imports we never want in the deploy file.
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "__future__" or module == "common" or module.startswith("common."):
                    drop_ranges.append((node.lineno - 1, (node.end_lineno or node.lineno) - 1))
                    continue
            segment = ast.get_source_segment(src, node)
            if segment is not None:
                import_segments.append(segment)
            drop_ranges.append((node.lineno - 1, (node.end_lineno or node.lineno) - 1))

    # Remove import lines from the body, preserving line ordering for what stays.
    drop_set: set[int] = set()
    for start, end in drop_ranges:
        for i in range(start, end + 1):
            drop_set.add(i)
    body_lines = [line for i, line in enumerate(src_lines) if i not in drop_set]
    body = "".join(body_lines)
    return import_segments, body


def _dedupe_imports(import_segments: list[str]) -> list[str]:
    """Return a stable-ordered, deduplicated list of import statements."""
    seen: set[str] = set()
    out: list[str] = []
    for seg in import_segments:
        key = " ".join(seg.split())  # canonicalise whitespace
        if key in seen:
            continue
        seen.add(key)
        out.append(seg)
    return out


def build_deploy_text() -> str:
    """Return the full text of the deployable pipe file.

    The function is pure: identical inputs produce identical output, which
    keeps the committed deploy file diff-stable. All imports from the inlined
    sources are hoisted into a single deduplicated block at the top so the
    output passes ruff's E402 / F811 / I001 checks.
    """
    all_imports: list[str] = []
    inlined_bodies: list[tuple[str, str]] = []

    for rel in ("common/envelope.py", "common/jarvis_client.py", "openwebui/nats_fleet_pipe.py"):
        raw = _read(rel)
        raw = _strip_module_docstring(raw)
        imports, body = _split_imports_and_body(raw)
        all_imports.extend(imports)
        inlined_bodies.append((rel, _normalise(body)))

    deduped_imports = _dedupe_imports(all_imports)

    parts: list[str] = []

    # 1. Combined module docstring.
    parts.append(
        '"""NATS Fleet Gateway Open WebUI Pipe — DEPLOYABLE (auto-generated).\n\n'
        "DO NOT EDIT BY HAND. Regenerate after any change to ``common/`` or to\n"
        "``openwebui/nats_fleet_pipe.py`` with::\n\n"
        "    python openwebui/build_pipe.py\n\n"
        "Source files (concatenated in order):\n"
        "    * common/envelope.py\n"
        "    * common/jarvis_client.py\n"
        "    * openwebui/nats_fleet_pipe.py\n\n"
        "This file is paste-ready for Open WebUI Admin → Workspace → Functions:\n"
        "the Open WebUI Python interpreter does not ship ``nats-py`` and cannot\n"
        "``pip install fleet-gateway-common``, so the shared envelope and\n"
        "JarvisClient code is inlined below between the BEGIN/END markers.\n"
        '"""\n\n'
    )

    # 2. Single ``from __future__`` line.
    parts.append("from __future__ import annotations\n\n")

    # 3. Hoisted import block (deduped).
    for seg in deduped_imports:
        parts.append(seg)
        parts.append("\n")
    parts.append("\n")

    # 4. Inlined module bodies.
    parts.append(f"{INLINE_BEGIN}\n")
    for rel, body in inlined_bodies[:2]:  # envelope + jarvis_client
        parts.append(f"# --- inlined from {rel} ---\n")
        parts.append(body)
        parts.append("\n")
    parts.append(f"{INLINE_END}\n\n")

    # 5. The pipe body (last entry).
    pipe_rel, pipe_body = inlined_bodies[2]
    parts.append(f"# --- inlined from {pipe_rel} ---\n")
    parts.append(pipe_body)

    return "".join(parts)


def _format_with_ruff(path: Path) -> None:
    """Best-effort: sort imports in the generated file via ``ruff check --fix``.

    The script writes valid Python without this step, but ruff's import
    sorting (rule ``I001``) keeps the committed deploy file lint-clean and
    diff-stable. If ruff is not on PATH, the step is silently skipped — the
    file is still valid and the project's lint check will surface the
    issue at CI time.
    """
    import subprocess  # noqa: PLC0415 — local import keeps top-level deps minimal

    try:
        subprocess.run(  # noqa: S603 — controlled args, no shell
            ["ruff", "check", "--fix", "--select", "I", "--exit-zero", str(path)],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        sys.stderr.write("ruff not found on PATH — skipping import sort.\n")


def main() -> int:
    """Write the deploy file to ``openwebui/nats_fleet_pipe.deploy.py``.

    Returns:
        Process exit code: ``0`` on success.
    """
    out = ROOT / "openwebui" / "nats_fleet_pipe.deploy.py"
    text = build_deploy_text()
    out.write_text(text, encoding="utf-8")
    _format_with_ruff(out)
    final_size = out.stat().st_size
    sys.stderr.write(f"Wrote {out} ({final_size} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
