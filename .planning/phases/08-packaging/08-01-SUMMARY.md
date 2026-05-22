---
phase: 08-packaging
plan: 01
subsystem: packaging
tags: [debian, pyproject, smoke, tray]
requires:
  - phase: 07-tray-helper-hardware-compatibility
    provides: Separate GTK3/Ayatana tray helper and packaging Recommends handoff
provides:
  - Phase 8 side-effect-free packaging smoke runner
  - Installable acercontrol-tray console script metadata
affects: [packaging, tray, debian]
tech-stack:
  added: []
  patterns: [staged source/static packaging smoke checks]
key-files:
  created: [tools/smoke_phase8.py]
  modified: [pyproject.toml]
key-decisions:
  - "Phase 8 smoke checks remain source/static only and skip future packaging surfaces until those files exist."
  - "Packaged installs expose acercontrol, acercontrol-gui, and acercontrol-tray through pyproject project.scripts."
patterns-established:
  - "Packaging smoke checks validate metadata and documentation without invoking Debian tools or mutating system paths."
requirements-completed: [PKG-01]
duration: 12min
completed: 2026-05-23
---

# Phase 8 Plan 01 Summary

**Packaging smoke substrate with CLI, GUI, and tray console script metadata**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-23T02:22:00+05:30
- **Completed:** 2026-05-23T02:33:58+05:30
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added `tools/smoke_phase8.py`, a side-effect-free packaging smoke runner.
- Added `acercontrol-tray = "acercontrol.tray:main"` to `[project.scripts]`.
- Verified the new packaging gate plus Phase 1, Phase 2, and Phase 7 smoke checks.

## Task Commits

1. **Task 1: Add Phase 8 smoke runner wave 0** - `8ad90de` (test)
2. **Task 2: Add tray console script metadata** - `f2dd8ad` (build)
3. **Task 3: 08-01 regression pass** - verification only; no code changes

**Plan metadata:** pending this commit

## Files Created/Modified

- `tools/smoke_phase8.py` - Phase 8 static smoke runner with staged checks for packaging files, installer, docs, and no-pyc paths.
- `pyproject.toml` - Adds the `acercontrol-tray` console script.

## Decisions Made

- Kept Phase 8 checks side-effect-free on macOS; Debian build/lintian execution remains a later optional Linux gate.
- Kept runtime dependency declarations out of `pyproject.toml`; apt dependencies belong in `debian/control`.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

08-02 can add Debian metadata, desktop assets, icon assets, and modprobe configuration. The Phase 8 smoke runner already has staged checks ready to become strict as those files appear.

---
*Phase: 08-packaging*
*Completed: 2026-05-23*
