---
phase: 07-tray-helper-hardware-compatibility
plan: 01
subsystem: tray-status
tags: [tray, statusnotifier, diagnostics, smoke-runner]

requires:
  - phase: 06-03
    provides: "Phase 6 boot persistence and resume reapply completion"
provides:
  - "Phase 7 side-effect-free smoke runner"
  - "GTK-version-neutral StatusNotifierWatcher availability detector"
  - "About diagnostics tray availability field without importing GTK3 tray code"
affects: [phase-07-tray-helper-hardware-compatibility, gui-diagnostics, tray]

tech-stack:
  added: []
  patterns:
    - "Gio-only session-bus query for org.kde.StatusNotifierWatcher"
    - "Tray availability reported as stable strings instead of raised exceptions"
    - "GTK4 GUI may import tray_status but never acercontrol.tray"

key-files:
  created:
    - "tools/smoke_phase7.py"
    - "acercontrol/tray_status.py"
    - ".planning/phases/07-tray-helper-hardware-compatibility/07-01-SUMMARY.md"
  modified:
    - "acercontrol/gui_about.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "The tray status helper imports Gio only and never requires Gtk, Adw, or Ayatana."
  - "Missing session bus, missing Gio, and absent StatusNotifierWatcher are graceful diagnostic states."
  - "The About dialog carries tray status through set_debug_info(), preserving the GUI/GTK3 process boundary."
  - "Phase 7 smoke checks are side-effect-free and can run on hosts without GTK typelibs or Acer hardware."

patterns-established:
  - "tools/smoke_phase7.py stages later helper, packaging, and hardware checks until their files exist."
  - "tray_status_detail() returns a dict with status, watcher, and detail for diagnostics."
  - "CLI bundler and GTK4 GUI isolation checks are enforced before the tray helper exists."

requirements-completed: [TRAY-02]

duration: 8 min
completed: 2026-05-23
---

# Phase 7 Plan 01: Tray Status Substrate Summary

Phase 7 now has a safe tray availability substrate. The GTK4 GUI can report whether a StatusNotifierWatcher is available without importing the future GTK3/Ayatana helper process.

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-23T01:23:00+05:30
- **Completed:** 2026-05-23T01:31:13+05:30
- **Tasks:** 4
- **Files changed:** 6

## Accomplishments

- Added `tools/smoke_phase7.py`, a side-effect-free Phase 7 smoke runner with quick/full modes and staged future checks.
- Added `acercontrol/tray_status.py` with Gio-only `StatusNotifierWatcher` detection and stable statuses: `available`, `missing-watcher`, `no-session-bus`, and `unknown`.
- Updated `acercontrol/gui_about.py` so About diagnostics include a top-level `"tray"` field from `tray_status_detail()`.
- Ran the 07-01 regression pass across Phase 1, Phase 2, Phase 3, and Phase 7 smoke gates.

## Task Commits

1. **Task 1: Phase 7 smoke runner wave 0** - `b8a49de`
2. **Task 2: Add tray availability detector** - `aeb43a5`
3. **Task 3: Add tray status to About diagnostics** - `2023406`
4. **Task 4: 07-01 regression pass** - no code changes; verification recorded below.

## Files Created/Modified

- `tools/smoke_phase7.py` - Phase 7 source/static smoke runner.
- `acercontrol/tray_status.py` - Gio-only session watcher detector.
- `acercontrol/gui_about.py` - About diagnostics tray field.
- `.planning/phases/07-tray-helper-hardware-compatibility/07-01-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- `tray_status.py` treats StatusNotifierWatcher absence as `missing-watcher`, not an error.
- Gio import/session-bus failures return `unknown` or `no-session-bus` details instead of raising.
- The About dialog imports `acercontrol.tray_status` only; `acercontrol.tray` remains isolated for the separate GTK3 process in 07-02.
- The smoke runner uses source/static checks and temp fixtures only, so it remains safe on macOS and CI-like hosts.

## Deviations from Plan

None.

---

**Total deviations:** 0.
**Impact on plan:** None.

## Issues Encountered

- Native session-bus StatusNotifierWatcher behavior cannot be exercised on this macOS host. Verification here is source/static plus Python compilation.

## Verification Results

- `python3 -m py_compile acercontrol/tray_status.py` -> passed.
- `python3 -m py_compile acercontrol/gui_about.py acercontrol/tray_status.py tools/smoke_phase7.py` -> passed.
- `python3 tools/smoke_phase7.py --quick` -> 6/6 passed.
- `python3 tools/smoke_phase3.py` -> 18/18 passed, retaining the existing editable-install console-script skip.
- `python3 tools/smoke_phase7.py` -> 9/9 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase7.py` -> passed.

## Human UAT Still Required

Run on the Ubuntu 24.04 GNOME target after 07-02:

- With AppIndicator enabled, confirm About diagnostics report tray status as available.
- With AppIndicator disabled or missing, confirm About diagnostics report tray unavailability without a traceback.

## User Setup Required

None for source execution. Session-bus watcher UAT requires Ubuntu/Linux with a graphical session and the AppIndicator extension state under test.

## Next Phase Readiness

Plan 07-02 can add the separate GTK3/Ayatana helper process using `tray_status()` as its startup gate.

## Self-Check: PASSED

- Production commits exist: `b8a49de`, `aeb43a5`, `2023406`.
- Summary file exists and lists requirements-completed: `[TRAY-02]`.
- Full 07-01 automated smoke gates exit 0 on this host.
- Modified production files are limited to `tools/smoke_phase7.py`, `acercontrol/tray_status.py`, and `acercontrol/gui_about.py`.

---
*Phase: 07-tray-helper-hardware-compatibility*
*Completed: 2026-05-23*
