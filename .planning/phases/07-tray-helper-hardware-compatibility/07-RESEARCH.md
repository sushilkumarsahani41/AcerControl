# Phase 7 Research: Tray Helper + Hardware Compatibility

**Phase:** 07 — Tray Helper + Hardware Compatibility  
**Researched:** 2026-05-23  
**Confidence:** HIGH for tray architecture and source/static gates; MEDIUM for live AppIndicator behavior until Ubuntu/GNOME UAT; MEDIUM for non-PHN hardware compatibility until fixture and hardware checks are executed.

## Phase Boundary

Phase 7 delivers:

- `acercontrol-tray` as a separate long-lived GTK3 + Ayatana AppIndicator helper process.
- Runtime detection of `org.kde.StatusNotifierWatcher`; if absent, tray helper exits 0 and the main GUI About dialog reports tray unavailability.
- Tray menu quick-switch for the five user-facing profiles plus `Show AcerControl`.
- Hardware compatibility verification for PHN16-72 and graceful partial-sensor/profile-choice degradation on other `predator_v4` laptops.

Phase 7 does **not** deliver:

- Debian packaging itself. Phase 8 creates `debian/`; Phase 7 must leave an executable packaging contract so Phase 8 declares tray packages as `Recommends`, not `Depends`.
- A root daemon, setuid helper, custom fan control, RGB, keyboard shortcut daemon, or raw D-Bus `StatusNotifierItem` implementation.
- GTK3 imports inside the GTK4 main GUI process.

## Canonical Inputs

- `.planning/ROADMAP.md` Phase 7 scope and success criteria.
- `.planning/REQUIREMENTS.md` TRAY-01..04 and HW-01..02.
- `.planning/research/STACK.md` decision #2: no GTK4-native AppIndicator; if shipped, use `gir1.2-ayatanaappindicator3-0.1` in a separate GTK3 helper process.
- `.planning/research/PITFALLS.md` P11: detect `org.kde.StatusNotifierWatcher`, degrade cleanly, package tray support as `Recommends`.
- `.planning/phases/06-boot-persistence-suspend-resume/06-03-SUMMARY.md`: Phase 6 source/static gates are green, but Linux hardware UAT remains pending.
- `tools/bundle_cli.py`: CLI bundler uses an explicit `BUNDLE_ORDER`, so new tray modules are safe if the order remains unchanged and smoke checks enforce no tray import enters bundle inputs.

## Architecture Decision

Use a **separate helper process**:

- Main GUI remains GTK4/libadwaita only.
- Tray helper imports GTK3 and `AyatanaAppIndicator3` only in `acercontrol.tray`, which the GTK4 GUI never imports.
- Shared logic remains in GTK-free modules (`core`, `profiles`, `privilege`) so the tray can read current profile and invoke the same privileged wrapper path as the GUI.
- `Show AcerControl` should activate the existing `Adw.Application` instance by launching `acercontrol-gui`; GApplication single-instance behavior focuses the existing window when present.

Rejected alternatives:

- `Gtk.StatusIcon`: removed from GTK4 and X11-era only.
- `gir1.2-appindicator3-0.1`: old Canonical fork; project research recommends Ayatana.
- Mixing GTK3 AppIndicator into the GTK4 GUI process: conflicting `gi.require_version("Gtk", ...)` calls.
- Direct raw `org.kde.StatusNotifierItem` implementation: possible but larger and riskier than the Ayatana helper for v1.

## Tray Runtime Shape

### Availability Detection

Add a GTK-version-neutral helper module, likely `acercontrol/tray_status.py`, using Gio only:

- Query session bus for `org.kde.StatusNotifierWatcher`.
- Return structured status: `available`, `missing-watcher`, `no-session-bus`, or `unknown`.
- Never raise on missing `gi`, missing session bus, GLib errors, or macOS.
- Used by both `acercontrol-tray` and About diagnostics.

### Tray Helper

Add `acercontrol/tray.py`:

- Imports `gi`, requires `Gtk 3.0` and `AyatanaAppIndicator3 0.1` only in the helper process.
- Exits 0 when tray status says unavailable or the Ayatana typelib is missing.
- Builds one `Gtk.Menu` with:
  - five profile items in exact order `eco`, `quiet`, `balanced`, `performance`, `turbo`;
  - checked/disabled styling for the current profile where GTK3 menu APIs allow it;
  - separator;
  - `Show AcerControl`;
  - `Quit`.
- Reads current profile with `read_profile()` and updates indicator state on `GLib.timeout_add_seconds(2, ...)`.
- Quick-switch uses `run_privileged(["acercontrol-setprofile", PROFILES[name]])`, then read-back refreshes state.
- No direct `pkexec`, no direct `sudo`, no direct sysfs writes, no `systemctl`, no shell=True.

### Show AcerControl

Use one of these source-level patterns:

- Prefer launching `acercontrol-gui` from `PATH`; the existing GApplication ID focuses the running instance.
- Development fallback: `sys.executable -m acercontrol.gui`.

Do not import `acercontrol.gui` in the tray helper, because that would load GTK4 into the GTK3 process.

## Hardware Compatibility Decision

Phase 7 does not broaden official support beyond `predator_v4`; it verifies graceful degradation within that support boundary.

Already-established compatible behavior:

- `available_profiles()` filters profile buttons by `platform_profile_choices`.
- `SensorReading` fields are optional; missing values render placeholders.
- `sysfs.find_hwmon()` resolves by `name`, tie-breaks by most input files, and never hardcodes hwmon indexes.
- `coretemp_max_package_temp()` handles multiple coretemp packages by taking the max package temperature.

Phase 7 should add explicit fixture-backed smoke coverage for:

- Acer hwmon with only `fan1_input`, `temp1_input`, and `temp2_input`; missing `fan2_input` and `temp3_input` must return `None`, not crash.
- `platform_profile_choices` missing one or more known kernel values; profile buttons remain present but unavailable choices are insensitive.
- Duplicate `acer` hwmon entries; most-populated candidate wins.
- Main GUI/About can mention tray availability without requiring Ayatana or StatusNotifier support.

Live UAT still required:

- PHN16-72 happy path: every profile button, sensors, boot persistence, suspend/resume, tray quick-switch.
- Non-primary compatible laptop or fixture-equivalent: missing fan/temp rows show placeholders, unavailable profile buttons are insensitive, and no traceback is logged.

## Validation Strategy

Automated on this macOS host:

- Add `tools/smoke_phase7.py` with side-effect-free source/static checks.
- Compile new Python files.
- Verify `tools/bundle_cli.py` still excludes tray modules from `BUNDLE_ORDER`.
- Verify `acercontrol/tray.py` is the only source file requiring `Gtk 3.0` / `AyatanaAppIndicator3`.
- Verify GTK4 GUI files do not import `acercontrol.tray`.
- Add tempdir fixture tests for partial hwmon/profile choices using monkeypatched module constants.
- Run full Phase 1-7 smoke chain.

Manual Linux UAT:

- With AppIndicator extension enabled: tray appears, reflects current profile, quick-switch works, Show AcerControl raises/focuses the GUI.
- With extension disabled: tray helper exits 0 within 5 seconds, GUI About mentions unavailable tray support.
- On PHN16-72: full v1 happy path remains green.
- On compatible partial-sensor hardware: missing rows show placeholders, unavailable profiles are insensitive, no crash.

## Open Questions

- Exact installed Ayatana typelib name on the target machine should be verified during Phase 7 UAT: `python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')"`.
- Whether profile-specific tray icon assets should ship in Phase 7 or Phase 8. For source implementation, a stable app icon plus indicator label/profile menu state is acceptable; Phase 8 owns install paths and icon-cache updates.
- TRAY-04 is inherently packaging-facing. Phase 7 should create a smoke/contract check that fails if `debian/control` exists with tray packages in `Depends` or missing from `Recommends`; Phase 8 will satisfy it when `debian/` is created.

## Research Complete

Phase 7 should be planned as three dependent plans:

1. Tray availability/status substrate, About integration, and Phase 7 smoke runner.
2. GTK3 Ayatana tray helper process with profile state, quick-switch menu, and Show AcerControl.
3. Hardware compatibility fixture gates, TRAY-04 packaging handoff gate, and full Phase 1-7 regression pass.
