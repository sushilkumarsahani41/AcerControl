# acercontrol/sysfs.py
"""Read-only sysfs path discovery and raw reads (CORE-02).

Pure stdlib. No `gi` imports — must be safe for the Phase 2 bundler.
Single-threaded contract: Phase 1 callers are synchronous; Phase 5's
GLib.timeout_add_seconds runs on the main loop, also single-threaded.
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Optional


HWMON_BASE = Path("/sys/class/hwmon")
_INPUT_RE = re.compile(r"^(fan|temp|in|curr|power)\d+_input$")
_PACKAGE_LABEL_RE = re.compile(r"Package id (\d+)")

_hwmon_cache: dict[tuple[str, tuple[str, ...]], Optional[str]] = {}


def _read_or_none(path: Path) -> Optional[str]:
    """Read text from a sysfs path, stripped. Returns None on OSError.

    Sysfs reads of small attribute files are atomic at the VFS layer —
    a single read() call sees a consistent snapshot.
    """
    try:
        return path.read_text().strip()
    except OSError:
        return None


def _count_inputs(dir_path: str) -> int:
    """Count files matching real-sensor-input regex. Used for tie-breaking."""
    try:
        return sum(1 for entry in os.listdir(dir_path) if _INPUT_RE.match(entry))
    except OSError:
        return 0


def find_hwmon(name: str, *, requires: tuple[str, ...] = ()) -> Optional[str]:
    """Resolve a hwmon device by reading each hwmon*/name file.

    Args:
        name: Exact match against the contents of /sys/class/hwmon/hwmonN/name.
        requires: File names that must all exist inside the hwmon dir for the
            candidate to qualify (e.g. ("fan1_input", "temp1_input") for 'acer').

    Returns:
        Absolute path to the matching hwmon directory, or None if no candidate
        qualifies. On multiple candidates, picks the one with the most real
        sensor-input files; alphabetical on further ties (determinism across
        reboots).

    Never raises FileNotFoundError (CORE-03 invariant).

    Result is cached. Callers that get an OSError during a downstream sensor
    read should call invalidate_hwmon_cache() and retry once.
    """
    key = (name, tuple(requires))
    if key in _hwmon_cache:
        return _hwmon_cache[key]

    candidates: list[str] = []
    try:
        entries = os.listdir(HWMON_BASE)
    except OSError:
        _hwmon_cache[key] = None
        return None

    for entry in entries:
        path = os.path.join(HWMON_BASE, entry)
        name_file = os.path.join(path, "name")
        actual = _read_or_none(Path(name_file))
        if actual != name:
            continue
        if not all(os.path.exists(os.path.join(path, r)) for r in requires):
            continue
        candidates.append(path)

    if not candidates:
        _hwmon_cache[key] = None
        return None

    # Most-populated wins; alphabetical tie-break.
    candidates.sort(key=lambda p: (-_count_inputs(p), p))
    _hwmon_cache[key] = candidates[0]
    return candidates[0]


def find_all_hwmon(name: str) -> list[str]:
    """All hwmon directories whose `name` file equals `name`, sorted alphabetically.

    Used by CORE-06 (multi-package coretemp). Not cached — caller iterates.
    """
    out: list[str] = []
    try:
        entries = sorted(os.listdir(HWMON_BASE))
    except OSError:
        return out
    for entry in entries:
        path = os.path.join(HWMON_BASE, entry)
        if _read_or_none(Path(path) / "name") == name:
            out.append(path)
    return out


def invalidate_hwmon_cache() -> None:
    """Drop the resolved-path cache. Called by callers on OSError during reads."""
    _hwmon_cache.clear()


def coretemp_max_package_temp() -> Optional[float]:
    """Return the maximum 'Package id N' temperature across all coretemp hwmon
    devices, in °C. None if no coretemp hwmon is found or no labels match.

    Mitigates P16: multi-package CPUs (e.g. PH317 dual-die systems) have
    multiple coretemp hwmon entries; reporting only hwmon0/temp1_input under-
    reports the hottest die.

    Algorithm:
      1. find_all_hwmon("coretemp")
      2. For each hwmon dir, scan tempN_label files for "Package id <n>"
      3. Read corresponding tempN_input, convert millidegrees → °C
      4. Return max of collected values
      5. Fallback: if no labels matched but at least one coretemp dir exists,
         read its temp1_input as a last resort.
    """
    package_temps: list[float] = []
    coretemp_dirs = find_all_hwmon("coretemp")
    if not coretemp_dirs:
        return None

    for d in coretemp_dirs:
        try:
            entries = os.listdir(d)
        except OSError:
            continue
        for entry in entries:
            if not entry.endswith("_label"):
                continue
            label = _read_or_none(Path(d) / entry)
            if not label or not _PACKAGE_LABEL_RE.search(label):
                continue
            # tempN_label → tempN_input
            input_name = entry[: -len("_label")] + "_input"
            raw = _read_or_none(Path(d) / input_name)
            if raw is None:
                continue
            try:
                package_temps.append(int(raw) / 1000.0)
            except ValueError:
                continue

    if package_temps:
        return max(package_temps)

    # Fallback: no labels found, but we have a coretemp — read temp1_input.
    fallback = _read_or_none(Path(coretemp_dirs[0]) / "temp1_input")
    if fallback is None:
        return None
    try:
        return int(fallback) / 1000.0
    except ValueError:
        return None


def read_acer_sensors(hwmon_path: Optional[str]) -> dict[str, Optional[float | int]]:
    """Read fan and temp values from the acer hwmon directory.

    Returns a dict with keys: fan1_rpm, fan2_rpm, temp1_c, temp2_c, temp3_c.
    Missing or unreadable values are None — never raises. Phase 5 will render
    None as "—".

    fanN_input is RPM (int). tempN_input is millidegrees (int) — converted to
    float °C in the returned dict.
    """
    result: dict[str, Optional[float | int]] = {
        "fan1_rpm": None, "fan2_rpm": None,
        "temp1_c": None, "temp2_c": None, "temp3_c": None,
    }
    if hwmon_path is None:
        return result

    base = Path(hwmon_path)
    for key, fname in (("fan1_rpm", "fan1_input"), ("fan2_rpm", "fan2_input")):
        raw = _read_or_none(base / fname)
        if raw is not None:
            try:
                result[key] = int(raw)
            except ValueError:
                pass

    for key, fname in (("temp1_c", "temp1_input"),
                       ("temp2_c", "temp2_input"),
                       ("temp3_c", "temp3_input")):
        raw = _read_or_none(base / fname)
        if raw is not None:
            try:
                result[key] = int(raw) / 1000.0
            except ValueError:
                pass

    return result
