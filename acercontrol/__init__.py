"""AcerControl — Linux platform_profile control for Acer Predator/Nitro.

Phase 1 public API: read-only library for profile mapping, sysfs reads,
hwmon discovery, and structured feature probing.

Imports of this package must remain GTK-free — the Phase 2 bundler
concatenates these modules into a single-file CLI.
"""
from __future__ import annotations

__version__ = "0.1.0.dev0"

# Re-exports added in Task 3 (after profiles.py, sysfs.py, core.py, features.py exist)
