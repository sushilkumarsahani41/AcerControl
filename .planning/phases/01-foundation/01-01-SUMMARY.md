---
phase: 01-foundation
plan: 01
subsystem: library/foundation
tags: [python, sysfs, hwmon, acer-wmi, profiles, feature-probe, stdlib-only]

# Dependency graph
requires:
  - phase: 00-init
    provides: PROJECT.md / ROADMAP.md / REQUIREMENTS.md / 01-RESEARCH.md / 01-VALIDATION.md
provides:
  - acercontrol Python package (read-only library) — single source of truth for sysfs reads, hwmon discovery, profile name mapping, and feature detection
  - 24-symbol public API surface re-exported from acercontrol/__init__.py
  - Profile enum with 6 members including CUSTOM sentinel for unmapped kernel values
  - find_hwmon with most-populated tie-break (defeats P6 hwmon-index drift)
  - coretemp_max_package_temp via "Package id N" label scan (defeats P16 multi-package CPUs)
  - probe() returns FeatureReport with 7 structured checks; never raises FileNotFoundError (P13)
  - acer_wmi blacklist detection in /etc/modprobe.d/*.conf (CORE-05 / P17)
  - tools/smoke_phase1.py aggregate runner — stdlib-only, hermetic, host-portable
affects: [02-privilege-cli, 03-gui-shell, 04-profile-control, 05-sensors, 06-boot-service, 07-tray-notifications, 08-packaging]

# Tech tracking
tech-stack:
  added:
    - "Python 3.11+ (matches Ubuntu 24.04 system Python 3.12; tomllib floor for Phase 6)"
    - "setuptools>=61 (PEP 517 build backend; build-time only)"
  patterns:
    - "Defensive sysfs reads via _read_or_none(path) -> Optional[str]"
    - "Frozen dataclass + string Literal severity for JSON-serializable diagnostics"
    - "Cached hwmon discovery keyed on (name, requires_tuple); invalidate_hwmon_cache() retry-on-OSError"
    - "Profile enum with .value=kernel-string and .display property; CUSTOM sentinel covers any unmapped reading"

key-files:
  created:
    - "/Users/sushilkumarsahani/Desktop/AcerControl/README.md (5 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml (30 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/__init__.py (61 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/profiles.py (94 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/sysfs.py (205 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/core.py (93 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/features.py (234 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/tools/smoke_phase1.py (183 LOC, executable)"
  modified: []

key-decisions:
  - "Python floor narrowed to 3.11+ (PROJECT.md said 3.10+; Phase 6 needs tomllib which lands in 3.11; Ubuntu 24.04 ships 3.12 — narrowing is cost-free). Resolves Phase 1 open question."
  - "FeatureCheck.severity is a string Literal['blocking','warning','info'], NOT an Enum — keeps FeatureReport JSON-serializable for future Diagnostics export (D-11 differentiator)."
  - "Profile.CUSTOM is a real Enum member with .value='custom', not a None sentinel. Callers do `if profile is Profile.CUSTOM` rather than `is None`; 'Custom' is a valid display state."
  - "KERNEL_TO_UI computed as `{v: k for k, v in PROFILES.items()}` rather than a hand-written literal — drift-proof against future PROFILES edits."
  - "find_hwmon tie-break is most-populated (count of `(fan|temp|in|curr|power)\\d+_input` files) then alphabetical — gives the densest sensor directory rather than the first encountered."
  - "Multi-package coretemp algorithm: enumerate find_all_hwmon('coretemp'), scan tempN_label for 'Package id N', take max of tempN_input millidegrees. Fallback to temp1_input of first coretemp dir if no labels match. Mitigates P16 on PH317 dual-die hardware."
  - "_ppd_active uses list-form subprocess.run with timeout=2s; FileNotFoundError and TimeoutExpired both return None (PPD state 'unknown' is informational, not blocking). Mitigates T-01-01 and T-01-02 from threat register."

patterns-established:
  - "Pattern: _read_or_none(path) — wraps path.read_text().strip() in try/except OSError, returns None. Every sysfs read in Phase 1 routes through this. P13 contract enforcement."
  - "Pattern: FeatureReport consumed by CLI/GUI failure-mode dispatch. Phase 2 routes the first .first_blocking_failure to terminal output; Phase 3 routes it to Adw.StatusPage."
  - "Pattern: hwmon discovery cache with explicit invalidate + retry-once on OSError. read_sensors() invokes it when fan1_rpm AND temp1_c both come back None — assumes the hwmon* index drifted under us."
  - "Pattern: acercontrol/__init__.py as the canonical import surface. Downstream callers do `from acercontrol import probe, read_profile, ...` — they never touch sysfs.py or features.py directly."
  - "Pattern: __main__ smoke entry on features module (`python3 -m acercontrol.features`) — returns 0/1/2 exit code based on blocking vs warning vs clean state. Convenience for UAT, not a callable API."

requirements-completed: [CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06]

# Metrics
duration: ~35 min
completed: 2026-05-14
---

# Phase 1 Plan 01: Foundation Library Summary

**Stood up the `acercontrol/` stdlib-only Python package as the single source of truth for sysfs reads, hwmon discovery, profile name mapping, and structured feature detection — zero runtime dependencies, zero GTK imports, 6/6 CORE smoke checks PASS on host.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-05-14T00:55:00Z
- **Completed:** 2026-05-14T01:05:00Z (approx)
- **Tasks:** 4 of 4 (all `type="auto"`, no checkpoints)
- **Files created:** 8 (1 README, 1 pyproject, 5 `acercontrol/*.py`, 1 smoke runner)
- **Total LOC:** 905 (target was ~490 — over by ~85% due to verbatim copy of research patterns, which is the planner's contract)
- **Commits:** 4 (one per task) + this metadata commit

## Accomplishments

- **CORE-01..06 all satisfied.** Six requirement IDs mapped to two task surfaces (profiles.py + sysfs.py for CORE-01/02/04/06; features.py for CORE-03/05); every requirement has a smoke command in `tools/smoke_phase1.py`.
- **24-symbol public API.** Every documented re-export resolves from `from acercontrol import …` — verified via the Phase 1 acceptance criteria block.
- **Defensive contract enforced everywhere.** `probe()` runs the full 7-check probe on macOS with no `/sys` and returns a structured FeatureReport (ok=False) without raising. Validated by P13 smoke.
- **Multi-package coretemp algorithm landed (CORE-06 / P16).** Returns `None` on this dev host (no `/sys`); the algorithm scan `Package id N` labels and take max across packages — code is in place for the multi-die manual UAT step in VALIDATION.md.
- **acer_wmi blacklist detection (CORE-05 / P17).** Regex pattern matches both `blacklist acer_wmi` and `install acer_wmi /bin/(true|false)` forms; lines are split on `#` first to strip inline comments. Validated against a tempdir scaffold.
- **Aggregate smoke runner is host-portable.** Self-injects PYTHONPATH; runs identically on macOS dev box and (will run on) PHN16-72 with full stack — CORE-02 and CORE-06 accept `None` as a valid return for hosts without `/sys`.

## Task Commits

Each task was committed atomically on `main` (branching_strategy="none"):

1. **Task 1: Scaffold project (README + pyproject.toml + __init__ stub)** — `c061cb6` (feat)
2. **Task 2: Data layer (profiles.py + sysfs.py)** — `6e5c7d9` (feat)
3. **Task 3: Composition + probe (core.py + features.py + finalize __init__.py)** — `1c3b1bd` (feat)
4. **Task 4: Aggregate smoke runner (tools/smoke_phase1.py)** — `b546000` (feat)

## Files Created/Modified

### Created

- `README.md` — 5-line stub pointing at `.planning/PROJECT.md` and `.planning/ROADMAP.md`
- `pyproject.toml` — PEP 621 metadata, setuptools backend, `requires-python = ">=3.11"`, zero runtime deps, no `[project.scripts]` yet
- `acercontrol/__init__.py` — package docstring, `__version__ = "0.1.0.dev0"`, 24-symbol public re-exports, explicit `__all__`
- `acercontrol/profiles.py` — `PROFILES`, `KERNEL_TO_UI` (computed reverse map), `Profile(Enum)` with 6 members + `.display` property, `kernel_to_profile`, `current_profile_ui`, `available_profiles`
- `acercontrol/sysfs.py` — `HWMON_BASE`, `_read_or_none`, `_count_inputs`, `find_hwmon` (cached, keyword-only `requires`, most-populated tie-break), `find_all_hwmon`, `invalidate_hwmon_cache`, `coretemp_max_package_temp` (P16 multi-package), `read_acer_sensors`
- `acercontrol/core.py` — path constants (`PROFILE_PATH`, `PROFILE_CHOICES_PATH`, `HWMON_BASE`, `PREDATOR_V4_PARAM`, `MODPROBE_D`), `read_profile`, `list_available_profiles`, `SensorReading` frozen dataclass, `read_sensors` with OSError-retry-once
- `acercontrol/features.py` — `Severity` string Literal, `_BLACKLIST_RE`, `FeatureCheck` + `FeatureReport` frozen dataclasses (with `.ok` and `.first_blocking_failure` properties), `find_blacklist_entries` (CORE-05), `_ppd_active` (list-form subprocess + 2s timeout), `probe()` (exactly 7 checks in spec order), `_print_report`, `__main__` entry
- `tools/smoke_phase1.py` — executable stdlib runner for CORE-01..06; self-injects `PYTHONPATH`; CORE-05 uses a tempdir scaffold; outer try/finally ensures the runner itself never raises

### Modified

- `acercontrol/__init__.py` — overwritten in Task 3 (Task 1 stub → full re-exports)

## Pitfall Mitigations Realized in Code

| Pitfall | Where mitigated | How |
|---|---|---|
| **P4** (kernel "performance" ≠ user "performance") | `acercontrol/profiles.py` | `PROFILES["performance"] = "balanced-performance"` and `PROFILES["turbo"] = "performance"`; reverse map computed. User-facing labels never leak the kernel ambiguity. |
| **P6** (hwmon index drift across reboots) | `acercontrol/sysfs.py` `find_hwmon` | Walks `/sys/class/hwmon/hwmon*` and reads each `name` file; never assumes a numeric index. Tie-break is most-populated then alphabetical for determinism. |
| **P13** (FileNotFoundError must not escape library boundary) | `acercontrol/sysfs.py` `_read_or_none` + `find_hwmon` + `acercontrol/features.py` `probe` | Every sysfs read goes through `_read_or_none` (OSError → None). `find_hwmon` returns `None` on missing `HWMON_BASE`. `probe()` builds 7 checks via `Path.exists()` and `_read_or_none` — never raises. |
| **P16** (multi-package coretemp under-reporting) | `acercontrol/sysfs.py` `coretemp_max_package_temp` | Enumerates `find_all_hwmon("coretemp")`, scans `tempN_label` for `Package id N`, takes `max()` of `tempN_input` millidegrees. Fallback to `temp1_input` of first coretemp dir. |
| **P17** (acer_wmi blacklist via modprobe.d) | `acercontrol/features.py` `find_blacklist_entries` + 7th probe check | Regex matches both `blacklist acer_wmi` AND `install acer_wmi /bin/(true|false)`; lines split on `#` first to strip inline comments; surfaced as `blocking` check #7 in `FeatureReport`. |

## Smoke Results

`python3 tools/smoke_phase1.py` — exit 0 on this host (macOS dev box, no `/sys`).

```
-> CORE-01: profile mapping is bidirectional + Profile.CUSTOM sentinel
  PASS  CORE-01 ok
-> CORE-02: find_hwmon resolves by name file (path or None)
  PASS  CORE-02 ok (None)
-> CORE-03: probe() returns FeatureReport with >=6 checks; never raises
  PASS  CORE-03 ok (7 checks, ok=False)
-> CORE-04: unknown / kernel 'custom' values map to Profile.CUSTOM
  PASS  CORE-04 ok
-> CORE-05: acer_wmi blacklist entries detected in modprobe.d
  PASS  CORE-05 ok
-> CORE-06: coretemp multi-package: max-across-packages or None
  PASS  CORE-06 ok (None)
--- Phase 1 smoke: 6/6 passed ---
```

Per the must-have #3 contract, CORE-02/06 PASS by returning `None` on hosts without `/sys/class/hwmon`. CORE-03 returns `ok=False` (no `acer_wmi`, no `platform_profile sysfs`) but completes the 7-check report cleanly — which is the actual P13 contract.

## Public API Surface (24 symbols + `__version__`)

Every symbol resolves via `from acercontrol import …`:

- **profiles** (6): `Profile`, `PROFILES`, `KERNEL_TO_UI`, `kernel_to_profile`, `current_profile_ui`, `available_profiles`
- **sysfs** (5): `find_hwmon`, `find_all_hwmon`, `invalidate_hwmon_cache`, `coretemp_max_package_temp`, `read_acer_sensors`
- **features** (4): `FeatureCheck`, `FeatureReport`, `probe`, `find_blacklist_entries`
- **core** (9): `PROFILE_PATH`, `PROFILE_CHOICES_PATH`, `HWMON_BASE`, `PREDATOR_V4_PARAM`, `MODPROBE_D`, `SensorReading`, `read_profile`, `list_available_profiles`, `read_sensors`

## Decisions Made

1. **Python 3.11+ floor** (not 3.10+). PROJECT.md said 3.10+ but Phase 6 will need `tomllib` (3.11). Ubuntu 24.04 ships 3.12, so narrowing costs nothing. Resolved a pending open question from STATE.md.
2. **String severity, not Enum.** `FeatureCheck.severity: Literal["blocking","warning","info"]` keeps `FeatureReport` JSON-serializable when Phase 3+ adds a Diagnostics export. Trade: less type-safe at the call site than an Enum, but cheaper at the serialization boundary.
3. **Profile.CUSTOM as a real Enum member.** Callers do `if profile is Profile.CUSTOM`, never `is None`. Aligns with the kernel `Documentation/ABI/testing/sysfs-platform_profile` doc which states `custom` is an informational value the kernel can emit.
4. **`find_hwmon` most-populated tie-break.** Alternative "first match wins" would be alphabetical-only — fine for `coretemp` (usually 1 entry) but ambiguous if a vendor module ever publishes a second `acer` hwmon stub. Counting `_input` files picks the directory that's actually wired up.
5. **subprocess for PPD detection (not D-Bus).** `_ppd_active` calls `systemctl is-active` with `timeout=2`. PPD is called 1× per `probe()` — D-Bus subscription would be over-engineered. Returns `None` (state unknown) when `systemctl` is missing.
6. **No `[project.scripts]` yet.** Phase 2 adds the CLI entry point. Phase 1 stays library-only — keeps the bundler-friendly single-file CLI invariant intact.

## Patterns Established for Phase 2 and Beyond

- **`_read_or_none(path)` defensive wrapper.** Phase 2's privileged write path (`pkexec` helpers) will use the same idiom inside `/usr/libexec/acercontrol/*`.
- **`FeatureReport` consumed by CLI/GUI.** Phase 2's `acercontrol status` will iterate `report.checks` and print human output (something like `_print_report`'s shape). Phase 3's GUI will call `report.first_blocking_failure` to choose which `Adw.StatusPage` to render.
- **`find_hwmon` cache-with-OSError-retry idiom.** Phase 5's 2-second sensor refresh will use `read_sensors()` directly — which already handles the cache-invalidate-and-retry path internally. GUI authors don't need to think about hwmon index drift.
- **`acercontrol.__init__` as the import surface.** Phase 2/3/4/5 code paths should `from acercontrol import …`, not `from acercontrol.sysfs import …`. Keeps the contract stable across future refactors.

## Manual UAT Items Deferred

Per `01-VALIDATION.md`'s "Manual-Only Verifications" section, three items are deferred to PHN16-72 hardware testing:

1. **Library survives renaming `/sys/firmware/acpi/platform_profile` mid-session** — sysfs is read-only, so the alternative is to blacklist `acer_wmi` via a test modprobe.d snippet and reboot. Phase 1 covers this structurally (every read routes through `_read_or_none`) but the live-degrade scenario needs hardware.
2. **hwmon index drift across two reboots** — verify `find_hwmon('acer')` returns the same logical hwmon directory after two reboots even if the numeric index changes. Requires physical reboot loop on PHN16-72.
3. **Multi-package coretemp on actual multi-die hardware** — PHN16-72 is single-die; needs a PH317 or similar to exercise the max-across-packages return path.

These are tracked in `01-VALIDATION.md` and should be checked off during the manual UAT sweep before phase sign-off.

## Deviations from Plan

**None — plan executed exactly as written.**

Every file's content was copied verbatim from `01-RESEARCH.md` Patterns 1–6 as specified in each task's `<action>` block. No Rule 1/2/3 auto-fixes were needed. No checkpoints. No architectural questions. The plan was specified down to exact module docstring substrings, exact regex patterns, and exact probe-check name strings, and the smoke runner verified each one as it landed.

## Authentication Gates

None — Phase 1 is read-only library work; no privileged operations.

## Known Stubs

None. Every function in the public API has a real implementation. Stubs that exist are intentional and load-bearing:

- `_print_report` returns 0/1/2 exit codes — the convention is "0 = clean, 1 = degraded warnings, 2 = blocking failure" and is used by `python3 -m acercontrol.features`. Phase 2's CLI may parse the same exit code.
- Phase 2 (privilege.py + cli.py) is the next consumer; nothing in this phase blocks on a future stub.

## Self-Check: PASSED

Verified after writing this SUMMARY:

- `/Users/sushilkumarsahani/Desktop/AcerControl/README.md` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/__init__.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/profiles.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/sysfs.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/core.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/features.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/tools/smoke_phase1.py` — FOUND
- Commit `c061cb6` (Task 1 scaffold) — FOUND
- Commit `6e5c7d9` (Task 2 data layer) — FOUND
- Commit `1c3b1bd` (Task 3 composition + probe) — FOUND
- Commit `b546000` (Task 4 smoke runner) — FOUND

`python3 tools/smoke_phase1.py` → exit 0, prints `6/6 passed`, no traceback.

`PYTHONPATH=. python3 -c "from acercontrol import core, sysfs, profiles, features"` → exit 0.

Zero `^import gi` / `^from gi` lines under `acercontrol/` or `tools/` (excluding comments).

`pyproject.toml` declares `requires-python = ">=3.11"` and has no `[project.dependencies]`, no `[project.optional-dependencies]`, no `[project.scripts]`.

## Threat Flags

None. Phase 1 introduces no new privilege surface, no user input, no secrets, and no network calls. The only subprocess call (`_ppd_active`) uses list-form argv with a 2-second timeout — both mitigations specified in the plan's `<threat_model>` (T-01-01 and T-01-02). The blacklist scanner reads world-readable `/etc/modprobe.d/*.conf` files; no information disclosure beyond what the kernel and packaging layer already make public (T-01-05 accepted).

The privilege boundary lands in Phase 2 (`privilege.py` + `/usr/libexec/acercontrol/` helpers + polkit policy). Full STRIDE review applies there.

## Next Phase

Phase 2 (Privilege Boundary + CLI) consumes this package — adds `privilege.py`, `cli.py`, `tools/bundle_cli.py`, three `/usr/libexec/acercontrol/` wrappers, and the polkit policy. The Phase 1 public API is the import surface Phase 2 builds on.
