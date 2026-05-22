# Phase 7 Human UAT: Tray Helper + Hardware Compatibility

These checks are manual Linux/hardware validation gates. They are not automated on the macOS development host. Local source/static coverage is handled by `python3 tools/smoke_phase7.py`.

## Target Environment

- Ubuntu 24.04 GNOME session on the PHN16-72 target laptop.
- Kernel 6.14+ with `acer_wmi predator_v4=1`.
- Acer platform profile sysfs present.
- Phase 1-7 source installed or run from the project checkout with wrappers/polkit policy available.
- Optional tray dependencies installed for AppIndicator-present checks:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1 gnome-shell-extension-appindicator
```

## Preflight

Run:

```bash
acercontrol status
acercontrol get
python3 tools/smoke_phase7.py
```

Expected:

- `acercontrol status` shows `acer_wmi`, `predator_v4=Y`, platform profile, and Acer hwmon present.
- `acercontrol get` prints one user-facing profile or `Custom`.
- Phase 7 smoke passes; packaging Recommends may be skipped until Phase 8 creates `debian/control`.

## TRAY-01: AppIndicator Present Flow

1. Confirm the AppIndicator extension is enabled in the GNOME session.
2. Start the tray helper:

   ```bash
   python3 acercontrol_tray.py
   ```

3. Confirm a tray indicator appears.
4. Open the tray menu.

Expected:

- The helper remains running as a separate process.
- The menu entries appear in this exact order: `eco`, `quiet`, `balanced`, `performance`, `turbo`, `Show AcerControl`, `Quit`.
- The active profile is visually marked where the shell/backend supports it.
- Unsupported profiles, if any, remain visible but insensitive.

## TRAY-02: StatusNotifierWatcher Absent Flow

1. Disable the AppIndicator extension or test in a session without `org.kde.StatusNotifierWatcher`.
2. Run:

   ```bash
   python3 acercontrol_tray.py
   echo $?
   ```

3. Open AcerControl -> About -> Troubleshooting / Diagnostics.

Expected:

- `acercontrol-tray` exits within 5 seconds.
- Exit code is `0`.
- No Python traceback appears.
- About diagnostics include `tray.status` as `missing-watcher`, `no-session-bus`, or `unknown`.

## TRAY-03: Quick Switch + Show AcerControl

With AppIndicator enabled and the tray running:

1. Select each profile from the tray menu in order:

   ```text
   eco
   quiet
   balanced
   performance
   turbo
   ```

2. After each selection, verify:

   ```bash
   acercontrol get
   ```

3. Click `Show AcerControl` while the GUI is closed.
4. Click `Show AcerControl` while the GUI is already open.
5. Click `Quit`.

Expected:

- Each tray quick-switch uses polkit/sudo only through the existing wrapper path.
- `acercontrol get` returns the selected user-facing profile after each switch.
- `Show AcerControl` launches the GUI when closed.
- `Show AcerControl` focuses the existing single-instance window when already open.
- `Quit` exits the tray helper without closing the main GUI.

## HW-01: PHN16-72 Full Happy Path

Run on the PHN16-72 target after Phases 5-7 are installed:

1. Launch `acercontrol-gui`.
2. Click each profile button in the GUI and confirm `acercontrol get` matches.
3. Leave the GUI open for at least 30 minutes.
4. Verify live sensors update about every 2 seconds without layout jumps.
5. Check logs:

   ```bash
   journalctl --user --since "30 min ago" | grep -E "AcerControl|Gtk-CRITICAL|Gtk-WARNING"
   ```

6. Configure a boot profile, cold boot, and verify before opening the GUI:

   ```bash
   acercontrol get
   systemctl status acer-performance.service --no-pager
   ```

7. Suspend and resume, then verify within 5 seconds of unlock:

   ```bash
   acercontrol get
   ```

8. Start the tray helper and quick-switch a profile from the tray.

Expected:

- Profile buttons, live sensors, boot persistence, suspend/resume restore, and tray quick-switch all work in the same session.
- No uncaught traceback or repeated notification spam appears.
- Turbo and performance retain the expected hardware distinction already confirmed for this laptop.

## HW-02: Compatible Partial Hardware

Use a compatible predator_v4 laptop with partial Acer hwmon exposure when available. If second hardware is not available, record fixture-equivalent coverage from `tools/smoke_phase7.py`.

Manual partial-hardware checks:

1. Confirm the Acer hwmon has only a subset of values, for example `fan1_input`, `temp1_input`, and `temp2_input`, with no `fan2_input` or `temp3_input`.
2. Launch `acercontrol-gui`.
3. Observe sensor rows for at least 60 seconds.
4. Open the profile choices file:

   ```bash
   cat /sys/firmware/acpi/platform_profile_choices
   ```

Expected:

- Missing fan/temp values render as `-` placeholders.
- Other sensor rows continue updating.
- No traceback appears in the terminal or user journal.
- Profile buttons remain in the five-profile order.
- Profiles absent from `platform_profile_choices` are insensitive with the existing unavailable-hardware tooltip.

Fixture-equivalent coverage when hardware is unavailable:

```bash
python3 tools/smoke_phase7.py
```

The smoke runner covers duplicate `acer` hwmon resolution, partial `read_acer_sensors()` output, and profile-choice filtering.

## TRAY-04: Packaging Handoff

Phase 7 enforces the source/static contract only when `debian/control` exists. Phase 8 must verify:

- `gir1.2-ayatanaappindicator3-0.1` is in `Recommends:`.
- `gnome-shell-extension-appindicator` is in `Recommends:`.
- Neither tray package is a hard runtime `Depends:`.

Until Phase 8 creates `debian/control`, this check is an explicit handoff skip in `tools/smoke_phase7.py`.

## Signoff Record

Fill this section on the Linux target:

- Date:
- Machine:
- Kernel:
- `acer_wmi predator_v4`:
- AppIndicator present flow:
- StatusNotifierWatcher absent flow:
- Tray quick-switch:
- Show AcerControl:
- PHN16-72 full happy path:
- Partial hardware or fixture-equivalent:
- Notes:
