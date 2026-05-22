---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Phase 8 source/static execution complete; Linux package UAT pending
last_updated: "2026-05-23T03:01:30+05:30"
last_activity: 2026-05-23 -- Phase 8 08-04 final source/static regression passed
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 16
  completed_plans: 16
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Click a profile button → laptop switches profile → see thermal state in real time.
**Current focus:** Phase 08 — packaging

## Current Position

Phase: 08 (packaging) — SOURCE/STATIC EXECUTION COMPLETE
Plan: 4 of 4
Status: Linux package build/lintian/no-pyc/clean-VM UAT pending
Last activity: 2026-05-23 -- Phase 8 08-04 final source/static regression passed

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**

- Total plans completed: 12
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| — | — | — | — |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 2 P1 | 50 | 6 tasks | 10 files |
| Phase 03 P02 | 13 min | 2 tasks | 2 files |
| Phase 04 P01 | 5 min | 3 tasks | 5 files |
| Phase 05 planning | — | 4 tasks planned | 5 files planned |
| Phase 05 P01 | 5 min | 4 tasks | 5 files |
| Phase 06 planning | — | 12 tasks planned | 9 files planned |
| Phase 06 P01 | 11 min | 4 tasks | 5 production files |
| Phase 06 P02 | 5 min | 4 tasks | 4 production files |
| Phase 06 P03 | 4 min | 4 tasks | 3 production files |
| Phase 07 planning | — | 12 tasks planned | 6 production files planned |
| Phase 07 P01 | 8 min | 4 tasks | 3 production files |
| Phase 07 P02 | 4 min | 4 tasks | 3 production files |
| Phase 07 P03 | 4 min | 4 tasks | 1 production file |
| Phase 08 planning | — | 15 tasks planned | 3 production files planned plus packaging/data/docs |
| Phase 08 P01 | 12 min | 3 tasks | 2 files |
| Phase 08 P02 | 4 min | 4 tasks | 15 files |
| Phase 08 P03 | 21 min | 4 tasks | 4 files |
| Phase 08 P04 | 3 min | 4 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Adopted research SUMMARY.md 8-phase build order verbatim — dependency-resolved, no deviation
- Roadmap: Privilege boundary stood up end-to-end against CLI in Phase 2 before any GUI exists (security model provable before UI)
- Roadmap: Sensor refresh uses `GLib.timeout_add_seconds(2, …)` on main loop (not a thread) — research finding overrides PROJECT.md/CLAUDE.md draft thread-based pattern; sub-ms sysfs reads make thread complexity unjustified
- Phase 5: MainWindow owns the shared `Adw.PreferencesPage`; profile controls and sensor rows are sibling groups under one scroller.
- Phase 5: Profile-change and critical-temperature feedback is centralized in notifier classes with focus-aware toast/system notification routing.
- Phase 5: Critical temperature notifications use hysteresis: enter at >=90 C, leave below 85 C, stable notification IDs.
- Phase 6 planning: Ship stable `acer-performance.service` for status/enable and templated `acer-performance@.service` for immediate profile apply.
- Phase 6 planning: Boot service mutations stay behind existing wrappers; GUI boot panel must not call pkexec/sudo/systemctl directly.
- Phase 6 planning: Resume handling uses Gio login1 `PrepareForSleep(false)` and best-effort reapply; no new D-Bus dependency.
- Phase 6 P01: Systemd units delegate profile writes to `acercontrol-setprofile`; no shell snippets or direct sysfs writes in unit files.
- Phase 6 P01: `acercontrol.systemd` is the GTK-free facade for boot config, service status, and bounded boot-unit waiting.
- Phase 6 P02: BootServicePanel uses wrapper-only mutations and displays only user-facing profile names.
- Phase 6 P02: MainWindow attempts a one-shot boot-service wait before live refresh and before profile-click writes.
- Phase 6 P03: Resume handling uses Gio login1 `PrepareForSleep`; before-sleep is ignored, after-resume re-applies only when read-back differs.
- Phase 6 P03: Resume restore failures/cancellations stay silent to avoid notification spam after repeated resume cycles.
- Phase 7 planning: Tray helper must be a separate GTK3/Ayatana process; the GTK4 GUI may report tray status but must not import the tray helper.
- Phase 7 planning: `StatusNotifierWatcher` absence is not an error; `acercontrol-tray` exits 0 and About diagnostics mention tray status.
- Phase 7 planning: TRAY-04 is enforced as a packaging handoff gate now and implemented by Phase 8 when `debian/control` exists.
- Phase 7 P01: `acercontrol.tray_status` is Gio-only and owns session watcher detection; the GTK4 GUI imports this helper, not the GTK3 tray process.
- Phase 7 P01: About diagnostics include a top-level `tray` object with stable status/watcher/detail fields.
- Phase 7 P02: `acercontrol.tray` is the only GTK3/Ayatana source and gates imports behind `tray_status()`.
- Phase 7 P02: Tray profile changes use `run_privileged(["acercontrol-setprofile", PROFILES[profile_name]])`; Show AcerControl uses process launch only and does not import GTK4 modules.
- Phase 7 P03: Hardware compatibility is fixture-gated for duplicate `acer` hwmon entries, missing fan/temp values, and filtered platform profile choices.
- Phase 7 P03: TRAY-04 remains a Phase 8 packaging handoff; the smoke check enforces Recommends once `debian/control` exists.
- Phase 8 planning: Split packaging into four plans: smoke/entrypoints, Debian data/metadata, manual installer/docs, and final build/lintian/UAT closeout.
- Phase 8 planning: `acercontrol-tray` must become a pyproject console script in 08-01; root `acercontrol_tray.py` remains a development shim.
- Phase 8 planning: Manual fallback install must copy wrappers to `/usr/libexec/acercontrol` so the installed polkit policy's `exec.path` annotations still match.
- Phase 8 planning: Linux-only package build/lintian/apt-install gates are documented and recorded truthfully if unavailable on the execution host.
- Phase 8 P01: `tools/smoke_phase8.py` is the staged, side-effect-free packaging gate; `debian/`, desktop/icon, installer, and UAT checks skip until their files exist.
- Phase 8 P01: `acercontrol-tray` is now an installable pyproject console script alongside `acercontrol` and `acercontrol-gui`.
- Phase 8 P02: Debian package metadata uses debhelper compat 13 + pybuild; system data installs through `debian/acercontrol.install`, not setuptools package data.
- Phase 8 P02: Desktop identity is `org.acercontrol.AcerControl.desktop` with matching hicolor color/symbolic icons; tray packages are `Recommends`, not `Depends`.
- Phase 8 P03: Manual `install.sh` installs launchers under `/usr/local/bin` but wrappers under `/usr/libexec/acercontrol` to keep polkit `exec.path` annotations valid.
- Phase 8 P03: Linux build/lintian/no-pyc/clean-VM checks are documented in `08-HUMAN-UAT.md`; local smoke remains source/static only.
- Phase 8 P04: Full Phase 1-8 source/static smoke passed on 2026-05-23; `dpkg-buildpackage`, `lintian`, and `dpkg` were unavailable locally and are recorded as Linux-pending UAT.
- [Phase ?]: Phase 2: Defense-in-depth wrapper allowlist (P2-NEW-01) — wrappers hardcode ALLOWED_KERNEL_VALUES literal tuples; pkexec scrubs PYTHONPATH
- [Phase ?]: Phase 2: SSH_CONNECTION → sudo precedence over pkexec (PRIV-05; pkexec hangs over SSH)
- [Phase ?]: Phase 2: Bundler concat semantics (P2-NEW-08) — hoisted future-import + stripped main blocks + SELF_ALIASES module bridges
- [Phase ?]: Phase 2: cmd_install step (c) systemctl enable acer-performance.service is best-effort with stderr warning until Phase 6 ships the unit

