---
phase: 06-boot-persistence-suspend-resume
plan: 02
subsystem: gui
tags: [gtk4, libadwaita, boot-service, startup-race, smoke-runner]

requires:
  - phase: 06-01
    provides: "Systemd boot units, systemd facade, service wrapper allowlist, and Phase 6 smoke runner"
provides:
  - "BootServicePanel for enable/disable, boot profile selection, status display, and apply-now"
  - "MainWindow boot panel ordering below profile controls and sensors"
  - "One-shot boot-service wait in route and profile-click paths before privileged profile writes"
affects: [phase-06-boot-persistence-suspend-resume, gui, privilege-boundary]

tech-stack:
  added: []
  patterns:
    - "Wrapper-only GUI mutations through run_privileged()"
    - "User-facing profile names in GUI controls; kernel values remain behind PROFILES mapping"
    - "Bounded best-effort startup wait before first profile writes"

key-files:
  created:
    - "acercontrol/gui_boot.py"
    - ".planning/phases/06-boot-persistence-suspend-resume/06-02-SUMMARY.md"
  modified:
    - "tools/smoke_phase6.py"
    - "acercontrol/gui_window.py"
    - "acercontrol/gui_profiles.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "Boot profile selection and Apply now both update /etc/default/acercontrol, then start the validated template instance."
  - "The boot panel displays only user-facing profile names in the fixed eco/quiet/balanced/performance/turbo order."
  - "The boot-service wait result is cached in MainWindow; it is attempted once and never blocks profile changes on failure."
  - "Smoke checks for later wiring stages are staged until the relevant source token appears, then become strict."

patterns-established:
  - "BootServicePanel refreshes actual state after every success, cancellation, or failure."
  - "MainWindow owns ProfileControlPanel, SensorPanel, and BootServicePanel as sibling PreferencesGroups on the shared page."
  - "ProfileControlPanel calls ensure_boot_service_ready() before setting pending UI or invoking acercontrol-setprofile."

requirements-completed: [BOOT-03, BOOT-04]

duration: 5 min
completed: 2026-05-23
---

# Phase 6 Plan 02: GUI Boot Panel Summary

The main GTK page now includes a Boot Service section below live sensors, uses wrapper-backed actions for boot persistence, and attempts a bounded boot-service wait before profile writes.

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-23T00:48:43+05:30
- **Completed:** 2026-05-23T00:53:29+05:30
- **Tasks:** 4
- **Files changed:** 7

## Accomplishments

- Expanded `tools/smoke_phase6.py` to enforce boot panel copy, wrapper-only mutation paths, main page ordering, and the profile-click wait guard.
- Added `acercontrol/gui_boot.py` with `BootServicePanel`, status row, enable-at-boot switch, boot profile combo, and Apply now action.
- Wired `BootServicePanel` into `MainWindow` after `SensorPanel`, with a cached `ensure_boot_service_ready()` method backed by `wait_for_boot_service()`.
- Updated `ProfileControlPanel._on_profile_clicked()` to attempt the boot-service wait before setting pending state and before calling `acercontrol-setprofile`.

## Task Commits

1. **Task 1: Expand Phase 6 smoke for boot panel and startup wait** - `599e200`
2. **Task 2: Add BootServicePanel** - `219bea4`
3. **Task 3: Wire boot panel into MainWindow** - `a8c0553`
4. **Task 4: Guard profile writes behind boot wait** - `d8e56e1`

## Files Created/Modified

- `tools/smoke_phase6.py` - Boot panel, ordering, and wait-guard source gates.
- `acercontrol/gui_boot.py` - Boot persistence Adwaita preferences group.
- `acercontrol/gui_window.py` - Boot panel creation, ordering, and one-shot boot-service wait.
- `acercontrol/gui_profiles.py` - Profile-click wait guard before privileged setprofile writes.
- `.planning/phases/06-boot-persistence-suspend-resume/06-02-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- Enable/disable uses `acercontrol-manage-service enable|disable acer-performance.service`, matching the plan and keeping service mutation behind the wrapper.
- Boot profile changes and Apply now share the same path: `acercontrol-set-boot-profile <kernel-value>` followed by `acercontrol-manage-service start acer-performance@<kernel-value>.service`.
- If the boot unit is not installed, the panel renders `not installed` and disables its mutation controls.
- The profile-click wait is best-effort; a false wait result does not block the user from changing profiles.

## Deviations from Plan

### Auto-fixed Issues

- Once `gui_boot.py` existed, the initial smoke runner immediately enforced later `gui_window.py` and `gui_profiles.py` checks before those tasks ran. Those checks were staged to SKIP until their respective wiring tokens appear, while staying strict after each wiring task.

---

**Total deviations:** 1 auto-fixed.
**Impact on plan:** No scope expansion; this preserved task-level verification without weakening final gates.

## Issues Encountered

- Native GTK rendering, polkit dialogs, and systemd state cannot be exercised on this macOS host. Verification here remains source/static plus Python compilation.

## Verification Results

- `python3 -m py_compile acercontrol/gui_boot.py acercontrol/gui_window.py acercontrol/gui_profiles.py` -> passed.
- `python3 tools/smoke_phase6.py --quick` -> 8/8 passed.
- `python3 tools/smoke_phase6.py` -> 10/10 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py` -> passed. Phase 3 retained its existing editable-install console-script skip.

## Human UAT Still Required

Run on the PHN16-72 Linux target after all Phase 6 plans:

- Toggle Enable at boot from the GUI and verify `systemctl is-enabled acer-performance.service` changes accordingly.
- Change Boot profile from the GUI and verify `/etc/default/acercontrol` stores the kernel value while the GUI shows a user-facing name.
- Launch the GUI immediately after login and click a profile quickly; verify the boot unit does not overwrite the user click afterward.

## User Setup Required

None for source execution. Hardware UAT requires installed wrappers, polkit policy, systemd units, GTK4/libadwaita typelibs, and the Acer platform profile sysfs path.

## Next Phase Readiness

Plan 06-03 can add the login1 resume controller and wire it into the same MainWindow profile reapply path.

## Self-Check: PASSED

- Production commits exist: `599e200`, `219bea4`, `a8c0553`, `d8e56e1`.
- Summary file exists and lists requirements-completed: `[BOOT-03, BOOT-04]`.
- Full Phase 1-6 automated smoke gates exit 0 on this host.
- Modified production files are limited to `tools/smoke_phase6.py`, `acercontrol/gui_boot.py`, `acercontrol/gui_window.py`, and `acercontrol/gui_profiles.py`.

---
*Phase: 06-boot-persistence-suspend-resume*
*Completed: 2026-05-23*
