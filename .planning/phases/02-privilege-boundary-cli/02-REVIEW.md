---
phase: 02-privilege-boundary-cli
reviewed: 2026-05-15T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - acercontrol/privilege.py
  - acercontrol/cli.py
  - libexec/acercontrol-setprofile
  - libexec/acercontrol-set-boot-profile
  - libexec/acercontrol-manage-service
  - data/org.acercontrol.policy
  - tools/verify_no_gtk.py
  - tools/bundle_cli.py
  - tools/smoke_phase2.py
  - pyproject.toml
findings:
  blocker: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-15
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Phase 2 stands up the privilege boundary cleanly: three real-binary wrappers
with hardcoded allowlists, polkit policy with named actions, SSH-aware
elevation, idempotent pkexec-cancel handling, locked `--json` schema, and a
stdlib-only bundler. The trust-boundary discipline is sound — wrappers
re-validate argv, refuse non-root invocation, hardcode allowlists rather than
trust scrubbed `PYTHONPATH`, and use absolute `#!/usr/bin/python3` shebangs so
`org.freedesktop.policykit.exec.path` matching works.

No BLOCKER issues found. Two correctness-adjacent WARNINGs surfaced:

1. **Polkit `exec.path` only annotates `/usr/libexec/...` but `resolve_wrapper`
   also returns `/usr/local/libexec/...` and `ACERCONTROL_DEV` paths.** When
   `install.sh` deploys to `/usr/local/libexec/` (the documented fallback),
   pkexec falls back to the implicit `org.freedesktop.policykit.exec` action
   and shows a generic "run /usr/local/libexec/.../acercontrol-setprofile as
   the super user" prompt instead of the named "Change the Acer performance
   profile" message. Security is intact; UX degrades silently.
2. **`_MAIN_BLOCK` regex stops at the first blank line.** Latent today (both
   actual `if __name__ == "__main__":` blocks are single-paragraph); becomes a
   real bug the moment any future contributor adds a blank line inside such a
   block — code below the blank would leak into the bundle and run before the
   `__main__` shim.

Two more WARNINGs cover deferred-impact issues (manage-service exit-code
collapse; pre-bundle gtk pattern weaker than post-bundle), and INFOs cover
unused imports, stderr noise in `--json` mode, and a placeholder URL.

JSON schema verified against `02-01-PLAN.md` lock (lines 281-300): all six
subcommand `--json` shapes match. `acercontrol status --json` adds
`blacklist_entries` to the probe payload — additive, allowed under
"append-only" rule.

## Warnings

### WR-01: Polkit policy `exec.path` does not cover `/usr/local/libexec/...` or dev paths

**File:** `data/org.acercontrol.policy:19,31,43` and `acercontrol/privilege.py:32-55`
**Issue:** All three actions annotate
`org.freedesktop.policykit.exec.path = /usr/libexec/acercontrol/<wrapper>`.
But `resolve_wrapper()` returns the first existing path from:
1. `/usr/libexec/acercontrol/<name>` (the .deb path — matches the policy)
2. `/usr/local/libexec/acercontrol/<name>` (the `install.sh` fallback —
   does NOT match)
3. `${ACERCONTROL_DEV}/libexec/<name>` (the in-repo dev path — does NOT match)

When pkexec is invoked with a binary path that no `<action>` annotates,
pkexec falls back to the implicit `org.freedesktop.policykit.exec` action.
The user sees a generic "Authentication is required to run
`/usr/local/libexec/acercontrol/acercontrol-setprofile` as the super user"
prompt instead of the named "Change the Acer performance profile" message
that `org.acercontrol.setprofile` declares. The action also won't honor
`auth_admin_keep` caching for AcerControl specifically; it'll cache against
the generic exec action.

This is a UX defect, not a security defect — the wrapper still re-validates
argv and refuses non-root.

**Fix (recommended):** Have `install.sh` symlink `/usr/local/libexec/acercontrol/*`
into `/usr/libexec/acercontrol/` (or install both — Phase 8 .deb path is
canonical). Do NOT broaden the policy to list both paths under one action;
pkexec ties an action to exactly one `exec.path` and listing two would
create two separate actions sharing the same `id` (undefined behavior). For
the dev path (`ACERCONTROL_DEV`), this is expected to use sudo or run as
root in dev — document this in the smoke runner output when the dev path
is hit.

