---
phase: 02-privilege-boundary-cli
type: research
depends_on: [01-foundation]
tags: [polkit, pkexec, cli, argparse, stdlib, privilege-boundary, bundler, json-schema, validation, security]
research_date: 2026-05-15
valid_until: 2026-06-14
confidence_overall: HIGH
---

# Phase 2: Privilege Boundary + CLI — Research

**Researched:** 2026-05-15
**Domain:** Linux polkit/pkexec privilege boundary, stdlib-only Python CLI, JSON-schema contract design
**Confidence:** HIGH (primary sources verified; Phase 1 patterns inherited unchanged)

## Summary

Phase 2 stands up the **end-to-end privilege boundary** with the CLI as its first consumer. The privilege model has three trust layers: (1) **CLI** (`acercontrol/cli.py`) validates user input against the user-name allowlist, picks the elevation method based on `$SSH_CONNECTION`, and translates wrapper/pkexec exit codes into human-aligned messages; (2) **`privilege.py`** is a thin elevation helper that knows how to invoke `pkexec` or `sudo` with the right argv and how to interpret exit codes 126/127; (3) **three real-binary wrappers** at `/usr/libexec/acercontrol/{acercontrol-setprofile, acercontrol-set-boot-profile, acercontrol-manage-service}` independently re-validate their argv against hardcoded allowlists, then perform the sysfs/systemctl write. The wrappers are the **trust boundary** — they never assume the CLI was the caller, because `pkexec` exposes the action ID `org.acercontrol.{setprofile,set-boot-profile,manage-service}` to anything on the system with the right session.

**Critical constraint surfaced during research:** `pkexec` scrubs `PYTHONPATH` and resets the environment to "a minimal known and safe environment" [VERIFIED: pkexec(1) Ubuntu Noble]. Until the `.deb` lands (Phase 8), `acercontrol` is not installed under `/usr/lib/python3/dist-packages/`. **Wrappers MUST NOT `from acercontrol.profiles import PROFILES`** under real `pkexec` invocation — `sys.path` won't resolve the package. Each wrapper hardcodes its allowlist as a literal tuple, with a comment pointing at `acercontrol/profiles.py` as the source of truth. The Phase 2 smoke runner exercises this contract via a `pkexec --disable-internal-agent`-equivalent harness on Linux (env-scrub simulation on macOS) so the bug is caught in CI, not on the user's first `set turbo`.

**Primary recommendation:** Three wrappers, each ~50 LOC stdlib-only Python, each pinned to a named polkit action via `org.freedesktop.policykit.exec.path`. CLI is argparse with `set_defaults(func=...)` subparser dispatch and a global `--json` slot. Bundler is stdlib-concat with a verifier that grep-gates `^import gi` / `^from gi` against both inputs AND output. macOS/CI smoke runs every command via `--dry-run` and returns exit 0; Linux UAT runs the full elevation path.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Argument parsing, user-name → kernel-value mapping | CLI (`acercontrol/cli.py`) | — | UX layer; fast typo feedback without a polkit prompt |
| Elevation method selection (`pkexec` vs `sudo`) | `acercontrol/privilege.py` | — | Single source of truth for `$SSH_CONNECTION` precedence and exit-code translation |
| Argv re-validation against allowlist | Wrapper binary (`/usr/libexec/acercontrol/*`) | — | Trust boundary — must NOT assume the CLI was the caller |
| Sysfs write (`platform_profile`) | Wrapper binary (root) | — | Privileged write; runs as uid 0 after polkit auth |
| Systemctl invocation (boot service) | Wrapper binary (root) | — | Same privilege model; `systemctl is-active` (read-only) stays in CLI under user uid |
| Auth dialog (with message + icon) | polkit daemon | `.policy` XML | Declarative; CLI/wrappers never render dialogs |
| Single-file bundling | `tools/bundle_cli.py` | `tools/verify_no_gtk.py` | Build-time only; not in runtime path |
| Read-back verification | CLI (`acercontrol/cli.py`) | — | Runs as user uid after wrapper exits; consumes Phase 1 `read_profile()` |

## User Constraints (from CONTEXT.md)

### Locked Decisions

(Copied verbatim from `02-CONTEXT.md`. Planner does NOT re-decide these.)

**PRIV-01..05, CLI-01..07** — see CONTEXT.md `<spec_lock>` for the per-requirement behavior contract. Highlights:

- Real-binary wrapper pattern at `/usr/libexec/acercontrol/` (never `pkexec bash -c '…'`).
- Three named polkit actions: `org.acercontrol.setprofile`, `org.acercontrol.set-boot-profile`, `org.acercontrol.manage-service`. Each pinned to its wrapper via `org.freedesktop.policykit.exec.path`. `allow_active = auth_admin_keep`; `allow_any` / `allow_inactive` = `auth_admin` (no `_keep`).
- `pkexec` exit 126 (auth cancelled) → CLI prints "Authentication cancelled" and exits cleanly.
- `$SSH_CONNECTION` set → escalate via `sudo` instead of `pkexec`.
- **Defense-in-depth wrapper validation** — each wrapper independently re-validates argv.
- **Plain default + `--json` opt-in** on `status` / `temps` / `get` / `list`.
- **`acercontrol install`** as non-root: print + exit 0. As root: execute.
- **`--dry-run` flag** on every privileged CLI command, composes with `--json`.
- **Wrapper filenames:** `acercontrol-setprofile`, `acercontrol-set-boot-profile`, `acercontrol-manage-service`.
- **Wrapper language:** Python, stdlib-only, gi-free.
- **CLI module structure:** `acercontrol/cli.py` (entry) + `acercontrol/privilege.py` (escalation helper).
- **Bundler:** stdlib concat → `dist/acercontrol` single executable file.
- **Boot service controlled by `manage-service`:** literal `acer-performance.service` (Phase 6 ships the actual unit).

### Claude's Discretion

(Copied verbatim from `02-CONTEXT.md`. The planner formalizes specific details inside these boundaries.)

- Whether the wrapper duplicates the allowlist as a literal or imports from `acercontrol.profiles` — **this research RESOLVES to "duplicate as literal", see Pattern 3 + Pitfall P2-NEW-01**.
- Exact JSON schema field names (this research locks the schema — see Pattern 8).
- Exact CLI message strings (this research suggests them; planner may refine).

### Deferred Ideas (OUT OF SCOPE)

- `acercontrol install --interactive`.
- `acercontrol set --no-verify`.
- `--quiet` / `-q` global flag.
- Per-action polkit `.rules` overlay.
- Shell completion.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRIV-01 | Privileged writes via real binary wrapper, never `pkexec bash -c` | Pattern 1 (privilege.py invokes wrappers); Pattern 3-5 (wrappers); Pitfall P1 |
| PRIV-02 | Polkit policy with 3 named actions, each pinned via `exec.path`; `auth_admin_keep` for `allow_active` | Pattern 6 (`org.acercontrol.policy` XML); DOCTYPE verified |
| PRIV-03 | Auth dialog shows configured human message, never `org.freedesktop.policykit.exec` fallback | Pattern 6 `<message>` elements; verified that pkexec picks named action when `exec.path` matches |
| PRIV-04 | Exit 126 handled idempotently — "Authentication cancelled" exit 0; second invocation within keep-alive window doesn't re-prompt | Pattern 1 (`run_privileged()` exit code translation); Validation row PRIV-04-UAT |
| PRIV-05 | `$SSH_CONNECTION` set → escalate via `sudo` instead of `pkexec` | Pattern 1 (`pick_elevation()`); Pitfall P14 |
| CLI-01 | `acercontrol status` — feature probe + current profile + available + fan/temp summary | Pattern 2 (`cmd_status`); consumes Phase 1 `probe()`, `read_profile()`, `read_sensors()`, `list_available_profiles()` |
| CLI-02 | `acercontrol get` user-name; `acercontrol get --raw` kernel value | Pattern 2 (`cmd_get`); uses Phase 1 `read_profile()` (returns `Profile`) |
| CLI-03 | `acercontrol set <profile>` validates → escalates → writes through wrapper → reads back → exits non-zero on mismatch | Pattern 2 (`cmd_set`); Pattern 1 (`run_privileged`); read-back via `read_profile()` |
| CLI-04 | `acercontrol list` user-facing profiles, marking active | Pattern 2 (`cmd_list`); uses `list_available_profiles()` + `read_profile()` |
| CLI-05 | `acercontrol temps` CPU package + fan1/2 + acer temps | Pattern 2 (`cmd_temps`); uses `read_sensors()` |
| CLI-06 | `acercontrol install` prints steps; executes when uid 0 | Pattern 2 (`cmd_install`); `os.geteuid()` branch |
| CLI-07 | Zero non-stdlib deps; bundled `dist/acercontrol` is single stdlib-only file; CI guard fails on `import gi` leak | Pattern 9 (`bundle_cli.py`); Pattern 10 (`verify_no_gtk.py`); enforced in Patterns 3-5 (wrappers) too |

## Standard Stack

### Core (no new runtime deps)
| Library/Module | Version | Purpose | Why Standard |
|---------------|---------|---------|--------------|
| `argparse` | stdlib | CLI subcommand parsing | Zero deps; CLAUDE.md stack decision #10 [CITED: ./CLAUDE.md L457-461] |
| `json` | stdlib | `--json` output | Append-only schema; stable across versions |
| `os` | stdlib | `geteuid()`, `environ`, `execvp()` | Standard privilege-detection idiom |
| `subprocess` | stdlib | Wrapper / `pkexec` / `sudo` invocation | List-form argv (no shell) — security req from Phase 1 |
| `sys` | stdlib | `sys.exit()`, `sys.argv`, `sys.stderr` | Standard CLI entry-point pattern |
| `pathlib` | stdlib | Path manipulation | Phase 1 idiom; consistent with `acercontrol/core.py` |
| `shutil.which()` | stdlib | Detect `pkexec` / `sudo` presence | Avoids `FileNotFoundError` at call time |
| `acercontrol` (Phase 1) | 0.1.0.dev0 | `read_profile`, `read_sensors`, `probe`, `list_available_profiles`, `Profile`, `PROFILES`, `kernel_to_profile`, `current_profile_ui`, `KERNEL_TO_UI` | Single source of truth from Phase 1 |

### Build-time only (NOT runtime)
| Library | Version | Purpose | Used By |
|---------|---------|---------|---------|
| `setuptools` | >=61 | PEP 517 backend (already in pyproject) | `pyproject.toml` build only |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `argparse` | `click` / `typer` | Both are PyPI deps. Violates the zero-deps + bundler-friendly constraint. `typer` additionally pulls `click` + `rich`. [CITED: ./CLAUDE.md L460-461] |
| Hardcoded wrapper allowlist | `from acercontrol.profiles import PROFILES` | **pkexec env-scrub breaks the import** (see P2-NEW-01). Until Phase 8 installs the package to `/usr/lib/python3/dist-packages/`, the wrapper cannot resolve the package. Hardcoded literal is the only correct Phase-2 answer. |
| stdlib concat bundler | `PyInstaller` / `Nuitka` / `shiv` / `zipapp` | All add a build-time dep. `zipapp` would actually work (stdlib) but produces a zip-prefixed file which `chmod +x` runs via shebang — fine in theory, but the concat approach is simpler, debuggable, and matches CLAUDE.md stack decision #8 (the "thin shim that does `from acercontrol.cli import main; main()`, or a bundler concatenating stdlib-only modules"). [CITED: ./CLAUDE.md L446-447] |
| `subprocess` for elevation | `os.execvp(["pkexec", ...])` after fork | `subprocess.run` with `check=False` gives clean exit-code introspection without manual fork/wait. `execvp` replaces the process — would mean the CLI dies before doing the read-back step in CLI-03. |

**No `pip install` step.** Phase 2 introduces ZERO new runtime dependencies; this is what makes CLI-07 satisfiable.

**Version verification:** Not applicable — Phase 2 ships no new third-party packages.

## Architecture Patterns

### System Architecture Diagram

```
                                 ┌─────────────────────────────────────────────┐
                                 │  USER SHELL  (uid: 1000)                    │
                                 │  $ acercontrol set turbo                    │
                                 └────────────────┬────────────────────────────┘
                                                  │ argv = ["set", "turbo"]
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  CLI LAYER  (acercontrol/cli.py — runs as user)                                         │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ argparse    │→ │ user-name       │→ │ privilege.py     │→ │ read-back verify     │  │
│  │ subparsers  │  │ allowlist check │  │ pick elevation   │  │ via read_profile()   │  │
│  │ + --json    │  │ (PROFILES dict) │  │ + run subprocess │  │ + compare requested  │  │
│  └─────────────┘  └─────────────────┘  └────────┬─────────┘  └──────────────────────┘  │
│        │ exit 2 on argparse error      ▲        │                                      │
│        │ exit 64 on allowlist miss     │        │                                      │
│        └───────────────────────────────┘        │                                      │
└─────────────────────────────────────────────────┼──────────────────────────────────────┘
                                                  │ $SSH_CONNECTION? → sudo : pkexec
                                                  ▼
                                   ┌──────────────────────────────┐
                                   │  ELEVATION                   │
                                   │  pkexec /usr/libexec/acer... │
                                   │  -or-                        │
                                   │  sudo  /usr/libexec/acer...  │
                                   │                              │
                                   │  pkexec → polkit daemon →    │
                                   │    .policy lookup by         │
                                   │    exec.path; auth dialog;   │
                                   │    auth_admin_keep cache     │
                                   └──────────────┬───────────────┘
                                                  │ exec via uid 0
                                                  │ (env scrubbed by pkexec —
                                                  │  PYTHONPATH gone)
                                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  WRAPPER  (/usr/libexec/acercontrol/acercontrol-setprofile — runs as root)              │
│  ┌─────────────────┐  ┌──────────────────────┐  ┌───────────────────────────────────┐  │
│  │ re-validate     │→ │ open PROFILE_PATH    │→ │ write kernel value, fsync, close  │  │
│  │ argv against    │  │ /sys/firmware/acpi/  │  │ exit 0 on success                 │  │
│  │ HARDCODED       │  │ platform_profile     │  │ exit 71 EX_OSERR on write failure │  │
│  │ allowlist       │  │                      │  │                                   │  │
│  │ (stdlib only —  │  └──────────────────────┘  └───────────────────────────────────┘  │
│  │  cannot import  │                                                                   │
│  │  acercontrol)   │                                                                   │
│  └────┬────────────┘                                                                   │
│       │ exit 64 EX_USAGE on argv mismatch                                              │
└───────┼────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   /sys/firmware/acpi/platform_profile  ← kernel acer_wmi predator_v4
```

