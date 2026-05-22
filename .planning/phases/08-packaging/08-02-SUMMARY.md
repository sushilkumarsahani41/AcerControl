---
phase: 08-packaging
plan: 02
subsystem: packaging
tags: [debian, desktop, icons, modprobe, tray]
requires:
  - phase: 08-packaging
    provides: Phase 8 packaging smoke runner and console-script metadata
provides:
  - Debian package metadata and install rules
  - GNOME desktop launcher identity and hicolor icons
  - Persistent acer_wmi predator_v4 modprobe configuration
  - Phase 7 TRAY-04 Recommends-only packaging handoff
affects: [packaging, desktop, polkit, systemd, tray]
tech-stack:
  added: [debhelper, pybuild]
  patterns: [hand-written debian packaging, FHS system data install rules]
key-files:
  created: [debian/control, debian/changelog, debian/copyright, debian/rules, debian/source/format, debian/acercontrol.install, debian/acercontrol.postinst, debian/acercontrol.postrm, data/org.acercontrol.AcerControl.desktop, data/99-acer-wmi.conf, data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg, data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg]
  modified: [tools/smoke_phase8.py, tools/smoke_phase7.py]
key-decisions:
  - "System data is installed through debian/acercontrol.install rather than setuptools package_data."
  - "Tray dependencies are Recommends only and are validated by both Phase 7 and Phase 8 smoke checks."
patterns-established:
  - "Debian maintainer scripts refresh desktop/icon caches and systemd daemon state while preserving #DEBHELPER#."
requirements-completed: [PKG-02, PKG-03, PKG-04, PKG-09, PKG-10, PKG-11, TRAY-04]
duration: 4min
completed: 2026-05-23
---

# Phase 8 Plan 02 Summary

**Debian metadata and desktop/system data install plane for AcerControl packaging**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-23T02:34:00+05:30
- **Completed:** 2026-05-23T02:37:54+05:30
- **Tasks:** 4
- **Files modified:** 15

## Accomplishments

- Added the `org.acercontrol.AcerControl.desktop` launcher and matching hicolor color/symbolic icons.
- Added `data/99-acer-wmi.conf` with `options acer_wmi predator_v4=1`.
- Added hand-written Debian metadata, install maps, and maintainer scripts.
- Satisfied the Phase 7 TRAY-04 gate against real `debian/control`.

## Task Commits

1. **Task 1: Expand smoke for Debian/data contracts** - `9ab0b68` (test)
2. **Task 2: Add desktop, icons, and modprobe data** - `dd1267a` (chore)
3. **Task 3: Add Debian metadata and install rules** - `62f5909` (chore)
4. **Task 4: 08-02 regression pass** - verification only; no code changes

**Plan metadata:** pending this commit

## Files Created/Modified

- `debian/control` - Build/runtime dependency metadata with tray packages under `Recommends`.
- `debian/acercontrol.install` - FHS install map for wrappers, policy, units, desktop file, icons, and modprobe config.
- `debian/acercontrol.postinst` / `debian/acercontrol.postrm` - Cache and daemon refresh hooks plus initramfs/reboot guidance.
- `data/org.acercontrol.AcerControl.desktop` - Desktop launcher basename matching the GTK application ID.
- `data/icons/hicolor/...` - Scalable color and symbolic SVG icons.
- `data/99-acer-wmi.conf` - Persistent `acer_wmi predator_v4=1` configuration.
- `tools/smoke_phase7.py` - Parser fix for Debian field extraction.
- `tools/smoke_phase8.py` - Stricter Debian maintainer-script and metadata checks.

## Decisions Made

- Used `Architecture: all` because the Python package and data files are architecture-independent.
- Kept AppIndicator libraries as `Recommends`, not hard dependencies, preserving minimal install support.

## Deviations from Plan

### Auto-fixed Issues

**1. Phase 7 Debian-control parser handled only paragraph-leading fields**
- **Found during:** Task 3 (Add Debian metadata and install rules)
- **Issue:** `tools/smoke_phase7.py` looked for `Depends:` and `Recommends:` only at paragraph start, which failed against valid Debian binary package paragraphs beginning with `Package:`.
- **Fix:** Added field extraction that scans fields and continuation lines inside a paragraph.
- **Files modified:** `tools/smoke_phase7.py`
- **Verification:** `python3 tools/smoke_phase7.py`
- **Committed in:** `62f5909`

**Total deviations:** 1 auto-fixed parser issue.
**Impact on plan:** Necessary for TRAY-04 validation against real Debian metadata; no requirement scope changed.

## Issues Encountered

None beyond the parser auto-fix above.

## User Setup Required

None.

## Next Phase Readiness

08-03 can add the manual `install.sh` fallback and packaging UAT documentation. Debian metadata and desktop/system data contracts are now enforced by Phase 8 smoke.

---
*Phase: 08-packaging*
*Completed: 2026-05-23*
