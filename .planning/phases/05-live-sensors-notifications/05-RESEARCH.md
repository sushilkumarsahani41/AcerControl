# Phase 5: Live Sensors + Notifications - Research

**Researched:** 2026-05-23  
**Domain:** GTK4/libadwaita live sensor UI, main-loop sysfs polling, focus-aware `Gio.Notification` behavior  
**Confidence:** HIGH for codebase contracts and no-thread refresh; MEDIUM for real desktop notification delivery until installed `.desktop` UAT on Linux

## User Constraints

No `05-CONTEXT.md` exists for this phase. Planning constraints come from `AGENTS.md`, `ROADMAP.md`, `REQUIREMENTS.md`, project research, Phase 4 summary, and the approved `05-UI-SPEC.md`.

### Locked Scope

- Phase 5 adds the live sensor panel and notifications only. Boot persistence, tray helper, suspend/resume, icons, and packaging remain later phases.
- Sensor refresh must use `GLib.timeout_add_seconds(2, ...)` on the GTK main loop. Do not add `threading.Thread`, `asyncio`, or a worker-to-GTK bridge in this phase.
- GUI sensor reads must use `acercontrol.core.read_sensors()`, not direct sysfs path walking in GUI modules.
- Existing Phase 3 blocker routing and Phase 4 profile-control behavior must continue passing their smoke suites.
- `Gio.Notification` support depends on `Adw.Application(application_id="org.acercontrol.AcerControl")`; the matching `.desktop` file is a Phase 8 packaging responsibility, so source-level support can ship now while live notification delivery is verified on the Linux target.

### Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SENS-01 | 2 second tick reads CPU package, fan 1/2 RPM, and available Acer temps. | `core.read_sensors()` already returns `SensorReading(cpu_package_c, fan1_rpm, fan2_rpm, acer_temp1_c, acer_temp2_c, acer_temp3_c)`. |
| SENS-02 | Temperature bars color-coded green/yellow/red and update without flicker. | Use stable rows with `Gtk.ProgressBar`/`Gtk.LevelBar`; update label text and fraction in place; threshold constants `<70`, `70-84`, `>=85`. |
| SENS-03 | Sensor read failures show placeholders, do not crash, and resolver retries once on `OSError`. | `core.read_sensors()` and `sysfs.read_acer_sensors()` return `None` for missing values; `read_sensors()` invalidates hwmon cache and retries once when both key Acer reads fail. |
| SENS-04 | 30 minute GUI soak produces zero GTK criticals. | Main-loop timer avoids cross-thread GTK writes; cleanup must remove GLib source on window close. |
| NOTI-01 | Profile-change notifications use Toast focused, Gio.Notification unfocused; stable ID. | Centralize in `MainWindow.notify_profile_change(profile_name)`, route Phase 4 success path and external profile-change detection through it. |
| NOTI-02 | Critical-temp notifier uses hysteresis and focus suppression. | Track `critical_active`; enter at `>=90`, leave at `<85`; use stable IDs `critical-temp` and `critical-temp-normal`; send Gio only when unfocused. |

## Summary

Phase 5 should be implemented as a narrow GUI extension on top of Phase 4: refactor main content so `MainWindow` owns one `Gtk.ScrolledWindow` and one `Adw.PreferencesPage`, then place the existing profile group followed by a new `SensorPanel`. The profile state machine remains in `gui_profiles.py`; the sensor UI and notification state machines should be separate modules so the Phase 4 code does not absorb thermal concerns.

Primary recommendation:

