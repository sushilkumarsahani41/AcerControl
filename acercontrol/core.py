# acercontrol/core.py
"""User-facing facade: path constants, high-level reads.

This module composes acercontrol.sysfs (raw reads) and acercontrol.profiles
(name mapping) into typed convenience functions. CLI (Phase 2) and GUI
(Phase 3) should import from here for stable APIs.

Pure stdlib. No `gi` imports.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from acercontrol import sysfs as _sysfs
from acercontrol.profiles import (
    Profile,
    PROFILES,
    KERNEL_TO_UI,
    kernel_to_profile,
    current_profile_ui as _current_profile_ui,
    available_profiles as _available_profiles,
)


# ── Sysfs paths (kernel surface) ──────────────────────────────────────────
PROFILE_PATH         = Path("/sys/firmware/acpi/platform_profile")
PROFILE_CHOICES_PATH = Path("/sys/firmware/acpi/platform_profile_choices")
HWMON_BASE           = Path("/sys/class/hwmon")
PREDATOR_V4_PARAM    = Path("/sys/module/acer_wmi/parameters/predator_v4")
MODPROBE_D           = Path("/etc/modprobe.d")


# ── High-level reads (re-exports + composition) ────────────────────────────

def read_profile() -> Profile:
    """Read /sys/firmware/acpi/platform_profile and return a Profile.

    Returns Profile.CUSTOM for missing sysfs path, unreadable file, or any
    unmapped kernel value. Never raises.
    """
    return _current_profile_ui(PROFILE_PATH)


def list_available_profiles() -> list[Profile]:
    """Profiles whose kernel value appears in platform_profile_choices."""
    return _available_profiles(PROFILE_CHOICES_PATH)


@dataclass(frozen=True)
class SensorReading:
    """One snapshot of all sensors. Each field is Optional — None = unavailable."""
    cpu_package_c: Optional[float]
    fan1_rpm:      Optional[int]
    fan2_rpm:      Optional[int]
    acer_temp1_c:  Optional[float]
    acer_temp2_c:  Optional[float]
    acer_temp3_c:  Optional[float]


def read_sensors() -> SensorReading:
    """Read CPU package temp + acer hwmon temps and fan RPMs.

    Never raises. Missing/unreadable values surface as None.
    """
    cpu_c = _sysfs.coretemp_max_package_temp()
    acer_hwmon = _sysfs.find_hwmon("acer", requires=("fan1_input", "temp1_input"))
    acer = _sysfs.read_acer_sensors(acer_hwmon)

    # If a read failed, retry once after invalidating the hwmon cache.
    if acer_hwmon and acer.get("fan1_rpm") is None and acer.get("temp1_c") is None:
        _sysfs.invalidate_hwmon_cache()
        acer_hwmon = _sysfs.find_hwmon("acer", requires=("fan1_input", "temp1_input"))
        acer = _sysfs.read_acer_sensors(acer_hwmon)

    return SensorReading(
        cpu_package_c=cpu_c,
        fan1_rpm=acer["fan1_rpm"],       # type: ignore[assignment]
        fan2_rpm=acer["fan2_rpm"],       # type: ignore[assignment]
        acer_temp1_c=acer["temp1_c"],    # type: ignore[assignment]
        acer_temp2_c=acer["temp2_c"],    # type: ignore[assignment]
        acer_temp3_c=acer["temp3_c"],    # type: ignore[assignment]
    )


# Re-export for downstream convenience
__all__ = [
    "PROFILE_PATH", "PROFILE_CHOICES_PATH", "HWMON_BASE",
    "PREDATOR_V4_PARAM", "MODPROBE_D",
    "Profile", "PROFILES", "KERNEL_TO_UI", "kernel_to_profile",
    "read_profile", "list_available_profiles",
    "SensorReading", "read_sensors",
]
