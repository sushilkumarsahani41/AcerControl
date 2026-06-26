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
    "acercontrol-setfan",
    "acercontrol-set-boot-profile",
    "acercontrol-manage-service",
    "acercontrol-disable-ppd",       # Phase 3 — PPD mask/unmask
    "acercontrol-reload-acer-wmi",   # Phase 3 — acer_wmi module reload
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
    cancelled: bool          # True iff pkexec exit was 126 (auth dismissed; PRIV-04)
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
      126 = polkit auth dialog cancelled (pkexec specific; cancelled=True; PRIV-04)
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
        # -- separates sudo options from wrapper path. We do want sudo
        # to prompt for password if needed (PRIV-05 SSH path).
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

    # PRIV-04: pkexec exit 126 = auth dialog dismissed → cancelled=True.
    # No spin-retry — caller (cmd_set) returns 0 cleanly (idempotent).
    return PrivilegedResult(
        returncode=result.returncode,
        elevation=method,
        argv=tuple(full_argv),
        cancelled=(method == "pkexec" and result.returncode == 126),
        stdout=result.stdout,
        stderr=result.stderr,
    )
