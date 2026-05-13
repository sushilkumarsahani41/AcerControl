# Requirements: AcerControl

**Defined:** 2026-05-14
**Core Value:** Click a profile button → laptop switches profile → see thermal state in real time.

## v1 Requirements

### Foundation (Core library, sysfs, profile mapping)

- [ ] **CORE-01**: `core.py` exposes a canonical user-name ↔ kernel-value mapping (`eco`/`quiet`/`balanced`/`performance`/`turbo` ↔ `low-power`/`quiet`/`balanced`/`balanced-performance`/`performance`) — every other module reads from this single source.
- [ ] **CORE-02**: `sysfs.find_hwmon(name, requires=...)` resolves hwmon devices by reading each `name` file at runtime, never by hardcoded index; on ties, picks the most-populated entry.
- [ ] **CORE-03**: `features.probe()` returns a structured `FeatureReport` covering acer_wmi loaded, predator_v4 mode, platform_profile sysfs, acer hwmon, coretemp hwmon, and PPD active state — no sysfs access can raise an uncaught `FileNotFoundError` past this layer.
- [ ] **CORE-04**: A kernel `custom` value (or any unknown sysfs value) maps to a "Custom" display state instead of crashing the UI.
- [ ] **CORE-05**: `modprobe.d` blacklist entries for `acer_wmi` are detected at startup and surfaced as a remediation state.
- [ ] **CORE-06**: Multi-package CPUs (e.g. PH317 systems) are handled — temp readings match `Package id 0` label and the maximum across packages is reported.

### Privilege & CLI

- [ ] **PRIV-01**: Privileged writes execute via a real binary wrapper at `/usr/libexec/acercontrol/acercontrol-setprofile`, never via `pkexec bash -c`.
- [ ] **PRIV-02**: Polkit policy ships at `/usr/share/polkit-1/actions/org.acercontrol.policy` with three named actions — `org.acercontrol.setprofile`, `org.acercontrol.set-boot-profile`, `org.acercontrol.manage-service` — each pinned to its wrapper via `org.freedesktop.policykit.exec.path` annotation. `auth_admin_keep` is used for `allow_active`.
- [ ] **PRIV-03**: The polkit auth dialog displays the configured human message (e.g. "Authentication is required to change the Acer performance profile"), never "Authentication is needed to run /usr/bin/bash".
- [ ] **PRIV-04**: `pkexec` exit code 126 (auth cancelled) is handled idempotently — the UI reverts and shows a toast, never raises a traceback.
- [ ] **PRIV-05**: When `$SSH_CONNECTION` is set, the CLI falls back to `sudo` instead of `pkexec` (which would hang waiting for a non-existent agent).
- [ ] **CLI-01**: `acercontrol status` prints feature probe report, current profile (user-name), available profiles, fan/temp summary.
- [ ] **CLI-02**: `acercontrol get` prints the current profile using user-facing names (`turbo`, not `performance`); `acercontrol get --raw` prints the kernel value.
- [ ] **CLI-03**: `acercontrol set <profile>` validates input against user-name mapping, escalates via pkexec/sudo, writes through the helper, reads back, and exits non-zero on mismatch.
- [ ] **CLI-04**: `acercontrol list` prints available user-facing profiles, marking the active one.
- [ ] **CLI-05**: `acercontrol temps` prints CPU package temp, fan 1/2 RPM, and all hwmon temps.
- [ ] **CLI-06**: `acercontrol install` prints (or executes when run as root) the install steps including modprobe.d snippet and `update-initramfs -u`.
- [ ] **CLI-07**: CLI has zero non-stdlib dependencies; the bundler produces a single-file `dist/acercontrol` containing only stdlib imports (CI guard fails the build if `gi` leaks in).

### GUI shell, profile control & failure states

- [ ] **GUI-01**: GUI uses `Adw.Application` with `application_id="org.acercontrol.AcerControl"`, and the main window is an `Adw.ApplicationWindow` with `Adw.ToolbarView` and `Adw.HeaderBar`.
- [ ] **GUI-02**: A second launch focuses the existing window instead of opening a duplicate.
- [ ] **GUI-03**: On startup, `features.probe()` runs; failed probes dispatch to dedicated `Adw.StatusPage` screens with fix-it text and one-click remediation buttons where possible (reload module, mask PPD).
- [ ] **GUI-04**: When PPD is detected active, a persistent `Adw.Banner` offers `[Disable PPD]` and `[Learn more]`; user consent invokes `pkexec systemctl mask --now power-profiles-daemon.service`.
- [ ] **GUI-05**: Main UI renders 5 profile buttons (eco/quiet/balanced/performance/turbo); the currently-active profile is visually highlighted at all times.
- [ ] **GUI-06**: Clicking a profile button shows a transient "Awaiting authorisation…" state, calls the pkexec helper, reads back the value, and on success shows an `Adw.Toast` "Switched to <profile>" and updates the highlight.
- [ ] **GUI-07**: If the read-back value does not equal the requested value, the GUI shows a warning toast ("Profile not applied — power-profiles-daemon may be overriding writes"), reverts the highlight, and re-surfaces the PPD banner if applicable.
- [ ] **GUI-08**: UI never renders raw kernel profile values; raw values appear only in About → Diagnostics export.

