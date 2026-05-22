# Phase 7 Patterns: Tray Helper + Hardware Compatibility

**Phase:** 07 — Tray Helper + Hardware Compatibility  
**Mapped:** 2026-05-23

## Existing Patterns To Reuse

| Pattern | Existing File(s) | Reuse in Phase 7 |
|---------|------------------|------------------|
| Source/static smoke runner with quick/full modes | `tools/smoke_phase6.py`, `tools/smoke_phase5.py` | Create `tools/smoke_phase7.py`; quick mode skips future tray files until they exist, full mode compiles and runs fixture checks. |
| Wrapper-only privileged writes | `acercontrol/gui_profiles.py`, `acercontrol/gui_boot.py`, `acercontrol/privilege.py` | Tray quick-switch must call `run_privileged(["acercontrol-setprofile", PROFILES[name]])`; no direct elevation tokens. |
| User-facing profile names only | `acercontrol/profiles.py`, `acercontrol/gui_profiles.py` | Tray menu order and labels use `("eco", "quiet", "balanced", "performance", "turbo")`; kernel values stay behind `PROFILES`. |
| Main-loop polling | `acercontrol/gui_window.py`, `acercontrol/gui_sensors.py` | Tray helper refreshes current profile with `GLib.timeout_add_seconds(2, ...)`; no worker thread. |
| Graceful optional runtime feature | `acercontrol/gui_resume.py`, `acercontrol/systemd.py` | Tray status helper catches missing session bus/Gio errors and returns safe status strings. |
| About diagnostics | `acercontrol/gui_about.py` | Add tray availability status to debug info without importing GTK3 tray helper. |
| Fixed bundler inputs | `tools/bundle_cli.py`, `tools/smoke_phase2.py` | Phase 7 smoke ensures tray modules are not added to `BUNDLE_ORDER`. |
| Sensor placeholders | `acercontrol/gui_sensors.py`, `acercontrol/core.py`, `acercontrol/sysfs.py` | Add fixture smoke for missing `fan2_input` and `temp3_input` returning `None` and rendering placeholders. |

## Proposed New Files

| File | Purpose |
|------|---------|
| `tools/smoke_phase7.py` | Phase 7 source/static and fixture verification. |
| `acercontrol/tray_status.py` | GTK-version-neutral tray availability detection and About diagnostic status. |
| `acercontrol/tray.py` | Separate GTK3 + Ayatana AppIndicator helper process. |

## Files To Touch Carefully

| File | Constraint |
|------|------------|
| `acercontrol/gui_about.py` | May import `tray_status`, but must not import `tray` or require GTK3. |
| `tools/bundle_cli.py` | Do not add tray modules to `BUNDLE_ORDER`; smoke should protect this invariant. |
| `acercontrol/gui_window.py` | No tray import; main GUI remains GTK4-only. |
| `acercontrol/gui_profiles.py` | Existing unavailable-profile behavior should remain unchanged unless fixture smoke reveals a real gap. |
| `acercontrol/gui_sensors.py` | Placeholder behavior should remain stable; avoid row deletion based on missing values. |

## Verification Patterns

Source/static:

- `tray.py` contains `gi.require_version("Gtk", "3.0")` and `gi.require_version("AyatanaAppIndicator3", "0.1")`.
- No GTK4 GUI module imports `acercontrol.tray`.
- No tray code contains direct `pkexec`, `sudo`, `systemctl`, `/sys/firmware/acpi/platform_profile`, or `shell=True`.
- `tray_status.py` contains `Gio.BusType.SESSION`, `NameHasOwner`, and `org.kde.StatusNotifierWatcher`.
- About diagnostics contain a tray status key and import only `tray_status`.
- If `debian/control` exists, tray packages are under `Recommends`, not `Depends`.

Fixture:

- Temporary hwmon tree with duplicate `acer` devices verifies most-populated tie-break.
- Temporary partial `acer` hwmon verifies missing fan/temp values return `None`.
- Temporary `platform_profile_choices` verifies unavailable profile buttons can be inferred from choices.

Manual UAT:

- AppIndicator present and absent flows.
- PHN16-72 full v1 happy path.
- Compatible partial hardware fallback behavior.

## Planning Decomposition

- `07-01` should establish smoke runner, tray status substrate, and About diagnostics.
- `07-02` should implement the tray helper process.
- `07-03` should add hardware compatibility fixtures, package Recommends handoff gate, and full regression verification.
