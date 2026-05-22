---
phase: 06-boot-persistence-suspend-resume
plan: 03
subsystem: resume
tags: [gio, login1, suspend-resume, profile-restore, smoke-runner]

requires:
  - phase: 06-02
    provides: "BootServicePanel, MainWindow boot wait guard, and profile-click wait path"
provides:
  - "ResumeReapplyController for login1 PrepareForSleep subscription and cleanup"
  - "MainWindow last-selected profile tracking and best-effort after-resume reapply"
  - "Full Phase 1-6 source/static regression verification"
affects: [phase-06-boot-persistence-suspend-resume, gui, suspend-resume]

tech-stack:
  added: []
  patterns:
    - "Gio system-bus subscription without new D-Bus dependencies"
    - "Before-sleep signal ignored; after-resume signal delegates to MainWindow"
    - "Read-before-write profile restore using the existing privileged setprofile wrapper"

key-files:
  created:
    - "acercontrol/gui_resume.py"
    - ".planning/phases/06-boot-persistence-suspend-resume/06-03-SUMMARY.md"
  modified:
    - "tools/smoke_phase6.py"
    - "acercontrol/gui_window.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "Resume handling subscribes to login1 through Gio, avoiding dasbus/pydbus and any worker thread."
  - "MainWindow tracks the last selected non-custom profile separately from the last seen profile notification state."
  - "After-resume restore reads the actual current profile first and writes only when it differs."
  - "Cancellation and failure during resume restore stay silent to avoid repeated notifications after unstable resume cycles."

patterns-established:
  - "ResumeReapplyController.start() degrades silently when the system bus or login1 is unavailable."
  - "ResumeReapplyController.stop() unsubscribes during MainWindow close-request cleanup."
  - "Phase 6 full smoke now covers units, wrappers, boot GUI, wait guard, and resume controller wiring."

requirements-completed: [BOOT-05]

duration: 4 min
completed: 2026-05-23
---

# Phase 6 Plan 03: Resume Reapply Summary

The GUI now listens for login1 resume signals and re-applies the last selected non-custom profile after resume when firmware or another service changed the current profile.

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-23T00:53:29+05:30
- **Completed:** 2026-05-23T00:56:55+05:30
- **Tasks:** 4
- **Files changed:** 6

## Accomplishments

- Extended `tools/smoke_phase6.py` with login1 resume source checks, forbidden dependency checks, and MainWindow resume wiring checks.
- Added `acercontrol/gui_resume.py` with `ResumeReapplyController`, a Gio system-bus subscription to `org.freedesktop.login1.Manager.PrepareForSleep`, before-sleep ignore behavior, after-resume delegation, and cleanup.
- Updated `MainWindow` to own the resume controller, track `_last_selected_profile_name`, and restore the last selected profile after resume when read-back differs.
- Ran the final Phase 1-6 regression chain with full Phase 6 smoke.

## Task Commits

1. **Task 1: Expand Phase 6 smoke for login1 resume** - `2cc1f2d`
2. **Task 2: Add ResumeReapplyController** - `7d98242`
3. **Task 3: Add MainWindow resume reapply hook** - `d230844`
4. **Task 4: Final Phase 6 regression pass** - no code changes; verification recorded below.

## Files Created/Modified

- `tools/smoke_phase6.py` - Resume controller and MainWindow restore source gates.
- `acercontrol/gui_resume.py` - login1 `PrepareForSleep` subscription and cleanup controller.
- `acercontrol/gui_window.py` - Resume controller ownership, last selected profile tracking, and reapply hook.
- `.planning/phases/06-boot-persistence-suspend-resume/06-03-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- The resume callback ignores `PrepareForSleep(true)` and only acts on `PrepareForSleep(false)`.
- The restore path compares `read_profile()` against `_last_selected_profile_name` before invoking `acercontrol-setprofile`.
- A successful restore refreshes the profile panel, updates `_last_seen_profile_name`, and shows the exact toast `Profile restored after resume`.
- Missing login1/system bus support is treated as graceful degradation, not a blocker for launching the GUI.

## Deviations from Plan

None.

---

**Total deviations:** 0.
**Impact on plan:** None.

## Issues Encountered

- Native suspend/resume, login1, GTK, polkit, and Acer sysfs UAT cannot run on this macOS host. Verification here is source/static plus Python compilation.

## Verification Results

- `python3 -m py_compile acercontrol/systemd.py acercontrol/gui_boot.py acercontrol/gui_resume.py acercontrol/gui_window.py acercontrol/gui_profiles.py tools/smoke_phase6.py` -> passed.
- `python3 tools/smoke_phase6.py --quick` -> 8/8 passed.
- `python3 tools/smoke_phase6.py` -> 10/10 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py` -> passed. Phase 3 retained its existing editable-install console-script skip.

## Human UAT Still Required

Run on the PHN16-72 Linux target:

- Suspend/resume with the GUI running; if firmware or another service changes the profile, verify the GUI restores the last selected non-custom profile after unlock.
- Repeat multiple suspend/resume cycles and confirm no repeated restore toasts appear when no restore is needed.
- Cold boot with a configured boot profile and verify `acercontrol get` returns the configured profile before opening the GUI.
- Launch the GUI within 2 seconds of `graphical.target`, immediately click a profile, and verify the boot unit does not clobber the click after 10 seconds.

## User Setup Required

None for source execution. Hardware UAT requires Ubuntu/Linux with GTK4/libadwaita typelibs, systemd/login1, polkit, installed wrappers, installed Phase 6 unit files, `acer_wmi predator_v4=1`, and platform profile sysfs.

## Next Phase Readiness

Phase 7 can proceed to tray helper and hardware compatibility planning. Phase 6 remains hardware-verification pending until cold-boot and suspend/resume UAT are run on the target Acer laptop.

## Self-Check: PASSED

- Production commits exist: `2cc1f2d`, `7d98242`, `d230844`.
- Summary file exists and lists requirements-completed: `[BOOT-05]`.
- Full Phase 1-6 automated smoke gates exit 0 on this host.
- Modified production files are limited to `tools/smoke_phase6.py`, `acercontrol/gui_resume.py`, and `acercontrol/gui_window.py`.

---
*Phase: 06-boot-persistence-suspend-resume*
*Completed: 2026-05-23*
