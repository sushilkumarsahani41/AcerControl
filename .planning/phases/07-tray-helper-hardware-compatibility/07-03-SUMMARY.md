---
phase: 07-tray-helper-hardware-compatibility
plan: 03
subsystem: hardware-compatibility
tags: [fixtures, hardware-uat, packaging-handoff, regression]

requires:
  - phase: 07-02
    provides: "Separate GTK3/Ayatana tray helper and launcher shim"
provides:
  - "Phase 7 hardware compatibility fixture coverage"
  - "TRAY-04 packaging Recommends handoff gate"
  - "Manual PHN16-72 and partial-hardware UAT checklist"
  - "Full Phase 1-7 source/static regression verification"
affects: [phase-07-tray-helper-hardware-compatibility, smoke-runner, hardware-uat]

tech-stack:
  added: []
  patterns:
    - "Tempdir hwmon fixtures with monkeypatched sysfs.HWMON_BASE"
    - "Fixture coverage for partial Acer fan/temp sensors and profile choices"
    - "Packaging contract skipped until Phase 8 creates debian/control, then enforced"

key-files:
  created:
    - ".planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md"
    - ".planning/phases/07-tray-helper-hardware-compatibility/07-03-SUMMARY.md"
  modified:
    - "tools/smoke_phase7.py"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "No production compatibility changes were required; fixtures validated existing sysfs/profile behavior."
  - "Phase 7 keeps TRAY-04 as a source/static handoff until Phase 8 owns debian/control."
  - "Partial compatible hardware is covered by fixtures now and by manual UAT when second hardware is available."
  - "Phase 7 closeout remains source/static on this host; native tray and Acer UAT are explicitly documented."

patterns-established:
  - "Full Phase 7 smoke now proves most-populated acer hwmon selection."
  - "Full Phase 7 smoke proves missing fan/temp values stay None."
  - "Full Phase 7 smoke proves omitted platform_profile_choices are excluded without raising."

requirements-completed: [TRAY-04, HW-01, HW-02]

duration: 4 min
completed: 2026-05-23
---

# Phase 7 Plan 03: Hardware Compatibility Summary

Phase 7 now has fixture coverage for partial hardware behavior, a documented PHN16-72 tray/hardware UAT checklist, and a final Phase 1-7 regression pass. No production compatibility fixes were needed.

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-23T01:35:23+05:30
- **Completed:** 2026-05-23T01:39:09+05:30
- **Tasks:** 4
- **Files changed:** 5

## Accomplishments

- Expanded `tools/smoke_phase7.py` full mode with tempdir fixtures for duplicate `acer` hwmon entries, partial Acer sensors, and profile-choice filtering.
- Kept the TRAY-04 packaging Recommends contract as a clear Phase 8 handoff skip while `debian/control` is absent.
- Verified the fixtures found no real compatibility gap in `core.py`, `sysfs.py`, `gui_profiles.py`, `gui_sensors.py`, or `features.py`.
- Added `07-HUMAN-UAT.md` covering AppIndicator present/absent flows, tray quick-switch, Show AcerControl, PHN16-72 happy path, partial hardware, and Phase 8 packaging follow-up.
- Ran the final Phase 1-7 automated regression chain.

## Task Commits

1. **Task 1: Expand smoke for hardware compatibility and packaging handoff** - `f75bb43`
2. **Task 2: Fix any compatibility gaps found by fixtures** - no production changes; fixtures passed.
3. **Task 3: Add Phase 7 human UAT checklist** - `665b532`
4. **Task 4: Final Phase 7 regression pass** - no code changes; verification recorded below.

## Files Created/Modified

- `tools/smoke_phase7.py` - Hardware compatibility fixtures and Phase 8 packaging handoff message.
- `.planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md` - Manual Linux/hardware validation checklist.
- `.planning/phases/07-tray-helper-hardware-compatibility/07-03-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- `sysfs.find_hwmon()` most-populated selection and `read_acer_sensors()` missing-value behavior are proven by fixtures rather than changed.
- `available_profiles()` filtering is proven with a temporary `platform_profile_choices` file missing turbo.
- The packaging dependency check remains active only when `debian/control` exists, because Phase 8 owns creating Debian packaging files.
- Human UAT is the authority for native AppIndicator rendering, polkit dialogs, suspend/resume, boot persistence, and actual PHN16-72 thermal behavior.

## Deviations from Plan

### Auto-fixed Issues

- The first full fixture run exposed that `tools/smoke_phase7.py` did not add the project root to `sys.path` before importing `acercontrol`. The runner bootstrap was updated and the fixture suite passed.

---

**Total deviations:** 1 auto-fixed.
**Impact on plan:** No production behavior change; this fixed the smoke runner only.

## Issues Encountered

- Native AppIndicator, GTK, polkit, systemd, suspend/resume, and Acer sysfs UAT cannot run on this macOS host.
- `debian/control` does not exist yet, so TRAY-04 is a Phase 8 handoff skip until packaging files are created.

## Verification Results

- `python3 tools/smoke_phase7.py --quick` -> 7/7 passed.
- `python3 tools/smoke_phase7.py` -> 10/10 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase7.py` -> passed.
- `test -s .planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md` -> passed.
- `rg -n "AppIndicator|StatusNotifierWatcher|PHN16-72|partial" .planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md` -> passed.
- `python3 -m py_compile tools/smoke_phase7.py acercontrol/tray_status.py acercontrol/tray.py acercontrol_tray.py acercontrol/gui_about.py` -> passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py && python3 tools/smoke_phase7.py` -> passed. Phase 3 retained its existing editable-install console-script skip.

## Human UAT Still Required

Run `.planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md` on Ubuntu 24.04 / PHN16-72:

- AppIndicator-present tray menu flow.
- StatusNotifierWatcher-absent exit 0 flow.
- Tray quick-switch for all five profiles.
- Show AcerControl launch/focus.
- PHN16-72 full happy path across profiles, sensors, boot persistence, suspend/resume, and tray.
- Partial hardware behavior on second compatible laptop, or fixture-equivalent signoff if unavailable.

## User Setup Required

None for source execution. Manual UAT requires Ubuntu/Linux with GTK4/libadwaita, GTK3 Ayatana AppIndicator typelibs, AppIndicator extension state under test, polkit, systemd/login1, installed wrappers/unit files, `acer_wmi predator_v4=1`, and Acer platform profile sysfs.

## Next Phase Readiness

Phase 8 can plan packaging. Its packaging plan must satisfy the TRAY-04 Recommends contract now enforced by `tools/smoke_phase7.py` when `debian/control` exists.

## Self-Check: PASSED

- Production commit exists: `f75bb43`.
- UAT checklist commit exists: `665b532`.
- Summary file exists and lists requirements-completed: `[TRAY-04, HW-01, HW-02]`.
- Full Phase 1-7 automated smoke gates exit 0 on this host.
- Modified production files for this plan are limited to `tools/smoke_phase7.py`; no core/sysfs/GUI compatibility changes were needed.

---
*Phase: 07-tray-helper-hardware-compatibility*
*Completed: 2026-05-23*
