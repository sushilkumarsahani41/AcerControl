# Phase 7 UI Spec: Tray Helper + Hardware Compatibility

**Phase:** 07 — Tray Helper + Hardware Compatibility  
**Status:** Design contract for planning/execution  
**Applies to:** `acercontrol-tray`, About diagnostics, existing main GUI compatibility behavior

## Stack Contract

- Main GUI remains GTK4 + libadwaita.
- Tray helper is a separate process using GTK3 + Ayatana AppIndicator.
- No file loaded by `acercontrol.gui` or `acercontrol.gui_window` may import `acercontrol.tray` or require GTK3.
- Tray helper may import GTK-free shared modules: `core`, `profiles`, `privilege`, and tray-specific status helpers.

## Tray Availability UX

When `org.kde.StatusNotifierWatcher` is unavailable:

- `acercontrol-tray` exits with status 0.
- It writes one concise line to stderr/stdout suitable for logs, for example `AcerControl tray unavailable: StatusNotifierWatcher missing`.
- It does not show a window, error dialog, or traceback.
- About diagnostics in the main GUI include a tray availability field such as:
  - `tray.status: available`
  - `tray.status: missing-watcher`
  - `tray.status: no-session-bus`
  - `tray.status: unknown`

## Tray Menu Contract

The tray menu must contain, in order:

1. `eco`
2. `quiet`
3. `balanced`
4. `performance`
5. `turbo`
6. separator
7. `Show AcerControl`
8. `Quit`

Rules:

- Profile labels are exactly lower-case user-facing names.
- Raw kernel profile values never appear in menu labels.
- The currently active profile is visibly marked where GTK3 menu APIs support it.
- Unsupported profiles from `platform_profile_choices` remain visible but insensitive.
- Quick-switch calls the same privileged wrapper path used by GUI profile buttons.

## Indicator State Contract

- The indicator uses the application icon name as the baseline icon.
- It reflects current profile through menu checked state and, where supported by the indicator backend, label/status updates.
- It refreshes profile state with `GLib.timeout_add_seconds(2, ...)`.
- Missing sysfs/current profile state maps to `custom`/unknown display without crashing.

## Show AcerControl Contract

- `Show AcerControl` launches `acercontrol-gui` or development fallback `python -m acercontrol.gui`.
- It must not import GTK4 modules inside the tray helper.
- The existing `Adw.Application(application_id="org.acercontrol.AcerControl")` handles focus/raise through single-instance activation.

## Hardware Compatibility UX

The existing main GUI must remain stable on partial sensor/profile surfaces:

- Missing fan/temp values render as `-` placeholders in existing sensor rows.
- Existing row layout remains stable; rows are not removed mid-session.
- Profile buttons remain in the five-profile order but unsupported choices are insensitive with tooltip `Unavailable on this hardware`.
- `Profile.CUSTOM` remains a normal state; no profile button is highlighted.

## Forbidden Patterns

- GTK3 imports in GTK4 GUI modules.
- GTK4 imports in `acercontrol.tray`.
- `Gtk.StatusIcon`.
- `gir1.2-appindicator3-0.1` / `AppIndicator3` legacy Canonical fork.
- Direct `pkexec`, direct `sudo`, direct sysfs writes, direct `systemctl`, `shell=True`, or arbitrary service control from tray code.
- Threading for profile polling; use GLib main-loop timers.