1. Add `tools/smoke_phase5.py` first as a GTK-free source/static runner.
2. Add `acercontrol/gui_notifications.py` with `ProfileChangeNotifier` and `CriticalTempNotifier`.
3. Add `acercontrol/gui_sensors.py` with `SensorPanel`, threshold constants, bar rows, and `read_sensors()` rendering.
4. Refactor `acercontrol/gui_window.py` and `acercontrol/gui_profiles.py` so one main page contains profile and sensor groups; own the 2 second timer and notification coordination from `MainWindow`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Sensor value discovery | `acercontrol.core` / `acercontrol.sysfs` | GUI rendering | Core already handles hwmon drift, missing values, and retry-on-read-failure. |
| Sensor rows and bars | `acercontrol.gui_sensors` | `MainWindow` lifecycle | Keeps GTK widgets and threshold styling isolated from profile-control state. |
| Timer lifecycle | `MainWindow` or `SensorPanel` with explicit `shutdown()` | GLib main loop | Source ID must be removed when the window closes to avoid callbacks against destroyed widgets. |
| Profile-change notification | `acercontrol.gui_notifications` | `ProfileControlPanel` / `MainWindow` | Centralizes focused/unfocused behavior and stable notification ID. |
| Critical-temp notification | `acercontrol.gui_notifications` | `SensorPanel` tick | Hysteresis state belongs outside display rows so UI rendering remains simple. |
| Static validation | `tools/smoke_phase5.py` | Phase 1-4 smoke suites | macOS host lacks GTK/sysfs/polkit; source gates catch architectural regressions. |

## Standard Stack

| Module / API | Use | Decision |
|--------------|-----|----------|
| `GLib.timeout_add_seconds(2, callback)` | Sensor refresh timer | Required by roadmap and stack research; no worker thread. |
| `GLib.source_remove(source_id)` | Window close cleanup | Required to prevent timer callbacks after window teardown. |
| `acercontrol.core.read_sensors()` | Sensor snapshot | Only GUI sensor read API in Phase 5. |
| `Gtk.ProgressBar` or `Gtk.LevelBar` | Sensor bars | Use stable dimensions; update in place. |
| `Adw.Toast` | Focused feedback | Existing `MainWindow.show_toast()` already wraps the toast overlay. |
| `Gio.Notification` | Unfocused system feedback | Use `application.send_notification(stable_id, notification)`. |
| `Adw.Application.props.active_window` / `Gtk.Window.is_active()` | Focus routing | Determine whether to use toast or system notification. |

## Codebase Findings

### Existing Sensor API

`acercontrol.core.SensorReading` is already shaped for Phase 5:

- `cpu_package_c: Optional[float]`
- `fan1_rpm: Optional[int]`
- `fan2_rpm: Optional[int]`
- `acer_temp1_c: Optional[float]`
- `acer_temp2_c: Optional[float]`
- `acer_temp3_c: Optional[float]`

`read_sensors()` never raises for missing sysfs values. The GUI should treat `None` as unavailable and render the placeholder.

### Existing Main Window Boundary

`MainWindow` currently appends `ProfileControlPanel(self)` directly after `_main_banners`. Because Phase 4's `ProfileControlPanel` owns a `Gtk.ScrolledWindow` and `Adw.PreferencesPage`, Phase 5 needs to move the single scroller/page boundary into `MainWindow` before adding `SensorPanel`. Otherwise the profile scroller will consume available vertical space and make the sensor panel a sibling that is awkward to reach or invisible.

### Existing Profile Success Path

`ProfileControlPanel._verify_readback()` currently calls `_toast(f"Switched to {requested_profile}")` directly. Phase 5 should change only the success-notification call site to delegate to `MainWindow.notify_profile_change(requested_profile)`. Failure, cancel, and mismatch messages remain Phase 4-owned exact strings.

### Existing Application ID

`AcerControlApp` uses `application_id="org.acercontrol.AcerControl"`. This is correct for `Gio.Notification`, but live delivery depends on Phase 8 installing a matching `org.acercontrol.AcerControl.desktop`. Phase 5 smoke can verify source support and manual UAT can verify notification behavior on the target.

## Notification State Machines

### ProfileChangeNotifier

Inputs:

- `profile_name: str`
- focused state from `MainWindow`