### Live sensors & notifications

- [ ] **SENS-01**: A `GLib.timeout_add_seconds(2, …)` tick reads CPU package temp, fan 1 RPM, fan 2 RPM, and all available `temp*_input` files from the `acer` hwmon.
- [ ] **SENS-02**: Temperature bars are color-coded — green when <70 °C, yellow when 70–84 °C, red when ≥85 °C — and update without flicker.
- [ ] **SENS-03**: Sensor read failures show `—` placeholders without crashing or stopping the refresh loop; the resolver re-runs once on `OSError`.
- [ ] **SENS-04**: GUI runs for ≥30 minutes with live panel active and produces zero `Gtk-CRITICAL` lines in `journalctl --user`.
- [ ] **NOTI-01**: Profile-change notifications use `Adw.Toast` while window is focused, `Gio.Notification` while unfocused; notification ID is stable so the OS replaces rather than stacks.
- [ ] **NOTI-02**: Critical-temperature notifier uses hysteresis: fires once at ≥90 °C, fires "back to normal" once at <85 °C, never spams between. Suppresses entirely while the GUI window is focused.

### Boot persistence, suspend/resume & service panel

- [ ] **BOOT-01**: A templated systemd unit `acer-performance@.service` ships with `Type=oneshot`, `ConditionKernelModuleLoaded=acer_wmi`, `ConditionPathExists=/sys/firmware/acpi/platform_profile`, `After=systemd-modules-load.service`, `Conflicts=power-profiles-daemon.service`, `Before=graphical.target`.
- [ ] **BOOT-02**: After a full power-off cold boot and login, `acercontrol get` (run before opening the GUI) returns the configured boot profile.
- [ ] **BOOT-03**: GUI service panel shows current enabled/disabled status of `acer-performance.service`, and exposes a dropdown to change the boot profile (which writes `/etc/default/acercontrol` and re-runs `systemctl start acer-performance@<profile>` via pkexec).
- [ ] **BOOT-04**: GUI startup calls `systemctl is-active --wait acer-performance.service` (bounded by short timeout) before allowing the first profile write, eliminating the boot/GUI race.
- [ ] **BOOT-05**: GUI subscribes to `org.freedesktop.login1` `PrepareForSleep`; on resume, re-applies the user's selected profile if the kernel reports a different one. (Test on PHN16-72 during build: if firmware preserves the value across S3, hook is belt-and-braces; otherwise it's required.)

### Tray indicator (separate GTK3 helper process)

- [ ] **TRAY-01**: A separate executable `acercontrol-tray` (GTK3 + `gir1.2-ayatanaappindicator3-0.1`) runs as a long-lived helper, talks to the main GUI/CLI over D-Bus or a UNIX socket, and exposes a tray icon with current profile.
- [ ] **TRAY-02**: Tray availability is detected at startup by querying `org.kde.StatusNotifierWatcher` on the session bus; if absent, the tray helper exits cleanly and the GUI mentions it in About without erroring.
- [ ] **TRAY-03**: Tray menu offers quick-switch among the 5 user-facing profiles and a "Show AcerControl" action that raises the main window.
- [ ] **TRAY-04**: AppIndicator dependency is declared as `Recommends:` (not `Depends:`) in `debian/control` so non-GNOME / minimal installs aren't forced to install it.

### Distribution & packaging

