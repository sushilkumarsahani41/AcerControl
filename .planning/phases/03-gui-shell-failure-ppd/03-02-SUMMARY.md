---
phase: 03-gui-shell-failure-ppd
plan: 02
subsystem: gui-shell
tags: [gap-closure, bl-01, modprobe, idempotency, libexec-wrapper, smoke-runner]

requires:
  - phase: 03-01
    provides: "GTK4/libadwaita GUI shell, StatusPage routing, and acer_wmi reload helper wiring"
provides:
  - "BL-01 fix: acercontrol-reload-acer-wmi skips modprobe -r when acer_wmi is already absent"
  - "Phase 3 smoke regression scenario for the unloaded-module reload path"
affects: [phase-03-verification, phase-04-profile-control]

tech-stack:
  added: []
  patterns:
    - "Idempotency pre-probe before privileged state-change work"
    - "Static smoke regression for privileged Linux-only branch coverage"

key-files:
  created:
    - ".planning/phases/03-gui-shell-failure-ppd/03-02-SUMMARY.md"
  modified:
    - "libexec/acercontrol-reload-acer-wmi"
    - "tools/smoke_phase3.py"

key-decisions:
  - "Used os.path.exists('/sys/module/acer_wmi') as the reload helper pre-probe rather than swallowing modprobe -r failures."
  - "Kept 03-REVIEW.md warning/info cleanup out of this gap closure."

patterns-established:
  - "Privileged wrappers should pre-probe cheap local state before executing destructive or failure-prone state transitions."
  - "Hardware/root-only behavior can be guarded by source-level smoke checks plus explicit human UAT carry-forward."

requirements-completed: [GUI-03]

duration: 13 min
completed: 2026-05-21
---

# Phase 3 Plan 2: BL-01 Gap Closure Summary

**acer_wmi reload helper now skips unload when the module is absent, with smoke coverage for the first-run Load module path.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-05-21T11:15:00Z
- **Completed:** 2026-05-21T11:28:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Patched `libexec/acercontrol-reload-acer-wmi` to pre-probe `/sys/module/acer_wmi` before calling `modprobe -r`.
- Added `scenario_reload_wmi_unloaded_path` to `tools/smoke_phase3.py` and registered it in the always-on quick smoke path.
- Restored the GUI-03 SC#2 remediation path: the GUI "Load module" CTA can now reach `modprobe acer_wmi predator_v4=1` when `acer_wmi` is not loaded.

## Task Commits

1. **Task 1: Patch reload wrapper pre-probe** - `250b4eb` (fix)
2. **Task 2: Add unloaded-module smoke regression** - `250b4eb` (fix)

## Files Created/Modified

- `libexec/acercontrol-reload-acer-wmi` - Added `os.path.exists("/sys/module/acer_wmi")` guard around the unload step.
- `tools/smoke_phase3.py` - Added and registered `scenario_reload_wmi_unloaded_path`.
- `.planning/phases/03-gui-shell-failure-ppd/03-02-SUMMARY.md` - Captures execution outcome and carry-forward UAT.

## Decisions Made

- Used the explicit `os.path.exists` guard from 03-VERIFICATION.md rather than dropping `check=True`; this keeps genuine unload failures visible while avoiding the "already unloaded" short-circuit.
- Left 03-REVIEW.md WR-01..WR-05 and IN-01..IN-03 untouched. They remain non-blocking cleanup for a future warning-cleanup slice or Phase 4 housekeeping.

## Deviations from Plan

### Auto-fixed Issues

None - plan executed as scoped.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope expansion. The only noted variance is that the plan's indentation grep for `[MODPROBE, "-r", MODULE]` conflicted with its own target code block; normal Python continuation indentation was kept and source order is verified by the new smoke scenario.

## Issues Encountered

- The consolidated wrapper shell assertion initially failed without diagnostics. Re-running individual assertions confirmed the wrapper contract: one guard token, rc 64 for extra argv, rc 77 for non-root, 0755 mode, correct shebang, no `from acercontrol` imports, and guard-before-unload source order.

## Verification Results

- `python3 tools/smoke_phase3.py` -> 18/18 passed.
- `python3 tools/smoke_phase3.py --quick` -> 14/14 passed.
- `python3 tools/smoke_phase1.py` -> 6/6 passed.
- `python3 tools/smoke_phase2.py` -> 28/28 passed.
- Wrapper contract checks passed individually.

## Human UAT Still Required

The BL-01 blocker is unblocked for real PHN16-72 testing, but these runtime checks still require Linux hardware, polkit, and a graphical session:

- StatusPage "Load module" end-to-end after `sudo modprobe -r acer_wmi`.
- Polkit dialog text for `org.acercontrol.reload-acer-wmi`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 3 automated gap closure is complete. Run human UAT on the PHN16-72, then re-run Phase 3 verification. Phase 4 can proceed after Phase 3 is marked verified.

## Self-Check: PASSED

- Production commit exists: `250b4eb`.
- Summary file exists and includes requirements-completed: `[GUI-03]`.
- Smoke results match the plan targets: Phase 3 full 18/18, Phase 3 quick 14/14, Phase 1 6/6, Phase 2 28/28.
- Modified production files are limited to `libexec/acercontrol-reload-acer-wmi` and `tools/smoke_phase3.py`.

---
*Phase: 03-gui-shell-failure-ppd*
*Completed: 2026-05-21*
