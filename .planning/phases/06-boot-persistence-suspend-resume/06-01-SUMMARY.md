---
phase: 06-boot-persistence-suspend-resume
plan: 01
subsystem: boot-persistence
tags: [systemd, boot-profile, privilege-wrapper, smoke-runner]

requires:
  - phase: 05-01
    provides: "MainWindow shared page, profile controls, sensor panel, and notification routing"
provides:
  - "Phase 6 smoke runner with source/static checks for boot units, systemd facade, GUI wiring, and resume hooks"
  - "Stable acer-performance.service boot unit backed by /etc/default/acercontrol"
  - "Templated acer-performance@.service immediate-apply unit for allowed kernel profile values"
  - "Stdlib-only acercontrol.systemd facade for boot config parsing, service status, and bounded startup wait"
  - "Strict acercontrol-manage-service allowlist covering only AcerControl boot units"
affects: [phase-06-boot-persistence-suspend-resume, systemd, privilege-boundary, gui]

tech-stack:
  added: []
  patterns:
    - "Boot profile writes delegate to existing real-binary wrappers; systemd units contain no shell redirection"
    - "Systemd status/config helpers degrade safely on non-systemd hosts"
    - "Service management wrapper uses literal allowlist entries, not wildcard service matching"

key-files:
  created:
    - "tools/smoke_phase6.py"
    - "data/acer-performance.service"
    - "data/acer-performance@.service"
    - "acercontrol/systemd.py"
    - ".planning/phases/06-boot-persistence-suspend-resume/06-01-SUMMARY.md"
  modified:
    - "libexec/acercontrol-manage-service"
    - ".planning/ROADMAP.md"
    - ".planning/STATE.md"

key-decisions:
  - "Kept the stable public unit name acer-performance.service for enable/status and added acer-performance@.service for immediate validated profile apply."
  - "Used /usr/libexec/acercontrol/acercontrol-setprofile from systemd ExecStart instead of shell snippets or direct sysfs writes."
  - "Centralized service/config behavior in acercontrol.systemd so GTK modules do not parse /etc/default/acercontrol or run systemctl directly."
  - "Expanded the service wrapper allowlist to the five known kernel-value template instances without wildcard support."

patterns-established:
  - "Phase 6 smoke checks SKIP future GUI/resume artifacts until they exist, then become strict source gates."
  - "read_boot_profile() returns Profile.BALANCED for missing or invalid config."
  - "wait_for_boot_service() uses a bounded systemctl is-active --wait call and never raises."

requirements-completed: [BOOT-01, BOOT-02]

duration: 11 min
completed: 2026-05-23
---

# Phase 6 Plan 01: Systemd Boot Substrate Summary

Boot persistence now has its non-GUI substrate: source/static gates, stable and templated systemd units, a safe systemd facade, and a service-management wrapper boundary that only accepts AcerControl boot units.

## Performance

- **Duration:** 11 min
- **Started:** 2026-05-23T00:37:53+05:30
- **Completed:** 2026-05-23T00:48:43+05:30
- **Tasks:** 4
- **Files changed:** 8

## Accomplishments

- Added `tools/smoke_phase6.py` with quick/full checks for planning docs, unit directives, stdlib-only systemd facade behavior, wrapper allowlist shape, and future GUI/resume wiring.
- Added `data/acer-performance.service`, a stable boot unit that reads `BOOT_PROFILE` from `/etc/default/acercontrol` and applies it through `acercontrol-setprofile`.
- Added `data/acer-performance@.service`, a templated immediate-apply unit that passes `%i` to the same privileged setprofile wrapper.
- Added `acercontrol/systemd.py` with defensive helpers for reading boot profile config, deriving safe template instances, reading service status, and waiting briefly for the boot unit.
- Extended `libexec/acercontrol-manage-service` to accept only `acer-performance.service` plus the five allowed template instances.

## Task Commits

