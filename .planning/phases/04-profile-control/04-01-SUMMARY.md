---
phase: 04-profile-control
plan: 01
subsystem: ui
tags: [gtk4, libadwaita, profile-control, polkit, smoke-runner, read-back]

requires:
  - phase: 03-01
    provides: "MainWindow shell, warning banner column, toast overlay, and show_ppd_banner(force)"
  - phase: 03-02
    provides: "Phase 3 reload-helper gap closure and regression smoke stability"
provides:
  - "Phase 4 smoke runner with quick/full source and regression gates"
  - "ProfileControlPanel with five read-back-driven profile buttons"
  - "MainWindow integration that replaces the Phase 3 empty-state placeholder"
affects: [phase-05-live-sensors-notifications, gui]

tech-stack:
  added: []
  patterns:
    - "Read-back-driven UI state: click intent never becomes active highlight until read_profile() confirms it"
    - "Short GLib.timeout_add(250, ...) reconciliation after privileged writes"
    - "Source/static smoke gates for GTK behavior that cannot run on this macOS host"

key-files:
  created:
    - "tools/smoke_phase4.py"
    - "acercontrol/gui_profiles.py"
    - ".planning/phases/04-profile-control/04-01-SUMMARY.md"
  modified:
    - "acercontrol/gui_window.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "Used Gtk.Button, not ToggleButton, so active styling can stay tied to actual read-back state."
  - "Kept kernel profile literals out of GUI files by using PROFILES[requested_profile]."
  - "Cancellation clears pending UI without read-back or PPD banner forcing."
  - "Read-back mismatch re-renders actual state and calls show_ppd_banner(force=True)."

requirements-completed: [GUI-05, GUI-06, GUI-07]

duration: 5 min
completed: 2026-05-22
---

# Phase 4 Plan 01: Profile Control Summary

Phase 4 execution is complete at the source/static level: the main GUI now renders five profile buttons, writes through the existing privileged wrapper, waits for read-back, and only then updates the active highlight.

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-22T23:54:00+05:30
- **Completed:** 2026-05-22T23:59:00+05:30
- **Tasks:** 3
- **Files changed:** 6

## Accomplishments

- Added `tools/smoke_phase4.py` with quick/full gates for GUI-05, GUI-06, GUI-07, privileged call shape, exact user-facing strings, focus/accessibility source coverage, and GUI-08 raw-kernel-value regression checks.
- Added `acercontrol/gui_profiles.py` with `ProfileControlPanel`, exact profile order `eco`, `quiet`, `balanced`, `performance`, `turbo`, pending/cancel/failure/success/mismatch handling, and `Profile.CUSTOM` rendering.
- Replaced the Phase 3 placeholder in `MainWindow` with `ProfileControlPanel(self)` while preserving blocker routing, warning banners, existing wrapper handlers, and `show_ppd_banner(force)`.
- Added timeout-capable toast support in `MainWindow` for the 3-second cancellation toast without breaking existing `_toast()` callers.

## Task Commits

1. **Task 1: Wave 0 Phase 4 smoke runner** - `9b71921`
2. **Task 2: Build read-back-driven ProfileControlPanel** - `537bc02`
3. **Task 3: Replace Phase 3 empty state and run full gates** - `8ad86b5`

## Files Created/Modified

- `tools/smoke_phase4.py` - New Phase 4 smoke runner.
- `acercontrol/gui_profiles.py` - New profile control panel and state machine.
- `acercontrol/gui_window.py` - Main view now appends `ProfileControlPanel`; toast helper accepts optional timeout.
- `.planning/phases/04-profile-control/04-01-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- Active profile styling is non-optimistic. The requested button is never highlighted just because it was clicked.
- The GUI delegates privilege to `run_privileged(["acercontrol-setprofile", PROFILES[requested_profile]])`; it never shells out and never writes sysfs directly.
- `power-profiles-daemon` overwrite detection is treated as a read-back mismatch, not as a write failure.
- The smoke runner stays GTK-free so it can run on this host without GTK typelibs.

## Deviations from Plan

### Auto-fixed Issues

- The initial `GLib.timeout_add` call wrapped its arguments across lines, while the Phase 4 smoke gate intentionally checked for the exact `GLib.timeout_add(250,` source token. The implementation was reformatted to match the planned invariant.

---

**Total deviations:** 1 auto-fixed.
**Impact on plan:** No scope expansion; the runtime behavior did not change.

## Issues Encountered

- Native GTK/polkit/sysfs UAT cannot run on this macOS host. Verification here is limited to source/static smoke, py_compile, and previous-phase regression smoke.

## Verification Results

- `python3 -m py_compile acercontrol/gui_profiles.py acercontrol/gui_window.py tools/smoke_phase4.py` -> passed.
- `python3 tools/smoke_phase4.py --quick` -> 8/8 passed.
- `python3 tools/smoke_phase4.py` -> 11/11 passed.
- `python3 tools/smoke_phase1.py` -> 6/6 passed.
- `python3 tools/smoke_phase2.py` -> 28/28 passed.
- `python3 tools/smoke_phase3.py` -> 18/18 passed. The console-script entry-point scenario remained a skip unless the package is reinstalled editable, as in prior Phase 3 behavior.

## Human UAT Still Required

Run on the PHN16-72 Linux target:

- Launch `acercontrol-gui`; verify blocker routing still hides controls when blockers are present.
- With blockers clear, confirm the five profile buttons render in order and keyboard focus moves through them correctly.
- Click each profile and verify `acercontrol get` matches the requested user-facing name.
- Confirm `turbo` blinks the chassis LED and `performance` leaves it solid.
- Cancel polkit with Escape; highlight must stay on the previous actual profile and toast must read `Authorization cancelled` for 3 seconds.
- Re-enable PPD, trigger an overwrite, and confirm the mismatch toast appears, highlight reverts to actual read-back state, and the PPD banner reappears.

## User Setup Required

None for source execution. Hardware UAT requires the existing target setup: Ubuntu/Linux with GTK4/libadwaita typelibs, polkit agent, `acer_wmi predator_v4=1`, and platform profile sysfs.

## Next Phase Readiness

Phase 5 can build the live sensor panel above or below the profile group using the same `MainWindow` main column. Profile-change toasts are already centralized through `show_toast()`, but system notifications remain Phase 5 scope.

## Self-Check: PASSED

- Production commits exist: `9b71921`, `537bc02`, `8ad86b5`.
- Summary file exists and lists requirements-completed: `[GUI-05, GUI-06, GUI-07]`.
- Full Phase 1-4 automated smoke gates exit 0.
- Modified production files are limited to `tools/smoke_phase4.py`, `acercontrol/gui_profiles.py`, and `acercontrol/gui_window.py`.

---
*Phase: 04-profile-control*
*Completed: 2026-05-22*