### Recommended Project Structure (deltas from Phase 1)

```
acercontrol/
├── __init__.py              # Phase 1 (no change)
├── core.py                  # Phase 1 (no change)
├── features.py              # Phase 1 (no change)
├── profiles.py              # Phase 1 (no change)
├── sysfs.py                 # Phase 1 (no change)
├── privilege.py             # NEW — elevation helper (~80 LOC)
└── cli.py                   # NEW — CLI entry (~250 LOC)

data/
└── org.acercontrol.policy   # NEW — polkit policy (~50 LOC XML)

libexec/                     # NEW directory — staging area; .deb installs to /usr/libexec/acercontrol/
├── acercontrol-setprofile           # NEW — ~50 LOC stdlib Python, executable
├── acercontrol-set-boot-profile     # NEW — ~50 LOC, executable
└── acercontrol-manage-service       # NEW — ~70 LOC, executable

tools/
├── smoke_phase1.py          # Phase 1 (no change)
├── smoke_phase2.py          # NEW — aggregate runner for PRIV/CLI requirements (~200 LOC)
├── bundle_cli.py            # NEW — stdlib-only concatenator → dist/acercontrol (~120 LOC)
└── verify_no_gtk.py         # NEW — grep gate over inputs AND outputs (~50 LOC)

dist/                        # gitignored output dir
└── acercontrol              # NEW — bundled single-file CLI, chmod +x

pyproject.toml               # MODIFIED — add [project.scripts]
```

**Note on `/usr/libexec/` vs project `libexec/`:** Phase 2 stages wrappers in repo-root `libexec/`. The `.deb` (Phase 8) installs them to `/usr/libexec/acercontrol/`. `install.sh` (Phase 8) ditto. For Phase 2 manual smoke, the planner may also include a `tools/install_phase2_dev.sh` that copies to `/usr/local/libexec/acercontrol/` for PHN16-72 testing — but that's a planner-call, not a research mandate.

---

### Pattern 1: `acercontrol/privilege.py` skeleton

**What:** Elevation helper. Single source of truth for `$SSH_CONNECTION` precedence, `pkexec` vs `sudo` selection, and exit-code translation.

**When to use:** Every privileged CLI command (`set`, `install` when root). Never directly from a wrapper (wrappers run as root already).

```python
# acercontrol/privilege.py
"""Privilege escalation helper for AcerControl CLI (PRIV-04, PRIV-05).

Picks pkexec or sudo based on $SSH_CONNECTION precedence. Translates
wrapper / pkexec exit codes into CLI-meaningful return values.

Pure stdlib. No `gi` imports. Importable from cli.py only — wrappers
never use this module (they run as root already and don't elevate).
"""
from __future__ import annotations
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# ── Wrapper locations ──────────────────────────────────────────────
#
# Installed by Phase 8 .deb to /usr/libexec/acercontrol/; install.sh
# may use /usr/local/libexec/acercontrol/. Resolution order:
#   1. /usr/libexec/acercontrol/<name>
#   2. /usr/local/libexec/acercontrol/<name>
#   3. <repo>/libexec/<name>  (dev mode — only when ACERCONTROL_DEV is set)
WRAPPER_NAMES = (
    "acercontrol-setprofile",
    "acercontrol-set-boot-profile",
    "acercontrol-manage-service",
)

_WRAPPER_DIRS = (
    Path("/usr/libexec/acercontrol"),
    Path("/usr/local/libexec/acercontrol"),
)


def resolve_wrapper(name: str) -> Path | None:
    """Return path to wrapper binary, or None if not installed.

    Honors ACERCONTROL_DEV env var for in-repo testing.
    """
    if name not in WRAPPER_NAMES:
        raise ValueError(f"unknown wrapper: {name!r}")
    for d in _WRAPPER_DIRS:
        p = d / name
        if p.exists() and os.access(p, os.X_OK):
            return p
    # Dev override
    dev_root = os.environ.get("ACERCONTROL_DEV")
    if dev_root:
        p = Path(dev_root) / "libexec" / name
        if p.exists() and os.access(p, os.X_OK):
            return p
    return None


Elevation = Literal["pkexec", "sudo", "none"]


def pick_elevation() -> Elevation:
    """Pick the elevation strategy for the current environment (PRIV-05).

    Precedence (verified against pkexec(1) and sshd(8) docs):
      1. If euid == 0 → "none" (caller is already root)
      2. If $SSH_CONNECTION is set → "sudo"   (pkexec hangs without a graphical agent)
      3. If shutil.which("pkexec") → "pkexec" (preferred — named action UX)
      4. If shutil.which("sudo")   → "sudo"   (fallback)
      5. Otherwise → "none" (caller path will surface an error)
    """
    if os.geteuid() == 0:
        return "none"
    if os.environ.get("SSH_CONNECTION"):
        return "sudo"
    if shutil.which("pkexec"):
        return "pkexec"
    if shutil.which("sudo"):
        return "sudo"
    return "none"


@dataclass(frozen=True)
class PrivilegedResult:
    """Outcome of a privileged invocation."""
    returncode: int          # wrapper exit code, OR pkexec/sudo exit code if elevation failed
    elevation: Elevation
    argv: tuple[str, ...]    # what was actually invoked (post-elevation prefix)
    cancelled: bool          # True iff pkexec exit was 126 (auth dismissed)
    stdout: str
    stderr: str


def run_privileged(
    wrapper_argv: list[str],
    *,
    timeout: int = 30,
    dry_run: bool = False,
) -> PrivilegedResult:
    """Run wrapper_argv with the right elevation. Never raises.

    wrapper_argv[0] MUST be one of WRAPPER_NAMES (validated). The wrapper
    is resolved by name to its installed path; resolve_wrapper() returns
    None when not installed and we surface that as returncode=127.

    Exit code translation (cli.py callers should map these to user messages):
      0   = success
      64  = wrapper rejected argv (EX_USAGE — should not reach here if CLI validated)
      71  = wrapper failed sysfs/systemctl write (EX_OSERR)
      126 = polkit auth dialog cancelled (pkexec specific; cancelled=True)
      127 = pkexec/sudo not available, OR wrapper not installed, OR auth denied
    """
    if not wrapper_argv:
        raise ValueError("wrapper_argv must be non-empty")
    name = wrapper_argv[0]
    wrapper_path = resolve_wrapper(name)
    if wrapper_path is None:
        return PrivilegedResult(
            returncode=127,
            elevation="none",
            argv=tuple(wrapper_argv),
            cancelled=False,
            stdout="",
            stderr=f"wrapper not installed: {name}\n",
        )

    method = pick_elevation()
    if method == "none":
        # Either we're already root, or there is no elevation available.
        # Caller decides whether that's an error.
        if os.geteuid() != 0:
            return PrivilegedResult(
                returncode=127,
                elevation="none",
                argv=tuple(wrapper_argv),
                cancelled=False,
                stdout="",
                stderr="no elevation method available (pkexec/sudo missing)\n",
            )
        full_argv = [str(wrapper_path), *wrapper_argv[1:]]
    elif method == "pkexec":
        full_argv = ["pkexec", str(wrapper_path), *wrapper_argv[1:]]
    elif method == "sudo":
        # -n: don't prompt; -- separates sudo options from wrapper path.
        # Caller path: we *do* want sudo to prompt for password if needed.
        full_argv = ["sudo", "--", str(wrapper_path), *wrapper_argv[1:]]
    else:  # pragma: no cover — Literal exhaustion
        raise AssertionError(method)

    if dry_run:
        return PrivilegedResult(
            returncode=0,
            elevation=method,
            argv=tuple(full_argv),
            cancelled=False,
            stdout=f"[dry-run] would invoke: {' '.join(full_argv)}\n",
            stderr="",
        )

    try:
        result = subprocess.run(
            full_argv,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return PrivilegedResult(
            returncode=124,   # GNU coreutils `timeout` convention
            elevation=method,
            argv=tuple(full_argv),
            cancelled=False,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\ntimeout after {timeout}s",
        )
    except FileNotFoundError:
        return PrivilegedResult(
            returncode=127,
            elevation=method,
            argv=tuple(full_argv),
            cancelled=False,
            stdout="",
            stderr=f"{method}: not found in PATH\n",
        )

    return PrivilegedResult(
        returncode=result.returncode,
        elevation=method,
        argv=tuple(full_argv),
        cancelled=(method == "pkexec" and result.returncode == 126),
        stdout=result.stdout,
        stderr=result.stderr,
    )
```

#### Exit Code Mapping (privilege.py's primary contract)

| Origin | Exit Code | Meaning | CLI-level Response |
|--------|-----------|---------|---------------------|
| Wrapper | 0 | Write succeeded | Continue to read-back |
| Wrapper | 64 | EX_USAGE — wrapper rejected argv [CITED: sysexits.h Noble] | "internal error: wrapper rejected '<argv>'" → exit 2 |
| Wrapper | 71 | EX_OSERR — sysfs write failed | "Failed to write profile: <wrapper stderr>" → exit 1 |
| Wrapper | 77 | EX_NOPERM — wrapper refuses non-root caller | "internal error: wrapper not privileged" → exit 1 |
| pkexec | 126 | Auth dialog dismissed [VERIFIED: pkexec(1) Noble] | "Authentication cancelled" → **exit 0** (PRIV-04 idempotent) |
| pkexec | 127 | Not authorized / authentication error / pkexec not found [VERIFIED: pkexec(1) Noble] | "Authentication required but not granted" → exit 1 |
| `subprocess.TimeoutExpired` | 124 | Local timeout from `run_privileged` | "Operation timed out after 30s" → exit 1 |

