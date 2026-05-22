# acercontrol/systemd.py
"""Systemd and boot-profile helpers for AcerControl.

This module is deliberately GTK-free and defensive so callers can import it on
non-systemd hosts, during tests, and before the package is installed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from acercontrol.profiles import PROFILES, Profile, kernel_to_profile


BOOT_CONFIG_PATH = Path("/etc/default/acercontrol")
BOOT_SERVICE = "acer-performance.service"
BOOT_TEMPLATE_PREFIX = "acer-performance@"
BOOT_WAIT_TIMEOUT = 5


def _clean_config_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'} and value[-1:] == value[0]:
        value = value[1:-1]
    return value.strip()


def read_boot_profile(path: Path = BOOT_CONFIG_PATH) -> Profile:
    """Return the configured boot profile, defaulting safely to Balanced."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return Profile.BALANCED

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != "BOOT_PROFILE":
            continue
        profile = kernel_to_profile(_clean_config_value(value))
        if profile is Profile.CUSTOM:
            return Profile.BALANCED
        return profile
    return Profile.BALANCED


def boot_instance_for_profile(profile_name: str) -> str:
    """Return the safe templated unit instance for a user-facing profile name."""
    if profile_name not in PROFILES:
        raise ValueError(f"unknown profile: {profile_name!r}")
    return f"{BOOT_TEMPLATE_PREFIX}{PROFILES[profile_name]}.service"


def _run_systemctl(args: list[str], timeout: int = BOOT_WAIT_TIMEOUT) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["systemctl", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


def service_enabled(service: str = BOOT_SERVICE) -> str:
    """Return enabled, disabled, not-found, or unknown for a unit."""
    result = _run_systemctl(["is-enabled", service])
    if result is None:
        return "unknown"

    stdout = result.stdout.strip()
    first = stdout.splitlines()[0].strip() if stdout else ""
    if first in {"enabled", "disabled"}:
        return first

    combined = f"{result.stdout}\n{result.stderr}".lower()
    if first == "not-found" or "not-found" in combined:
        return "not-found"
    if "could not be found" in combined or "does not exist" in combined:
        return "not-found"
    return "unknown"


def service_active(service: str = BOOT_SERVICE) -> str:
    """Return systemctl is-active output, or unknown when it cannot be read."""
    result = _run_systemctl(["is-active", service])
    if result is None:
        return "unknown"

    stdout = result.stdout.strip()
    if stdout:
        return stdout.splitlines()[0].strip()
    return "unknown"


def wait_for_boot_service(timeout: int = BOOT_WAIT_TIMEOUT) -> bool:
    """Wait briefly for the boot unit to settle. Never raises."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--wait", BOOT_SERVICE],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


__all__ = [
    "BOOT_CONFIG_PATH",
    "BOOT_SERVICE",
    "BOOT_TEMPLATE_PREFIX",
    "BOOT_WAIT_TIMEOUT",
    "boot_instance_for_profile",
    "read_boot_profile",
    "service_active",
    "service_enabled",
    "wait_for_boot_service",
]
