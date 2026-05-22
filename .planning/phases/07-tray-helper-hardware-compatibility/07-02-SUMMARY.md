---
phase: 07-tray-helper-hardware-compatibility
plan: 02
subsystem: tray-helper
tags: [gtk3, ayatana, appindicator, quick-switch, smoke-runner]

requires:
  - phase: 07-01
    provides: "Gio-only tray availability detector and About diagnostics"
provides:
  - "Separate GTK3/Ayatana tray helper process"
  - "Wrapper-backed profile quick-switch menu"
  - "Show AcerControl launcher action without importing GTK4 modules"
  - "Root-level acercontrol_tray.py development shim"
affects: [phase-07-tray-helper-hardware-compatibility, tray, privilege-boundary]

tech-stack:
  added: []
  patterns:
    - "StatusNotifierWatcher gate before optional GTK3/Ayatana imports"
    - "Profile polling on the GTK main loop via GLib.timeout_add_seconds(2, ...)"
    - "Tray mutations routed through run_privileged() and existing libexec wrapper names"

key-files:
  created:
    - "acercontrol/tray.py"
    - "acercontrol_tray.py"
    - ".planning/phases/07-tray-helper-hardware-compatibility/07-02-SUMMARY.md"
  modified:
    - "tools/smoke_phase7.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "The tray helper exits 0 before loading GTK3 when StatusNotifierWatcher is unavailable."
  - "The helper imports Ayatana AppIndicator only inside the tray stack loader."
  - "Quick-switch uses `run_privileged([\"acercontrol-setprofile\", PROFILES[profile_name]])` and never writes sysfs directly."
  - "Show AcerControl launches `acercontrol-gui` from PATH, falling back to `python -m acercontrol.gui` for development."

patterns-established:
  - "Tray menu contains eco, quiet, balanced, performance, turbo, separator, Show AcerControl, and Quit in that order."
  - "Unsupported profile choices remain visible but insensitive when platform_profile_choices is readable."
  - "tools/smoke_phase7.py now enforces GTK3/GTK4 process isolation and wrapper-only tray mutations."

requirements-completed: [TRAY-01, TRAY-03]

duration: 4 min
completed: 2026-05-23
---

# Phase 7 Plan 02: Tray Helper Summary

The optional tray process now exists as a separate GTK3/Ayatana helper. It gates startup on `StatusNotifierWatcher`, reflects profile state through menu checks, quick-switches through the existing privileged wrapper path, and can launch or raise the main GUI without importing GTK4.

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-23T01:31:13+05:30
- **Completed:** 2026-05-23T01:35:23+05:30
- **Tasks:** 4
- **Files changed:** 6

## Accomplishments

- Expanded `tools/smoke_phase7.py` to enforce tray helper source contracts, menu order, forbidden patterns, and shim imports.
- Added `acercontrol/tray.py` with StatusNotifierWatcher gating, lazy GTK3/Ayatana imports, Ayatana indicator construction, profile polling, and profile menu actions.
- Added `acercontrol_tray.py` as a root-level manual/development shim for running the helper before Phase 8 console scripts.
- Ran the 07-02 regression pass across Phase 1, Phase 2, Phase 3, and Phase 7 smoke gates.

## Task Commits

1. **Task 1: Expand smoke for tray helper source contract** - `580e222`
2. **Task 2: Add GTK3 Ayatana tray helper** - `abc747f`
3. **Task 3: Add quick-switch and Show AcerControl actions** - `1572f1f`
4. **Task 4: 07-02 regression pass** - no code changes; verification recorded below.

## Files Created/Modified

- `tools/smoke_phase7.py` - Strict tray helper and shim source gates.
- `acercontrol/tray.py` - Optional GTK3/Ayatana AppIndicator helper process.
- `acercontrol_tray.py` - Root-level launcher shim.
- `.planning/phases/07-tray-helper-hardware-compatibility/07-02-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- The helper checks `tray_status()` before importing GTK3/Ayatana and exits 0 for unavailable tray environments.
- Profile menu items use `Gtk.CheckMenuItem` with radio-style drawing for current-profile marking.
- `list_available_profiles()` controls sensitivity only when choices are known; unreadable choices keep all five profile entries available.
- The tray uses `subprocess.Popen()` only for launching the GUI, not for profile writes or service management.

## Deviations from Plan

None.

---

**Total deviations:** 0.
**Impact on plan:** None.

## Issues Encountered

- Native AppIndicator rendering, right-click menu behavior, and profile switching from tray cannot be exercised on this macOS host. Verification here is source/static plus Python compilation.

## Verification Results

- `python3 tools/smoke_phase7.py --quick` -> 7/7 passed before and after helper/shim implementation.
- `python3 -m py_compile acercontrol/tray.py acercontrol_tray.py` -> passed.
- `python3 tools/smoke_phase2.py` -> 28/28 passed.
- `python3 tools/smoke_phase7.py` -> 10/10 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase7.py` -> passed. Phase 3 retained its existing editable-install console-script skip.

## Human UAT Still Required

Run on the Ubuntu 24.04 GNOME target:

- With the AppIndicator extension enabled, run `python3 acercontrol_tray.py` and confirm the tray icon/menu appears.
- Switch each profile from the tray and confirm `acercontrol get` reports the requested user-facing name.
- Use Show AcerControl while the GUI is closed and while already open; confirm it launches or focuses the existing window.
- Disable the AppIndicator extension and confirm `acercontrol-tray` exits 0 without a traceback.

## User Setup Required

None for source execution. Tray UAT requires Ubuntu/Linux with GTK3 typelibs, Ayatana AppIndicator typelibs, a session bus, the AppIndicator extension, installed libexec wrappers, polkit, and Acer platform profile sysfs.

## Next Phase Readiness

Plan 07-03 can add hardware compatibility fixtures, packaging handoff checks, and the consolidated manual UAT checklist.

## Self-Check: PASSED

- Production commits exist: `580e222`, `abc747f`, `1572f1f`.
- Summary file exists and lists requirements-completed: `[TRAY-01, TRAY-03]`.
- Full 07-02 automated smoke gates exit 0 on this host.
- Modified production files are limited to `tools/smoke_phase7.py`, `acercontrol/tray.py`, and `acercontrol_tray.py`.

---
*Phase: 07-tray-helper-hardware-compatibility*
*Completed: 2026-05-23*
