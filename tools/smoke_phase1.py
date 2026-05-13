#!/usr/bin/env python3
"""Aggregate smoke runner for Phase 1 (acercontrol/) — CORE-01..06.

Exits 0 on all-pass. Exits non-zero if any CORE-NN check raises a
Python traceback or fails its assertion. Designed to run on:
  - PHN16-72 with acer_wmi loaded (full pass)
  - generic Linux without acer_wmi (CORE-02/03/06 return None but no traceback)
  - macOS dev box / CI without /sys (every sysfs read returns None; no traceback)

Usage:
    python3 tools/smoke_phase1.py
    PYTHONPATH=. python3 tools/smoke_phase1.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Ensure imports resolve regardless of how the runner is invoked.
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# Per-check payloads — kept as Python source strings (NOT f-strings)
# so they pass through subprocess unchanged. Each payload prints a
# success marker on its own.
CORE_01_PAYLOAD = (
    "from acercontrol.profiles import Profile, PROFILES, KERNEL_TO_UI, kernel_to_profile\n"
    "assert all(KERNEL_TO_UI[v] == k for k, v in PROFILES.items()), 'reverse map drift'\n"
    "assert set(PROFILES.values()) == {p.value for p in Profile if p is not Profile.CUSTOM}, 'enum mismatch'\n"
    "assert kernel_to_profile('custom') is Profile.CUSTOM\n"
    "assert kernel_to_profile('garbage') is Profile.CUSTOM\n"
    "assert kernel_to_profile(None) is Profile.CUSTOM\n"
    "print('CORE-01 ok')\n"
)

CORE_02_PAYLOAD = (
    "from acercontrol.sysfs import find_hwmon\n"
    "result = find_hwmon('acer', requires=('fan1_input','temp1_input'))\n"
    "assert result is None or result.startswith('/sys/class/hwmon/hwmon'), result\n"
    "print(f'CORE-02 ok ({result})')\n"
)

CORE_03_PAYLOAD = (
    "from acercontrol.features import probe, FeatureReport\n"
    "r = probe()\n"
    "assert isinstance(r, FeatureReport)\n"
    "assert hasattr(r, 'checks') and len(r.checks) >= 6, f'expected >=6 checks, got {len(r.checks)}'\n"
    "assert isinstance(r.ok, bool)\n"
    "print(f'CORE-03 ok ({len(r.checks)} checks, ok={r.ok})')\n"
)

CORE_04_PAYLOAD = (
    "from acercontrol.profiles import Profile, kernel_to_profile\n"
    "assert kernel_to_profile('custom') is Profile.CUSTOM\n"
    "assert kernel_to_profile('zzz-undefined') is Profile.CUSTOM\n"
    "assert kernel_to_profile(None) is Profile.CUSTOM\n"
    "assert kernel_to_profile('performance') is Profile.TURBO\n"
    "assert kernel_to_profile('balanced-performance') is Profile.PERFORMANCE\n"
    "assert Profile.CUSTOM.display == 'Custom'\n"
    "print('CORE-04 ok')\n"
)

# CORE-05 payload is parameterized by the tempdir; built at runtime below.
def core_05_payload(glob_pattern: str, conf_basename: str) -> str:
    # NOTE: keep this string literal-safe — glob_pattern is a controlled tempdir path.
    return (
        "from acercontrol.features import find_blacklist_entries\n"
        f"hits = find_blacklist_entries({glob_pattern!r})\n"
        "assert len(hits) == 1, hits\n"
        f"assert hits[0][0].endswith({conf_basename!r})\n"
        "assert hits[0][1] == 'blacklist acer_wmi'\n"
        "print('CORE-05 ok')\n"
    )

CORE_06_PAYLOAD = (
    "from acercontrol.sysfs import coretemp_max_package_temp\n"
    "t = coretemp_max_package_temp()\n"
    "assert t is None or (0 < t < 120), t\n"
    "print(f'CORE-06 ok ({t})')\n"
)


def run_check(label: str, description: str, payload: str) -> bool:
    """Run a single CORE-NN smoke command in a subprocess.

    Returns True on PASS (returncode == 0), False on FAIL. Never raises:
    any internal exception is caught and reported as a structured FAIL.
    """
    print(f"-> {label}: {description}")
    try:
        env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}
        result = subprocess.run(
            [sys.executable, "-c", payload],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except Exception as exc:  # noqa: BLE001 — runner must never raise
        print(f"  FAIL  runner exception: {type(exc).__name__}: {exc}")
        return False

    if result.returncode == 0:
        out = result.stdout.strip()
        print(f"  PASS  {out}")
        return True

    print(f"  FAIL  rc={result.returncode}")
    if result.stdout:
        print(f"    stdout: {result.stdout.rstrip()}")
    if result.stderr:
        print(f"    stderr: {result.stderr.rstrip()}")
    return False


def main() -> int:
    failures: list[str] = []
    checks_run = 0
    tmpdir: str | None = None

    # CORE-05 needs a tempdir scaffold so we don't depend on /etc/modprobe.d
    # contents on the dev host. Built once, removed in finally.
    try:
        try:
            tmpdir = tempfile.mkdtemp(prefix="acerctrl-smoke-")
            conf_path = os.path.join(tmpdir, "99-test.conf")
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write("blacklist acer_wmi\n")
            core_05 = core_05_payload(os.path.join(tmpdir, "*.conf"), "99-test.conf")
        except Exception as exc:  # noqa: BLE001
            # Scaffold failure is itself a FAIL for CORE-05; don't abort other checks.
            print(f"-> CORE-05 scaffold FAIL: {type(exc).__name__}: {exc}")
            core_05 = None

        plan: list[tuple[str, str, str | None]] = [
            ("CORE-01", "profile mapping is bidirectional + Profile.CUSTOM sentinel", CORE_01_PAYLOAD),
            ("CORE-02", "find_hwmon resolves by name file (path or None)", CORE_02_PAYLOAD),
            ("CORE-03", "probe() returns FeatureReport with >=6 checks; never raises", CORE_03_PAYLOAD),
            ("CORE-04", "unknown / kernel 'custom' values map to Profile.CUSTOM", CORE_04_PAYLOAD),
            ("CORE-05", "acer_wmi blacklist entries detected in modprobe.d", core_05),
            ("CORE-06", "coretemp multi-package: max-across-packages or None", CORE_06_PAYLOAD),
        ]

        for label, description, payload in plan:
            checks_run += 1
            if payload is None:
                # Scaffold for this check failed earlier; record as FAIL.
                print(f"-> {label}: {description}")
                print("  FAIL  scaffold missing — see CORE-05 scaffold FAIL above")
                failures.append(label)
                continue
            if not run_check(label, description, payload):
                failures.append(label)
    except Exception as exc:  # noqa: BLE001 — outer guard so runner never raises
        print(f"FATAL: runner top-level exception: {type(exc).__name__}: {exc}")
        # Treat any unaccounted checks as failures.
        for label in ("CORE-01", "CORE-02", "CORE-03", "CORE-04", "CORE-05", "CORE-06"):
            if label not in failures:
                failures.append(label)
    finally:
        if tmpdir and os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir, ignore_errors=True)

    passed = max(0, checks_run - len(failures))
    total = 6
    print(f"--- Phase 1 smoke: {passed}/{total} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