- [ ] **PKG-01**: Repository root contains a `pyproject.toml` using PEP 621 metadata with the `setuptools` build backend and `[project.scripts]` entry points for `acercontrol` and `acercontrol-gui`.
- [ ] **PKG-02**: A hand-written `debian/` builds a `.deb` via `dpkg-buildpackage -us -uc -b`, using `debhelper-compat (= 13)`, `dh-sequence-python3`, and `pybuild-plugin-pyproject`.
- [ ] **PKG-03**: `debian/control` declares runtime `Depends:` `python3-gi`, `python3-gi-cairo`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `policykit-1`, `desktop-file-utils`, `hicolor-icon-theme`, plus `${python3:Depends}` and `${misc:Depends}`. `Recommends:` `gnome-shell-extension-appindicator`, `gir1.2-ayatanaappindicator3-0.1`.
- [ ] **PKG-04**: `debian/postinst` runs `update-desktop-database -q`, `gtk-update-icon-cache -q -f /usr/share/icons/hicolor`, and `systemctl daemon-reload` on `configure`.
- [ ] **PKG-05**: `lintian acercontrol_*.deb` exits with zero errors (warnings reviewed but acceptable).
- [ ] **PKG-06**: No `.pyc` files are shipped inside the `.deb` (verified via `dpkg -c | grep '\.pyc$'`).
- [ ] **PKG-07**: `apt install ./acercontrol_*.deb` works cleanly on a clean Ubuntu 24.04 VM and the launcher entry appears in Activities without logout/login.
- [ ] **PKG-08**: `install.sh` fallback works for non-Debian and manual installs — copies binaries, writes modprobe.d snippet, registers systemd unit, runs `update-initramfs -u`.
- [ ] **PKG-09**: `data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg` is a custom color SVG; `data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg` is a monochrome `currentColor` variant for tray/list contexts.
- [ ] **PKG-10**: `data/org.acercontrol.AcerControl.desktop` is registered under `/usr/share/applications/`, basename matches `application_id`, `Icon=org.acercontrol.AcerControl`, `Categories=System;HardwareSettings;`.
- [ ] **PKG-11**: `data/99-acer-wmi.conf` writes `options acer_wmi predator_v4=1` to `/etc/modprobe.d/`; the postinst flow makes clear that `update-initramfs -u` + reboot is required for the parameter to take effect.

### Hardware compatibility

- [ ] **HW-01**: All controls work on the user's PHN16-72 (Ubuntu 24.04, kernel 6.14+).
- [ ] **HW-02**: GUI loads on any acer_wmi laptop where `predator_v4=1` works (PHN16-71/72, PHN18-71, PH315-xx, PH317-xx, Nitro V), gracefully disabling controls whose underlying sysfs paths are missing rather than crashing.

## v2 Requirements

Deferred — tracked but not in current roadmap.

### Sensors & monitoring

- **SENS2-01**: Temperature history graph (last N minutes) using a Cairo drawing area
- **SENS2-02**: CPU/GPU usage shown alongside temps
- **SENS2-03**: Telemetry export to `~/.local/share/acercontrol/log.csv`

### Profile intelligence

