#!/usr/bin/env python3
# tools/verify_no_gtk.py
"""CLI-07 enforcement: refuse if any input contains `import gi` / `from gi`.

Used by bundle_cli.py (post-bundle on dist/acercontrol) and by
smoke_phase2.py (pre-bundle on each acercontrol/*.py going into the
bundle). Stdlib only.

Usage:
    python3 tools/verify_no_gtk.py <file> [<file>...]
Returns 0 on no matches, 1 on any match, 64 (EX_USAGE) on empty argv.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Anchor on start-of-line; allow leading whitespace (catch indented imports
# inside functions / try blocks). Comment lines are stripped explicitly in
# `check()` so `# from gi import ...` documentation passes.
#
# `gi` must be followed by a word boundary (end-of-line, dot, whitespace, or
# `as <alias>`) so we don't false-positive on `gibberish` (Rule 1 fix vs
# research pattern which required `\.|\s` and missed `import gi$`).
_GTK_IMPORT = re.compile(
    r"(^|\n)\s*(import\s+gi(\b|\.)|from\s+gi(\b|\.))"
)


def check(path: Path) -> list:
    """Return list of (line_number, line) hits in path. Never raises."""
    text = path.read_text(encoding="utf-8", errors="replace")
    hits: list = []
    for i, line in enumerate(text.splitlines(), start=1):
        # Skip comments — `# from gi import ...` is documentation, not code.
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if re.match(r"^\s*(import\s+gi(\b|\.)|from\s+gi(\b|\.))", line):
            hits.append((i, line.rstrip()))
    return hits


def main(argv: list) -> int:
    if len(argv) < 2:
        sys.stderr.write(f"usage: {argv[0]} <file> [<file>...]\n")
        return 64
    bad = 0
    for arg in argv[1:]:
        p = Path(arg)
        if not p.exists():
            sys.stderr.write(f"{p}: not found\n")
            bad += 1
            continue
        hits = check(p)
        if hits:
            bad += 1
            for ln, code in hits:
                sys.stderr.write(f"{p}:{ln}: {code}\n")
    if bad:
        sys.stderr.write(f"verify_no_gtk: {bad} file(s) failed CLI-07\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