**Sources:**
- `pkexec(1)` Ubuntu Noble — exit 126: "the authorization could not be obtained because the user dismissed the authentication dialog"; exit 127: "the calling process is not authorized or an authorization could not be obtained through authentication or an error occured" [VERIFIED: https://manpages.ubuntu.com/manpages/noble/en/man1/pkexec.1.html]
- `sysexits.h(3head)` Ubuntu Noble — EX_USAGE=64, EX_OSERR=71, EX_NOPERM=77 [VERIFIED: https://manpages.ubuntu.com/manpages/noble/en/man3/sysexits.h.3head.html]

---

### Pattern 2: `acercontrol/cli.py` argparse layout

**What:** Main CLI entry. Argparse with subparser dispatch via `set_defaults(func=...)`. Six subcommands. Global `--json` flag at each subparser. `--dry-run` on privileged commands.

**When to use:** `main()` is the entry point bound by `pyproject.toml [project.scripts]` AND the entry point bundled into `dist/acercontrol`.

```python
# acercontrol/cli.py
"""AcerControl CLI — status/get/set/list/temps/install (CLI-01..07).

Stdlib only — no gi imports. Imports from acercontrol.* for shared logic.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Any

from acercontrol import (
    PROFILES,
    KERNEL_TO_UI,
    Profile,
    SensorReading,
    kernel_to_profile,
    list_available_profiles,
    probe,
    read_profile,
    read_sensors,
)
from acercontrol.privilege import (
    pick_elevation,
    resolve_wrapper,
    run_privileged,
)


__all__ = ["main"]


# ── Output helpers ─────────────────────────────────────────────────

def _emit(data: dict[str, Any] | None, text: str, *, as_json: bool) -> None:
    """Emit either JSON (one line) or human text. data may be None when as_json."""
    if as_json:
        if data is None:
            data = {"message": text}
        sys.stdout.write(json.dumps(data, separators=(",", ":"), default=str) + "\n")
    else:
        sys.stdout.write(text + ("\n" if not text.endswith("\n") else ""))


def _sensor_to_json(s: SensorReading) -> dict[str, Any]:
    """Map SensorReading dataclass to the locked JSON schema (see Pattern 8)."""
    return {
        "cpu_package_c": s.cpu_package_c,
        "fan1_rpm":      s.fan1_rpm,
        "fan2_rpm":      s.fan2_rpm,
        "acer_temp1_c":  s.acer_temp1_c,
        "acer_temp2_c":  s.acer_temp2_c,
        "acer_temp3_c":  s.acer_temp3_c,
    }


# ── Subcommand handlers ────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    """CLI-01: feature probe + profile + list + temps."""
    report = probe()
    prof = read_profile()
    avail = list_available_profiles()
    sensors = read_sensors()
    if args.json:
        payload = {
            "probe": {
                "checks": [
                    {
                        "name": c.name,
                        "present": c.present,
                        "detail": c.detail,
                        "fix": c.fix,
                        "severity": c.severity,
                    }
                    for c in report.checks
                ],
                "ok": report.ok,
                "first_blocking_failure": (
                    None if report.first_blocking_failure is None else {
                        "name": report.first_blocking_failure.name,
                        "fix":  report.first_blocking_failure.fix,
                    }
                ),
                "blacklist_entries": [
                    {"file": f, "line": l} for f, l in report.blacklist_entries
                ],
            },
            "profile": {
                "profile":      prof.display.lower() if prof is not Profile.CUSTOM else "custom",
                "kernel_value": prof.value,
            },
            "list": {
                "profiles": [p.display.lower() for p in avail
                             if p is not Profile.CUSTOM],
                "active":   prof.display.lower() if prof is not Profile.CUSTOM else "custom",
            },
            "temps": _sensor_to_json(sensors),
        }
        sys.stdout.write(json.dumps(payload, separators=(",", ":"), default=str) + "\n")
    else:
        # Human text — planner refines exact format
        print(f"AcerControl status  (probe ok={report.ok})")
        print("-" * 60)
        for c in report.checks:
            mark = "OK" if c.present else c.severity[:3].upper()
            print(f"  [{mark}] {c.name}: {c.detail}")
        print()
        print(f"Current profile: {prof.display}  (kernel: {prof.value})")
        print(f"Available:       {', '.join(p.display for p in avail) or '(unknown)'}")
        print()
        print(f"CPU package: {sensors.cpu_package_c}°C   "
              f"Fan1: {sensors.fan1_rpm} RPM   Fan2: {sensors.fan2_rpm} RPM")
    # Exit code matches features.py _print_report semantics:
    #   0 clean, 1 degraded, 2 blocking failure
    if not report.ok:
        return 2
    if any(c.severity == "warning" and not c.present for c in report.checks):
        return 1
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """CLI-02: print profile. --raw prints kernel value."""
    prof = read_profile()
    if args.raw:
        if args.json:
            _emit({"kernel_value": prof.value}, prof.value, as_json=True)
        else:
            print(prof.value)
    else:
        name = prof.display.lower() if prof is not Profile.CUSTOM else "custom"
        if args.json:
            _emit(
                {"profile": name, "kernel_value": prof.value},
                name,
                as_json=True,
            )
        else:
            print(name)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """CLI-04: list available profiles, mark active."""
    avail = list_available_profiles()
    active = read_profile()
    active_name = active.display.lower() if active is not Profile.CUSTOM else "custom"
    names = [p.display.lower() for p in avail if p is not Profile.CUSTOM]
    if args.json:
        _emit(
            {"profiles": names, "active": active_name},
            ",".join(names),
            as_json=True,
        )
    else:
        for n in names:
            marker = " *" if n == active_name else ""
            print(f"{n}{marker}")
    return 0


def cmd_temps(args: argparse.Namespace) -> int:
    """CLI-05: print CPU package + fan1/2 + acer temps."""
    s = read_sensors()
    if args.json:
        _emit(_sensor_to_json(s), "", as_json=True)
    else:
        print(f"CPU package:  {s.cpu_package_c}°C")
        print(f"Fan 1:        {s.fan1_rpm} RPM")
        print(f"Fan 2:        {s.fan2_rpm} RPM")
        print(f"acer temp1:   {s.acer_temp1_c}°C")
        print(f"acer temp2:   {s.acer_temp2_c}°C")
        print(f"acer temp3:   {s.acer_temp3_c}°C")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    """CLI-03: validate → escalate → write through wrapper → read back."""
    # 1. CLI-side validation (fast feedback; no polkit prompt for typos)
    if args.profile not in PROFILES:
        sys.stderr.write(
            f"unknown profile: {args.profile!r}\n"
            f"available: {', '.join(PROFILES.keys())}\n"
        )
        if args.json:
            _emit({"error": "unknown_profile", "value": args.profile},
                  "", as_json=True)
        return 2

    kernel_value = PROFILES[args.profile]

    # 2. Dry-run path (CI / macOS testing)
    if args.dry_run:
        method = pick_elevation()
        wrapper_path = resolve_wrapper("acercontrol-setprofile")
        payload = {
            "dry_run":      True,
            "profile":      args.profile,
            "kernel_value": kernel_value,
            "wrapper":      str(wrapper_path) if wrapper_path else None,
            "elevation":    method,
            "argv":         [
                "acercontrol-setprofile",
                kernel_value,
            ],
        }
        if args.json:
            _emit(payload, "", as_json=True)
        else:
            print(f"[dry-run] would set profile={args.profile} (kernel={kernel_value})")
            print(f"[dry-run] elevation={method}")
            print(f"[dry-run] wrapper={wrapper_path}")
        return 0

    # 3. Real invocation
    result = run_privileged(["acercontrol-setprofile", kernel_value])

    # 4. Translate exit codes (see Pattern 1 mapping table)
    if result.cancelled:
        # PRIV-04: idempotent — exit 0
        if args.json:
            _emit({"cancelled": True}, "Authentication cancelled", as_json=True)
        else:
            print("Authentication cancelled.")
        return 0
    if result.returncode == 127:
        sys.stderr.write(result.stderr or "elevation unavailable\n")
        if args.json:
            _emit({"error": "elevation_unavailable",
                   "stderr": result.stderr}, "", as_json=True)
        return 1
    if result.returncode != 0:
        sys.stderr.write(result.stderr or f"wrapper exit {result.returncode}\n")
        if args.json:
            _emit({"error": "wrapper_failed",
                   "exit_code": result.returncode,
                   "stderr": result.stderr}, "", as_json=True)
        return 1

    # 5. Read-back verification (CLI-03 exits non-zero on mismatch)
    actual = read_profile()
    if actual.value != kernel_value:
        msg = (
            f"Profile not applied — requested {args.profile} ({kernel_value}), "
            f"got {actual.display} ({actual.value}). "
            f"power-profiles-daemon may be overriding writes."
        )
        sys.stderr.write(msg + "\n")
        if args.json:
            _emit({"error": "mismatch",
                   "requested": kernel_value,
                   "actual":    actual.value}, msg, as_json=True)
        return 1

    if args.json:
        _emit({"profile": args.profile, "kernel_value": kernel_value},
              f"Switched to {args.profile}", as_json=True)
    else:
        print(f"Switched to {args.profile}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """CLI-06: print install steps (non-root) OR execute them (root)."""
    steps_text = (
        "# AcerControl install steps\n"
        "\n"
        "# 1. Configure acer_wmi to use predator_v4 mode\n"
        "echo 'options acer_wmi predator_v4=1' "
        "> /etc/modprobe.d/99-acer-wmi.conf\n"
        "\n"
        "# 2. Rebuild initramfs so the option applies on next boot\n"
        "update-initramfs -u\n"
        "\n"
        "# 3. Enable the boot profile service (Phase 6 ships the unit)\n"
        "systemctl daemon-reload\n"
        "systemctl enable acer-performance.service\n"
        "\n"
        "# 4. Reboot to pick up the modprobe.d change\n"
        "reboot\n"
    )
    steps_list = [
        {"step": 1, "what": "modprobe.d snippet",
         "cmd":  "echo 'options acer_wmi predator_v4=1' > /etc/modprobe.d/99-acer-wmi.conf"},
        {"step": 2, "what": "update-initramfs",
         "cmd":  "update-initramfs -u"},
        {"step": 3, "what": "enable boot service",
         "cmd":  "systemctl daemon-reload && systemctl enable acer-performance.service"},
        {"step": 4, "what": "reboot to apply",
         "cmd":  "reboot"},
    ]

    is_root = os.geteuid() == 0
    if args.dry_run:
        if args.json:
            _emit({"dry_run": True, "is_root": is_root,
                   "steps": steps_list}, "", as_json=True)
        else:
            print(f"[dry-run] is_root={is_root}")
            print(steps_text)
        return 0

    if not is_root:
        # CONTEXT.md lock: print + exit 0
        if args.json:
            _emit({"is_root": False, "steps": steps_list,
                   "advice": "rerun as root to execute"}, "", as_json=True)
        else:
            print(steps_text)
        return 0

    # Root path — execute steps via manage-service wrapper for the systemctl part
    # (sysfs and file writes happen directly here since we're already root).
    # Planner formalizes exact subprocess call shape.
    # ... omitted in skeleton ...
    return 0


# ── Parser construction ────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="acercontrol",
        description="Acer Predator/Nitro performance control",
    )
    # add_subparsers required=True per Python 3.7+ recommendation
    sub = p.add_subparsers(dest="cmd", required=True)

    # status
    p_status = sub.add_parser("status", help="full system status")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    # get
    p_get = sub.add_parser("get", help="current profile (user-name)")
    p_get.add_argument("--raw",  action="store_true", help="print kernel value")
    p_get.add_argument("--json", action="store_true")
    p_get.set_defaults(func=cmd_get)

    # set
    p_set = sub.add_parser("set", help="set profile (requires privilege)")
    p_set.add_argument("profile", help=f"one of: {', '.join(PROFILES.keys())}")
    p_set.add_argument("--dry-run", action="store_true",
                       help="validate + print what would happen; no elevation")
    p_set.add_argument("--json",    action="store_true")
    p_set.set_defaults(func=cmd_set)

    # list
    p_list = sub.add_parser("list", help="available profiles")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    # temps
    p_temps = sub.add_parser("temps", help="CPU/fan/acer temperatures")
    p_temps.add_argument("--json", action="store_true")
    p_temps.set_defaults(func=cmd_temps)

    # install
    p_install = sub.add_parser(
        "install",
        help="print install steps; execute when run as root",
    )
    p_install.add_argument("--dry-run", action="store_true")
    p_install.add_argument("--json",    action="store_true")
    p_install.set_defaults(func=cmd_install)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

**Notes on argparse exit codes:**
- argparse calls `parser.error()` on usage errors, which prints to stderr and exits **2** [VERIFIED: Python argparse docs, https://docs.python.org/3/library/argparse.html]. We do NOT override this — the CLI inherits exit-2-on-usage-error from argparse.
- Subcommand handlers return their own exit code; `main()` returns `args.func(args)`; the `if __name__ == "__main__":` block does `sys.exit(...)`.

---

### Pattern 3: `libexec/acercontrol-setprofile` (PRIV-01 wrapper)

**What:** The privileged write binary for `platform_profile`. Runs as root after polkit auth. **Defense-in-depth** — re-validates argv against a hardcoded literal allowlist; never imports `acercontrol.profiles`.

**When to use:** Invoked exclusively by `privilege.run_privileged(["acercontrol-setprofile", <kernel-value>])`.

```python
#!/usr/bin/python3
# /usr/libexec/acercontrol/acercontrol-setprofile
"""Privileged wrapper: write a kernel platform_profile value (PRIV-01).

This is the trust boundary. pkexec invokes us under the action
`org.acercontrol.setprofile` (matched via org.freedesktop.policykit.exec.path).
We MUST re-validate argv even though the CLI also validates — another
local process with the right session could pkexec us directly.

Why the hardcoded ALLOWED_KERNEL_VALUES tuple instead of importing from
acercontrol.profiles? pkexec sanitizes the environment to a minimal
known-safe set (see pkexec(1) Ubuntu Noble — "minimal known and safe
environment in order to avoid injecting code through LD_LIBRARY_PATH or
similar mechanisms"). PYTHONPATH is scrubbed. Until the Phase 8 .deb
installs acercontrol to /usr/lib/python3/dist-packages/, the package
is not on sys.path. Hardcoding the literal is the only correct answer
for Phase 2 — and it keeps the trust boundary independent of any
Python-level "I might forget to update the dist-packages" hazard.

Source of truth: acercontrol/profiles.py PROFILES dict values. If that
changes, this literal must change in lockstep — covered by Phase 2 smoke.

Stdlib only. No third-party imports.
"""
import os
import sys

PROFILE_PATH = "/sys/firmware/acpi/platform_profile"

# Source of truth: acercontrol/profiles.py PROFILES.values()
# Must update in lockstep when PROFILES changes.
ALLOWED_KERNEL_VALUES = (
    "low-power",
    "quiet",
    "balanced",
    "balanced-performance",
    "performance",
)

EX_OK    = 0
EX_USAGE = 64
EX_OSERR = 71
EX_NOPERM = 77


def main(argv: list[str]) -> int:
    # 1. Argv shape
    if len(argv) != 2:
        sys.stderr.write(
            f"usage: {os.path.basename(argv[0] or 'acercontrol-setprofile')} "
            f"<kernel-value>\n"
        )
        return EX_USAGE

    value = argv[1]

    # 2. Allowlist re-validation (defense-in-depth)
    if value not in ALLOWED_KERNEL_VALUES:
        sys.stderr.write(
            f"refusing: {value!r} not in allowlist "
            f"{ALLOWED_KERNEL_VALUES}\n"
        )
        return EX_USAGE

    # 3. Privilege check — we should be uid 0 here
    if os.geteuid() != 0:
        sys.stderr.write(
            f"refusing: must run as root (effective uid {os.geteuid()})\n"
        )
        return EX_NOPERM

    # 4. Write
    try:
        with open(PROFILE_PATH, "w") as f:
            f.write(value)
    except OSError as exc:
        sys.stderr.write(f"write failed: {exc}\n")
        return EX_OSERR

    return EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

**Shebang choice:** `#!/usr/bin/python3` (absolute path) rather than `#!/usr/bin/env python3`. Inside `/usr/libexec/` under a polkit-elevated context, the convention is absolute paths because `pkexec` rebuilds PATH from a known-safe minimal environment [CITED: pkexec(1) Noble]. Ubuntu 24.04 ships `/usr/bin/python3` ≥ 3.12; this is guaranteed by the `Depends: python3` line we'll declare in Phase 8.

---

### Pattern 4: `libexec/acercontrol-set-boot-profile`

**What:** Writes the boot-time profile to `/etc/default/acercontrol` so Phase 6's `acer-performance.service` can read it on next boot. Same trust-boundary discipline as Pattern 3.

```python
#!/usr/bin/python3
# /usr/libexec/acercontrol/acercontrol-set-boot-profile
"""Privileged wrapper: persist the boot profile (PRIV-01).

Writes /etc/default/acercontrol with key=value pairs that
Phase 6's acer-performance.service consumes via EnvironmentFile.

Allowlist matches acercontrol-setprofile (same source-of-truth).
"""
import os
import sys
import tempfile

BOOT_CONFIG_PATH = "/etc/default/acercontrol"

ALLOWED_KERNEL_VALUES = (
    "low-power",
    "quiet",
    "balanced",
    "balanced-performance",
    "performance",
)

EX_OK    = 0
EX_USAGE = 64
EX_OSERR = 71
EX_NOPERM = 77


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(
            f"usage: {os.path.basename(argv[0])} <kernel-value>\n"
        )
        return EX_USAGE
    value = argv[1]
    if value not in ALLOWED_KERNEL_VALUES:
        sys.stderr.write(
            f"refusing: {value!r} not in allowlist\n"
        )
        return EX_USAGE
    if os.geteuid() != 0:
        sys.stderr.write("refusing: must run as root\n")
        return EX_NOPERM

    # Atomic write — tempfile in /etc, rename over target
    try:
        d = os.path.dirname(BOOT_CONFIG_PATH)
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".acercontrol.", dir=d)
        try:
            os.write(fd, f"BOOT_PROFILE={value}\n".encode("utf-8"))
            os.close(fd)
            os.chmod(tmp, 0o644)
            os.rename(tmp, BOOT_CONFIG_PATH)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        sys.stderr.write(f"write failed: {exc}\n")
        return EX_OSERR
    return EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

---

### Pattern 5: `libexec/acercontrol-manage-service`

**What:** Privileged systemctl invocations for the boot service. Allowlist is `(action × service)` tuple.

```python
#!/usr/bin/python3
# /usr/libexec/acercontrol/acercontrol-manage-service
"""Privileged wrapper: manage acer-performance.service (PRIV-01).

Allowlist is (action, service) tuple. Service name is the LITERAL
'acer-performance.service' from CONTEXT.md Phase 2 lock. Phase 6
ships the actual unit file.

OPEN QUESTION carried forward: BOOT-01 in REQUIREMENTS.md says
the unit is TEMPLATED (acer-performance@.service). If Phase 6
ships the templated form, this wrapper's allowlist must extend
to (action, service-template-instance). See Open Questions section.
"""
import os
import subprocess
import sys

ALLOWED_ACTIONS  = ("enable", "disable", "start", "stop")
ALLOWED_SERVICES = ("acer-performance.service",)

EX_OK    = 0
EX_USAGE = 64
EX_OSERR = 71
EX_NOPERM = 77


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(
            f"usage: {os.path.basename(argv[0])} "
            f"<action> <service>\n"
            f"  action  ∈ {ALLOWED_ACTIONS}\n"
            f"  service ∈ {ALLOWED_SERVICES}\n"
        )
        return EX_USAGE

    action, service = argv[1], argv[2]
    if action not in ALLOWED_ACTIONS:
        sys.stderr.write(f"refusing: action {action!r} not allowed\n")
        return EX_USAGE
    if service not in ALLOWED_SERVICES:
        sys.stderr.write(f"refusing: service {service!r} not allowed\n")
        return EX_USAGE
    if os.geteuid() != 0:
        sys.stderr.write("refusing: must run as root\n")
        return EX_NOPERM

    # systemctl always present on Ubuntu 24.04 (PID 1 is systemd)
    try:
        result = subprocess.run(
            ["systemctl", action, service],
            capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"systemctl failed: {exc}\n")
        return EX_OSERR
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode if result.returncode in (0,) else EX_OSERR


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

---

### Pattern 6: `data/org.acercontrol.policy` polkit XML

**What:** Three named actions, each pinned to its wrapper binary via `org.freedesktop.policykit.exec.path`. Pinning means the polkit-shown dialog message comes from THIS file, not the generic `org.freedesktop.policykit.exec` fallback ("Authentication is needed to run /usr/bin/bash") [VERIFIED: pkexec(1) Noble].

**Verbatim DOCTYPE** from polkit(8) Ubuntu Noble — do NOT paraphrase:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC "-//freedesktop//DTD polkit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/software/polkit/policyconfig-1.dtd">

<policyconfig>

  <vendor>AcerControl</vendor>
  <vendor_url>https://github.com/acercontrol/acercontrol</vendor_url>

  <!-- Action 1: write platform_profile  (CLI-03 / GUI-06) -->
  <action id="org.acercontrol.setprofile">
    <description>Change the Acer performance profile</description>
    <message>Authentication is required to change the Acer performance profile</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-setprofile</annotate>
  </action>

  <!-- Action 2: write /etc/default/acercontrol  (BOOT-03) -->
  <action id="org.acercontrol.set-boot-profile">
    <description>Change the Acer boot-time performance profile</description>
    <message>Authentication is required to change the Acer boot-time profile</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-set-boot-profile</annotate>
  </action>

  <!-- Action 3: enable/disable/start/stop acer-performance.service  (BOOT-03) -->
  <action id="org.acercontrol.manage-service">
    <description>Manage the AcerControl boot service</description>
    <message>Authentication is required to manage the AcerControl boot service</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-manage-service</annotate>
  </action>

</policyconfig>
```

**Install location:** `/usr/share/polkit-1/actions/org.acercontrol.policy` (filename matches action namespace prefix) [VERIFIED: polkit(8) Noble — "Policy files install into /usr/share/polkit-1/actions"]. Mode `0644 root:root`.

**Why action `org.acercontrol.setprofile` and not generic `org.freedesktop.policykit.exec`:** pkexec checks if any policy declares `org.freedesktop.policykit.exec.path == <binary>` for the binary being invoked; if so, that named action is selected and its `<message>` is what the user sees [VERIFIED: pkexec(1) Noble — "To use another action, use the org.freedesktop.policykit.exec.path annotation on an action with the value set to the full path of the program"]. This is exactly what PRIV-03 requires.

**Implicit auth values used** [VERIFIED: polkit(8) Noble]:
- `auth_admin` — requires an administrative user to authenticate.
- `auth_admin_keep` — like `auth_admin`, but authorization persists for ~5 minutes. PRIV-04 verification ("second invocation within polkit's keep-alive window does not re-prompt") depends on this.
- Not used: `no`, `yes`, `auth_self`, `auth_self_keep`. The CONTEXT.md lock chose `auth_admin_keep` for `allow_active` because writing to `/sys/firmware/acpi/platform_profile` is fundamentally an admin action [CITED: ./CLAUDE.md L405-406].

---

### Pattern 7: `pyproject.toml` `[project.scripts]` addition

**What:** Wires the CLI entry point so `pip install -e .` (and the Phase 8 `.deb`) provide an `acercontrol` command. The bundled `dist/acercontrol` is a separate artifact — they're not in conflict.

```toml
# pyproject.toml — Phase 2 delta (existing file; APPEND this section)
[project.scripts]
acercontrol = "acercontrol.cli:main"
# acercontrol-gui = "acercontrol.gui:main"   # Phase 3 adds this
```

**Verification command** (post-edit):
```bash
grep -A 2 '\[project.scripts\]' pyproject.toml
```

---

### Pattern 8: JSON Schema (`--json` opt-in)

**What:** Locked JSON contract for `status` / `temps` / `get` / `list` / `set` / `install`. **Append-only** — future versions add keys, never remove. Phase 3 GUI imports `acercontrol.core` directly (same process); `--json` exists for scripting users AND for the Phase 2 smoke runner parsing test outputs on Linux.

All numeric fields are **nullable** — Phase 1 `SensorReading` already returns `None` for missing sysfs paths, so every numeric field's JSON type is `number | null`.

```json
// acercontrol get --json
{
  "profile":       "turbo",                 // string, user-facing; "custom" for unmapped
  "kernel_value":  "performance"            // string, raw sysfs value
}

// acercontrol get --raw --json
{ "kernel_value": "performance" }

// acercontrol list --json
{
  "profiles":  ["eco", "quiet", "balanced", "performance", "turbo"],
  "active":    "turbo"
}

// acercontrol temps --json
{
  "cpu_package_c": 55.0,                    // number | null
  "fan1_rpm":      6976,                    // integer | null
  "fan2_rpm":      7142,                    // integer | null
  "acer_temp1_c":  58.0,                    // number | null
  "acer_temp2_c":  53.0,                    // number | null
  "acer_temp3_c":  null                     // number | null
}

// acercontrol status --json
{
  "probe": {
    "checks": [
      {
        "name":     "acer_wmi module loaded",
        "present":  true,
        "detail":   "/sys/module/acer_wmi present",
        "fix":      "",
        "severity": "blocking"               // "blocking" | "warning" | "info"
      }
      // ... 6 more checks
    ],
    "ok": true,
    "first_blocking_failure": null,          // null OR { "name": "...", "fix": "..." }
    "blacklist_entries": []                  // list of { "file": "...", "line": "..." }
  },
  "profile": {                               // same shape as `get --json`
    "profile":      "turbo",
    "kernel_value": "performance"
  },
  "list": {                                  // same shape as `list --json`
    "profiles": ["eco", "quiet", "balanced", "performance", "turbo"],
    "active":   "turbo"
  },
  "temps": { /* same shape as `temps --json` */ }
}

// acercontrol set <profile> --json   (success)
{ "profile": "turbo", "kernel_value": "performance" }

// acercontrol set --dry-run --json
{
  "dry_run":      true,
  "profile":      "turbo",
  "kernel_value": "performance",
  "wrapper":      "/usr/libexec/acercontrol/acercontrol-setprofile",
  "elevation":    "pkexec",                  // "pkexec" | "sudo" | "none"
  "argv":         ["acercontrol-setprofile", "performance"]
}

// acercontrol set <profile> --json   (cancelled — PRIV-04)
{ "cancelled": true }

// acercontrol set <profile> --json   (mismatch)
{
  "error":     "mismatch",
  "requested": "performance",
  "actual":    "balanced"
}

// acercontrol install --json   (non-root)
{
  "is_root": false,
  "steps":   [
    { "step": 1, "what": "modprobe.d snippet", "cmd": "echo 'options ..." },
    // ...
  ],
  "advice":  "rerun as root to execute"
}
```

**Append-only invariant:** Phase 3+ MAY add fields to any payload. Phase 3+ MUST NOT remove or rename existing fields. Tests in `smoke_phase2.py` assert key presence, not key absence — adding new keys does not break smoke. This is the GUI/scripting contract.

---

### Pattern 9: `tools/bundle_cli.py` (stdlib concat → single-file)

**What:** Concatenates `acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` into `dist/acercontrol`, prefixed by `#!/usr/bin/env python3` + a `__main__` shim. Stdlib only.

```python
#!/usr/bin/env python3
# tools/bundle_cli.py
"""Bundle the stdlib-only AcerControl CLI into dist/acercontrol.

Approach: concatenate the relevant acercontrol/*.py files (after
stripping cross-imports between them) with a single __main__ shim
at the end. The bundled file is a stdlib-only Python script with
no package imports — works as `cp dist/acercontrol /usr/local/bin/`.

Why not zipapp / shiv / PyInstaller:
- zipapp works (stdlib), but produces a zip-prefixed file — debugging
  is harder, error tracebacks reference the zip member path.
- shiv / PyInstaller / Nuitka all add build-time deps; PROJECT.md
  forbids pip-only packages for the GUI but Phase 2 chooses to extend
  the zero-deps invariant to build-time too (one less moving piece).
- This concat approach is ~120 LOC and produces a debuggable file.

Inputs and outputs are GTK-free. verify_no_gtk.py guards this.
"""
from __future__ import annotations
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Order matters — definitions must precede uses.
BUNDLE_ORDER = [
    REPO / "acercontrol" / "profiles.py",
    REPO / "acercontrol" / "sysfs.py",
    REPO / "acercontrol" / "core.py",
    REPO / "acercontrol" / "features.py",
    REPO / "acercontrol" / "privilege.py",
    REPO / "acercontrol" / "cli.py",
]

OUTPUT = REPO / "dist" / "acercontrol"

HEADER = """#!/usr/bin/env python3
# AcerControl CLI — bundled single-file build.
# Generated by tools/bundle_cli.py. Do not edit this file directly.
# Source: https://github.com/acercontrol/acercontrol
"""

# Regex matches `from acercontrol[...] import X` and `import acercontrol[...]`
# at the start of a line. These imports are intra-bundle and must be stripped.
_INTRA_IMPORT = re.compile(
    r"^(from\s+acercontrol(\.\w+)?\s+import\s+.+|"
    r"import\s+acercontrol(\.\w+)?\s*(as\s+\w+)?)\s*$",
    re.MULTILINE,
)


def _strip_intra_imports(src: str) -> str:
    """Comment out imports that resolve inside the bundle.

    We comment rather than delete so line numbers in stack traces
    still map back to the source file.
    """
    return _INTRA_IMPORT.sub(lambda m: "# bundled: " + m.group(0), src)


def _check_no_gtk(src: str, source_path: Path) -> None:
    """Inline guard — refuses to bundle GTK imports (CLI-07).

    Pre-bundle. verify_no_gtk.py does a separate post-bundle check.
    """
    if re.search(r"^(import\s+gi|from\s+gi(\.|\s))", src, re.MULTILINE):
        raise SystemExit(
            f"refusing to bundle {source_path}: contains `import gi` "
            f"or `from gi` — CLI-07 violation"
        )


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out_lines: list[str] = [HEADER, ""]
    for src in BUNDLE_ORDER:
        if not src.exists():
            raise SystemExit(f"missing source: {src}")
        text = src.read_text(encoding="utf-8")
        _check_no_gtk(text, src)
        text = _strip_intra_imports(text)
        out_lines.append(f"# === BEGIN {src.name} ===")
        out_lines.append(text)
        out_lines.append(f"# === END {src.name} ===")
        out_lines.append("")

    # __main__ shim — main() is defined by cli.py at the bottom of the bundle.
    out_lines.append("if __name__ == '__main__':")
    out_lines.append("    import sys")
    out_lines.append("    sys.exit(main())")

    OUTPUT.write_text("\n".join(out_lines), encoding="utf-8")
    OUTPUT.chmod(0o755)
    print(f"wrote {OUTPUT}  ({OUTPUT.stat().st_size} bytes)")

    # Post-bundle verification — run verify_no_gtk.py on the OUTPUT.
    verifier = REPO / "tools" / "verify_no_gtk.py"
    rc = subprocess.run([sys.executable, str(verifier), str(OUTPUT)]).returncode
    if rc != 0:
        OUTPUT.unlink(missing_ok=True)
        raise SystemExit(f"verify_no_gtk.py failed on {OUTPUT}; bundle removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Stripping `from acercontrol... import` lines:** intra-bundle imports cannot resolve in the concatenated file (there's no `acercontrol/` package available). The regex commented-out form keeps line numbers stable for stack traces.

**Two-stage gtk-check:** Pre-bundle (`_check_no_gtk` on each input) AND post-bundle (`verify_no_gtk.py` on output) — belt-and-braces per advisor recommendation. A future drift (someone adds `import gi` to `core.py` for Phase 3 by accident) is caught by the pre-stage; an exotic bundling-side bug introducing `gi` is caught by the post-stage.

---

### Pattern 10: `tools/verify_no_gtk.py` (build gate)

**What:** Grep-based gate. Exits non-zero if any input file contains `^import gi` or `^from gi`. Used twice: by `bundle_cli.py` (post-bundle) and by Phase 2 smoke runner (pre-bundle on all bundle inputs).

```python
#!/usr/bin/env python3
# tools/verify_no_gtk.py
"""CLI-07 enforcement: refuse if any input contains `import gi` / `from gi`.

Used by bundle_cli.py (post-bundle on dist/acercontrol) and by
smoke_phase2.py (pre-bundle on each acercontrol/*.py going into the
bundle). Stdlib only.

Usage:
    python3 tools/verify_no_gtk.py <file> [<file>...]
Returns 0 on no matches, 1 on any match.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

# Anchor on start-of-line; allow leading whitespace? NO — `import gi`
# at any indent is also a violation. We use re.MULTILINE for ^ to mean
# 'start of line' but DO NOT require column-0 (to also catch indented
# imports inside functions / try blocks).
_GTK_IMPORT = re.compile(
    r"(^|\n)\s*(import\s+gi(\.|\s)|from\s+gi(\.|\s))"
)


def check(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line) hits in path."""
    text = path.read_text(encoding="utf-8", errors="replace")
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        # Skip comments — `# from gi import ...` is documentation, not code.
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        if re.match(r"^\s*(import\s+gi(\.|\s)|from\s+gi(\.|\s))", line):
            hits.append((i, line.rstrip()))
    return hits


def main(argv: list[str]) -> int:
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
```

**Why `re.match` and not `re.search`:** anchored to start-of-line means `# from gi import ...` documentation lines are skipped (no match), but `        from gi import Gtk` (indented inside a function) IS caught. Comment-only lines are also explicitly stripped.

**Coverage scope:** invoked by `bundle_cli.py` against `dist/acercontrol` AND by `smoke_phase2.py` against `acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` plus the three `libexec/*` wrappers. NOT invoked against `tools/bundle_cli.py` or `tools/verify_no_gtk.py` themselves (they're build tooling, not bundled).

---

### Pattern 11: `tools/smoke_phase2.py` aggregate runner

**What:** Same shape as `tools/smoke_phase1.py` — subprocess each check, never raises, exits non-zero on any FAIL. Each PRIV/CLI requirement has at least one smoke check.

```python
#!/usr/bin/env python3
"""Aggregate smoke runner for Phase 2 (acercontrol/cli.py + wrappers).

Exits 0 on all-pass. Designed to run on:
  - macOS dev box (every privileged path goes through --dry-run; reads
    degrade to None via Phase 1 contract)
  - generic Linux without acer_wmi (same as macOS, --dry-run works)
  - PHN16-72 with acer_wmi loaded + wrappers installed (full UAT)

Style copied from tools/smoke_phase1.py.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run(label: str, argv: list[str], *, expect_rc: int = 0,
        stdin: str | None = None, env_extra: dict | None = None,
        check_json_parses: bool = False) -> bool:
    """Run a subprocess, return True on PASS."""
    print(f"-> {label}")
    env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=15, env=env, input=stdin)
    except Exception as e:
        print(f"  FAIL  runner exception: {e}")
        return False
    if r.returncode != expect_rc:
        print(f"  FAIL  rc={r.returncode} (expected {expect_rc})")
        print(f"    stdout: {r.stdout.rstrip()}")
        print(f"    stderr: {r.stderr.rstrip()}")
        return False
    if check_json_parses:
        try:
            json.loads(r.stdout)
        except json.JSONDecodeError as e:
            print(f"  FAIL  JSON parse error: {e}")
            print(f"    stdout: {r.stdout!r}")
            return False
    print(f"  PASS")
    return True


# Smoke plan — one entry per PRIV/CLI requirement.
CLI = [sys.executable, "-m", "acercontrol.cli"]
SCENARIOS = [
    # CLI-01
    ("CLI-01 status text",  CLI + ["status"],
        {"expect_rc": None}),     # rc can be 0/1/2 depending on host probe
    ("CLI-01 status JSON",  CLI + ["status", "--json"],
        {"expect_rc": None, "check_json_parses": True}),

    # CLI-02
    ("CLI-02 get text",     CLI + ["get"], {}),
    ("CLI-02 get --raw",    CLI + ["get", "--raw"], {}),
    ("CLI-02 get --json",   CLI + ["get", "--json"], {"check_json_parses": True}),

    # CLI-03 — dry-run path covers macOS/CI
    ("CLI-03 set dry-run text", CLI + ["set", "turbo", "--dry-run"], {}),
    ("CLI-03 set dry-run JSON", CLI + ["set", "turbo", "--dry-run", "--json"],
        {"check_json_parses": True}),
    ("CLI-03 set bad profile",  CLI + ["set", "zzzz"], {"expect_rc": 2}),

    # CLI-04
    ("CLI-04 list text",    CLI + ["list"], {}),
    ("CLI-04 list JSON",    CLI + ["list", "--json"], {"check_json_parses": True}),

    # CLI-05
    ("CLI-05 temps text",   CLI + ["temps"], {}),
    ("CLI-05 temps JSON",   CLI + ["temps", "--json"], {"check_json_parses": True}),

    # CLI-06 — non-root invocation must exit 0
    ("CLI-06 install non-root", CLI + ["install"], {"expect_rc": 0}),
    ("CLI-06 install dry-run JSON", CLI + ["install", "--dry-run", "--json"],
        {"check_json_parses": True}),

    # PRIV-05 — SSH_CONNECTION forces sudo (verifiable in dry-run)
    ("PRIV-05 SSH_CONNECTION → sudo",
        CLI + ["set", "turbo", "--dry-run", "--json"],
        {"env_extra": {"SSH_CONNECTION": "1.2.3.4 22 5.6.7.8 22"},
         "check_json_parses": True}),

    # CLI-07 — verify_no_gtk on all bundle inputs
    ("CLI-07 verify_no_gtk inputs",
        [sys.executable, str(Path(PROJECT_ROOT) / "tools" / "verify_no_gtk.py"),
         *[str(Path(PROJECT_ROOT) / "acercontrol" / f)
           for f in ("profiles.py", "sysfs.py", "core.py",
                     "features.py", "privilege.py", "cli.py")]],
        {}),

    # CLI-07 — bundle + verify the output
    ("CLI-07 bundle_cli produces dist/acercontrol",
        [sys.executable,
         str(Path(PROJECT_ROOT) / "tools" / "bundle_cli.py")], {}),
    ("CLI-07 bundled file is executable and runs --help",
        [str(Path(PROJECT_ROOT) / "dist" / "acercontrol"), "--help"], {}),
    ("CLI-07 verify_no_gtk against dist/acercontrol",
        [sys.executable,
         str(Path(PROJECT_ROOT) / "tools" / "verify_no_gtk.py"),
         str(Path(PROJECT_ROOT) / "dist" / "acercontrol")], {}),

    # PRIV-02 / PRIV-03 — polkit policy XML is well-formed
    ("PRIV-02 polkit policy XML well-formed",
        [sys.executable, "-c",
         f"import xml.etree.ElementTree as ET; "
         f"ET.parse({str(Path(PROJECT_ROOT) / 'data' / 'org.acercontrol.policy')!r}); "
         f"print('XML ok')"], {}),

    # PRIV-02 — exactly three actions with correct IDs
    ("PRIV-02 policy declares exactly three actions",
        [sys.executable, "-c", _three_actions_check_src()], {}),

    # Wrapper allowlist (defense-in-depth)
    ("acercontrol-setprofile rejects bad value",
        [sys.executable, str(Path(PROJECT_ROOT) / "libexec" /
                             "acercontrol-setprofile"), "garbage"],
        {"expect_rc": 64}),
    ("acercontrol-setprofile rejects no argv",
        [sys.executable, str(Path(PROJECT_ROOT) / "libexec" /
                             "acercontrol-setprofile")],
        {"expect_rc": 64}),
]
```

The `_three_actions_check_src()` helper parses the `.policy` file and asserts the three expected action IDs are present and each has the `exec.path` annotation pointing at the right wrapper. (Planner finalizes the exact source string.)

**Smoke runner contract (matches Phase 1 style):**
- Subprocess each scenario; capture stdout/stderr/rc.
- Never raises; runner-side exceptions are caught and reported as FAIL.
- macOS/CI: every privileged path uses `--dry-run`; every read path degrades gracefully via Phase 1 contract (returns `None`). Expected rc varies — `status` may return 2 (no `/sys`), so `expect_rc: None` means "any rc OK as long as stdout is parseable / format matches".
- Linux UAT: same smoke + the manual PRIV-04 keep-alive check.

---

### Anti-Patterns to Avoid

- **`pkexec bash -c '…'`** — anti-pattern called out by CONTEXT.md (PRIV-01). Uses the generic `org.freedesktop.policykit.exec` action; dialog reads "Authentication is needed to run /usr/bin/bash"; introduces shell-quoting / env-scrub TOCTOU bugs. Use a named wrapper binary with an `exec.path` pinned action.
- **`from acercontrol.profiles import PROFILES` inside a wrapper** — fails under real `pkexec` because `PYTHONPATH` is scrubbed. See P2-NEW-01.
- **`sudo NOPASSWD` for the sysfs path** — security regression; bypasses polkit UX. Out of scope for v1.
- **`os.execvp(["pkexec", wrapper, ...])` from the CLI** — replaces the CLI process; the read-back verify step in CLI-03 never runs. Use `subprocess.run`.
- **Single-line argparse `--json-or-plain` ternary in handlers** — duplicates output logic six times. Use the `_emit()` helper (Pattern 2).
- **Catching `Exception` in wrappers** — masks bugs that should surface as a non-zero exit + stderr. Catch `OSError` for I/O, let everything else propagate.
- **`Gtk.StatusIcon` / `gir1.2-appindicator3-0.1`** — tray belongs in Phase 7; not relevant to Phase 2, but the verify_no_gtk gate keeps `gi` out of the CLI permanently.
- **Long-lived elevated daemon** — explicit Out of Scope in PROJECT.md. polkit invocations only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Manual `sys.argv` indexing | `argparse` (stdlib) | Subparser dispatch, type coercion, `--help` autogen [CITED: ./CLAUDE.md L457-461] |
| Privilege escalation | Setuid binary / persistent root daemon | `pkexec` + polkit `.policy` | Auth dialog UX, audit trail, no stored credentials [CITED: ./CLAUDE.md L403-410] |
| Exit-code dialog dismiss tracking | Polling auth daemon over D-Bus | `pkexec` exit 126 | One-line `subprocess.run` rc check [VERIFIED: pkexec(1) Noble] |
| JSON output | Manual `f'{{"k": "{v}"}}'` | `json.dumps(...)` (stdlib) | Quoting / escaping / Unicode handled correctly |
| Wrapper allowlist | Regex of arbitrary characters | Hardcoded `tuple` literal + `in` check | One-line, no ReDoS surface, identical to source-of-truth |
| Path existence check | `try open(); except OSError` | `pathlib.Path.exists()` + Phase 1 `_read_or_none` | Phase 1 established the pattern; consistent contract |
| SSH detection | Probing `/dev/tty` + `os.isatty` | `os.environ.get("SSH_CONNECTION")` | Documented behavior in sshd(8); set for both interactive and non-interactive sessions |
| Bundling | PyInstaller / Nuitka / shiv | stdlib `tools/bundle_cli.py` concat | Zero deps; debuggable output; CLAUDE.md decision #8 [CITED: ./CLAUDE.md L446-447] |

**Key insight:** Phase 2 is in the "every primitive already exists in the stdlib + polkit" territory. The whole job is sticking these primitives together correctly. The interesting engineering is in the **trust boundary discipline** (Pattern 3) and the **JSON schema lock** (Pattern 8) — not in any algorithm.

## Runtime State Inventory

Not applicable to Phase 2 — this is greenfield code (new modules, new wrappers, new policy file). No renames, no migrations, no datastore changes. The "stored data" question is `/etc/default/acercontrol` (created by Pattern 4 wrapper), but it's new with this phase — there's no pre-existing file to migrate.

## Common Pitfalls

References to **P1** (real-binary wrapper) and **P14** (SSH detection / cancel handling) come from `.planning/ROADMAP.md` Phase 2 entry. The "P2-NEW-NN" pitfalls below were surfaced during this research and the advisor pass.

### Pitfall P1: Generic `org.freedesktop.policykit.exec` action / `pkexec bash -c`

**What goes wrong:** Polkit dialog reads "Authentication is needed to run /usr/bin/bash" (or whatever the invoked binary is). User has no idea what they're authorizing. Action ID is `org.freedesktop.policykit.exec`, not a named action — the `.policy` message is the generic fallback.

**Why it happens:** `pkexec /bin/bash -c 'echo X > /sys/...'` invokes `/bin/bash`. pkexec looks up `org.freedesktop.policykit.exec.path == /bin/bash` — no policy declares that — falls back to generic action.

**How to avoid:** A real binary at a stable path (`/usr/libexec/acercontrol/acercontrol-setprofile`). `.policy` declares `org.freedesktop.policykit.exec.path == /usr/libexec/acercontrol/acercontrol-setprofile`. pkexec picks the named action; dialog shows our `<message>`.

**Warning signs:** PRIV-03 verification fails — auth dialog says "/usr/bin/bash" or "/usr/libexec/.../acercontrol-setprofile" generic. Cause is either policy not installed, policy filename wrong, or path mismatch between policy and actual binary location.

### Pitfall P14: SSH detection precedence and `pkexec` hang

**What goes wrong:** Over SSH (no graphical agent), `pkexec` hangs forever waiting for a `polkit-agent-helper-1` that doesn't exist. The user sees the CLI hang with no output.

**Why it happens:** `pkexec` registers a polkit authentication agent; over SSH the session has no graphical environment for that agent to render a dialog.

**How to avoid:** Detect SSH at the CLI layer. PRIV-05 specifies `$SSH_CONNECTION` — set by `sshd` for both interactive and non-interactive sessions [CITED: sshd(8) ENVIRONMENT section]. Use `os.environ.get("SSH_CONNECTION")` precedence; fall back to `sudo` (which works in a tty). `SSH_TTY` is a weaker signal — only set when a pseudo-tty is allocated, so `ssh host "acercontrol set turbo"` (no tty) wouldn't trigger on `SSH_TTY` alone.

**Cancel-handling sub-case:** Pressing Escape on the polkit dialog yields `pkexec` exit code 126 [VERIFIED: pkexec(1) Noble]. PRIV-04 requires this be idempotent — "Authentication cancelled" message and exit 0, never a traceback. Pattern 1's `PrivilegedResult.cancelled` flag drives this.

**No spin-retry:** If `pkexec` exits 126, do NOT auto-retry. User dismissed for a reason. CLI exits cleanly; if they want to try again they re-run.

**Warning signs:** PRIV-05 verification fails — `acercontrol set turbo` over SSH hangs instead of escalating via sudo. Confirms `pkexec` was picked despite `$SSH_CONNECTION` being set.

### Pitfall P2-NEW-01: `pkexec` env scrub breaks `from acercontrol.profiles import PROFILES` in wrappers

**What goes wrong:** Wrapper imports `from acercontrol.profiles import PROFILES`. Under `pkexec`, the import raises `ModuleNotFoundError`. Wrapper exits 1, never writes sysfs.

**Why it happens:** pkexec(1) [VERIFIED: Ubuntu Noble] explicitly scrubs the environment: "set to a minimal known and safe environment in order to avoid injecting code through LD_LIBRARY_PATH or similar mechanisms". `PYTHONPATH` is gone. `sys.path` defaults to system locations (`/usr/lib/python3/dist-packages`, `/usr/local/lib/python3/dist-packages`, etc). Until the Phase 8 `.deb` installs `acercontrol` to `dist-packages`, the package is not on `sys.path`. **In dev mode (`pip install -e .` from the repo) the import works because `-e` adds the repo to a `.pth` file in user site-packages — but that path is also not visible after pkexec env scrub.**

**How to avoid:** Hardcode the allowlist as a literal `tuple` in each wrapper. Comment points at `acercontrol/profiles.py` as the source of truth. The Phase 2 smoke runner asserts the wrapper's literal `ALLOWED_KERNEL_VALUES == tuple(PROFILES.values())` so drift is caught at build time, not run time. See Pattern 3.

**Warning signs:** Wrapper works during `python3 libexec/acercontrol-setprofile turbo` from the repo, but fails under `pkexec /usr/libexec/.../acercontrol-setprofile turbo` with a `ModuleNotFoundError`. Cause is `PYTHONPATH` env scrub; fix is to remove the package import.

### Pitfall P2-NEW-02: argparse usage-error exit code vs. CLI semantic exit codes

**What goes wrong:** Tests/scripts expect `acercontrol set` (no arg) to exit 64 (EX_USAGE), but argparse exits 2.

**Why it happens:** `argparse.ArgumentParser.error()` exits with code 2 by default [VERIFIED: Python docs]. The CLI-level invariant (planner-locked): we accept argparse defaults (0 success, 2 argparse error) and do not override. The 64 (EX_USAGE) exit code lives on the **wrapper** layer, not the CLI.

**How to avoid:** Document the per-layer exit code story:

| Layer | Exit Codes |
|-------|-----------|
| CLI | 0 OK, 1 runtime failure (write/elevation/mismatch), 2 usage error (argparse), 0 also for auth-cancelled (PRIV-04) |
| Wrapper | 0 OK, 64 EX_USAGE, 71 EX_OSERR, 77 EX_NOPERM |
| pkexec | passes through wrapper exit on success; 126 on cancel; 127 on auth not granted |

Smoke tests `expect_rc=2` for `acercontrol set` (no arg) and `expect_rc=64` for direct wrapper invocation with bad argv.

**Warning signs:** Smoke test for `acercontrol set zzz` fails because we expected 64 but argparse returned 2 (or vice versa). Fix: align expectation with the layer being tested.

### Pitfall P2-NEW-03: BOOT-01 templated unit name vs. CONTEXT.md literal

**What goes wrong:** Phase 2 wrapper allowlist is `("acer-performance.service",)`. Phase 6 ships `acer-performance@.service` (templated). Phase 6 GUI cannot enable any instance via the Phase 2 wrapper.

**Why it happens:** BOOT-01 in `.planning/REQUIREMENTS.md` (line 54) specifies a templated unit: `A templated systemd unit acer-performance@.service ships with Type=oneshot...`. CONTEXT.md `<decisions>` and `<specifics>` blocks (line 123) explicitly say "the literal `acer-performance.service`". CONTEXT.md is the spec-lock for Phase 2; the discrepancy lives between phases.

**How to avoid:** Phase 2 follows CONTEXT.md — wrapper allowlist is the literal name. **Open Question OQ-01 below** is filed for Phase 6 to either (a) ship a non-templated unit alongside the templated one, or (b) re-litigate the Phase 2 wrapper allowlist to include `("acer-performance.service", "acer-performance@eco.service", "acer-performance@quiet.service", ...)` against the 5 user-facing names.

**Warning signs:** Phase 6 GUI tries to invoke `manage-service start acer-performance@turbo.service` and gets EX_USAGE.

### Pitfall P2-NEW-04: `pkexec` argv1 annotation seductive but wrong for this design

**What goes wrong:** A reviewer asks "why not declare 5 actions per kernel value, each pinned to setprofile + `exec.argv1`, so polkit itself enforces the allowlist and the wrapper has nothing to check?"

**Why it happens:** `pkexec` supports `org.freedesktop.policykit.exec.argv1` [VERIFIED: pkexec(1) Noble] — "If the org.freedesktop.policykit.exec.argv1 annotation is present, the action will only be picked if the first argument to the program matches the value of the annotation." Tempting design.

**How to avoid:** Don't take the bait. Cost: 5 (profile values) × 3 (action types) = 15 polkit actions, plus a separate `<message>` per kernel value (bad UX — user prompt would read "Authentication is required to change profile to balanced-performance"; PRIV-03 wants ONE message for all profile changes). Adding a new profile in v2 (`PROFILES["super-eco"] = "super-low-power"`) would require a policy edit + reinstall + daemon-reload. CONTEXT.md locks 3 actions; defense-in-depth lives in the wrapper. **Defense-in-depth is also more robust** — if a future polkit bug makes argv1 matching unreliable, the wrapper still rejects bad argv.

### Pitfall P2-NEW-05: `auth_admin_keep` second-invocation cannot be smoke-tested

**What goes wrong:** Researcher / planner writes a smoke test that "asserts no prompt on second invocation within 5 minutes". The test cannot work — the prompt is interactive and there is no exit-code distinction between "prompted then auth'd" and "cached and auth'd".

**Why it happens:** `auth_admin_keep` cache lives inside the polkit daemon. From a calling subprocess we see only the exit code. Success-exit-code is 0 either way.

**How to avoid:** Mark as manual UAT only — see Validation Architecture row PRIV-04-UAT. Manual UAT instruction: "On PHN16-72, run `acercontrol set turbo`, complete the auth dialog. Within 60 seconds, run `acercontrol set balanced`. Observed: no second auth dialog appears (the keep-alive worked)."

**Warning signs:** Phase 2 smoke runner includes `expect_no_prompt_within_keep_alive` check that always reports PASS regardless of reality. That's the smell — there's no observable signal to assert on.

### Pitfall P2-NEW-06: `verify_no_gtk` scope ambiguity

**What goes wrong:** Bundler runs `verify_no_gtk` only on the output `dist/acercontrol`. Phase 3 lands `gi` imports in `core.py` (by accident — copy-paste from a GUI file). Bundler concats `core.py` into `dist/acercontrol`. Verifier on output catches it. So far so good — but the developer's local `pip install -e . && acercontrol set turbo` doesn't go through the bundle, so the misplaced import goes unnoticed until the bundler-then-deploy step.

**How to avoid:** Run verify_no_gtk against **both** inputs AND output:
- Pre-bundle (inputs): `verify_no_gtk acercontrol/{profiles,sysfs,core,features,privilege,cli}.py libexec/*` — must pass before `pip install -e .` or `bundle_cli.py` runs.
- Post-bundle (output): `verify_no_gtk dist/acercontrol` — run automatically by `bundle_cli.py`.

Smoke runner exercises both.

**Warning signs:** A regression that adds `import gi` to a non-bundled CLI module path slips past Phase 3 verification because the bundler isn't run in dev.

## Code Examples

Most code lives in Patterns 1–11 above. The remaining "external" example worth quoting is the exact `pyproject.toml [project.scripts]` delta:

```toml
# After Phase 2 modifications to pyproject.toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "acercontrol"
version = "0.1.0.dev0"
description = "Acer Predator/Nitro performance control for Linux"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "GPL-3.0-or-later" }
authors = [
    { name = "AcerControl contributors" },
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: System :: Hardware",
]

# Zero runtime dependencies. Stdlib only.

[project.scripts]
acercontrol = "acercontrol.cli:main"
# acercontrol-gui = "acercontrol.gui:main"  # Phase 3 enables

[tool.setuptools]
packages = ["acercontrol"]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `gksudo` / `kdesudo` graphical sudo | `pkexec` + polkit `.policy` | polkit 0.105+ (~2014); legacy tools deprecated/removed | Standard Linux desktop privilege escalation; works on GNOME, KDE, Sway |
| `setup.py` build script | `pyproject.toml` PEP 621 | setuptools deprecation cycle 2021+ | Build is declarative; better tooling support [CITED: ./CLAUDE.md L443-449] |
| `Gtk.StatusIcon` (X11 tray) | Ayatana AppIndicator (Phase 7) | GTK4 removal | Not Phase 2 concern; CLI is GTK-free [CITED: ./CLAUDE.md L399-401] |
| `optparse` | `argparse` | Python 2.7+ | Modern stdlib parser; subparser dispatch is idiomatic |

**Deprecated/outdated (do NOT use):**
- `pkexec bash -c '…'` — wrong action ID; see Pitfall P1.
- `gksudo` / `kdesudo` — removed in modern distros.
- `setup.py` — only as a shim now; primary metadata is `pyproject.toml`.
- `notify-send` shelled via subprocess — Phase 4+ concern; Phase 2 CLI has no notification surface.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | CLI, wrappers | (verify on target) | ≥3.11 | None — hard floor, set in pyproject |
| `pkexec` | privilege.py, polkit policy install | Ubuntu 24.04 ships `policykit-1` by default | 124+ on Noble | Auto-fallback to `sudo` |
| `sudo` | privilege.py SSH path & pkexec fallback | Ubuntu 24.04 default | 1.9+ | None — if absent + pkexec absent, `set` cannot work; surfaced via "no elevation method available" |
| polkit daemon | actual auth dialog rendering | Ubuntu 24.04 default | 124+ | None — without daemon, pkexec fails with rc=127 |
| `systemctl` | `acercontrol-manage-service` wrapper, also Phase 1 `_ppd_active` | Ubuntu 24.04 PID-1 | (systemd version varies) | None — if absent, wrapper exits EX_OSERR |
| `/usr/libexec/acercontrol/` dir | wrappers installation path | Created by Phase 8 `.deb` | n/a | `/usr/local/libexec/acercontrol/` (`install.sh`); `ACERCONTROL_DEV=<repo>` for dev |
| `/usr/share/polkit-1/actions/` | polkit policy install location | Standard polkit install (provided by `policykit-1`) | n/a | If absent: pkexec falls back to generic action; PRIV-03 fails |

**Missing dependencies with no fallback:** None — Phase 2's external surface is the standard Ubuntu 24.04 baseline (`policykit-1` + `systemd` are both default-installed).

**Missing dependencies with fallback:**
- `pkexec` absent → `sudo` fallback (works in tty).
- `systemctl` absent → `manage-service` wrapper returns EX_OSERR; CLI surfaces error cleanly.

**Development environment note:** Same as Phase 1 — macOS dev box runs everything via `--dry-run`. Linux without `acer_wmi` runs the same way (reads return `None`, dry-run prints what it would do). Actual UAT requires PHN16-72.

## Validation Architecture

> Required by `workflow.nyquist_validation: true` in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None — PROJECT.md `Out of Scope` excludes automated test suite for v1; smoke commands via `python3 -c` and `subprocess.run` |
| Config file | none — see Wave 0 |
| Quick run command | `python3 tools/smoke_phase2.py` |
| Full suite command | `python3 tools/smoke_phase2.py` (Phase 2 has no separate full suite) |
| Estimated runtime | ~5 seconds on macOS dev; ~10 seconds on PHN16-72 (real elevation paths skipped via dry-run by default) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRIV-01 | All privileged writes via real-binary wrappers | unit (file existence) | `test -x libexec/acercontrol-setprofile && test -x libexec/acercontrol-set-boot-profile && test -x libexec/acercontrol-manage-service && echo OK` | ❌ Wave 0 |
| PRIV-01 | Wrapper actually performs sysfs write | hardware smoke | `python3 tools/smoke_phase2.py PRIV-01-write` (PHN16-72 only — invokes wrapper as root, checks `/sys/firmware/acpi/platform_profile` after) | ❌ Wave 0 |
| PRIV-02 | `org.acercontrol.policy` is well-formed XML, declares exactly 3 expected action IDs, each with `exec.path` annotation | unit | `python3 -c "import xml.etree.ElementTree as ET; t = ET.parse('data/org.acercontrol.policy'); ids = sorted(a.get('id') for a in t.findall('action')); assert ids == ['org.acercontrol.manage-service', 'org.acercontrol.set-boot-profile', 'org.acercontrol.setprofile'], ids; print('PRIV-02 ok')"` | ❌ Wave 0 |
| PRIV-02 | `<defaults>` uses `auth_admin_keep` for `<allow_active>` on all 3 actions | unit | `python3 tools/smoke_phase2.py PRIV-02-defaults` | ❌ Wave 0 |
| PRIV-03 | Auth dialog shows configured message, not generic fallback | manual UAT on PHN16-72 | (visual) Run `acercontrol set turbo`; observe dialog title text | ❌ manual |
| PRIV-04 | `pkexec` exit 126 → CLI exits 0 with "Authentication cancelled" | manual UAT | (interactive) Run `acercontrol set turbo`, press Escape on auth dialog. Expected: prints "Authentication cancelled", `echo $?` shows 0 | ❌ manual |
| PRIV-04-UAT | `auth_admin_keep` keep-alive — second invocation within window doesn't re-prompt | manual UAT (cannot be smoke-tested, see Pitfall P2-NEW-05) | (interactive) Run `acercontrol set turbo`, complete auth. Within 60 s run `acercontrol set balanced`. Expected: no second auth dialog. | ❌ manual |
| PRIV-05 | `$SSH_CONNECTION` set → `sudo` chosen, not `pkexec` | unit (via dry-run) | `SSH_CONNECTION='1.2.3.4 22 5.6.7.8 22' python3 -m acercontrol.cli set turbo --dry-run --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['elevation']=='sudo', d; print('PRIV-05 ok')"` | ❌ Wave 0 |
| CLI-01 | `acercontrol status` runs, exits 0/1/2 cleanly, output contains feature probe + profile + list + temps sections | unit | `python3 -m acercontrol.cli status > /dev/null; echo $?` (rc 0/1/2 acceptable on host without `/sys`) AND `python3 -m acercontrol.cli status --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'probe' in d and 'profile' in d and 'list' in d and 'temps' in d; print('CLI-01 ok')"` | ❌ Wave 0 |
| CLI-02 | `acercontrol get` prints user-name; `--raw` prints kernel value | unit | `python3 -m acercontrol.cli get --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'profile' in d and 'kernel_value' in d; print('CLI-02 ok')"` | ❌ Wave 0 |
| CLI-03 | `acercontrol set <profile>` dry-run validates and prints; bad profile returns 2 | unit | `python3 -m acercontrol.cli set turbo --dry-run --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['dry_run'] and d['kernel_value']=='performance'; print('CLI-03 ok')"` AND `python3 -m acercontrol.cli set zzzz; test $? -eq 2` | ❌ Wave 0 |
| CLI-03 | Real set + read-back + mismatch → exit 1 | hardware UAT (PHN16-72) | `acercontrol set turbo && acercontrol get; sudo systemctl unmask --now power-profiles-daemon; acercontrol set turbo; echo $?` (expect 1 on the second attempt due to PPD overriding) | ❌ manual |
| CLI-04 | `acercontrol list` prints profiles, marks active | unit | `python3 -m acercontrol.cli list --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'profiles' in d and 'active' in d; print('CLI-04 ok')"` | ❌ Wave 0 |
| CLI-05 | `acercontrol temps` prints CPU package + fan1/2 + acer temps | unit | `python3 -m acercontrol.cli temps --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert set(d.keys()) >= {'cpu_package_c','fan1_rpm','fan2_rpm','acer_temp1_c','acer_temp2_c','acer_temp3_c'}; print('CLI-05 ok')"` | ❌ Wave 0 |
| CLI-06 | `acercontrol install` non-root: prints + exits 0 | unit | `python3 -m acercontrol.cli install; test $? -eq 0` (non-root assumed in CI / macOS) | ❌ Wave 0 |
| CLI-06 | `acercontrol install` root: executes (deferred to PHN16-72 UAT) | manual UAT | `sudo python3 -m acercontrol.cli install` on PHN16-72; expect modprobe.d snippet written, systemctl enable issued | ❌ manual |
| CLI-07 | Zero non-stdlib runtime deps; bundled file imports only stdlib | unit | `python3 tools/verify_no_gtk.py acercontrol/profiles.py acercontrol/sysfs.py acercontrol/core.py acercontrol/features.py acercontrol/privilege.py acercontrol/cli.py libexec/acercontrol-setprofile libexec/acercontrol-set-boot-profile libexec/acercontrol-manage-service` AND `python3 tools/bundle_cli.py && python3 tools/verify_no_gtk.py dist/acercontrol && dist/acercontrol --help > /dev/null` | ❌ Wave 0 |
| CLI-07 (injected import) | Deliberately injected `import gi` fails the bundler | unit | Add `import gi` to a copy of `acercontrol/core.py`, run `bundle_cli.py`, expect exit 1; remove the injection | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 tools/smoke_phase2.py` (subset relevant to that task's requirements)
- **Per wave merge:** Full `python3 tools/smoke_phase2.py`
- **Phase gate:** Full smoke green on macOS dev box + PHN16-72; manual UAT items checked off before `/gsd-verify-work`

**macOS / CI smoke contract:** Every smoke must exit 0 on macOS / CI **under default conditions**:
- `status` / `temps` / `get` / `list` / `list --json` etc. degrade through Phase 1 contract — `read_profile()` returns `Profile.CUSTOM`, `read_sensors()` returns all-`None`. Exit codes can vary (status returns 0/1/2 depending on degradation level), so smoke scenarios use `expect_rc: None` (any) where appropriate.
- `set` and `install` use `--dry-run` to skip elevation. Exit 0 on valid input, 2 on argparse error / invalid profile.
- Wrapper smokes (direct invocation) accept `expect_rc=64` for argv allowlist tests — this works on macOS because the wrapper exits before any sysfs write attempt.

**No `if sys.platform != "linux": skip` branches** — the design is that the same smoke runs on macOS dev, generic Linux, and PHN16-72 with no platform conditionals.

### Wave 0 Gaps

These files must be created in Wave 0 of the Phase 2 plan before the per-task smokes can run:

- [ ] `tools/smoke_phase2.py` — aggregate runner (Pattern 11)
- [ ] `tools/verify_no_gtk.py` — build gate (Pattern 10)
- [ ] `tools/bundle_cli.py` — bundler (Pattern 9)
- [ ] `acercontrol/privilege.py` — elevation helper (Pattern 1)
- [ ] `acercontrol/cli.py` — main CLI (Pattern 2)
- [ ] `libexec/acercontrol-setprofile` — wrapper 1 (Pattern 3)
- [ ] `libexec/acercontrol-set-boot-profile` — wrapper 2 (Pattern 4)
- [ ] `libexec/acercontrol-manage-service` — wrapper 3 (Pattern 5)
- [ ] `data/org.acercontrol.policy` — polkit policy (Pattern 6)
- [ ] `pyproject.toml` — add `[project.scripts]` (Pattern 7)

No test framework install — same stdlib-only approach as Phase 1.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes (high) | polkit + pkexec; `auth_admin_keep` is the chosen primitive [CITED: polkit(8) Noble]. No password storage. No tokens. |
| V3 Session Management | Yes (low) | polkit's `auth_admin_keep` cache lives inside the polkit daemon, not in our process. ~5 minute lifetime. We don't manage it. |
| V4 Access Control | Yes (high) | Wrapper allowlist + polkit action ID. Two trust boundaries (CLI → polkit → wrapper, wrapper argv re-validation). |
| V5 Input Validation | Yes (critical) | Both CLI (user-name allowlist) and wrapper (kernel-value allowlist) validate before any side effect. Wrapper validation is independent — defense-in-depth. |
| V6 Cryptography | No | No crypto used. No secrets stored. |
| V7 Error Handling and Logging | Minor | Wrapper writes failures to stderr; CLI translates to user message. No structured logging in Phase 2 (Diagnostics export is Phase 3+ scope). |
| V12 Files and Resources | Yes | All file paths are constants: `/sys/firmware/acpi/platform_profile`, `/etc/default/acercontrol`, `/usr/share/polkit-1/actions/org.acercontrol.policy`, `/usr/libexec/acercontrol/*`. No user-controlled paths. |

### STRIDE Threat Patterns

Trust boundaries this phase introduces:

1. **Boundary A** (CLI → polkit): user argv crosses into the polkit daemon. polkit selects an action and shows a dialog. The CLI is **untrusted** from polkit's perspective.
2. **Boundary B** (polkit → wrapper): pkexec invokes the wrapper as uid 0 after auth. The wrapper receives `argv[1:]` (CLI input, polkit-relayed). The wrapper is the **last line of defense** before sysfs.

| # | Threat (STRIDE) | Boundary | Standard Mitigation |
|---|-----------------|----------|---------------------|
| T-02-01 | Spoofing — another local app invokes `pkexec acercontrol-setprofile` directly | B | Wrapper re-validates argv against literal allowlist (Pattern 3); polkit auth still required (auth_admin); the attacker cannot escalate without admin credential. |
| T-02-02 | Tampering — argv injection (`acercontrol set "$(rm -rf /)"`) | A → B | argparse parses positional; shell metachars are not expanded (no `shell=True` anywhere). Wrapper allowlist rejects anything not in the literal tuple. |
| T-02-03 | Tampering — env injection (`LD_PRELOAD`, `PYTHONPATH`, `LANG`) | A → B | pkexec scrubs env to a minimal known-safe set [VERIFIED: pkexec(1) Noble]. Wrappers do not consume env vars. |
| T-02-04 | Repudiation — user denies running `set turbo` | A | polkit logs every action invocation to the systemd journal with action ID + invoking uid. Audit trail exists; nothing for AcerControl to do beyond not adding its own logging that conflicts. |
| T-02-05 | Information disclosure — wrapper stderr leaks `/etc/default/acercontrol` contents | B | Wrapper does not read user-content files. The only file read is the polkit policy (in pre-deployment). |
| T-02-06 | Denial of service — flood polkit daemon with `acercontrol set turbo` calls | A | Out of scope for v1 — polkit has its own rate limits; CLI doesn't expose a remote endpoint. |
| T-02-07 | Elevation of privilege — wrapper exits 0 without writing | B | Wrapper performs the write inside the same try; failure exits EX_OSERR. CLI does read-back verification (CLI-03) — mismatch surfaces. |
| T-02-08 | Elevation of privilege — bug in wrapper allows arbitrary sysfs write | B | Wrapper opens only the hardcoded `PROFILE_PATH` constant; the value comes from allowlist; no string interpolation into file paths. |
| T-02-09 | Spoofing — fake `pkexec` binary on `$PATH` ahead of the real one | A | `subprocess.run(["pkexec", ...])` resolves via PATH. In a user environment the user's PATH is what they control — out of scope for v1 (matches PROJECT.md "polished personal tool" quality bar). |
| T-02-10 | Tampering — argv1 annotation NOT used; whole argv goes through wrapper | A → B | The wrapper IS the validator. The polkit action allows ANY argv to setprofile (within `exec.path` constraint); the wrapper rejects bad argv. This is the intentional design (see P2-NEW-04). |
| T-02-11 | Information disclosure — `acercontrol status --json` exposes hardware details | A (none — read-only) | Status output is the same info `cat /sys/...` would show — no new disclosure surface. |
| T-02-12 | Tampering — adversary modifies `/usr/libexec/acercontrol/acercontrol-setprofile` to write arbitrary sysfs | B | Local-root-attack scenario; out of scope (an attacker with root already has the capability without our binary). File ships in `.deb` with `0755 root:root`. |

**Bottom line:** Phase 2's security model is the canonical polkit pattern, plus a defense-in-depth wrapper allowlist. The novel concern is **P2-NEW-01** (env-scrub forces hardcoded allowlist) which is a footgun, not a vulnerability — and is fully mitigated by the Pattern 3 design.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | pkexec under Ubuntu 24.04 with the GNOME session has a working polkit agent (`polkit-gnome-authentication-agent-1`) | Pattern 1 | If absent: `pkexec` blocks indefinitely waiting for an agent. Mitigated by SSH detection (PRIV-05) and the 30s timeout in `run_privileged`. **Low risk on the target environment.** |
| A2 | `/usr/lib/python3/dist-packages/` is on the default pkexec-environment-PATH `sys.path` for `/usr/bin/python3` | Pattern 3 | Even if this is true today, Pattern 3's hardcoded literal makes the wrapper independent of the assumption. **No risk** — design is robust either way. |
| A3 | The Phase 8 `.deb` will declare `Depends: python3` so wrapper shebang `#!/usr/bin/python3` resolves | Pattern 3 | Confirmed in the Phase 1 RESEARCH (Ubuntu 24.04 system Python is 3.12 by default). Phase 8 declaration is downstream. **Low risk.** |
| A4 | `subprocess.run(..., timeout=30)` on the `pkexec` call is long enough for a human to enter their password | Pattern 1 | 30s is ample for a single password entry. If user is slow, timeout fires and CLI surfaces "Operation timed out". User retries. **Low risk.** |
| A5 | The polkit `<message>` element accepts plain ASCII text without escaping | Pattern 6 | The DTD allows raw text per polkit spec; we keep our messages ASCII-only. **No risk.** |
| A6 | `sshd(8)` sets `$SSH_CONNECTION` for both interactive (`ssh user@host`) and non-interactive (`ssh user@host "command"`) sessions | Pattern 1 / Pitfall P14 | Confirmed via WebSearch (multiple SSH guides + sshd(8) excerpts cite the same behavior). If wrong, we'd miss non-interactive cases — but PRIV-05's purpose is to prevent the `pkexec` hang, which manifests in BOTH cases. **Low risk.** |
| A7 | `setuptools >= 61` is on the build path on Ubuntu 24.04 (for `[project.scripts]` PEP 621 support) | Pattern 7 | Ubuntu 24.04 ships setuptools 68.x in `python3-setuptools`. **No risk.** |
| A8 | `argparse.ArgumentParser.add_subparsers(required=True)` is supported on Python 3.11+ | Pattern 2 | Added in Python 3.7. **No risk.** |
| A9 | The Phase 6 boot service name remains `acer-performance.service` (not the templated `acer-performance@.service` that BOOT-01 suggests) | Pattern 5 | If Phase 6 chooses the templated form, the `manage-service` wrapper's allowlist needs to extend. Filed as **Open Question OQ-01**. **Medium risk** — discrepancy is real, lives between phases. |
| A10 | The bundler concat approach produces a Python file whose stack traces are useful for debugging | Pattern 9 | Stack traces reference the bundled file with line numbers; we keep intra-imports as commented-out lines to preserve line numbering. Manual UAT during Phase 2 includes "intentionally raise from cli.py, observe the traceback in `dist/acercontrol`". **Low risk.** |
| A11 | `data/org.acercontrol.policy` is XML, not XSD-validated against the freedesktop DTD by the policykit-1 install scripts at install time | Pattern 6 | Tested in PRIV-02 smoke as `xml.etree.ElementTree.parse()` — that's well-formedness, not DTD validity. `lintian` (Phase 8) may flag DTD issues. If the DTD URL is unreachable at the user's machine, polkit still parses the file. **Low risk.** |
| A12 | `acercontrol install` non-root print-then-exit-0 composes with `sudo bash` | Pattern 2 | The output IS valid bash. If a Phase 8 reviewer wants a JSON-pipeable variant, `--json` already provides it. **Low risk.** |

**Confirmation needed from user / PHN16-72 maintainer:** A9 — does Phase 6 want templated `acer-performance@.service` (per BOOT-01) or literal `acer-performance.service` (per Phase 2 CONTEXT.md)? See OQ-01 below.

## Open Questions

These should be flagged for the planner; some are resolvable in planning, some belong to later phases.

### OQ-01: `acer-performance.service` literal vs. `acer-performance@.service` templated

**Phase 2 effect:** wrapper allowlist (Pattern 5) is `("acer-performance.service",)`.

**Phase 6 ambiguity:** BOOT-01 in `.planning/REQUIREMENTS.md` line 54 specifies a **templated** unit (`acer-performance@.service`). BOOT-03 says "writes `/etc/default/acercontrol` and re-runs `systemctl start acer-performance@<profile>` via pkexec".

**What this means:** Phase 6 will need to do `manage-service start acer-performance@turbo.service` (or similar). The Phase 2 wrapper allowlist as locked in CONTEXT.md will reject that.

**Options for resolution (filed for Phase 6 planning, not Phase 2):**
- (a) Phase 6 ships BOTH a non-templated `acer-performance.service` (for `enable`/`disable`) AND a templated `acer-performance@.service` (for `start <instance>`); Phase 2 wrapper allowlist accepts the literal form only; Phase 6 either edits the wrapper allowlist or routes its `start` calls differently.
- (b) Phase 6 ships only the non-templated form; the boot profile lives in `/etc/default/acercontrol` (which Pattern 4 already writes), and the service reads it via `EnvironmentFile=`. No template instances needed.
- (c) Phase 2 expands the allowlist now to `("acer-performance.service", "acer-performance@eco.service", "acer-performance@quiet.service", "acer-performance@balanced.service", "acer-performance@performance.service", "acer-performance@turbo.service")` — preemptive but contradicts the CONTEXT.md lock.

**Recommendation:** Adopt **(b)** in Phase 6. The Pattern 4 wrapper already writes `/etc/default/acercontrol`; a `Type=oneshot` unit that reads `BOOT_PROFILE` from that env file and writes the value to `platform_profile` is simpler than 5 template instances.

### OQ-02: Should the wrapper validate argv1 against `PROFILES.values()` order-strictly or set-strictly?

**Status:** Cosmetic. Pattern 3 uses set membership (`if value not in ALLOWED_KERNEL_VALUES`). Order doesn't matter for correctness.

**Resolution:** Set membership. Planner doesn't need to revisit.

### OQ-03: Should `dist/acercontrol` be committed to git or only built on demand?

**Status:** Convention call.

**Recommendation:** **`.gitignore` `dist/`**. The bundled file is a build artifact; it's regenerated by `tools/bundle_cli.py` from the source modules. Phase 8 `.deb` packaging will produce the production artifact via `dpkg-buildpackage` — not from a pre-committed `dist/acercontrol`. Add a `Makefile` target `make bundle` or a `tools/build.sh` for convenience.

### OQ-04: Should the install steps inside `acercontrol install` include the polkit policy file?

**Status:** Implementation detail of Pattern 2 `cmd_install`.

**Recommendation:** Yes — non-root `acercontrol install` should print "cp data/org.acercontrol.policy /usr/share/polkit-1/actions/" (or equivalent). The `.deb` (Phase 8) installs the file automatically via `debian/<package>.install`. `install.sh` (Phase 8) writes it manually. `acercontrol install` (Phase 2) is the manual-instructions surface — it should mention the policy step.

## Sources

### Primary (HIGH confidence)
- **pkexec(1)** — Ubuntu Noble manpage. EXIT STATUS (126, 127), environment sanitization, `org.freedesktop.policykit.exec.path` annotation, action selection rules. [https://manpages.ubuntu.com/manpages/noble/en/man1/pkexec.1.html]
- **polkit(8)** — Ubuntu Noble manpage. `.policy` DOCTYPE/DTD, `<defaults>` values (`auth_admin`, `auth_admin_keep`, etc.), install location `/usr/share/polkit-1/actions/`, action ID character set. [https://manpages.ubuntu.com/manpages/noble/en/man8/polkit.8.html]
- **Python argparse documentation** — subparsers, `set_defaults(func=...)`, `parser.error()` exit code 2, `required=True`. [https://docs.python.org/3/library/argparse.html]
- **sysexits.h(3head)** — Ubuntu Noble. EX_USAGE=64, EX_OSERR=71, EX_NOPERM=77 constants. [https://manpages.ubuntu.com/manpages/noble/en/man3/sysexits.h.3head.html]
- **CLAUDE.md project instructions** — Stack decisions #3 (polkit + auth_admin_keep + named-binary), #10 (argparse for CLI), #8 (pyproject.toml [project.scripts] + stdlib bundler), the "What NOT to Use" consolidated table, the polkit `.policy` skeleton (verbatim structural template).
- **`.planning/phases/01-foundation/01-RESEARCH.md`** — Phase 1 patterns inherited unchanged: `_read_or_none`, `FeatureReport`, `kernel_to_profile()`, `read_profile()`, `read_sensors()`. Security Domain section (lines 1161-1186) is the template style for this phase's Security Domain section.
- **`.planning/phases/01-foundation/01-VERIFICATION.md`** — Carry-forward: `kernel_to_profile()` is the canonical path, not `KERNEL_TO_UI.get()`; `__init__` is the canonical import surface; PPD check name varies by `systemctl` availability.
- **`.planning/phases/01-foundation/01-VALIDATION.md`** — Style template for Phase 2 VALIDATION sampling rate + manual UAT pattern.

### Secondary (MEDIUM confidence)
- **SSH ENVIRONMENT variables** — WebSearch corroborated `SSH_CONNECTION` is set for both interactive and non-interactive SSH sessions; `SSH_TTY` only when a pty is allocated. Multiple consistent sources but not a single canonical man page fetch. [Cross-verified across O'Reilly SSH guide, sshd(8) excerpts, and OpenSSH wikibooks.]
- **`gnu/sysexits.h` header constants meaning** — `sysexits(3)` Linux convention. Standard across BSDs and Linux for ~30 years; widely understood "best-practice CLI exit code" reference.

### Tertiary (LOW confidence)
- None. Every Phase 2 claim is either primary-source verified or inherited from a Phase 1 HIGH-confidence finding.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every Phase 2 module uses stdlib; no third-party additions; bundler decision is locked in CLAUDE.md.
- Architecture (3 wrappers + polkit policy + CLI + bundler): HIGH — patterns are textbook polkit + stdlib argparse; the novel design is the wrapper-hardcoded-allowlist (Pattern 3) which is a direct response to a verified env-scrub behavior.
- Pitfalls: HIGH — 2 carried from ROADMAP (P1, P14) + 6 surfaced by primary-source research and advisor review (P2-NEW-01..06), each with concrete avoidance pattern.
- Validation Architecture: HIGH — every PRIV/CLI requirement has at least one automated smoke command runnable on macOS (via `--dry-run`) and one manual UAT for the interactive paths (PRIV-04, CLI-03 hardware read-back).
- Security Domain: HIGH — STRIDE table covers all trust-boundary crossings; mitigations are concrete; out-of-scope items are explicit.
- JSON schema (append-only): HIGH — schema is locked; future phases extend.

**Research date:** 2026-05-15
**Valid until:** 2026-06-14 (30 days; primary-source pkexec/polkit/argparse behavior is stable across Ubuntu LTS releases).

---

## Files-to-Create List (for the planner)

The planner generates tasks creating exactly these files in dependency order. All paths absolute. All content sketched in Patterns 1–11 above.

| # | Absolute Path | Purpose | LOC est. | Depends on |
|---|---------------|---------|----------|------------|
| 1 | `/Users/sushilkumarsahani/Desktop/AcerControl/tools/verify_no_gtk.py` | CI gate: refuses if any input contains `^(import gi|from gi)` (Pattern 10) | ~55 | — |
| 2 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/privilege.py` | Elevation helper + exit-code translation (Pattern 1) | ~125 | Phase 1 acercontrol package |
| 3 | `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-setprofile` | Privileged sysfs writer (Pattern 3) | ~55 | — (stdlib only) |
| 4 | `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-set-boot-profile` | Privileged `/etc/default/acercontrol` writer (Pattern 4) | ~70 | — |
| 5 | `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-manage-service` | Privileged systemctl wrapper (Pattern 5) | ~75 | — |
| 6 | `/Users/sushilkumarsahani/Desktop/AcerControl/data/org.acercontrol.policy` | polkit policy XML (Pattern 6) | ~50 | #3, #4, #5 (paths referenced inside) |
| 7 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/cli.py` | Argparse CLI entry (Pattern 2) | ~280 | Phase 1 acercontrol, #2 |
| 8 | `/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml` (MODIFIED) | Add `[project.scripts]` (Pattern 7) | +3 lines | #7 |
| 9 | `/Users/sushilkumarsahani/Desktop/AcerControl/tools/bundle_cli.py` | Stdlib-concat bundler → dist/acercontrol (Pattern 9) | ~125 | #1, #7 |
| 10 | `/Users/sushilkumarsahani/Desktop/AcerControl/tools/smoke_phase2.py` | Aggregate smoke runner (Pattern 11) | ~200 | All of the above |
| 11 | `/Users/sushilkumarsahani/Desktop/AcerControl/.gitignore` (MODIFIED) | Add `dist/` | +1 line | #9 |

**Total: ~1,035 LOC across 9 new files + 2 modifications.** A planner can split into 3 waves:
- Wave 1 (build tools + privilege helper, no GTK dependencies): `verify_no_gtk.py`, `privilege.py`, the three wrappers, `org.acercontrol.policy`.
- Wave 2 (CLI surface): `cli.py`, `pyproject.toml` edit.
- Wave 3 (bundler + smoke): `bundle_cli.py`, `smoke_phase2.py`, `.gitignore` edit.

Waves can run in sequence on a single agent; if parallelization is desired, Waves 1 and 3 share no files (and Wave 3 depends on Wave 1's tools). Wave 2 depends on Wave 1.

## Smoke Test Section (for the planner's `<acceptance_criteria>`)

After all files exist, the planner should embed this in the final task's acceptance criteria:

```bash
# Phase 2 end-of-phase gate — runs on macOS dev AND Linux UAT

# 1. Bundle is GTK-free (CLI-07)
cd /Users/sushilkumarsahani/Desktop/AcerControl
python3 tools/verify_no_gtk.py \
    acercontrol/profiles.py acercontrol/sysfs.py acercontrol/core.py \
    acercontrol/features.py acercontrol/privilege.py acercontrol/cli.py \
    libexec/acercontrol-setprofile libexec/acercontrol-set-boot-profile \
    libexec/acercontrol-manage-service
test $? -eq 0

# 2. Build the bundle
python3 tools/bundle_cli.py
test -x dist/acercontrol
python3 tools/verify_no_gtk.py dist/acercontrol
test $? -eq 0

# 3. Bundle is invokable
dist/acercontrol --help > /dev/null
test $? -eq 0

# 4. Aggregate smoke
python3 tools/smoke_phase2.py
test $? -eq 0
# Expected: every CLI/PRIV unit-smoke PASS; rc 0
```

This is what `/gsd-verify-work` consumes as the structural evidence for Phase 2 sign-off; the manual UAT checklist (PRIV-03, PRIV-04 interactive, PRIV-04-UAT keep-alive, CLI-03 read-back mismatch under live PPD) runs separately on PHN16-72 hardware.

---

*Research complete: 2026-05-15. Confidence HIGH. Ready for `/gsd-plan-phase 2`.*
