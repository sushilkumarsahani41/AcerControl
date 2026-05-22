---
phase: 05-live-sensors-notifications
plan: 01
subsystem: ui
tags: [gtk4, libadwaita, live-sensors, notifications, smoke-runner]

requires:
  - phase: 04-01
    provides: "ProfileControlPanel, MainWindow toast overlay, read-back profile success path, and show_ppd_banner(force)"
provides:
  - "Phase 5 smoke runner with quick/full gates for live sensors and notifications"
  - "ProfileChangeNotifier and CriticalTempNotifier with focus-aware routing and stable notification IDs"
  - "SensorPanel with CPU package, Acer temperature, and fan RPM rows"
  - "MainWindow-owned shared profile/sensor page with 2-second main-loop refresh"
affects: [phase-06-boot-persistence-suspend-resume, gui, notifications]

tech-stack:
  added: []
  patterns:
    - "Main-loop telemetry polling with GLib.timeout_add_seconds(2, ...) and explicit GLib.source_remove cleanup"
    - "Centralized focused/unfocused notification routing"
    - "Threshold-colored sensor rows fed only by core.SensorReading snapshots"
    - "Source/static smoke gates for native GTK behavior that cannot run on this macOS host"

key-files:
  created:
    - "tools/smoke_phase5.py"
    - "acercontrol/gui_notifications.py"
    - "acercontrol/gui_sensors.py"
    - ".planning/phases/05-live-sensors-notifications/05-01-SUMMARY.md"
  modified:
    - "acercontrol/gui_profiles.py"
    - "acercontrol/gui_window.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "Kept sensor refresh on the GTK main loop; no worker thread was introduced."
  - "Moved page/scroller ownership from ProfileControlPanel to MainWindow so profile and sensor groups share one PreferencesPage."
  - "Routed profile success through MainWindow.notify_profile_change to avoid duplicate tick notifications."
  - "Used critical-temperature hysteresis with separate enter and exit thresholds to avoid notification spam."

patterns-established:
  - "SensorPanel accepts SensorReading snapshots and never walks hwmon directly."
  - "Notifier classes decide toast versus Gio.Notification based on MainWindow.is_focused()."
  - "MainWindow stops live sensor sources before blocker StatusPages and on close-request."

requirements-completed: [SENS-01, SENS-02, SENS-03, SENS-04, NOTI-01, NOTI-02]

duration: 5 min
completed: 2026-05-23
---

# Phase 5 Plan 01: Live Sensors + Notifications Summary

The GTK main page now shows live thermal/fan state below profile controls, refreshes through a 2-second GLib timer, and routes profile/critical-temperature events through focused toasts or stable desktop notifications.

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-23T00:20:25+05:30
- **Completed:** 2026-05-23T00:25:00+05:30
- **Tasks:** 4
- **Files changed:** 7

## Accomplishments

- Added `tools/smoke_phase5.py` with quick/full checks for sensor layout, notification IDs, forbidden threading/blocking patterns, direct hwmon access, timer lifecycle, and prior-phase regressions.
- Added `acercontrol/gui_notifications.py` with `ProfileChangeNotifier` and `CriticalTempNotifier`, including critical enter/exit hysteresis and stable `profile-change`, `critical-temp`, and `critical-temp-normal` IDs.
- Added `acercontrol/gui_sensors.py` with stable rows for CPU package, three Acer temperatures, and two fans; missing values render `-`, temperature rows use green/yellow/red threshold CSS, and fan bars use a fixed 8000 RPM scale.
- Refactored `MainWindow` so one scroller/page owns `ProfileControlPanel` first and `SensorPanel` second, with live refresh start/stop tied to blocker routing and close cleanup.
- Updated `ProfileControlPanel` success routing so confirmed profile changes call `notify_profile_change()` while cancellation, failure, and mismatch copy remain unchanged.

## Task Commits

1. **Task 1: Wave 0 Phase 5 smoke runner** - `0863457`
2. **Task 2: Focused/unfocused notification state machines** - `59d2a94`
3. **Task 3: Live sensor panel component** - `b1082d4`
4. **Task 4: Main page, refresh lifecycle, and profile notification routing** - `e8ee055`

## Files Created/Modified

