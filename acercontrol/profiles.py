# acercontrol/profiles.py
"""Canonical user-name ↔ kernel-value profile mapping for acer_wmi predator_v4.

Single source of truth for CORE-01. Re-exported from acercontrol/__init__.py.
"""
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Optional


# CLAUDE.md profile mapping — verbatim. Do not edit without updating tests.
PROFILES: dict[str, str] = {
    "eco":         "low-power",
    "quiet":       "quiet",
    "balanced":    "balanced",
    "performance": "balanced-performance",
    "turbo":       "performance",
}
"""user-facing name -> kernel platform_profile value."""

KERNEL_TO_UI: dict[str, str] = {v: k for k, v in PROFILES.items()}
"""Reverse map. Used by current_profile_ui()."""


class Profile(Enum):
    """A profile the library can report.

    Member `.value` is the kernel platform_profile string.
    Member `.display` (via property) is the user-facing name.
    `Profile.CUSTOM` is the sentinel for the kernel 'custom' value or any
    unmapped sysfs reading — callers should treat it as a valid display
    state, not as 'profile unknown'.

    Per kernel Documentation/ABI/testing/sysfs-platform_profile:
        "This file may also emit the string 'custom' to indicate that
         multiple platform profiles drivers are in use but have different
         values. This string can not be written to this interface and is
         solely for informational purposes."
    """
    ECO         = "low-power"
    QUIET       = "quiet"
    BALANCED    = "balanced"
    PERFORMANCE = "balanced-performance"
    TURBO       = "performance"
    CUSTOM      = "custom"  # sentinel — also matches any unmapped value

    @property
    def display(self) -> str:
        """User-facing label. 'Custom' for the sentinel."""
        if self is Profile.CUSTOM:
            return "Custom"
        return KERNEL_TO_UI[self.value]


def kernel_to_profile(raw: Optional[str]) -> Profile:
    """Map a raw kernel platform_profile value to a Profile.

    Returns Profile.CUSTOM for None, for 'custom', or for any value not
    in PROFILES.values(). Never raises.
    """
    if raw is None:
        return Profile.CUSTOM
    raw = raw.strip()
    try:
        return Profile(raw)
    except ValueError:
        return Profile.CUSTOM


def current_profile_ui(profile_path: Path) -> Profile:
    """Read profile_path and return a Profile. Never raises FileNotFoundError.

    Args:
        profile_path: Usually core.PROFILE_PATH (/sys/firmware/acpi/platform_profile).
    """
    try:
        raw = profile_path.read_text().strip()
    except OSError:
        return Profile.CUSTOM
    return kernel_to_profile(raw)


def available_profiles(choices_path: Path) -> list[Profile]:
    """Return Profiles whose kernel value appears in platform_profile_choices.

    Used by the planner-stage check that PROFILES.values() ⊆ choices.
    Returns the empty list if choices_path is unreadable (treated as 'unknown').
    """
    try:
        raw = choices_path.read_text().split()
    except OSError:
        return []
    return [Profile(v) for v in raw if v in {p.value for p in Profile}]