```sh
# install.sh — after copying wrappers to /usr/local/libexec/acercontrol/
sudo install -d /usr/libexec/acercontrol
for w in acercontrol-setprofile acercontrol-set-boot-profile acercontrol-manage-service; do
    sudo ln -sf "/usr/local/libexec/acercontrol/$w" "/usr/libexec/acercontrol/$w"
done
```

### WR-02: `_MAIN_BLOCK` regex in bundler stops at internal blank lines

**File:** `tools/bundle_cli.py:128-131,158-169`
**Issue:** The regex
`r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*\n(?:[ \t]+.*\n?)+"`
matches consecutive non-blank indented lines after the `if __name__` header.
A blank line inside the main block ends the match, leaving any trailing
indented code uncommented. The bundler then concatenates that trailing code
verbatim, where it runs at bundle import time — BEFORE the appended
`sys.exit(main())` shim — and short-circuits the CLI entry.

Empirically verified:
```
src = "if __name__ == '__main__':\n    print('hello')\n\n    print('world')\n"
match = "if __name__ == '__main__':\n    print('hello')\n"   # 'world' line leaks through
```

Latent today: both real main blocks (`features.py:_print_report(probe())` and
`cli.py:sys.exit(main())`) are single-paragraph. Becomes a real bug the moment
any contributor adds a blank line.

**Fix:** Either (a) change the trailing group to also match blank lines:

```python
_MAIN_BLOCK = re.compile(
    r"^if\s+__name__\s*==\s*['\"]__main__['\"]\s*:\s*\n"
    r"(?:(?:[ \t]+.*|[ \t]*)\n?)+",
    re.MULTILINE,
)
```

or (b) parse the source with `ast` and walk to find `If` nodes with
`__name__ == "__main__"` tests, recording line ranges, then comment those
ranges out by line number — this is robust to all formatting and is parallel
to how `_drift_gate_check_src` already uses `ast.parse` for the wrapper
allowlist.

### WR-03: `acercontrol-manage-service` collapses non-zero systemctl exits to EX_OSERR

**File:** `libexec/acercontrol-manage-service:62`
**Issue:** `return result.returncode if result.returncode == 0 else EX_OSERR`
discards meaningful systemctl exit codes (1=generic failure, 3=service not
active, 4=no such unit, 5=invalid argument) and reports them all as 71. The
caller (Phase 3 GUI / Phase 4 callers) cannot distinguish "service not
installed yet" from "operation refused" without parsing stderr — defeating
the whole point of having a structured exit-code contract.

Phase 2 has no CLI consumer of this wrapper yet (no `acercontrol service ...`
subcommand), but Phase 3 is documented as the consumer.

**Fix:** Pass through the systemctl returncode as-is. The CLI/GUI caller can
then map it to user-facing messages. Reserve EX_OSERR for the
`FileNotFoundError`/`TimeoutExpired` paths where systemctl truly couldn't run.

```python
# Pass through systemctl's exit code directly so callers can distinguish
# "no such unit" (4) from "operation failed" (1) etc.
return result.returncode
```

### WR-04: Pre-bundle gtk-import check is weaker than post-bundle check

**File:** `tools/bundle_cli.py:178` vs `tools/verify_no_gtk.py:39`
**Issue:** `bundle_cli._check_no_gtk` uses
`r"^(import\s+gi|from\s+gi(\.|\s))"` — no leading whitespace allowance.
`verify_no_gtk.check` uses `r"^\s*(import\s+gi(\b|\.)|from\s+gi(\b|\.))"` —
allows leading whitespace.

A source file with an indented `import gi` (e.g. inside a `try:` block, an
`if` guard, or a function body) PASSES the pre-bundle inline check but FAILS
the post-bundle verify_no_gtk run on `dist/acercontrol`. Defense-in-depth
catches it (the bundle is unlinked on failure), but the inline error message
is more informative — "refusing to bundle X" with the source path — and
should fire on the same surface that the post-bundle stage rejects.

```python
src = "def foo():\n    import gi  # indented\n"
# bundle_cli._check_no_gtk: NOT MATCHED   (passes pre-bundle)
# verify_no_gtk pattern:    MATCHED       (fails post-bundle)
```

**Fix:** Align the pre-bundle pattern with `verify_no_gtk` (anchor + leading
whitespace + word boundary):