- `tools/smoke_phase5.py` - Phase 5 source/static smoke runner.
- `acercontrol/gui_notifications.py` - Focus-aware profile and critical-temperature notification state machines.
- `acercontrol/gui_sensors.py` - Sensor group with rows, value formatting, placeholders, and threshold bar styling.
- `acercontrol/gui_profiles.py` - Profile panel is now a group and delegates success notification routing.
- `acercontrol/gui_window.py` - Shared main page, sensor timer lifecycle, profile-change detection, and notifier coordination.
- `.planning/phases/05-live-sensors-notifications/05-01-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- `SensorPanel` is a read-only renderer. It receives `SensorReading` from `MainWindow` and does not import or call `read_sensors()`.
- `MainWindow` owns `_last_seen_profile_name`; profile-button success updates it immediately so the next 2-second tick does not duplicate the success notification.
- Focus suppression lives in `gui_notifications.py`, not in profile/sensor components.
- The live refresh callback reads sensors and profile synchronously because the project research found sysfs reads are sub-millisecond.

## Deviations from Plan

### Auto-fixed Issues

- The initial `GLib.timeout_add_seconds` call wrapped its arguments across lines, while the Phase 5 smoke gate intentionally checked for the exact `GLib.timeout_add_seconds(2,` token. The call was reformatted to match the planned invariant.

---

**Total deviations:** 1 auto-fixed.
**Impact on plan:** No scope expansion; runtime behavior did not change.

## Issues Encountered

- Native GTK/Gio/sysfs UAT cannot run on this macOS host. Verification here is limited to source/static smoke, py_compile, and prior-phase regression smoke.

## Verification Results

- `python3 -m py_compile acercontrol/gui_notifications.py acercontrol/gui_sensors.py acercontrol/gui_profiles.py acercontrol/gui_window.py tools/smoke_phase5.py` -> passed.
- `python3 tools/smoke_phase5.py --quick` -> 5/5 passed.
- `python3 tools/smoke_phase5.py` -> 10/10 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py` -> passed. Phase 3 retained its existing editable-install console-script skip.

## Human UAT Still Required

Run on the PHN16-72 Linux target:

- Launch `acercontrol-gui`; verify Phase 3 blocker routing still hides the main page when blockers are present.
- With blockers clear, confirm profile controls appear first and `Sensors` appears below them.
- Leave the GUI open for at least 30 minutes; `journalctl --user --since "30 min ago"` has zero `Gtk-CRITICAL` or `Gtk-WARNING` lines from AcerControl.
- Watch values for at least 60 seconds; CPU package, Acer temps, and fan rows update around every 2 seconds without row resizing or flicker.
- Temporarily hide one Acer temp input; only that row shows the placeholder, other rows continue updating, and the value returns within one tick after restoration.
- Unfocus the GUI and run `stress-ng --cpu 0 --timeout 90s`; exactly one `CPU temperature critical` notification appears crossing >=90 C and one `CPU temperature back to normal` notification appears crossing <85 C.
- Repeat the stress run with the GUI focused; zero system notifications appear and toasts are used instead.
- Unfocus the GUI, change profile via CLI, and confirm one stable `Profile changed` notification.

## User Setup Required

None for source execution. Hardware UAT requires Ubuntu/Linux with GTK4/libadwaita typelibs, a working polkit agent, `acer_wmi predator_v4=1`, platform profile sysfs, and readable hwmon sensors.

## Next Phase Readiness

Phase 6 can add boot persistence and suspend/resume on top of the same `MainWindow` shared page pattern. The profile-control and live-sensor loop is in place, but Phase 5 remains hardware-verification pending until PHN16-72 UAT is run.

## Self-Check: PASSED

- Production commits exist: `0863457`, `59d2a94`, `b1082d4`, `e8ee055`.
- Summary file exists and lists requirements-completed: `[SENS-01, SENS-02, SENS-03, SENS-04, NOTI-01, NOTI-02]`.
- Full Phase 1-5 automated smoke gates exit 0 on this host.
- Modified production files are limited to `tools/smoke_phase5.py`, `acercontrol/gui_notifications.py`, `acercontrol/gui_sensors.py`, `acercontrol/gui_profiles.py`, and `acercontrol/gui_window.py`.

---
*Phase: 05-live-sensors-notifications*
*Completed: 2026-05-23*
