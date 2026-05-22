---
phase: 5
slug: live-sensors-notifications
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-23
---

# Phase 5 - Validation Strategy

> Per-phase validation contract for live sensors and notifications.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Project smoke runners, no pytest dependency |
| Config file | `pyproject.toml`; no pytest config |
| Quick run command | `python3 tools/smoke_phase5.py --quick` |
| Full suite command | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py` |
| Estimated runtime | Less than 15 seconds for source/static smoke checks on this host |

---

## Sampling Rate

- After every task commit: run `python3 tools/smoke_phase5.py --quick` once Wave 0 creates it.
- After the plan wave: run the full Phase 1-5 smoke suite.
- Before `$gsd-verify-work`: full automated suite must be green, then manual PHN16-72 UAT must cover GTK/sysfs/notification behavior.
- Max feedback latency: 15 seconds for automated source/static checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | SENS-01, SENS-02, SENS-03, NOTI-01, NOTI-02 | T-05-01..T-05-06 | Phase 5 invariants are source-gated before implementation. | source smoke | `python3 tools/smoke_phase5.py --quick` | no - Wave 0 creates it | pending |
| 05-01-02 | 01 | 1 | NOTI-01, NOTI-02 | T-05-05, T-05-06 | Notifications use stable IDs and focus-aware routing. | source smoke + manual UAT | `python3 tools/smoke_phase5.py --quick` | no - Wave 0 creates it | pending |
| 05-01-03 | 01 | 1 | SENS-01, SENS-02, SENS-03 | T-05-01, T-05-02, T-05-03 | Sensor rows render `read_sensors()` snapshots without direct sysfs reads or GTK threads. | source smoke + manual UAT | `python3 tools/smoke_phase5.py --quick` | no - Wave 0 creates it | pending |
| 05-01-04 | 01 | 1 | SENS-01, SENS-04, NOTI-01, NOTI-02 | T-05-01, T-05-03, T-05-04, T-05-05 | MainWindow owns timer lifecycle, single scroll page, and profile/sensor notification coordination. | source smoke + regression | full Phase 1-5 smoke suite | no - depends on tasks 1-3 | pending |

*Status values: pending, green, red, flaky.*

---

## Wave 0 Requirements

- [ ] `tools/smoke_phase5.py` - source/static smoke runner covering SENS-01..04 and NOTI-01..02.
- [ ] Quick mode can pass before `gui_sensors.py` / `gui_notifications.py` exist; strict checks activate once implementation files exist.
- [ ] Smoke checks forbid `threading.Thread`, `GLib.idle_add`, direct `/sys/class/hwmon` reads in GUI modules, and raw worker-thread GTK patterns.
- [ ] Smoke checks require `GLib.timeout_add_seconds(2,`, `GLib.source_remove`, `read_sensors()`, named threshold constants, and stable notification IDs.
- [ ] Smoke checks preserve Phase 1-4 regression behavior.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 30 minute GTK soak with live panel active. | SENS-04 | Requires Linux GTK session and target hardware. | Open `acercontrol-gui` for 30 minutes; run `journalctl --user --since "30 min ago"` and confirm zero `Gtk-CRITICAL` or `Gtk-WARNING` lines from AcerControl. |
| Real sensor refresh cadence and no flicker. | SENS-01, SENS-02 | Requires live hwmon values. | Watch CPU package, Acer temps, and fan rows for at least 60 seconds; values update at roughly 2 second cadence and rows do not resize or flicker. |
| Missing single sensor placeholder. | SENS-03 | Requires controlled sysfs/hwmon manipulation or bind-mount test on Linux. | Temporarily hide one Acer `temp*_input`; confirm only that row shows the placeholder while other rows continue updating; restore file and confirm value returns within one tick. |
| Critical temperature hysteresis unfocused. | NOTI-02 | Requires real desktop notification service and thermal stress. | Unfocus GUI, run `stress-ng --cpu 0 --timeout 90s`, confirm exactly one `CPU temperature critical` notification crossing >=90 C and exactly one `CPU temperature back to normal` notification crossing <85 C. |
| Critical temperature focused. | NOTI-02 | Requires active GUI focus and thermal stress. | Repeat stress with GUI focused; confirm zero system notifications and in-app toast feedback only. |
| Profile changed externally. | NOTI-01 | Requires running GUI plus CLI writes. | Unfocus GUI, run `acercontrol set balanced` or another profile from terminal, confirm one stable `Profile changed` system notification. |

---

## Threat References

| ID | Threat | Mitigation |
|----|--------|------------|
| T-05-01 | GTK crash from cross-thread widget updates. | Use `GLib.timeout_add_seconds(2, ...)` on the main loop; forbid worker threads. |
| T-05-02 | GUI bypasses core sensor resolver and reintroduces hwmon index drift. | GUI code imports `read_sensors()` only; direct hwmon/sysfs paths remain in core/sysfs. |
| T-05-03 | Timer callback survives window teardown. | Store source ID and remove it with `GLib.source_remove()` on close/destroy. |
| T-05-04 | Misleading thermal UI due color-only state. | Render numeric values/placeholders alongside bars; color is secondary. |
| T-05-05 | Notification spam while temperature stays critical. | Hysteresis state sends only on crossings and uses stable notification IDs. |
| T-05-06 | Focused-window system notification noise. | Focus-aware router uses `Adw.Toast` while focused and `Gio.Notification` only while unfocused. |

---

## Validation Sign-Off

- [x] All phase requirements have automated smoke coverage planned or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing automated references.
- [x] No watch-mode flags.
- [x] Feedback latency target is less than 15 seconds for automated checks.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-05-23