```python
if re.search(
    r"^\s*(import\s+gi(\b|\.)|from\s+gi(\b|\.))",
    src,
    re.MULTILINE,
):
    raise SystemExit(...)
```

## Info

### IN-01: Unused imports in `acercontrol/cli.py`

**File:** `acercontrol/cli.py:26-27,31,34`
**Issue:** Four imports are never referenced in the module:
- Line 26: `from dataclasses import asdict` — not used; `_sensor_to_json`
  hand-builds the dict.
- Line 27: `from typing import Any` — not used.
- Line 31: `KERNEL_TO_UI` — not used; `Profile.display` already does the
  reverse mapping internally.
- Line 34: `kernel_to_profile` — not used; `read_profile()` returns a
  `Profile` directly.

These trip flake8 / ruff and will trigger lintian's `pyflakes` warnings on
the .deb in Phase 8.

**Fix:**
```python
# Drop these from the imports block:
# from dataclasses import asdict
# from typing import Any
# (and remove KERNEL_TO_UI, kernel_to_profile from the acercontrol-package import)
```

### IN-02: Unused import in `tools/bundle_cli.py`

**File:** `tools/bundle_cli.py:33`
**Issue:** `import shutil` is never used in the module. The bundler does
file I/O via `Path.read_text` / `Path.write_text` and uses `subprocess.run`
to invoke `verify_no_gtk.py` — no `shutil.copy` etc.

**Fix:** Remove `import shutil`.

### IN-03: stderr noise in `--json` mode duplicates JSON error payload

**File:** `acercontrol/cli.py:198-204,243-248,249-255,260-270,352-356,363-374,403-414`
**Issue:** Every `cmd_set` and `cmd_install` error path writes a
human-readable error to stderr THEN emits the structured error JSON to
stdout. A `--json` consumer that only parses stdout gets clean JSON, but
tools that capture both streams (or interleave them) see the human prose
mixed in. The locked schema is silent on whether `--json` mode should
suppress stderr; current behavior is "JSON on stdout AND human stderr".

This is a quality concern (not a bug) — JSON output is valid and
parseable. Consider either:
- documenting this as the contract ("`--json` always emits JSON on stdout;
  stderr may also receive prose for `tee`/log readability"), or
- in `--json` mode, suppress the redundant `sys.stderr.write` calls before
  the structured payload.

The current code is consistent across all error paths — this is a design
choice that's worth nailing down before Phase 3 GUI consumers parse the
output.

### IN-04: Placeholder vendor URL in polkit policy

**File:** `data/org.acercontrol.policy:8`
**Issue:** `<vendor_url>https://github.com/acercontrol/acercontrol</vendor_url>`
returns HTTP 404 — the GitHub org/repo doesn't exist (or is private).
polkit displays vendor info in some auth dialogs and in `pkaction --verbose`
output. A 404 makes the project look abandoned/typo'd to anyone who clicks
through.

If this is the intended placeholder until the repo goes public, leave it;
otherwise replace with a real URL or omit the element (it's optional in the
polkit DTD).

### IN-05: `run_privileged(dry_run=True)` branch is unreachable from current callers

**File:** `acercontrol/privilege.py:97,149-157` and `acercontrol/cli.py:210-230`
**Issue:** `cmd_set` implements its own dry-run path (lines 210-230)
that calls `pick_elevation()` and `resolve_wrapper()` directly and
short-circuits before reaching `run_privileged()`. Consequently the
`dry_run=True` branch inside `run_privileged` (lines 149-157) is never
exercised by Phase 2 code or smoke tests. This is OK as a documented
future-API surface (Phase 3 GUI may use it), but the divergence is
worth calling out: the `cmd_set` dry-run JSON shape is hand-built in
`cli.py`, while the `run_privileged(dry_run=True)` shape is a
`PrivilegedResult` with a `[dry-run] would invoke: ...` stdout string.
If both ever go live, they need to converge.

**Fix:** Either delete the `dry_run` parameter from `run_privileged` (YAGNI
until Phase 3 needs it) or have `cmd_set`'s dry-run path delegate to
`run_privileged(dry_run=True)` and shape the JSON from
`PrivilegedResult.argv`. Pick one — the current state is two parallel dry-run
implementations.

---

_Reviewed: 2026-05-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
