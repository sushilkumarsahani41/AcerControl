---
phase: 08-packaging
plan: 03
subsystem: packaging
tags: [install, docs, uat, cli-bundle]
requires:
  - phase: 08-packaging
    provides: Debian metadata, desktop assets, icons, and modprobe config
provides:
  - Manual fallback install script
  - User-facing Debian build/install documentation
  - Phase 8 Linux package and fallback UAT checklist
affects: [packaging, install, documentation]
tech-stack:
  added: []
  patterns: [root-aware manual installer, Linux-only UAT separated from local smoke]
key-files:
  created: [install.sh, .planning/phases/08-packaging/08-HUMAN-UAT.md]
  modified: [README.md, tools/smoke_phase8.py]
key-decisions:
  - "Fallback install writes wrappers to /usr/libexec/acercontrol so the installed polkit policy action annotations remain valid."
  - "Linux package build, lintian, no-pyc archive inspection, and VM install remain manual/Linux UAT when unavailable locally."
patterns-established:
  - "Manual fallback launchers set PYTHONPATH to /usr/local/share/acercontrol before running GUI/tray modules."
requirements-completed: [PKG-08, PKG-11]
duration: 21min
completed: 2026-05-23
---

# Phase 8 Plan 03 Summary

**Manual installer fallback and Linux package UAT documentation**

## Performance

- **Duration:** 21 min
- **Started:** 2026-05-23T02:38:00+05:30
- **Completed:** 2026-05-23T02:59:08+05:30
- **Tasks:** 4
- **Files modified:** 4

## Accomplishments

- Added executable `install.sh` for manual/non-Debian installs.
- Documented Debian build/install and fallback install flows in `README.md`.
- Added Phase 8 human UAT for build, lintian, no-pyc archive checks, clean VM install, launcher/icon, polkit, wrappers, systemd, modprobe, and fallback installer validation.
- Verified Phase 2, Phase 7, and Phase 8 smoke gates after installer/docs changes.

## Task Commits

1. **Task 1: Expand smoke for fallback installer and docs** - `f9d8d0f` (test)
2. **Task 2: Add install.sh fallback** - `55cfb7c` (chore)
3. **Task 3: Update README and add Phase 8 UAT checklist** - `9b4dd20` (docs)
4. **Task 4: 08-03 regression pass** - verification only; no code changes

**Plan metadata:** pending this commit

## Files Created/Modified

- `install.sh` - Root-aware fallback installer for CLI, GUI/tray launchers, package code, wrappers, policy, units, desktop file, icons, modprobe config, and cache/initramfs refresh.
- `README.md` - Runtime deps, build deps, `.deb` build/install flow, fallback install flow, command names, and reboot note.
- `.planning/phases/08-packaging/08-HUMAN-UAT.md` - Linux packaging and fallback install UAT checklist.
- `tools/smoke_phase8.py` - Added fallback launcher/package-copy assertions.

## Decisions Made

- Manual fallback uses `/usr/libexec/acercontrol` for wrappers despite installing launchers under `/usr/local/bin`, preserving named polkit action compatibility.
- `install.sh --dry-run` is supported for previewing system writes without mutating the target.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## User Setup Required

None for source/static verification. Linux package build/install UAT remains manual on Ubuntu 24.04 or target hardware.

## Next Phase Readiness

08-04 can run final source/static regression locally and attempt optional Debian build/lintian/no-pyc checks if the host provides Debian tooling.

---
*Phase: 08-packaging*
*Completed: 2026-05-23*