1. **Task 1: Phase 6 smoke runner wave 0** - `045612c`
2. **Task 2: Add systemd boot units** - `2850afa`
3. **Task 3: Add stdlib systemd facade** - `6e0577f`
4. **Task 4: Extend service wrapper allowlist** - `1056a9d`

## Files Created/Modified

- `tools/smoke_phase6.py` - Phase 6 source/static smoke runner.
- `data/acer-performance.service` - Stable boot profile service.
- `data/acer-performance@.service` - Templated immediate-apply profile service.
- `acercontrol/systemd.py` - GTK-free boot config and systemd status facade.
- `libexec/acercontrol-manage-service` - Strict service allowlist expanded for Phase 6 units.
- `.planning/phases/06-boot-persistence-suspend-resume/06-01-SUMMARY.md` - This execution summary.
- `.planning/ROADMAP.md` / `.planning/STATE.md` - Phase progress metadata.

## Decisions Made

- The boot unit uses `Environment=BOOT_PROFILE=balanced` plus `EnvironmentFile=-/etc/default/acercontrol`, so missing config falls back to balanced.
- The template unit has no `[Install]` section because it is intended for immediate `systemctl start acer-performance@<kernel-value>.service` calls, not persistent enablement.
- `service_enabled()` intentionally collapses unusual states such as masked/static to `unknown`; the GUI can display that safely without inventing remediation.
- The wrapper rejection message now says `unsupported service` for unrelated services while preserving the same exit-code behavior.

## Deviations from Plan

### Auto-fixed Issues

- The first smoke runner check for GTK-free `acercontrol/systemd.py` looked for the token `gi`, which also appears inside normal words like `config`. It was narrowed to import-level tokens (`import gi`, `from gi`) before the facade was added.
- The full Phase 6 wrapper check expected the phrase `unsupported service`; the wrapper previously said `service ... not allowed`. The message was updated without changing the allowlist or return code.

---

**Total deviations:** 2 auto-fixed.
**Impact on plan:** No scope expansion; both changes made the planned source/static gates more accurate.

## Issues Encountered

- Native systemd, polkit, sysfs, and boot UAT cannot run on this macOS host. Verification here is limited to source/static smoke, py_compile, and wrapper rejection paths that do not call systemctl.

## Verification Results

- `python3 -m py_compile acercontrol/systemd.py tools/smoke_phase6.py` -> passed.
- `python3 tools/smoke_phase6.py --quick` -> 8/8 passed.
- `python3 tools/smoke_phase6.py` -> 10/10 passed.
- `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py` -> passed. Phase 3 retained its existing editable-install console-script skip.

## Human UAT Still Required

Run on the PHN16-72 Linux target after all Phase 6 plans:

- Install/copy the unit files, run `systemctl daemon-reload`, enable `acer-performance.service`, set a boot profile, cold boot, and verify `acercontrol get` before launching the GUI.
- Verify `journalctl -u acer-performance.service -b` shows the unit reached `active (exited)` before `graphical.target`.
- Confirm `systemctl start acer-performance@performance.service` applies Turbo only after the wrapper allowlist and polkit path are installed.

## User Setup Required

None for source execution. Hardware UAT requires Ubuntu/Linux with systemd, polkit, the libexec wrappers installed under `/usr/libexec/acercontrol/`, `acer_wmi predator_v4=1`, and platform profile sysfs available.

## Next Phase Readiness

Plan 06-02 can build the GUI boot panel on top of `acercontrol.systemd`, `run_privileged()`, the stable service name, and the template-instance helper.

## Self-Check: PASSED

- Production commits exist: `045612c`, `2850afa`, `6e0577f`, `1056a9d`.
- Summary file exists and lists requirements-completed: `[BOOT-01, BOOT-02]`.
- Full Phase 1-6 automated smoke gates exit 0 on this host.
- Modified production files are limited to `tools/smoke_phase6.py`, `data/acer-performance.service`, `data/acer-performance@.service`, `acercontrol/systemd.py`, and `libexec/acercontrol-manage-service`.

---
*Phase: 06-boot-persistence-suspend-resume*
*Completed: 2026-05-23*