Behavior:

- Focused: `MainWindow.show_toast(f"Switched to {profile_name}")`; no `send_notification`.
- Unfocused: create `Gio.Notification.new("Profile changed")`, set body `AcerControl is now using <profile>.`, call `application.send_notification("profile-change", notification)`.
- Stable ID means repeated changes replace rather than stack.

External CLI profile changes can be detected by comparing `read_profile()` on each 2 second tick with the last seen profile. Do not notify on initial seed. When Phase 4 profile clicks succeed, update the last-seen profile before or immediately after notifying to avoid duplicate notifications on the next tick.

### CriticalTempNotifier

Inputs:

- `cpu_package_c: float | None`
- focused state from `MainWindow`

Behavior:

- Missing temperature: do nothing and retain prior state.
- Normal -> critical when `cpu_package_c >= 90.0`.
- Critical -> normal when `cpu_package_c < 85.0`.
- Critical -> critical and normal -> normal: do nothing.
- Focused crossings use toasts only.
- Unfocused crossings use stable IDs `critical-temp` and `critical-temp-normal`.

## Sensor Rendering Details

Temperature rows:

- Labels: `CPU Package`, `Acer Temp 1`, `Acer Temp 2`, `Acer Temp 3`.
- Value format: integer-rounded display such as `55 C` or one decimal only if implementation chooses consistent precision.
- Bar fraction: clamp temp to `0..100` and divide by 100.
- State classes: `sensor-ok`, `sensor-warm`, `sensor-hot`.

Fan rows:

- Labels: `Fan 1`, `Fan 2`.
- Value format: `<rpm> RPM`.
- Bar fraction: clamp `rpm / FAN_MAX_RPM` to `0..1`; start with `FAN_MAX_RPM = 8000`.
- Missing values render placeholder and empty bar.

## Package Legitimacy Audit

Phase 5 installs no external packages. GTK4, libadwaita, GLib, and Gio are already project stack dependencies. No PyPI, npm, crates.io, or extra apt package should be introduced.

## Validation Architecture

Automated validation should remain source/static plus py_compile on this host:

1. `tools/smoke_phase5.py --quick`
   - Checks `05-UI-SPEC.md` exists.
   - Checks `gui_sensors.py` and `gui_notifications.py` may be absent before implementation but become strict once present.
   - Checks no thread/idle-add pattern appears in Phase 5 GUI code.
2. `tools/smoke_phase5.py`
   - Checks `GLib.timeout_add_seconds(2,`, `GLib.source_remove`, `read_sensors()`, threshold constants, notification IDs, and MainWindow wiring.
   - Runs `python3 -m py_compile` on Phase 5 files.
3. Regression suite
   - `python3 tools/smoke_phase1.py`
   - `python3 tools/smoke_phase2.py`
   - `python3 tools/smoke_phase3.py`
   - `python3 tools/smoke_phase4.py`
   - `python3 tools/smoke_phase5.py`

Manual PHN16-72 UAT:

- 30 minute soak with GUI open: zero `Gtk-CRITICAL` or `Gtk-WARNING` lines in `journalctl --user --since "30 min ago"`.
- Temporarily remove or hide one Acer temp input and verify only that row renders the placeholder.
- Stress test crossing `>=90 C` and `<85 C` unfocused: exactly one critical and one back-to-normal system notification.
- Repeat stress test focused: zero `Gio.Notification` system notifications; toasts only.
- Change profile via GUI focused: toast only.
- Change profile via CLI while GUI is unfocused: one stable `Profile changed` notification.

## Deferred Items

- Boot profile persistence and service panel remain Phase 6.
- Suspend/resume profile re-apply remains Phase 6/7 per roadmap split.
- Tray helper remains Phase 7.
- `.desktop` and icon packaging required for reliable `Gio.Notification` delivery remain Phase 8, though Phase 5 must implement source support now.
