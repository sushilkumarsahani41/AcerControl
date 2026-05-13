# Phase 1: Foundation — Research

**Researched:** 2026-05-14
**Domain:** Linux sysfs introspection library — `acercontrol/` Python package (read-only foundation; no privileged writes, no GUI, no CLI surface yet)
**Confidence:** HIGH (stack already locked by upstream STACK/ARCHITECTURE research; this phase synthesizes them into committed Phase 1 design)

## Summary

Phase 1 stands up the `acercontrol/` Python package as the **single source of truth** for sysfs reads, hwmon discovery, profile name mapping, and feature detection on Acer Predator/Nitro laptops. The deliverable is a stdlib-only, GTK-free, read-only library that every downstream phase (CLI in Phase 2, GUI in Phase 3+) consumes without rewriting any of this logic.

The package decomposes into four sibling modules — `profiles.py` (canonical user↔kernel name mapping with `Profile.CUSTOM` sentinel), `sysfs.py` (path discovery and raw reads, including `find_hwmon` with "most-populated on tie" disambiguation), `features.py` (structured `FeatureReport` from a defensive probe), and `core.py` (thin user-facing facade tying them together). Plus a minimal `pyproject.toml` (PEP 621, setuptools, `requires-python >= 3.11`) with **no `[project.scripts]` yet** — entry points land in Phase 2 with the CLI.

The architectural invariant the planner must enforce: **no module in this phase imports `gi`, GTK, or Adwaita**. The CLI bundler in Phase 2 will concatenate these modules into a single-file stdlib-only CLI; any GTK leak fails the build forever.

**Primary recommendation:** Implement four small files (`profiles.py`, `sysfs.py`, `features.py`, `core.py`) + `__init__.py` + `pyproject.toml`. Total LOC ≈ 400. Validate via `python3 -m acercontrol.features` smoke entry — must print a structured report on any Linux box (degraded if `acer_wmi` absent, never crashing).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Sysfs path discovery (`find_hwmon`, blacklist scan) | Backend / Library | — | Pure stdlib filesystem reads; consumed by everything above. |
| Profile name mapping (`Profile` enum, `PROFILES`, `KERNEL_TO_UI`) | Backend / Library | — | Pure data + tiny lookup helpers; no I/O at module-import time. |
| Feature probe (`FeatureReport`) | Backend / Library | — | Read-only sysfs introspection + a single `subprocess` call to `systemctl is-active`. No widgets, no privilege escalation. |
| Sensor reading (`coretemp_max_package_temp`, `read_acer_sensors`) | Backend / Library | — | Composes `sysfs.py` paths into typed reads; no caching beyond the hwmon-path cache. |

Phase 1 is single-tier by design — the privilege boundary (Phase 2) and UI tiers (Phase 3+) consume this library; they do not exist yet.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11+ | Runtime | `tomllib` stdlib (3.11+), exception groups, better tracebacks, no Debian-11 cost since Ubuntu 24.04 ships 3.12 and Debian 12 ships 3.11. `[CITED: PEP 657, PEP 654, PEP 680]` |
| setuptools | ≥61 (any 3.11-era) | Build backend for `pyproject.toml` | PEP 621 native; what `pybuild-plugin-pyproject` is best-tested against. `[VERIFIED: STACK.md §8]` |
| Python stdlib only | — | All of: `os`, `pathlib`, `dataclasses`, `enum`, `glob`, `re`, `subprocess`, `typing` | Phase 1 has zero non-stdlib runtime deps — non-negotiable for the Phase 2 bundler. `[VERIFIED: CLAUDE.md "Single-file CLI" constraint]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none) | — | — | Phase 1 deliberately ships zero third-party deps. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python 3.11+ floor | Python 3.10 (PROJECT.md original) | Loses `tomllib` (need INI/configparser for user config) and exception groups; no compensating gain on the Ubuntu 24.04/Debian 12 target matrix. **Reject — bump to 3.11+.** `[VERIFIED: STATE.md open question]` |
| `setuptools` backend | `hatchling`, `flit_core`, `poetry-core` | `pybuild-plugin-pyproject` (Phase 8 Debian build) is best-tested against setuptools; hatchling/flit work but add risk. **Reject for v1.** `[CITED: STACK.md §8]` |
| `@dataclass(frozen=True)` for `FeatureReport` | `TypedDict`, `NamedTuple`, plain dict | Frozen dataclass gives `__repr__`, type checks, hashability for tests, and a clean docstring slot; `TypedDict` loses runtime validation; `NamedTuple` lacks future-proofing for adding methods (`report.ok`). **Pick frozen dataclass.** `[ASSUMED — idiomatic Python]` |
| `enum.Enum` for `Profile` | Plain str constants + dict, `dataclasses.dataclass(frozen=True)` | Enum gives `Profile.CUSTOM` as a real sentinel (`is` comparison), exhaustiveness checks at static-analysis time, IDE autocomplete. **Pick `Enum` with `.value` = kernel string + a `display` property for the user name.** `[ASSUMED — see Q1 below]` |

**Installation (developer setup, one-time):**
```bash
# Verify Python floor on target
python3 --version  # must be >= 3.11