### Pending Todos

- Phase 5 hardware UAT: 30-minute GTK soak, missing-sensor row fallback, focused/unfocused critical-temperature notifications, and unfocused CLI profile-change notification on PHN16-72.
- Phase 6 hardware UAT: cold boot persistence, GUI boot-service toggle/profile write, startup race, and suspend/resume profile restore on PHN16-72.
- Phase 7 Ubuntu UAT: complete `.planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md`.
- Phase 8 Linux UAT: run `dpkg-buildpackage -us -uc -b`, `lintian ../acercontrol_*.deb`, no-pyc archive inspection, clean Ubuntu 24.04 VM install, and target hardware checks from `08-HUMAN-UAT.md`.

### Blockers/Concerns

- Open question (resolve during Phase 7 / Phase 1): does `acer_wmi predator_v4=1` preserve `platform_profile` across S3 on PHN16-72? Determines whether BOOT-05 logind hook is belt-and-braces or required.
- Open question (resolve in Phase 1): Python version floor — PROJECT.md says 3.10+ but `tomllib` requires 3.11+; Ubuntu 24.04 ships 3.12 so narrowing to 3.11+ is cost-free.
- Coverage note: REQUIREMENTS.md footer says "52 total" v1 items but the actual REQ-IDs sum to 54 (CORE 6 + PRIV 5 + CLI 7 + GUI 8 + SENS 4 + NOTI 2 + BOOT 5 + TRAY 4 + PKG 11 + HW 2). Footer counter to be corrected during traceability update; all 54 mapped to phases.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-05-23T03:01:30+05:30
Stopped at: Phase 8 source/static execution complete; Linux package UAT pending
Resume file: None