- **PROF2-01**: AC/battery-aware auto-switching (cooperate with PPD's vocabulary first)
- **PROF2-02**: PPD D-Bus cooperative mode — write via PPD API for its 3 profiles, direct for quiet/turbo
- **PROF2-03**: Per-application profile rules (process-name → profile)
- **PROF2-04**: Keyboard-shortcut profile switching (global GNOME shortcut)
- **PROF2-05**: Hardware "performance mode" Fn-key integration (if evdev event is usable on PHN16-72)

### Distribution

- **PKG2-01**: GitHub Actions CI building the `.deb` on tag push
- **PKG2-02**: Launchpad PPA publishing
- **PKG2-03**: Flatpak/AppImage for non-Debian distros
- **PKG2-04**: Automated unit tests for `core.py` parsing logic
- **PKG2-05**: Multi-distro CI matrix (Debian 12, Fedora, Arch)

### Other Acer hardware

- **HW2-01**: Classic `acer_wmi` (non-predator_v4) support — hide turbo/LED features when absent
- **HW2-02**: Verified support for additional models (PH317 multi-die handling already in v1 via CORE-06)

## Out of Scope

Explicit exclusions — anti-features baked into the design.

| Feature | Reason |
|---------|--------|
| Direct fan RPM control / custom fan curves | `acer_wmi` does not expose fan PWM writes; faking control via userspace loops is unsafe |
| Keyboard RGB / per-key backlight / macro keys | Different subsystem (USB HID + vendor protocols); orthogonal to thermal control |
| GPU overclocking | NVIDIA-specific; separate tooling concern |
| Battery charge limits / health features | Separate subsystem; would muddy product scope |
| Windows / cross-platform support | Linux-only by design; sysfs is OS-specific, no abstraction justified |
| Automated test suite / CI | v1 quality bar is "polished personal tool"; manual UAT on PHN16-72 is acceptable |
| Persistent root daemon / setuid binaries | polkit invocations only; no long-running elevated processes |
| Telemetry by default | Privacy-respecting; diagnostics export is on-demand only |
| Auto-applying turbo without user consent | UX anti-pattern; every write requires explicit click + polkit |

## Traceability

All v1 requirements mapped to exactly one phase. See ROADMAP.md for phase goals and success criteria.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CORE-01 | Phase 1 — Foundation | Pending |
| CORE-02 | Phase 1 — Foundation | Pending |
| CORE-03 | Phase 1 — Foundation | Pending |
| CORE-04 | Phase 1 — Foundation | Pending |
| CORE-05 | Phase 1 — Foundation | Pending |
| CORE-06 | Phase 1 — Foundation | Pending |
| PRIV-01 | Phase 2 — Privilege Boundary + CLI | Pending |
| PRIV-02 | Phase 2 — Privilege Boundary + CLI | Pending |
| PRIV-03 | Phase 2 — Privilege Boundary + CLI | Pending |
| PRIV-04 | Phase 2 — Privilege Boundary + CLI | Pending |
| PRIV-05 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-01 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-02 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-03 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-04 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-05 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-06 | Phase 2 — Privilege Boundary + CLI | Pending |
| CLI-07 | Phase 2 — Privilege Boundary + CLI | Pending |
| GUI-01 | Phase 3 — GUI Shell + Failure States + PPD Banner | Pending |
| GUI-02 | Phase 3 — GUI Shell + Failure States + PPD Banner | Pending |
| GUI-03 | Phase 3 — GUI Shell + Failure States + PPD Banner | Pending |
| GUI-04 | Phase 3 — GUI Shell + Failure States + PPD Banner | Pending |
| GUI-08 | Phase 3 — GUI Shell + Failure States + PPD Banner | Pending |
| GUI-05 | Phase 4 — Profile Control (core value loop) | Pending |
| GUI-06 | Phase 4 — Profile Control (core value loop) | Pending |
| GUI-07 | Phase 4 — Profile Control (core value loop) | Pending |
| SENS-01 | Phase 5 — Live Sensors + Notifications | Pending |
| SENS-02 | Phase 5 — Live Sensors + Notifications | Pending |
| SENS-03 | Phase 5 — Live Sensors + Notifications | Pending |
| SENS-04 | Phase 5 — Live Sensors + Notifications | Pending |
| NOTI-01 | Phase 5 — Live Sensors + Notifications | Pending |
| NOTI-02 | Phase 5 — Live Sensors + Notifications | Pending |
| BOOT-01 | Phase 6 — Boot Persistence + Suspend/Resume | Pending |
| BOOT-02 | Phase 6 — Boot Persistence + Suspend/Resume | Pending |
| BOOT-03 | Phase 6 — Boot Persistence + Suspend/Resume | Pending |
| BOOT-04 | Phase 6 — Boot Persistence + Suspend/Resume | Pending |
| BOOT-05 | Phase 6 — Boot Persistence + Suspend/Resume | Pending |
| TRAY-01 | Phase 7 — Tray Helper + Hardware Compatibility | Pending |
| TRAY-02 | Phase 7 — Tray Helper + Hardware Compatibility | Pending |
| TRAY-03 | Phase 7 — Tray Helper + Hardware Compatibility | Pending |
| TRAY-04 | Phase 7 — Tray Helper + Hardware Compatibility | Pending |
| HW-01 | Phase 7 — Tray Helper + Hardware Compatibility | Pending |
| HW-02 | Phase 7 — Tray Helper + Hardware Compatibility | Pending |
| PKG-01 | Phase 8 — Packaging | Pending |
| PKG-02 | Phase 8 — Packaging | Pending |
| PKG-03 | Phase 8 — Packaging | Pending |
| PKG-04 | Phase 8 — Packaging | Pending |
| PKG-05 | Phase 8 — Packaging | Pending |
| PKG-06 | Phase 8 — Packaging | Pending |
| PKG-07 | Phase 8 — Packaging | Pending |
| PKG-08 | Phase 8 — Packaging | Pending |
| PKG-09 | Phase 8 — Packaging | Pending |
| PKG-10 | Phase 8 — Packaging | Pending |
| PKG-11 | Phase 8 — Packaging | Pending |

**Coverage:**
- v1 requirements: 54 total (CORE 6 + PRIV 5 + CLI 7 + GUI 8 + SENS 4 + NOTI 2 + BOOT 5 + TRAY 4 + PKG 11 + HW 2 = 54; the previous "52 total" figure was a miscount)
- Mapped to phases: 54
- Unmapped: 0
- Orphans: 0
- Duplicates: 0

---
*Requirements defined: 2026-05-14*
*Last updated: 2026-05-14 after roadmap creation and traceability mapping*
