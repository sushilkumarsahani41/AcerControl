# acercontrol/__init__.py
"""AcerControl — Linux platform_profile control for Acer Predator/Nitro.

Phase 1 public API: read-only library for profile mapping, sysfs reads,
hwmon discovery, and structured feature probing.

Imports of this package must remain GTK-free — the Phase 2 bundler
concatenates these modules into a single-file CLI.
"""
from __future__ import annotations

__version__ = "0.1.0.dev0"

from acercontrol.profiles import (
    Profile,
    PROFILES,
    KERNEL_TO_UI,
    kernel_to_profile,
    current_profile_ui,
    available_profiles,
)
from acercontrol.sysfs import (
    find_hwmon,
    find_all_hwmon,
    invalidate_hwmon_cache,
    coretemp_max_package_temp,
    read_acer_sensors,
)
from acercontrol.features import (
    FeatureCheck,
    FeatureReport,
    probe,
    find_blacklist_entries,
)
from acercontrol.core import (
    PROFILE_PATH,
    PROFILE_CHOICES_PATH,
    HWMON_BASE,
    PREDATOR_V4_PARAM,
    MODPROBE_D,
    SensorReading,
    read_profile,
    list_available_profiles,
    read_sensors,
)

__all__ = [
    "__version__",
    # profiles
    "Profile", "PROFILES", "KERNEL_TO_UI",
    "kernel_to_profile", "current_profile_ui", "available_profiles",
    # sysfs
    "find_hwmon", "find_all_hwmon", "invalidate_hwmon_cache",
    "coretemp_max_package_temp", "read_acer_sensors",
    # features
    "FeatureCheck", "FeatureReport", "probe", "find_blacklist_entries",
    # core
    "PROFILE_PATH", "PROFILE_CHOICES_PATH", "HWMON_BASE",
    "PREDATOR_V4_PARAM", "MODPROBE_D",
    "SensorReading", "read_profile", "list_available_profiles", "read_sensors",
]