# Phase 1 itself has no apt deps beyond python3 (already on Ubuntu 24.04)
# Editable install for manual testing
cd /Users/sushilkumarsahani/Desktop/AcerControl
pip install -e .   # or: PYTHONPATH=. python3 -m acercontrol.features
```

**Version verification:** No third-party packages to verify in Phase 1. The only version concern is the Python floor — locked to `>=3.11` in `pyproject.toml`.

## Project Constraints (from CLAUDE.md)

CLAUDE.md is consulted but the binding contracts are in PROJECT.md / REQUIREMENTS.md / ROADMAP.md. CLAUDE.md is a draft and several of its examples are **explicitly contradicted** by later research:

| CLAUDE.md draft says | Phase 1 honors | Phase 1 overrides |
|----------------------|----------------|-------------------|
| `acercontrol.py` standalone CLI at repo root | — | **OVERRIDE** — Phase 1 builds `acercontrol/` package; no top-level scripts (avoids two-source-of-truth, ARCHITECTURE.md §"Reconciling the Single-File CLI Constraint"). |
| Profile dict `PROFILES = {"eco": "low-power", ...}` (no enum) | Mapping content kept verbatim | **EXTEND** — wrap in `Profile` enum to support `Profile.CUSTOM`. |
| `pkexec bash -c "echo ..."` privilege pattern | — | **OUT OF PHASE** — Phase 1 has no privileged writes. Phase 2 owns the named-wrapper redesign. |
| `SensorMonitor` with `threading.Thread` + `GLib.idle_add` | — | **OUT OF PHASE** — Phase 5 owns sensor refresh; SUMMARY.md decision #3 supersedes with `GLib.timeout_add_seconds`. Phase 1 only exposes the synchronous reader the timer will call. |
| Single `core.py` for all logic | Module name `core.py` kept | **SPLIT** — logic split across `core.py`/`sysfs.py`/`profiles.py`/`features.py` per ARCHITECTURE.md. `core.py` becomes a thin facade. |
| Sysfs paths (`PROFILE_PATH`, `HWMON_BASE`, etc.) | **KEEP verbatim** in `core.py` | — |
| Hwmon discovery by `name` file content | **KEEP — non-negotiable** | — |
| Multi-package coretemp note ("temp1_input → package temp") | — | **EXTEND** — `Package id N` label match + max across packages (CORE-06). |

Project skill rules (CLAUDE.md global level) noted: no rules/*.md directives currently in scope; CLAUDE.md serves as background context.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Canonical user-name ↔ kernel-value profile mapping is the single source of truth | `profiles.py` ships `Profile` enum + `PROFILES` dict + `KERNEL_TO_UI` reverse map; `__init__.py` re-exports. Roundtrip property test in Validation Architecture. |
| CORE-02 | `sysfs.find_hwmon(name, requires=...)` resolves hwmon by `name` file, picks most-populated on tie | `sysfs.find_hwmon` algorithm specified below; "most-populated" defined as count of `*_input` files matching `(fan|temp|in|curr|power)[0-9]+_input`; tie-break alphabetical. |
| CORE-03 | `features.probe()` returns structured `FeatureReport` with no `FileNotFoundError` past this layer | `features.py` ships `@dataclass(frozen=True)` `FeatureReport` + `FeatureCheck` list; every sysfs read goes through `_read_or_none`; renaming `platform_profile` mid-session produces a degraded report, not a traceback. |
| CORE-04 | Kernel `custom` value (or any unknown) maps to "Custom" display state, never crashes | `Profile.CUSTOM` enum member; `kernel_to_profile(raw)` returns `Profile.CUSTOM` for unknown values. **`[CITED: kernel.org Documentation/ABI/testing/sysfs-platform_profile]`** — `custom` is officially documented: "This file may also emit the string 'custom' to indicate that multiple platform profiles drivers are in use but have different values. This string can not be written to this interface and is solely for informational purposes." |
| CORE-05 | `acer_wmi` blacklist entries in `/etc/modprobe.d/*.conf` detected at startup | `features.find_blacklist_entries()` globs `/etc/modprobe.d/*.conf`, strips comments, regex-matches `^\s*(blacklist\s+acer_wmi\|install\s+acer_wmi\s+/bin/(true\|false))\s*$`. Surfaced as a `FeatureCheck` with severity `blocking`. |
| CORE-06 | Multi-package coretemp handled — match `Package id 0` label, report max across packages | `sysfs.coretemp_max_package_temp()` enumerates all `coretemp` hwmon directories (via `find_all_hwmon`), reads `tempN_label` files, regex-matches `Package id (\d+)`, collects corresponding `tempN_input`, returns `max(values) / 1000.0` (°C). Fallback when no labels: read `temp1_input` from first coretemp hwmon. |

## Architecture Patterns

### System Architecture Diagram

```
                  ┌────────────────────────────────────────┐
                  │   Phase 1 PUBLIC API (acercontrol/__init__.py)
                  │   Profile, PROFILES, KERNEL_TO_UI,
                  │   FeatureReport, probe(),
                  │   current_profile_ui(), find_hwmon()
                  └──────────────┬─────────────────────────┘
                                 │  (re-exports only)
        ┌────────────────────────┴────────────────────────┐
        ▼                                                  ▼
   ┌────────────┐                                  ┌────────────┐
   │ core.py    │ ← facade for downstream callers  │ features.py│
   │  read_     │                                  │  probe()   │
   │  profile() │                                  │  Feature   │
   │  read_     │                                  │  Report    │
   │  sensors() │                                  │  find_     │
   │            │                                  │  blacklist │
   │  path      │                                  │  _entries  │
   │  consts    │                                  │            │
   └──┬─────────┘                                  └──┬─────────┘
      │       │                                       │
      │       │   ┌───────────────────┐               │
      │       └──▶│ profiles.py       │◀──────────────┘
      │           │  Profile (Enum)   │
      │           │  PROFILES dict    │
      │           │  KERNEL_TO_UI     │
      │           │  kernel_to_       │
      │           │   profile(raw)    │
      │           │  current_profile_ │
      │           │   ui()            │
      │           └────────┬──────────┘
      │                    │
      ▼                    ▼
   ┌─────────────────────────────────────┐
   │ sysfs.py                            │
   │  _read_or_none(path)                │
   │  find_hwmon(name, requires=...)     │
   │  find_all_hwmon(name)               │
   │  read_acer_sensors(hwmon_path)      │
   │  coretemp_max_package_temp()        │
   │  _hwmon_cache: dict[str, str|None]  │
   └────────────────┬────────────────────┘
                    │
                    ▼
   ┌────────────────────────────────────────────────────┐
   │            KERNEL SURFACE (read-only)               │
   │  /sys/firmware/acpi/platform_profile                │
   │  /sys/firmware/acpi/platform_profile_choices        │
   │  /sys/class/hwmon/hwmon*/{name,fanN_input,tempN_*}  │
   │  /sys/module/acer_wmi/{,parameters/predator_v4}     │
   │  /etc/modprobe.d/*.conf  (blacklist detection)      │
   │  $ systemctl is-active power-profiles-daemon  (PPD) │
   └────────────────────────────────────────────────────┘
```

**Data flow (synchronous, no threads, no async):**

1. Caller imports `from acercontrol import features`.
2. Caller calls `features.probe()`.
3. `probe()` invokes (a) `sysfs.find_hwmon`, (b) `_read_or_none` on each known sysfs path, (c) `subprocess.run(["systemctl", "is-active", ...])`, (d) `find_blacklist_entries()`.
4. Each sub-call returns its result (or `None` / empty list on missing) — never raises `FileNotFoundError`.
5. `probe()` packages all results into a frozen `FeatureReport(checks=[...])` and returns.

### Recommended Project Structure (Phase 1 scope only)

```
/Users/sushilkumarsahani/Desktop/AcerControl/
├── pyproject.toml                          # NEW — PEP 621, setuptools, requires-python>=3.11
├── acercontrol/                            # NEW — importable package (Phase 1 modules only)
│   ├── __init__.py                         # NEW — re-exports + __version__
│   ├── core.py                             # NEW — path constants, _read_or_none, read_profile, read_sensors
│   ├── profiles.py                         # NEW — Profile enum, PROFILES, KERNEL_TO_UI, helpers
│   ├── sysfs.py                            # NEW — find_hwmon, find_all_hwmon, read_acer_sensors, coretemp_max_package_temp
│   └── features.py                         # NEW — FeatureCheck, FeatureReport, probe(), find_blacklist_entries, __main__
├── .planning/                              # already present
├── CLAUDE.md                               # already present
└── README.md                               # NOT IN PHASE 1 — defer
```

**Modules deliberately NOT created in Phase 1** (per ROADMAP phase boundaries):
- `acercontrol/privilege.py` — Phase 2
- `acercontrol/cli.py` — Phase 2
- `acercontrol/gui.py`, `monitor.py`, `notifier.py`, `tray.py` — Phase 3+
- `acercontrol/service.py`, `config.py` — Phase 6
- `helpers/`, `data/`, `debian/`, `tools/bundle_cli.py` — Phase 2/6/8

### Pattern 1: `Profile` enum with kernel value + display property

**What:** Use `enum.Enum` where each member's `.value` is the kernel string (what sysfs reads/writes) and a separate `.display` property returns the user-facing name. `Profile.CUSTOM` is a real enum member representing the kernel `custom` value or any unmapped reading.

**When to use:** Any time the library reports the current profile to a caller. Callers do `if profile is Profile.CUSTOM:` — never `is None`. "Custom" is a valid state, not absence.

**Code skeleton** (goes in `acercontrol/profiles.py`):

```python
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
```

### Pattern 2: `find_hwmon` with "most-populated on tie" disambiguation

**What:** Walk `/sys/class/hwmon/hwmon*`, read each `name` file, filter to candidates matching the requested name AND containing the `requires=` set of files. On multiple matches, pick the directory with the most "real sensor input" files (matching `(fan|temp|in|curr|power)[0-9]+_input`). Alphabetical tie-break for determinism.

**When to use:** Discovering `acer` and `coretemp` hwmon paths at probe time. **Resolve once, cache, re-resolve on OSError.**

**Contract** (binding on the planner):
- `find_hwmon(name, requires=()) -> str | None` — returns absolute path string or `None`. **Never raises** (CORE-03 invariant).
- `find_all_hwmon(name) -> list[str]` — returns sorted list (possibly empty), used for multi-package coretemp.
- Module-level `_hwmon_cache: dict[tuple[str, tuple[str, ...]], str | None]` keyed on `(name, requires)`.
- On `OSError` during a sensor read, callers invoke `invalidate_hwmon_cache()` then retry once; returning `None` after retry means "sensor unavailable" (the UI in Phase 5 renders "—").

**Code skeleton** (goes in `acercontrol/sysfs.py`):

```python
# acercontrol/sysfs.py
"""Read-only sysfs path discovery and raw reads.

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
```

### Pattern 3: `FeatureReport` as a frozen dataclass with structured checks

**What:** `features.probe()` returns a `FeatureReport(checks=[FeatureCheck(...), ...])`. Each check has `name`, `present`, `detail`, `fix`, `severity` (string literal `"blocking" | "warning" | "info"`). Frozen so it's hashable and read-only. `report.ok` is a derived property: `all(c.present for c in checks if c.severity == "blocking")`.

**Why string severity, not Enum:** keeps the report JSON-serializable for the eventual Diagnostics export (D-11 differentiator), and simpler for the planner's downstream UI rendering.

**Code skeleton** (goes in `acercontrol/features.py`):

```python
# acercontrol/features.py
"""Structured feature probe for the AcerControl runtime environment.

Single entry point: features.probe() -> FeatureReport. Never raises;
every sysfs check goes through sysfs._read_or_none. The FeatureReport
is consumed by the CLI (Phase 2) for `acercontrol status` and by the
GUI (Phase 3) to route to Adw.StatusPage failure screens.

Smoke entry: python3 -m acercontrol.features
"""
from __future__ import annotations
import glob
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from acercontrol import core
from acercontrol.sysfs import _read_or_none, find_hwmon


Severity = Literal["blocking", "warning", "info"]

_BLACKLIST_RE = re.compile(
    r"^\s*(blacklist\s+acer_wmi|install\s+acer_wmi\s+/bin/(?:true|false))\s*(#.*)?$"
)


@dataclass(frozen=True)
class FeatureCheck:
    """Single feature-probe result."""
    name: str
    present: bool
    detail: str = ""
    fix: str = ""
    severity: Severity = "blocking"


@dataclass(frozen=True)
class FeatureReport:
    """Full environment probe — consumed by CLI/GUI failure-mode dispatch."""
    checks: tuple[FeatureCheck, ...]
    blacklist_entries: tuple[tuple[str, str], ...] = ()  # (file_path, matched_line)

    @property
    def ok(self) -> bool:
        """True iff every 'blocking' check is present."""
        return all(c.present for c in self.checks if c.severity == "blocking")

    @property
    def first_blocking_failure(self) -> FeatureCheck | None:
        for c in self.checks:
            if c.severity == "blocking" and not c.present:
                return c
        return None


def find_blacklist_entries(
    pattern: str = "/etc/modprobe.d/*.conf",
) -> list[tuple[str, str]]:
    """Scan modprobe.d for entries blacklisting acer_wmi (CORE-05).

    Returns list of (file_path, matched_line). Lines after a '#' comment
    are stripped before matching. Caller may pass a custom pattern (used
    by tests pointing at /tmp/test-blacklist.conf).
    """
    hits: list[tuple[str, str]] = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    # Strip inline comments BUT keep the matched line for display
                    code = raw_line.split("#", 1)[0]
                    if _BLACKLIST_RE.match(code):
                        hits.append((path, raw_line.rstrip("\n")))
        except OSError:
            continue
    return hits


def _ppd_active() -> bool | None:
    """Returns True/False if systemctl was reachable; None if systemctl is missing.

    Per SUMMARY.md decision #1 / pitfall P2: PPD detection is a probe input,
    not a write trigger. Phase 1 only reports state.
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "power-profiles-daemon.service"],
            capture_output=True, text=True, timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    # systemctl is-active exits 0 only when active.
    return result.returncode == 0


def probe() -> FeatureReport:
    """Run the full environment probe. Never raises.

    Order matters: blocking checks first, then warnings (PPD, blacklist).
    The first blocking failure is what the GUI's Adw.StatusPage will surface.
    """
    checks: list[FeatureCheck] = []

    # 1. acer_wmi module loaded
    acer_loaded = Path("/sys/module/acer_wmi").exists()
    checks.append(FeatureCheck(
        name="acer_wmi module loaded",
        present=acer_loaded,
        detail="/sys/module/acer_wmi " + ("present" if acer_loaded else "missing"),
        fix="sudo modprobe acer_wmi predator_v4=1",
        severity="blocking",
    ))

    # 2. predator_v4 mode
    pv4 = _read_or_none(core.PREDATOR_V4_PARAM)
    checks.append(FeatureCheck(
        name="predator_v4 mode",
        present=(pv4 == "Y"),
        detail=f"predator_v4={pv4!r}",
        fix=(
            "Add 'options acer_wmi predator_v4=1' to "
            "/etc/modprobe.d/99-acer-wmi.conf, then "
            "sudo update-initramfs -u, then reboot."
        ),
        severity="blocking",
    ))

    # 3. platform_profile sysfs
    pp_present = core.PROFILE_PATH.exists()
    checks.append(FeatureCheck(
        name="platform_profile sysfs",
        present=pp_present,
        detail=str(core.PROFILE_PATH) + (" present" if pp_present else " missing"),
        fix="Requires kernel with ACPI platform_profile support (>= 6.6 recommended).",
        severity="blocking",
    ))

    # 4. acer hwmon
    acer_hwmon = find_hwmon("acer", requires=("fan1_input", "temp1_input"))
    checks.append(FeatureCheck(
        name="acer hwmon (fan+temp)",
        present=acer_hwmon is not None,
        detail=acer_hwmon or "no hwmon entry named 'acer' with fan1_input+temp1_input",
        fix="Verify acer_wmi loaded with predator_v4=1; sensor exposure may lag module load.",
        severity="warning",  # GUI renders "—" placeholders rather than refusing to load
    ))

    # 5. coretemp hwmon
    coretemp_hwmon = find_hwmon("coretemp", requires=("temp1_input",))
    checks.append(FeatureCheck(
        name="coretemp hwmon",
        present=coretemp_hwmon is not None,
        detail=coretemp_hwmon or "no hwmon entry named 'coretemp'",
        fix="sudo modprobe coretemp",
        severity="info",  # CPU package temp is nice-to-have, not blocking
    ))

    # 6. PPD active state
    ppd = _ppd_active()
    if ppd is None:
        checks.append(FeatureCheck(
            name="power-profiles-daemon state",
            present=True,  # 'unknown' is not a failure here
            detail="systemctl unavailable — PPD state unknown",
            fix="",
            severity="info",
        ))
    else:
        checks.append(FeatureCheck(
            name="power-profiles-daemon inactive",
            present=not ppd,
            detail="active — will overwrite profile writes" if ppd else "inactive",
            fix="sudo systemctl mask --now power-profiles-daemon.service",
            severity="warning",
        ))

    # 7. acer_wmi blacklist entries
    blacklist = find_blacklist_entries()
    checks.append(FeatureCheck(
        name="acer_wmi not blacklisted",
        present=not blacklist,
        detail=(
            f"{len(blacklist)} blacklist entr"
            f"{'y' if len(blacklist)==1 else 'ies'}"
            if blacklist else "no blacklist entries"
        ),
        fix=(
            "Remove or comment out matching lines in /etc/modprobe.d/*.conf "
            "and run sudo update-initramfs -u, then reboot."
        ),
        severity="blocking" if blacklist else "info",
    ))

    return FeatureReport(
        checks=tuple(checks),
        blacklist_entries=tuple(blacklist),
    )


def _print_report(report: FeatureReport) -> int:
    """Human-readable smoke output for `python3 -m acercontrol.features`.

    Returns shell exit code: 0 (clean), 1 (degraded), 2 (blocking failure).
    Phase 1 callers don't depend on the exit code — it's a convenience for
    UAT.
    """
    sev_glyph = {"blocking": "[!]", "warning": "[~]", "info": "[i]"}
    print(f"AcerControl FeatureReport  (ok={report.ok})")
    print("-" * 60)
    for c in report.checks:
        mark = "OK " if c.present else sev_glyph[c.severity]
        print(f"  {mark}  {c.name}")
        if c.detail:
            print(f"         detail: {c.detail}")
        if not c.present and c.fix:
            print(f"         fix:    {c.fix}")
    if report.blacklist_entries:
        print()
        print("Blacklist entries detected:")
        for path, line in report.blacklist_entries:
            print(f"  {path}: {line}")
    if not report.ok:
        return 2
    if any(c.severity == "warning" and not c.present for c in report.checks):
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_print_report(probe()))
```

### Pattern 4: `core.py` as thin facade with path constants

**Why a separate `core.py`:** keeps Phase 1's public API surface stable across the refactor. Downstream callers will `from acercontrol import core` for path constants and high-level reads; they do not need to know whether a value comes from `sysfs.py` or `profiles.py`. The planner uses this module as the single import path the CLI/GUI talks to.

**Code skeleton** (goes in `acercontrol/core.py`):

```python
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
```

### Pattern 5: `__init__.py` minimal re-exports

```python
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
```

### Pattern 6: Minimal `pyproject.toml` (Phase 1 only)

```toml
# pyproject.toml — Phase 1 scope. [project.scripts] added in Phase 2.
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
# Zero runtime dependencies in Phase 1 — stdlib only.

[tool.setuptools]
packages = ["acercontrol"]
```

**Notes for the planner:**
- `readme = "README.md"` references a file that does not exist yet. Either (a) create a one-line README "AcerControl — see .planning/PROJECT.md" as part of the task, or (b) drop the `readme` key for now. **Recommend (a)** — every `.deb` build expects a README, even a stub.
- No `[project.scripts]` — Phase 2 adds `acercontrol = "acercontrol.cli:main"` (and Phase 3 adds `-gui`).
- No `[tool.pytest.ini_options]` — Phase 1 validates via inline `python3 -c` per the Validation Architecture section below (PROJECT.md says no automated tests for v1).

### Anti-Patterns to Avoid

- **Importing `gi` anywhere in Phase 1 modules.** The bundler in Phase 2 will hard-fail. If you ever need a typelib symbol in this layer, you've architecturally misrouted it — push it up to `gui.py`.
- **Hardcoding `hwmon7` (or any numeric hwmon index).** P6. The whole point of `find_hwmon` is to never hardcode indices.
- **Raising `FileNotFoundError` past the library boundary.** CORE-03 contract. Wrap every `read_text()` in `_read_or_none`. `find_hwmon` returns `None`, not raises.
- **`None`-typing the unknown profile state.** Use `Profile.CUSTOM` instead — callers do `is`-comparison, not null-check.
- **Validating `PROFILES.values() ⊆ choices` at module import time.** Phase 1 must import cleanly on systems without `acer_wmi`. Validate lazily, on first call to a function that needs the choices.
- **Adding tests directory in Phase 1.** PROJECT.md/REQUIREMENTS.md Out of Scope: "Automated test suite / CI". Validation is the inline `python3 -c` snippets below.
- **Stuffing everything in `core.py`.** CLAUDE.md draft puts all logic in `core.py`; ARCHITECTURE.md splits it. Honor the split — easier to refactor a 100-line `sysfs.py` than a 400-line `core.py`.
- **Caching the `FeatureReport` at module load.** Probe is cheap (< 10 ms); always call fresh. Caching across the GUI's lifetime is Phase 3's concern, not Phase 1's.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Profile name mapping | Custom string → string lookup with manual reverse map drift | `Profile(Enum)` + dict comprehension for `KERNEL_TO_UI` | `Enum` gives `Profile.CUSTOM` as a real sentinel and prevents drift between forward/reverse maps. |
| Sysfs path discovery by integer | `Path("/sys/class/hwmon/hwmon7/...")` (hardcoded) | `find_hwmon(name, requires=...)` | hwmon numbering is unstable (P6, ARCHITECTURE Anti-Pattern 6). |
| TOML reading (later phases) | `configparser` or hand-roll INI | `tomllib` (stdlib, Python 3.11+) | The Python 3.11 floor exists precisely so we don't ship `tomli` as a third-party dep. |
| TOML writing (later phases) | `tomli-w` (third-party) | Simple line-emit helper | Phase 1 doesn't write config yet; Phase 6 will. Avoid pulling a dep for ~10 lines. |
| Frozen value object | Manual `__init__` + `__eq__` + `__hash__` | `@dataclass(frozen=True)` | Less code, hashable for cache keys, free `__repr__` for debugging. |
| Severity enum | `enum.Enum` for `Severity` | `Literal["blocking", "warning", "info"]` | Severity is JSON-serializable as-is (future Diagnostics export); `Literal` gives static-type checking without runtime overhead. |
| `subprocess.Popen` ceremony | Manual pipes for `systemctl is-active` | `subprocess.run(..., capture_output=True, timeout=2)` | Three-line idiom, type-safe, timeout-bounded. |
| Path manipulation by string | `os.path.join` everywhere | `pathlib.Path` | Where we already use `pathlib`, keep it; mixed `os.path`/`pathlib` is fine in `sysfs.py` because `os.listdir` returns strings and conversions add noise. |

**Key insight:** Phase 1 deliberately ships *zero* runtime dependencies. Every third-party temptation (typer/click for CLI args, tomli for TOML, attrs for dataclasses, pydantic for validation) is rejected at this layer to preserve the Phase 2 single-file bundler invariant. If you find yourself wanting a third-party dep here, you're in the wrong module.

## Common Pitfalls

### Pitfall P4: Kernel "performance" ≠ user "performance"
**What goes wrong:** Kernel `performance` means turbo (LED blinks) on Predator hardware. UX "performance" means high-perf-no-LED (kernel `balanced-performance`). Any code rendering raw sysfs values inverts the labels.
**Why it happens:** Hardware vendors named the kernel state, then UX needed a clearer 5-tier vocabulary that doesn't match.
**How to avoid:** `KERNEL_TO_UI` is the only allowed bridge. `Profile` enum's `.display` property is the only allowed UI-string generator. Grep guard in later phases: no string literals matching `low-power|balanced-performance|performance|quiet` (kernel values) outside `profiles.py`.
**Warning signs:** A button labelled "performance" makes the LED blink. CLI `get` returns "performance" while the GUI highlights "turbo". (Detected by Phase 4's read-back property test, but the prevention lives here.)

### Pitfall P6: hwmon index drift
**What goes wrong:** `hwmon7` after one boot, `hwmon3` after another. Hardcoded path breaks. Or: two devices share `name == "coretemp"` (one per CPU package).
**Why it happens:** hwmonN allocation is module-load-order-dependent. Suspend/resume and unrelated driver loads renumber.
**How to avoid:** Always `find_hwmon(name, requires=...)`. For coretemp specifically, use `find_all_hwmon` and aggregate. Cache once, invalidate on `OSError`.
**Warning signs:** Sensors disappear after `apt upgrade`. "fan = 0 RPM" alongside live "temp = 65 °C" (wrong hwmon picked).

### Pitfall P13: Defensive probe contract
**What goes wrong:** A kernel update renames a sysfs path; the library crashes with `FileNotFoundError`; the GUI shows a Python traceback to the user.
**Why it happens:** Forgetting that sysfs is a kernel interface, not a guaranteed-stable file tree.
**How to avoid:** Every read goes through `_read_or_none`. `find_hwmon` returns `None`, never raises. `features.probe()` is the failure-domain boundary — no `FileNotFoundError` past this layer. The Phase 3 GUI consumes `FeatureReport.first_blocking_failure` to render an `Adw.StatusPage`.
**Warning signs:** Renaming `/sys/firmware/acpi/platform_profile` while the library is loaded must produce a degraded `FeatureReport`, not a traceback (ROADMAP success criterion #4).

### Pitfall P16: Multi-package coretemp picks wrong die
**What goes wrong:** On dual-die CPUs (PH317 systems with some i9 SKUs), `coretemp` exposes one hwmon per package. Reading only `hwmon0/temp1_input` shows package 0 — package 1 might be 15 °C hotter under load.
**Why it happens:** Assuming a single CPU package; testing only on the user's PHN16-72 (i9-14900HX, single package, single die).
**How to avoid:** `coretemp_max_package_temp()` enumerates all coretemp hwmon entries, regex-matches `Package id N` in `tempN_label`, returns the max.
**Warning signs:** Reported CPU temp on a multi-package system is suspiciously low under load. (Not directly testable on PHN16-72; flag for compatible-hardware UAT in Phase 7.)

### Pitfall P17: acer_wmi blacklist or unload
**What goes wrong:** A previous TLP/thermald install left `blacklist acer_wmi` in `/etc/modprobe.d/`. User installs AcerControl; on next boot the module fails to load; AcerControl shows a generic "module not loaded" error without telling the user *why*.
**Why it happens:** Modprobe blacklist files are persistent and survive package operations.
**How to avoid:** `find_blacklist_entries()` scans `/etc/modprobe.d/*.conf` at probe time and elevates the blacklist check to severity `blocking` with a specific remediation ("Remove or comment out matching lines in /etc/modprobe.d/*.conf").
**Warning signs:** "acer_wmi module not loaded" persists across `sudo modprobe acer_wmi predator_v4=1`. The user runs `dmesg` and sees a "blacklisted" message.

## Runtime State Inventory

> Phase 1 is greenfield code creation — no rename/refactor/migration. This section is N/A and omitted.

## Code Examples

All examples are verified against the kernel sysfs spec and the upstream research docs. Each is a complete, runnable snippet.

### Example 1: Resolve the acer hwmon and read fan RPM

```python
from acercontrol.sysfs import find_hwmon, read_acer_sensors

hwmon = find_hwmon("acer", requires=("fan1_input", "temp1_input"))
if hwmon is None:
    print("acer hwmon not found (module loaded?)")
else:
    data = read_acer_sensors(hwmon)
    print(f"Fan1: {data['fan1_rpm']} RPM  Fan2: {data['fan2_rpm']} RPM")
    print(f"Temps: {data['temp1_c']} / {data['temp2_c']} / {data['temp3_c']} °C")
```

### Example 2: Get the current profile in user-facing terms

```python
from acercontrol import read_profile, Profile

p = read_profile()
if p is Profile.CUSTOM:
    print("Profile: Custom (multiple drivers disagree)")
else:
    print(f"Profile: {p.display}  (kernel value: {p.value})")
```

### Example 3: Run the full feature probe and act on it

```python
from acercontrol import probe

report = probe()
if not report.ok:
    failure = report.first_blocking_failure
    print(f"BLOCKED: {failure.name}")
    print(f"  detail: {failure.detail}")
    print(f"  fix:    {failure.fix}")
else:
    print("Environment OK — ready for profile control")
```

### Example 4: Multi-package CPU temperature

```python
from acercontrol.sysfs import coretemp_max_package_temp

t = coretemp_max_package_temp()
print(f"CPU package temp (max across packages): {t} °C" if t is not None else "no coretemp")
```

### Example 5: Detect acer_wmi blacklist (CORE-05)

```python
from acercontrol.features import find_blacklist_entries

hits = find_blacklist_entries()  # defaults to /etc/modprobe.d/*.conf
for path, line in hits:
    print(f"  {path}: {line}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setup.py` as primary config | `pyproject.toml` (PEP 621) | PEP 621 (May 2020); setuptools 61 (Mar 2022) deprecated `setup.py` for declarative metadata | Phase 1 lays this groundwork; Phase 8 (`debian/rules` + `pybuild-plugin-pyproject`) depends on it. |
| `tomli` third-party package | `tomllib` (stdlib) | Python 3.11 (Oct 2022) | Justifies the 3.11+ floor — no dep needed for TOML reads. |
| Multiple separate dataclass-like libs | `dataclasses` (stdlib) | Python 3.7 (Jun 2018) | `@dataclass(frozen=True)` is the canonical immutable value object. |
| `typing.Literal["foo"]` requires `typing_extensions` | Stdlib `typing.Literal` | Python 3.8+ | `Severity = Literal[...]` works without extras. |
| `os.path.join` | `pathlib.Path / "subdir"` | Python 3.6+ | Mixed usage acceptable but prefer pathlib at boundaries. |

**Deprecated/outdated (do NOT use in Phase 1):**
- `setup.py` as the only metadata source — use `pyproject.toml`.
- `tomli` package for TOML reads — use stdlib `tomllib`.
- `attrs` for dataclasses — use stdlib `dataclasses`.
- Hardcoded `hwmon7` paths — use `find_hwmon` by name.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All Phase 1 code | (verify on target) | — | If only 3.10 available: bump to 3.11 via apt or pyenv. Project floor is hard-locked. |
| `systemctl` | `features._ppd_active()` | Usually yes on Ubuntu 24.04 (systemd is PID 1) | — | If missing: `_ppd_active()` returns `None` → reported as `info`, not a failure. **Already handled.** |
| `/sys/class/hwmon/` | Sensor probes | Linux kernel guarantee | — | If missing: not on Linux; out of scope. |
| `/sys/firmware/acpi/` | Profile path probe | ACPI kernel surface | — | If `platform_profile` missing: `FeatureCheck` reports it as blocking with a kernel-version fix message. **Already handled.** |
| `/sys/module/acer_wmi/` | Module-loaded probe | Requires `modprobe acer_wmi predator_v4=1` | — | If absent: probe reports it. Phase 2 will offer remediation; Phase 1 just reports state. |
| `acer_wmi` kernel module loaded with `predator_v4=1` | Meaningful integration test of CORE-02..06 | User-confirmed on PHN16-72 (per STATE.md context) | kernel 6.14+ | Without this, library still works (returns degraded `FeatureReport`) — only the *Acer-specific* integration validation needs the real hardware. |

**Missing dependencies with no fallback:** None for Phase 1 — every external interaction is wrapped in defensive error handling.

**Missing dependencies with fallback:** All handled within `_read_or_none` / `subprocess` try-except patterns. The library degrades gracefully on any non-Acer Linux box (useful for development on the macOS host noted in env, via Linux VM).

**Development environment note:** The dev machine (per `<env>` block) is macOS Darwin. Phase 1 library *imports* and unit-level smoke tests will run there because there's no GTK dependency. The full feature probe will report "all blocking checks failed" on macOS — which is the correct, non-crashing behavior. Actual integration validation (CORE-02 returning a real `/sys/class/hwmon/...` path) MUST occur on the Ubuntu 24.04 / PHN16-72 target.

## Validation Architecture

> Required by `workflow.nyquist_validation: true` in `.planning/config.json`. Phase 1 has no CLI/GUI surface — validation is via Python introspection commands a human runs after build.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None — PROJECT.md explicitly excludes automated tests for v1 |
| Config file | none — see Wave 0 |
| Quick run command | `python3 -m acercontrol.features` |
| Full suite command | (none; see Phase Requirements → Validation Commands table below) |

### Phase Requirements → Validation Commands

Each requirement validates via a one-line shell invocation a human can run on the PHN16-72 target. The planner should copy these verbatim into `<acceptance_criteria>` of the Phase 1 plan(s).

| Req ID | Behavior | Validation Type | Command | Pass Criterion |
|--------|----------|-----------------|---------|----------------|
| CORE-01 | Bidirectional, exhaustive profile mapping | unit-level smoke | `python3 -c "from acercontrol.profiles import PROFILES, KERNEL_TO_UI, Profile; assert all(KERNEL_TO_UI[v] == k for k, v in PROFILES.items()); assert set(PROFILES.values()) == {p.value for p in Profile if p is not Profile.CUSTOM}; print('CORE-01 ok')"` | Exit 0, prints `CORE-01 ok` |
| CORE-02 | `find_hwmon` resolves by name, picks most-populated | hardware smoke | `python3 -c "from acercontrol.sysfs import find_hwmon; p = find_hwmon('acer', requires=('fan1_input','temp1_input')); print(p)"` | On PHN16-72: prints a `/sys/class/hwmon/hwmonN` path. On macOS dev: prints `None`. **Never raises.** |
| CORE-02 (drift) | hwmon path is stable across reboots (by name) | hardware UAT | After three reboots, `python3 -c "from acercontrol.sysfs import find_hwmon; print(find_hwmon('acer', requires=('fan1_input','temp1_input')))"` returns a (possibly different `hwmonN`) but always-valid path. | Path is non-None and exists each time. |
| CORE-03 | `features.probe()` returns structured report; no uncaught `FileNotFoundError` | integration smoke | `python3 -m acercontrol.features` | Exit code 0/1/2 depending on environment; prints structured report. **Never tracebacks**, even if `/sys/firmware/acpi/platform_profile` is absent. |
| CORE-03 (degraded) | Renaming sysfs path mid-session degrades the report, not crashes | hardware UAT | `sudo mv /sys/firmware/acpi/platform_profile /sys/firmware/acpi/platform_profile.bak; python3 -m acercontrol.features; sudo mv /sys/firmware/acpi/platform_profile.bak /sys/firmware/acpi/platform_profile` | Probe runs without traceback; reports `platform_profile sysfs: missing`. **Note:** sysfs files cannot actually be renamed — alternative is to test via mocked path or unload `acer_wmi` (which removes its sysfs nodes). |
| CORE-04 | `custom` and unknown values map to `Profile.CUSTOM` | unit-level smoke | `python3 -c "from acercontrol.profiles import Profile, kernel_to_profile; assert kernel_to_profile('custom') is Profile.CUSTOM; assert kernel_to_profile('zzz-undefined') is Profile.CUSTOM; assert kernel_to_profile(None) is Profile.CUSTOM; assert kernel_to_profile('performance') is Profile.TURBO; print('CORE-04 ok')"` | Exit 0, prints `CORE-04 ok` |
| CORE-05 | Blacklist entries in modprobe.d detected | unit-level smoke (no root) | `mkdir -p /tmp/acerctrl-test && printf 'blacklist acer_wmi\n' > /tmp/acerctrl-test/99.conf && python3 -c "from acercontrol.features import find_blacklist_entries; hits = find_blacklist_entries('/tmp/acerctrl-test/*.conf'); assert hits == [('/tmp/acerctrl-test/99.conf', 'blacklist acer_wmi')], hits; print('CORE-05 ok')"` | Exit 0, prints `CORE-05 ok` |
| CORE-05 (variants) | `install acer_wmi /bin/true` form also detected | unit-level smoke | Replace file content with `install acer_wmi /bin/true` — should also match | Returns the line as a hit. |
| CORE-06 | Multi-package coretemp returns max across packages | unit-level smoke (any Linux) | `python3 -c "from acercontrol.sysfs import coretemp_max_package_temp; t = coretemp_max_package_temp(); print(f'coretemp_max={t}')"` | On PHN16-72: prints a plausible float (30–105 °C). On systems with no coretemp: prints `None`. Single-package CPUs: returns the single Package id 0 value. |

### Sampling Rate
- **Per task commit:** `python3 -m acercontrol.features` (must exit cleanly even on dev macOS — degraded report is OK, traceback is not).
- **Per wave merge:** All CORE-01..06 unit-level commands above (the ones that don't require Linux sysfs).
- **Phase gate:** All commands above run on the PHN16-72 target, all green. The "hardware UAT" rows are mandatory before `/gsd-verify-work`.

### Wave 0 Gaps
- [x] No test framework needed — PROJECT.md says no automated tests for v1.
- [ ] `pyproject.toml` must exist before `pip install -e .` works — created as part of Wave 1.
- [ ] `README.md` referenced from `pyproject.toml` — create a one-line stub or drop the key. **Recommend stub** ("# AcerControl\n\nSee `.planning/PROJECT.md`.\n").
- [ ] A short UAT script (`tools/phase1_uat.sh`) that runs the validation commands above and exits non-zero on any failure. **Optional** for the planner — the planner may inline the commands into the plan's acceptance criteria instead.

*If no gaps: "None — existing test infrastructure covers all phase requirements"* → **Not applicable** here; no test infrastructure existed before Phase 1.

## Security Domain

> `security_enforcement` is not explicitly set to `false` in `.planning/config.json`. Phase 1 is a **read-only library** with no user input, no network, no privileged writes, no secrets. The applicable ASVS categories evaluate trivially:

### Applicable ASVS Categories

| ASVS Category | Applies to Phase 1 | Standard Control |
|---------------|---------------------|------------------|
| V2 Authentication | No | (Phase 2 owns the privilege boundary — `pkexec` + polkit policy.) |
| V3 Session Management | No | No sessions. |
| V4 Access Control | No | Read-only; everything Phase 1 reads is world-readable kernel sysfs. |
| V5 Input Validation | Minimal | The only "input" is data read from `/sys` and `/etc/modprobe.d/*.conf`. Strings stripped, regex-anchored, integer conversions in try/except. **No shell interpolation anywhere** — `subprocess.run` uses list form. |
| V6 Cryptography | No | No crypto in this phase. |
| V12 Files and Resources | Yes (minor) | All file paths are constants (kernel sysfs) or sourced from a fixed glob; no user-controlled paths. |

### Known Threat Patterns for stdlib-only Python on sysfs

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via user input | Tampering | Not applicable — Phase 1 takes no user-controlled paths. The blacklist scan glob is hardcoded; tests can pass a custom pattern but they're trusted. |
| Shell injection via `subprocess` | Tampering | All `subprocess.run` calls use the list-of-args form (`["systemctl", "is-active", ...]`) — never a shell string. Verified in code skeleton above. |
| Untrusted YAML/pickle deserialization | Tampering | None used. Sysfs reads are plain text; no deserializers. |
| Resource exhaustion via malformed sysfs | DoS | `subprocess.run(..., timeout=2)` bounds the one external call. File reads of sysfs attributes are bounded by their natural size (typically < 4 KB). |
| Information disclosure via logs | Disclosure | Phase 1 logs nothing. Adding logging is a Phase 3+ concern. |

**Bottom line:** No new privilege surface. No new attack surface. No secrets to protect. Security review is N/A for Phase 1 *implementation* but mandatory for Phase 2 when `privilege.py` + the helper binaries land.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `enum.Enum` with `.value` = kernel string + `.display` property is more idiomatic than `dataclasses.dataclass(frozen=True)` for `Profile` | Pattern 1 | If wrong: codebase is mildly noisier than it could be; not behavior-affecting. **Low risk.** |
| A2 | "Most populated" = count of files matching `(fan|temp|in|curr|power)[0-9]+_input` | sysfs.py | If a future kernel introduces a new hwmon input class (e.g. `pwm[0-9]+_input`) we'd undercount it. Unlikely for the `acer`/`coretemp` use case. **Low risk.** |
| A3 | Caching `find_hwmon` results across the library's lifetime is safe (single-threaded contract) | sysfs.py | If Phase 5 ever spawns a real worker thread (it won't per SUMMARY.md decision #3), unguarded mutation of `_hwmon_cache` would be racy. Documented in the docstring; revisit if threading is reintroduced. **Low risk.** |
| A4 | `subprocess.run(["systemctl", "is-active", ...], timeout=2)` is fast enough for the probe (typically < 100 ms) | features.py `_ppd_active` | If `systemd` is hung, the probe blocks for 2 s. Acceptable since the probe runs once at startup. **Low risk.** |
| A5 | Severity as `Literal["blocking", "warning", "info"]` (string) is preferable to `enum.Enum` for JSON-serializability | features.py | A future Diagnostics export (D-11) might prefer enum for type safety — trivial to swap. **Negligible risk.** |
| A6 | `find_blacklist_entries` regex covers the meaningful blacklist forms (`blacklist acer_wmi`, `install acer_wmi /bin/true`, `install acer_wmi /bin/false`) | features.py | Other obscure forms (`alias acer_wmi off`, custom modprobe scripts) would be missed. Acceptable per P17 priority (LOW). **Low risk.** |
| A7 | `Profile.CUSTOM` enum member with `.value = "custom"` cleanly handles the kernel's documented `custom` value AND serves as a sentinel for any unmapped value | profiles.py | If a future kernel uses `custom` to mean something other than "drivers disagree", semantics shift — but the `[CITED]` source above documents this is the intent. **Very low risk.** |
| A8 | Single-threaded contract for Phase 1 callers (no GIL contention concerns, no need for `threading.Lock` on `_hwmon_cache`) | sysfs.py | Holds because SUMMARY.md decision #3 (sensors via `GLib.timeout_add_seconds`, not a worker thread) is locked. If Phase 5 reverses that, add a `threading.Lock` around the cache mutations. **Low risk, documented.** |

**Confirmation needed from user/PHN16-72 maintainer:** A2, A6 — could be tightened with real `/sys/class/hwmon/*` listings from the target machine.

## Open Questions

1. **Does `tools/phase1_uat.sh` belong in this phase or Phase 2?**
   - What we know: Validation commands are documented; planner can inline them into acceptance criteria.
   - What's unclear: Whether a committed shell script is the right form, or whether per-task `python3 -c` blocks suffice.
   - Recommendation: **Inline `python3 -c` in plan tasks for Phase 1.** Commit a script in Phase 2 when the CLI ships and `acercontrol status` is a one-command UAT.

2. **Should `README.md` be created in Phase 1 (as a stub) or in Phase 8?**
   - What we know: `pyproject.toml` references `readme = "README.md"`; setuptools warns if missing.
   - What's unclear: Whether a stub now creates a documentation maintenance burden, or whether deferring creates a packaging-time scramble.
   - Recommendation: **Create a one-paragraph stub in Phase 1.** Two sentences ("AcerControl: Linux performance control for Acer Predator/Nitro. See `.planning/PROJECT.md` for project overview.") is enough to satisfy setuptools and the future `dpkg-buildpackage` build.

3. **`core.py` vs `__init__.py` for re-exports — which one should the CLI/GUI import?**
   - What we know: Both work; `core.py` is the established name from CLAUDE.md, `__init__.py` is the standard Python idiom.
   - What's unclear: Which call-site path the planner should use in Phase 2 plans (`from acercontrol import read_profile` vs `from acercontrol.core import read_profile`).
   - Recommendation: **Both work, both are exported.** Convention: `from acercontrol import X` for the canonical public API; `from acercontrol.core import X` is also fine and identical. Document in Phase 2 planning that either form is acceptable.

4. **Does the kernel's `cool` profile (documented in sysfs-platform_profile) need handling?**
   - What we know: Kernel docs list `low-power | cool | quiet | balanced | balanced-performance | performance` as valid values. PROFILES (per CLAUDE.md and REQUIREMENTS.md) does NOT include `cool`.
   - What's unclear: Whether `cool` appears in `platform_profile_choices` on any acer_wmi predator_v4 hardware.
   - Recommendation: **Defer to runtime detection.** `available_profiles(PROFILE_CHOICES_PATH)` already filters by what the kernel exposes; if a future hardware variant exposes `cool`, it would map to `Profile.CUSTOM` (the planner can decide later whether to add a `Profile.COOL` member). Out of scope for Phase 1.

## Sources

### Primary (HIGH confidence)
- **Kernel ABI documentation** — `https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-platform_profile` — verified the `custom` value is officially documented (raised CORE-04 confidence to HIGH).
- **PROJECT.md** — `/Users/sushilkumarsahani/Desktop/AcerControl/.planning/PROJECT.md` — scope, constraints, key decisions.
- **REQUIREMENTS.md** — `/Users/sushilkumarsahani/Desktop/AcerControl/.planning/REQUIREMENTS.md` — Phase 1 requirements CORE-01..06 verbatim.
- **ROADMAP.md** — Phase 1 success criteria + pitfall mitigation list.
- **research/STACK.md** — Python version floor, setuptools/PEP 621 layout, stdlib-only constraint.
- **research/ARCHITECTURE.md** — Module split (`core.py`/`sysfs.py`/`profiles.py`/`features.py`), single-source-of-truth invariant, `acercontrol/` package boundary.
- **research/PITFALLS.md** — P4/P6/P13/P16/P17 detailed mitigations + manual UAT items.
- **research/SUMMARY.md** — 8-phase build order, decision #3 (no sensor thread), TL;DR locked architecture.

### Secondary (MEDIUM confidence)
- **CLAUDE.md** — original profile mapping, sysfs path constants. Treated as draft; explicit overrides noted in Project Constraints table.

### Tertiary (LOW confidence)
- None for Phase 1 — every claim above is either kernel-spec verifiable or inherited from upstream HIGH-confidence research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — locked by STACK.md; Phase 1 deps are stdlib-only.
- Architecture: HIGH — locked by ARCHITECTURE.md; Phase 1 modules are a strict subset of the documented split.
- Pitfalls: HIGH — five mitigations (P4, P6, P13, P16, P17) all have concrete code skeletons above.
- Profile mapping (CORE-04 specifically): HIGH (raised from MEDIUM after kernel.org WebFetch verification).
- Validation commands: HIGH — every CORE requirement maps to a single concrete `python3 -c` invocation.

**Research date:** 2026-05-14
**Valid until:** 2026-06-13 (30-day default for a stable read-only library layer)

---

## Files-to-Create List (for the planner)

The planner should generate plan tasks that create exactly these files, in this dependency order. All paths absolute. All content sketched in the Patterns section above.

| # | Absolute Path | Purpose | LOC est. | Depends on |
|---|---------------|---------|----------|------------|
| 1 | `/Users/sushilkumarsahani/Desktop/AcerControl/README.md` | One-paragraph project stub referenced by `pyproject.toml` | ~5 | — |
| 2 | `/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml` | PEP 621 metadata, setuptools backend, `requires-python>=3.11`, **NO `[project.scripts]`** (Phase 2 adds those) | ~25 | #1 |
| 3 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/profiles.py` | `Profile` enum, `PROFILES`, `KERNEL_TO_UI`, `kernel_to_profile`, `current_profile_ui`, `available_profiles` | ~70 | #2 |
| 4 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/sysfs.py` | `_read_or_none`, `find_hwmon`, `find_all_hwmon`, `invalidate_hwmon_cache`, `coretemp_max_package_temp`, `read_acer_sensors` | ~140 | #2 |
| 5 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/core.py` | Path constants, `read_profile`, `read_sensors`, `SensorReading` dataclass | ~70 | #3, #4 |
| 6 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/features.py` | `FeatureCheck`, `FeatureReport`, `probe()`, `find_blacklist_entries`, `_ppd_active`, `__main__` smoke entry | ~140 | #4, #5 |
| 7 | `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/__init__.py` | Re-exports + `__version__` | ~40 | #3, #4, #5, #6 |

**Total: ~490 LOC across 7 files.** A single agent can deliver this as one wave; alternatively, the planner can split into two waves (waves intentionally not prescribed here — that's the planner's job).

## Smoke Test Section (for the planner's `<acceptance_criteria>`)

After all 7 files exist:

```bash
# 1. Module imports cleanly (works on macOS dev or Linux target)
cd /Users/sushilkumarsahani/Desktop/AcerControl
PYTHONPATH=. python3 -c "import acercontrol; print(f'acercontrol {acercontrol.__version__} OK')"
# Expected: prints "acercontrol 0.1.0.dev0 OK", exits 0

# 2. CORE-01: profile mapping bidirectional and exhaustive
PYTHONPATH=. python3 -c "
from acercontrol.profiles import PROFILES, KERNEL_TO_UI, Profile
assert all(KERNEL_TO_UI[v] == k for k, v in PROFILES.items()), 'CORE-01 reverse map drift'
assert set(PROFILES.values()) == {p.value for p in Profile if p is not Profile.CUSTOM}, 'CORE-01 enum mismatch'
print('CORE-01 ok')
"

# 3. CORE-02: find_hwmon returns path-or-None, never raises
PYTHONPATH=. python3 -c "
from acercontrol.sysfs import find_hwmon
result = find_hwmon('acer', requires=('fan1_input','temp1_input'))
print(f'CORE-02: find_hwmon returned {result!r}')
"
# Expected on PHN16-72: prints a /sys/class/hwmon/hwmonN path
# Expected on macOS:    prints None
# In both cases:        exits 0, no traceback

# 4. CORE-03: probe() returns FeatureReport, no FileNotFoundError
PYTHONPATH=. python3 -m acercontrol.features
# Expected: structured human-readable report; exit code 0/1/2 (not traceback)

# 5. CORE-04: 'custom' and unknown values map to Profile.CUSTOM
PYTHONPATH=. python3 -c "
from acercontrol.profiles import Profile, kernel_to_profile
assert kernel_to_profile('custom') is Profile.CUSTOM
assert kernel_to_profile('zzz-undefined') is Profile.CUSTOM
assert kernel_to_profile(None) is Profile.CUSTOM
assert kernel_to_profile('performance') is Profile.TURBO  # turbo, not 'PERFORMANCE' user-string
assert kernel_to_profile('balanced-performance') is Profile.PERFORMANCE  # the UI 'performance' label
print('CORE-04 ok')
"

# 6. CORE-05: blacklist detection
mkdir -p /tmp/acerctrl-test
printf 'blacklist acer_wmi\n' > /tmp/acerctrl-test/99.conf
PYTHONPATH=. python3 -c "
from acercontrol.features import find_blacklist_entries
hits = find_blacklist_entries('/tmp/acerctrl-test/*.conf')
assert hits == [('/tmp/acerctrl-test/99.conf', 'blacklist acer_wmi')], hits
print('CORE-05 ok')
"
rm -rf /tmp/acerctrl-test

# 7. CORE-06: coretemp max-across-packages
PYTHONPATH=. python3 -c "
from acercontrol.sysfs import coretemp_max_package_temp
t = coretemp_max_package_temp()
print(f'CORE-06: coretemp_max={t}')
# On Linux with coretemp: a plausible float (10-105). On macOS: None.
# Both acceptable — no raise.
"

# 8. Editable install works (the foundation for Phase 2's CLI entry point)
pip install -e . --quiet
python3 -c "from acercontrol import probe; print(type(probe()).__name__)"  # → 'FeatureReport'
```

**Hardware-only UAT (run on PHN16-72 after all above pass):**

```bash
# 9. find_hwmon returns valid Acer path
PYTHONPATH=. python3 -c "
from acercontrol.sysfs import find_hwmon
import os
p = find_hwmon('acer', requires=('fan1_input','temp1_input'))
assert p is not None, 'CORE-02 failed on real hardware'
assert os.path.isdir(p), f'{p} is not a directory'
print(f'CORE-02 hardware: {p}')
"

# 10. probe() reports ok=True on a properly configured PHN16-72
PYTHONPATH=. python3 -c "
from acercontrol.features import probe
r = probe()
print(f'report.ok = {r.ok}')
for c in r.checks:
    print(f'  {\"OK \" if c.present else \"FAIL\"}  {c.name}: {c.detail}')
"

# 11. Degraded-report behavior: unload acer_wmi, probe must NOT raise
sudo modprobe -r acer_wmi
PYTHONPATH=. python3 -m acercontrol.features  # MUST exit non-zero but NOT traceback
sudo modprobe acer_wmi predator_v4=1  # restore
```

If steps 1–11 all pass (steps 9–11 on hardware only), Phase 1 is **DONE** and Phase 2 can begin.
