---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
stopped_at: Phase 7 plan 07-01 complete; ready to execute 07-02
last_updated: "2026-05-23T01:31:13+05:30"
last_activity: 2026-05-23 -- Phase 7 plan 07-01 complete
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 12
  completed_plans: 10
  percent: 83
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-13)

**Core value:** Click a profile button → laptop switches profile → see thermal state in real time.
**Current focus:** Phase 07 — tray-helper-hardware-compatibility

## Current Position

Phase: 07 (tray-helper-hardware-compatibility) — IN PROGRESS
Plan: 1 of 3 complete
Status: Ready to execute 07-02
Last activity: 2026-05-23 -- Phase 7 plan 07-01 complete

Progress: [████████░░] 83%

## Performance Metrics

**Velocity:**

- Total plans completed: 10
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
- [Phase ?]: Phase 2: Defense-in-depth wrapper allowlist (P2-NEW-01) — wrappers hardcode ALLOWED_KERNEL_VALUES literal tuples; pkexec scrubs PYTHONPATH
- [Phase ?]: Phase 2: SSH_CONNECTION → sudo precedence over pkexec (PRIV-05; pkexec hangs over SSH)
- [Phase ?]: Phase 2: Bundler concat semantics (P2-NEW-08) — hoisted future-import + stripped main blocks + SELF_ALIASES module bridges
- [Phase ?]: Phase 2: cmd_install step (c) systemctl enable acer-performance.service is best-effort with stderr warning until Phase 6 ships the unit

### Pending Todos

- Phase 5 hardware UAT: 30-minute GTK soak, missing-sensor row fallback, focused/unfocused critical-temperature notifications, and unfocused CLI profile-change notification on PHN16-72.
- Phase 6 hardware UAT: cold boot persistence, GUI boot-service toggle/profile write, startup race, and suspend/resume profile restore on PHN16-72.
- Execute Phase 7 plans 07-02 and 07-03.

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

Last session: 2026-05-23T01:31:13+05:30
Stopped at: Phase 7 plan 07-01 complete; ready to execute 07-02
Resume file: None
