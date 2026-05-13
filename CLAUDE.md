# AcerControl — Acer WMI Control Tool for Linux

## Project Overview

A Linux system control tool for Acer Predator/Nitro laptops (primarily PHN16-72) that wraps the `acer_wmi` kernel module. Provides both a CLI tool and a GTK4 GUI application to control:

- Platform performance profiles (eco / quiet / balanced / performance / turbo)
- Fan speed monitoring
- Temperature monitoring (CPU, GPU, sensors)
- Boot-time profile persistence via systemd

## Target Hardware

- **Primary**: Acer Predator Helios Neo 16 PHN16-72 (i9-14900HX / RTX 4070)
- **Compatible**: PHN16-71, PHN18-71, PH315-xx, PH317-xx series
- **OS**: Ubuntu 24.04 LTS, kernel 6.14+
- **Module**: `acer_wmi` with `predator_v4=1` parameter

## Tech Stack

- **Language**: Python 3.10+
- **GUI Framework**: GTK4 + Adwaita (via `libadwaita`) — native GNOME look
- **CLI**: `argparse` based, zero dependencies
- **Sysfs interface**: Direct read/write to `/sys/firmware/acpi/platform_profile`
- **Monitoring**: `/sys/class/hwmon/hwmon*/` for temps and fan speeds
- **Systemd**: D-Bus via `dasbus` or subprocess for service management
- **Packaging**: Single-file install + optional `.deb` package

## Project Structure

```
acercontrol/
├── CLAUDE.md                    ← this file
├── README.md
├── acercontrol.py               ← CLI tool (already built, working)
├── acercontrol_gui.py           ← GTK4 GUI app (to build)
├── acercontrol/
│   ├── __init__.py
│   ├── core.py                  ← shared logic (sysfs read/write)
│   ├── cli.py                   ← CLI entry point
│   ├── gui.py                   ← GTK4 GUI entry point
│   ├── monitor.py               ← background monitoring thread
│   └── systemd.py               ← systemd service management
├── data/
│   ├── acercontrol.desktop      ← .desktop launcher file
│   ├── acercontrol.service      ← systemd service template
│   └── icons/
│       └── acercontrol.svg      ← app icon
├── install.sh                   ← one-shot installer
└── acercontrol.spec             ← future: RPM/DEB spec
```

## Sysfs Paths

```python
# Platform profile
PROFILE_PATH         = "/sys/firmware/acpi/platform_profile"
PROFILE_CHOICES_PATH = "/sys/firmware/acpi/platform_profile_choices"

# Fan and temperature (hwmon — find by name == "acer")
HWMON_BASE = "/sys/class/hwmon"
# fan1_input, fan2_input  → CPU fan, GPU fan (RPM)
# temp1_input, temp2_input, temp3_input → millidegrees Celsius

# CPU package temp (hwmon name == "coretemp")
# temp1_input → package temp in millidegrees

# Module parameter
PREDATOR_V4_PARAM = "/sys/module/acer_wmi/parameters/predator_v4"
```

## Profile Mapping

```python
PROFILES = {
    "eco":         "low-power",           # battery saver
    "quiet":       "quiet",               # silent fan
    "balanced":    "balanced",            # default
    "performance": "balanced-performance",# performance without turbo LED
    "turbo":       "performance",         # max, turbo LED blinks
}
```

Note: The kernel uses `performance` to mean turbo on this hardware. The GUI should show user-friendly names (eco/quiet/balanced/performance/turbo).

## CLI Tool (already working)

```bash
acercontrol status       # full system status
acercontrol get          # current profile name
acercontrol get --raw    # raw sysfs value
acercontrol set turbo    # set profile (requires sudo)
acercontrol list         # list available profiles
acercontrol temps        # show temps and fan RPM
acercontrol install      # print install instructions
```

The CLI auto-escalates with `sudo` when not root. Keep this behavior.

## GUI Requirements

### Window Layout

```
┌─────────────────────────────────────────┐
│  ⚙ AcerControl          [─][□][×]       │
├─────────────────────────────────────────┤
│  Model: Predator PHN16-72               │
│  Module: acer_wmi ✓  predator_v4: Y ✓  │
├─────────────────────────────────────────┤
│  PERFORMANCE PROFILE                    │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐        │
│  │eco│ │qut│ │bal│ │per│ │TRB│← active │
│  └───┘ └───┘ └───┘ └───┘ └───┘        │
├─────────────────────────────────────────┤
│  SENSORS              live refresh      │
│  CPU Package   55°C   ████████░░ 55%   │
│  Fan 1       6976 RPM ████████████ 87% │
│  Fan 2       7142 RPM ████████████ 89% │
├─────────────────────────────────────────┤
│  BOOT SERVICE                           │
│  acer-performance.service  [enabled ✓] │
│  Boot profile: turbo        [change]   │
└─────────────────────────────────────────┘
```

### GUI Features

1. **Profile buttons** — 5 buttons (eco/quiet/balanced/performance/turbo), highlight active one. Clicking sets immediately (with polkit auth if needed).
2. **Live sensor panel** — refresh every 2 seconds via `GLib.timeout_add`. Show temp bars (color: green < 70°C, yellow < 85°C, red ≥ 85°C). Show fan RPM bars.
3. **Boot service section** — show `acer-performance.service` status (enabled/disabled/failed). Toggle enable/disable. Change boot profile dropdown.
4. **System tray / indicator** — optional: show current profile in system tray with quick-switch menu.
5. **Notifications** — `Gio.Notification` when profile changes or temps go critical (>90°C).

### Privilege Escalation

Writing to `/sys/firmware/acpi/platform_profile` requires root. Use:
1. **polkit** via `pkexec` — proper GNOME way, shows auth dialog
2. Fallback: `subprocess.run(["sudo", ...])` if polkit unavailable

```python
def set_profile_privileged(value):
    try:
        subprocess.run(
            ["pkexec", "bash", "-c", f"echo {value} > {PROFILE_PATH}"],
            check=True, timeout=30
        )
    except FileNotFoundError:
        subprocess.run(
            ["sudo", "bash", "-c", f"echo {value} > {PROFILE_PATH}"],
            check=True
        )
```

### GTK4 / Adwaita Setup

```python
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio
```

Use `Adw.ApplicationWindow`, `Adw.PreferencesGroup`, `Adw.ActionRow`, `Adw.SwitchRow` for native look. Use `Adw.StatusPage` for error states (module not loaded etc.).

### Install GTK4 dependencies

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libadwaita-1-dev
```

## Systemd Service Management

```python
import subprocess

def service_status(name):
    result = subprocess.run(
        ["systemctl", "is-enabled", name],
        capture_output=True, text=True
    )
    return result.stdout.strip()  # "enabled", "disabled", "not-found"

def service_enable(name):
    subprocess.run(["pkexec", "systemctl", "enable", "--now", name], check=True)

def service_disable(name):
    subprocess.run(["pkexec", "systemctl", "disable", "--now", name], check=True)
```

## Background Monitoring Thread

```python
import threading

class SensorMonitor:
    def __init__(self, callback, interval=2):
        self.callback = callback  # called with dict of sensor data
        self.interval = interval
        self._stop = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.interval):
            data = get_temps_fans()  # from core.py
            GLib.idle_add(self.callback, data)  # safe GTK update
```

## Error States to Handle

| Condition | UI Response |
|---|---|
| `acer_wmi` not loaded | Show `Adw.StatusPage` with fix instructions |
| `predator_v4=Y` missing | Warning banner, button to reload module |
| `platform_profile` missing | Error with command to fix |
| polkit auth cancelled | Silent fail, keep previous state |
| Sensor read failure | Show "—" instead of value, don't crash |
| Service not found | Show "not installed" with install button |

## Desktop Integration

### .desktop file (`data/acercontrol.desktop`)
```ini
[Desktop Entry]
Name=AcerControl
Comment=Acer laptop performance control
Exec=acercontrol-gui
Icon=acercontrol
Terminal=false
Type=Application
Categories=System;HardwareSettings;
Keywords=acer;fan;performance;turbo;cooling;
StartupNotify=true
```

### Polkit policy (`data/org.acercontrol.policy`)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<policyconfig>
  <action id="org.acercontrol.setprofile">
    <description>Set Acer performance profile</description>
    <message>Authentication required to change performance profile</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
  </action>
</policyconfig>
```

## Install Script (`install.sh`)

```bash
#!/bin/bash
set -e

echo "[AcerControl] Installing..."

# CLI
sudo cp acercontrol.py /usr/local/bin/acercontrol
sudo chmod +x /usr/local/bin/acercontrol

# GUI
sudo cp acercontrol_gui.py /usr/local/bin/acercontrol-gui
sudo chmod +x /usr/local/bin/acercontrol-gui

# acer_wmi module param
echo "options acer_wmi predator_v4=1" | sudo tee /etc/modprobe.d/acer-wmi.conf

# systemd service
sudo cp data/acercontrol.service /etc/systemd/system/acer-performance.service
sudo systemctl daemon-reload
sudo systemctl enable acer-performance.service

# Desktop entry
sudo cp data/acercontrol.desktop /usr/share/applications/

# Update initramfs
sudo update-initramfs -u

echo "[AcerControl] Done! Run: acercontrol status"
```

## Development Notes

- Keep CLI (`acercontrol.py`) as a standalone single-file tool — no dependencies, works without GTK
- GUI (`acercontrol_gui.py`) can import from `acercontrol/core.py` when refactored
- All sysfs writes need root — never store passwords, always use polkit/sudo at time of action
- Test error states by temporarily renaming `/sys/firmware/acpi/platform_profile`
- The hwmon number (`hwmon7`) can change between boots — always find by `name` file content
- Fan control (setting RPM directly) is NOT supported by acer_wmi — only profile-based control
- `balanced-performance` = Performance mode (no LED), `performance` = Turbo (LED blinks)

## Current Status

- [x] CLI tool working (`acercontrol.py`)
- [x] acer_wmi loading with predator_v4=1
- [x] Boot persistence via systemd
- [x] Performance/turbo mode confirmed working (LED blink)
- [ ] GUI application (next to build)
- [ ] System tray indicator
- [ ] Desktop entry / app icon
- [ ] .deb package

## Commands to Run First

```bash
# Verify environment before building GUI
acercontrol status

# Install GTK4 dependencies
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

# Test GTK4 is available
python3 -c "import gi; gi.require_version('Adw', '1'); from gi.repository import Adw; print('GTK4+Adwaita OK')"

# Clone / init project
mkdir -p ~/acercontrol && cd ~/acercontrol
cp /usr/local/bin/acercontrol acercontrol.py
```

<!-- GSD:project-start source:PROJECT.md -->
## Project

**AcerControl**

A Linux desktop application (GTK4 + libadwaita) that controls Acer Predator/Nitro laptop performance via the `acer_wmi` kernel module. Provides a polished GUI — profile switching, live temperature/fan monitoring, system tray indicator, boot-time persistence — plus a CLI tool sharing the same core logic, distributed as a `.deb` package for Ubuntu/Debian.

**Core Value:** **Click a profile button → laptop switches profile → see thermal state in real time.** Everything else (tray, notifications, boot service, packaging) supports this loop. If profile control or live sensors fail, the product has failed.

### Constraints

- **OS**: Ubuntu 24.04 LTS (and Debian 12+) — primary target. Other distros may work but are not the v1 priority.
- **Language**: Python 3.10+ (matches Ubuntu 24.04 system Python; avoids a runtime install).
- **GUI stack**: GTK4 + `libadwaita` only — no Qt, no Electron. Adwaita is mandated for native GNOME feel.
- **Dependencies**: keep runtime deps to what ships in Ubuntu's repos — `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`. No pip-only packages for the GUI.
- **Privilege**: never store credentials; always escalate at the moment of action via polkit/sudo.
- **Single-file CLI**: `acercontrol` CLI must remain a zero-dependency single-file script suitable for `cp /usr/local/bin/`. GUI can use the package.
- **Compatibility**: hwmon index numbers change between boots — always locate sensors by `name` file content, never by hardcoded `hwmon7`.
- **Distribution**: `.deb` is the v1 distribution channel; `install.sh` is the fallback only.
- **Quality bar**: polished personal tool — manual UAT on PHN16-72, decent error UX, `.deb` installs cleanly. No automated tests required for v1.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Stack Decisions (summary)
| # | Decision | Recommendation | Confidence |
|---|----------|---------------|------------|
| 1 | GTK4 + Adwaita binding | `python3-gi` (PyGObject 3.48.x) + `gir1.2-gtk-4.0` (GTK 4.14.x) + `gir1.2-adw-1` (libadwaita 1.5.x) from Ubuntu 24.04 repos | HIGH identity, MEDIUM micro |
| 2 | System tray indicator | **Defer tray to a post-v1 polish phase.** If shipped: `gir1.2-ayatanaappindicator3-0.1` in a separate GTK3 helper process. Anti-rec `Gtk.StatusIcon` (removed in GTK4) and `gir1.2-appindicator3-0.1` (legacy Canonical fork) | HIGH |
| 3 | Privilege escalation | `pkexec` + a `.policy` XML in `/usr/share/polkit-1/actions/org.acercontrol.policy`. `auth_admin_keep`. `sudo` only as CLI fallback | HIGH |
| 4 | Desktop notifications | `Gio.Notification` for system notifications, `Adw.Toast` + `Adw.ToastOverlay` for in-app feedback. Anti-rec `notify2`, legacy `Notify`, deprecated `Adw.AppNotification` | HIGH |
| 5 | Background sensor refresh | `GLib.timeout_add_seconds(2, ...)` on the main loop — sysfs reads are sub-millisecond. `threading.Thread` + `GLib.idle_add` reserved for future expensive reads | HIGH |
| 6 | `.deb` packaging | `debhelper-compat (= 13)` + `dh_python3` + `dh-sequence-python3` + `pybuild-plugin-pyproject`. Build with `dpkg-buildpackage -us -uc -b`. Anti-rec `stdeb`, `debmake` | MEDIUM-HIGH |
| 7 | systemd unit | `Type=oneshot` + `RemainAfterExit=yes`. `.deb` installs to `/usr/lib/systemd/system/`; `install.sh` writes to `/etc/systemd/system/` | HIGH |
| 8 | Project layout | `pyproject.toml` (PEP 621, `setuptools` backend) with `[project.scripts]`. Anti-rec `setup.py` as primary config; anti-rec Poetry/Hatch for an apt-shipped app | HIGH |
| 9 | App icon | `/usr/share/icons/hicolor/scalable/apps/acercontrol.svg` (color) + `.../symbolic/apps/acercontrol-symbolic.svg` (monochrome, currentColor) | HIGH |
| 10 | CLI library | `argparse` (stdlib). Zero-deps trumps `click`/`typer` DX | HIGH |
| ++ | systemd from GUI | `subprocess.run(["pkexec", "systemctl", ...])`. Anti-rec `dasbus`/`pydbus` — overkill for 3 calls/lifetime | HIGH |
## Core Technologies (Ubuntu 24.04 apt packages)
| Package | Provides | Used for |
|---------|----------|----------|
| `python3` | Python 3.12 (system Python on Noble) | Runtime |
| `python3-gi` | PyGObject (the `gi` module) | GTK/Adwaita/GLib from Python |
| `python3-gi-cairo` | Cairo bindings for `gi` | Drawing areas / custom rendering |
| `gir1.2-gtk-4.0` | GTK 4 typelib | `gi.require_version('Gtk', '4.0')` |
| `gir1.2-adw-1` | libadwaita 1 typelib | `gi.require_version('Adw', '1')` |
| `gir1.2-glib-2.0` | GLib/Gio typelib | `GLib.timeout_add_seconds`, `Gio.Notification` |
| `policykit-1` | polkit daemon + `pkexec` | Privilege escalation |
| `systemd` | Service manager | Unit files, `systemctl` |
| kernel `acer_wmi` | Hardware interface | Kernel-provided, not apt |
| Package | Provides |
|---------|----------|
| `gir1.2-ayatanaappindicator3-0.1` | Ayatana AppIndicator 3 (GTK3-flavored) |
| `gnome-shell-extension-appindicator` | Preinstalled bridge on Ubuntu 24.04 from GNOME 46 panel to AppIndicator/KStatusNotifierItem |
| Package | Provides |
|---------|----------|
| `debhelper-compat (= 13)` (build-dep) | Modern dh sequencer baseline on Noble |
| `dh-sequence-python3` | Drives `pybuild` from `dh $@` |
| `pybuild-plugin-pyproject` | Makes `pybuild` understand `pyproject.toml` |
| `python3-setuptools`, `python3-wheel` | PEP 517 build backend |
| `dpkg-dev`, `devscripts`, `lintian` | Source-package build + lint |
## Detailed Rationale
### 1. GTK4 + Adwaita binding
- Adwaita 1.x has been the standard GNOME app look since 2022 and tracks GNOME release cadence (Adwaita 1.5 ships with GNOME 46 / Ubuntu 24.04; Adwaita 1.6 with GNOME 47). Noble ships GNOME 46.
- PyGObject's canonical install on Ubuntu/Debian is `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0` (verified, Context7 `/gnome/pygobject`).
- Required boilerplate:
### 2. System tray indicator
- GNOME 46 has no built-in tray. Ubuntu 24.04 ships `gnome-shell-extension-appindicator` preinstalled and enabled — AppIndicator icons render in the GNOME panel.
- There is **no GTK4-native AppIndicator binding.** `libayatana-appindicator` builds against GTK3 (Context7 `/ayatanaindicators/libayatana-appindicator` — `pkg-config gtk+-3.0 ayatana-appindicator3-0.1`). Using it from a GTK4 Python app means `gi.require_version('Gtk', '3.0')` somewhere — conflicts with `Gtk 4.0` in the same process.
- Ubuntu 24.04 default desktop is Wayland — `Gtk.StatusIcon` (X11 system-tray protocol) is removed in GTK4 anyway.
- `Gtk.StatusIcon` — does not exist in GTK4.
- `gir1.2-appindicator3-0.1` (old Canonical/Unity `libappindicator`) — superseded by the Ayatana fork.
- Mixing GTK3 AppIndicator code inside the GTK4 process — produces confusing import-version errors.
### 3. Privilege escalation
- polkit `.policy` XML (in `/usr/share/polkit-1/actions/`) is how applications **declare** auth-required actions. polkit `.rules` JS files (in `/etc/polkit-1/rules.d/`) are how sysadmins **override** those declarations. An app ships `.policy`; `.rules` is sysadmin-only.
- `auth_admin_keep` caches the credential for ~5 minutes — good UX for users flipping profiles. Still requires *admin* credentials.
- `auth_self_keep` requires the active user's own password (not admin). On a single-user laptop the user *is* admin, so functionally identical; we recommend `auth_admin_keep` because writing to `/sys/firmware/acpi/platform_profile` is fundamentally an admin action.
- `<allow_any>` and `<allow_inactive>` should be `auth_admin` (no `_keep`).
- `pkexec bash -c 'echo ... > /sys/...'` — env scrubbing / quoting footguns; action ID becomes generic `org.freedesktop.policykit.exec`, so the GNOME prompt reads "Authentication required to run /bin/bash". Use a named helper binary.
- `sudo NOPASSWD` for the profile path — bypasses polkit UX, security regression.
- Long-lived elevated daemon — unnecessary; profile writes are one-off events.
### 4. Desktop notifications
- `Gio.Notification` is the GTK-native, freedesktop-spec-conformant API. Integrated with `Gtk.Application` — no extra deps.
- **Critical footgun:** `Gio.Notification` requires the `Gtk.Application` to have a registered `application_id` AND a matching `.desktop` file installed at `/usr/share/applications/<application_id>.desktop`. If the application ID is `org.acercontrol.AcerControl`, the desktop file must be `org.acercontrol.AcerControl.desktop`. Without this, notifications **silently fail**.
- `Adw.Toast` is the modern in-app feedback widget. Add an `Adw.ToastOverlay` as the root child of the window, then `overlay.add_toast(Adw.Toast(title="Switched to Turbo"))`.
- `notify2` (PyPI) — unmaintained, duplicates `Gio.Notification`.
- `pynotifier`, `plyer` — cross-platform abstractions, unnecessary on Linux-only.
- `gi.repository.Notify` (libnotify directly) — older C API; `Gio.Notification` is the successor.
- `Adw.AppNotification` / `.app-notification` style class — deprecated upstream.
### 5. Background sensor refresh
- Reading `/sys/class/hwmon/hwmon*/temp1_input` is a synchronous kernel read; completes in well under 1 ms. The GTK main loop runs at 16 ms (60 fps); a sub-ms read every 2 s causes zero visible jank.
- Avoiding a thread eliminates an entire class of concurrency bugs.
- Callback returns `GLib.SOURCE_CONTINUE` / `True` to keep ticking, `GLib.SOURCE_REMOVE` / `False` to stop. Store the source ID and call `GLib.source_remove(id)` on window close.
- Use threading **only if** a future sensor genuinely blocks (e.g. IPMI/EC over LPC > 100 ms). At that point use the documented pattern: daemon `threading.Thread` + `GLib.idle_add(callback, data)`.
- `threading.Thread` upfront — over-engineering, racy shutdown if not joined.
- `asyncio` + GLib via `gbulb` — unnecessary cognitive load for a 2-second poll.
- `GLib.timeout_add(2000, ...)` — works, but the `_seconds` variant aligns to whole-second ticks (power-friendlier) and is GLib-recommended for intervals at least 1 s.
### 6. `.deb` packaging
- `debhelper` compat 13 is the canonical baseline on Noble.
- `dh-sequence-python3` is the modern shorthand — gives `dh $@` (no explicit `--with python3`) and auto-discovers `pyproject.toml` when `pybuild-plugin-pyproject` is present.
- Hand-written `debian/` gives clean `lintian` output without manual fixups.
- `stdeb` is for PyPI-to-deb glue; AcerControl is not on PyPI and ships polkit `.policy`, systemd unit, `.desktop`, icons, modprobe.d snippet — none fit `stdeb`'s model.
- `stdeb` — doesn't handle polkit/systemd/desktop data files.
- `debmake` — auto-generated output needs manual cleanup anyway.
- Vendoring Python deps into the `.deb` — runtime constraint says "Ubuntu-shipped packages only".
- `compat` file vs. `Build-Depends: debhelper-compat` — both work; the latter (single source of truth in `control`) is current.
### 7. systemd unit
- The boot service does one thing: write a configured profile string to `/sys/firmware/acpi/platform_profile` after `acer_wmi` is loaded, then exit. `Type=oneshot` matches exactly. `RemainAfterExit=yes` makes systemd treat the unit as "active" after the process exits, so `systemctl is-active` reports correctly.
- Vendor-installed units belong in `/usr/lib/systemd/system/` on merged-usr distros. Ubuntu 24.04 is merged-usr; `/lib/systemd/system/` is a compatibility symlink. `dh_installsystemd` writes to `/usr/lib/...`.
- Sysadmin/local units belong in `/etc/systemd/system/`. The CLAUDE.md `install.sh` uses `/etc/systemd/system/` — correct for manual install.
- `Type=simple` — marks the unit failed when the script exits.
- Writing to `/sys/...` directly inside `ExecStart` without a wrapper — TOCTOU/quoting issues.
- Installing to `/lib/systemd/system/` from a `.deb` on Noble — works via symlink, but canonical is `/usr/lib/...`.
### 8. Project layout
- `[project.scripts]` maps `acercontrol = "acercontrol.cli:main"` and `acercontrol-gui = "acercontrol.gui:main"`.
- Non-Python data installs via `debian/acercontrol.install` — **not** setuptools `package_data` — keeps the Python package clean.
- The "single-file copyable CLI" path: a thin shim that does `from acercontrol.cli import main; main()`, or a bundler concatenating stdlib-only modules into `dist/acercontrol`.
- `setup.py` as primary config — deprecated.
- Poetry — adds runtime tooling, `pybuild` doesn't grok `tool.poetry`.
- Hatch / flit — fine for PyPI-first, but `pybuild-plugin-pyproject` is best tested against `setuptools`.
### 9. App icon
- GNOME HIG specifies `hicolor` as the install location. `scalable/apps/` is the catch-all for SVG; size-specific raster fallbacks no longer required.
- Symbolic icons use `currentColor` so GNOME re-tints them by context. Must live under `symbolic/apps/` and end in `-symbolic.svg`. HIG expects a 16x16 conceptual viewBox.
- `.desktop` `Icon=` field uses the basename without extension: `Icon=acercontrol`.
- The `.deb` postinst should run `gtk-update-icon-cache /usr/share/icons/hicolor`; `dh_icons` does this automatically when icons are installed under hicolor.
- PNG-only — doesn't scale on HiDPI.
- `pixmaps/` — legacy GNOME 2 location.
### 10. CLI library
- Zero-deps constraint is non-negotiable for the single-file CLI.
- Surface is small: `status | get | set <profile> | list | temps | install`. `argparse` handles this in ~50 lines.
- `click` and `typer` are PyPI deps; `typer` additionally pulls `click` + `rich`.
- `click` / `typer` — violate zero-deps single-file constraint.
- `docopt` — abandoned upstream.
### ++ Systemd interaction from the GUI
- GUI hits systemd ~3 times in its entire lifetime: `is-enabled`, `enable --now`, `disable --now`. No event subscription, no transient units.
- `subprocess` keeps the dep surface at zero new packages.
- `python-systemd` is the right answer for journal logging — not applicable here.
- D-Bus (systemd1) is the right answer for unit-state-change subscriptions — not needed.
- `dasbus` — fine library, overkill. PROJECT.md's "via `dasbus` or subprocess" should be resolved as subprocess.
- `pydbus` — unmaintained as of 2023.
## Alternatives Considered
| Recommended | Alternative | When the alternative would be better |
|-------------|-------------|--------------------------------------|
| GTK4 + Adwaita | Qt 6 + PySide6 | If cross-platform was a goal — explicit non-goal |
| `pkexec` + `.policy` | `sudo` only | Strictly headless / non-graphical sessions — fallback only |
| `auth_admin_keep` | `auth_self_keep` | Multi-user laptops where the active user shouldn't gain admin — rare on a personal gaming laptop |
| `GLib.timeout_add_seconds` | `threading.Thread` + `GLib.idle_add` | Future sensor reads that block > 50 ms |
| `Gio.Notification` | `Adw.Toast` | In-app while focused → Toast. Out-of-app / unfocused → Gio.Notification |
| Hand-written `debian/` | `stdeb` | One-off personal packaging of a PyPI-only tool with no system data files |
| `argparse` | `click` / `typer` | CLI grows past ~10 subcommands and zero-deps is relaxed |
| `subprocess` for systemctl | `dasbus` / D-Bus | Subscribe to unit state-change events |
| Deferred tray | Ayatana AppIndicator (separate process) | User research shows tray is essential for v1 |
## What NOT to Use (consolidated)
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `Gtk.StatusIcon` | Removed in GTK4; X11-only protocol | Ayatana AppIndicator (separate process) or defer tray |
| `gir1.2-appindicator3-0.1` (old Canonical) | Superseded by Ayatana fork | `gir1.2-ayatanaappindicator3-0.1` |
| `notify2` (PyPI) | Unmaintained, redundant | `Gio.Notification` + `Adw.Toast` |
| `gi.repository.Notify` (libnotify) | Older C API, not GApplication-integrated | `Gio.Notification` |
| `Adw.AppNotification` / `.app-notification` | Deprecated upstream | `Adw.Toast` + `Adw.ToastOverlay` |
| `notify-send` shelled from Python | External process for built-in capability | `Gio.Notification` |
| `pkexec bash -c '...'` | TOCTOU / env scrubbing; generic action ID | `pkexec /usr/libexec/acercontrol-setprofile <arg>` |
| `sudo NOPASSWD` rules for sysfs | Bypasses polkit UX; security regression | polkit `.policy` |
| `setup.py` as primary config | Deprecated by setuptools | `pyproject.toml` with `[project]` (PEP 621) |
| `stdeb` for this project | No polkit/systemd/desktop support | Hand-written `debian/` + `dh_python3` |
| Poetry for an apt-shipped app | `pybuild` doesn't understand it | `setuptools` backend in `pyproject.toml` |
| `Type=simple` for the boot service | Marks unit failed on exit | `Type=oneshot` + `RemainAfterExit=yes` |
| `pydbus` | Unmaintained since 2023 | `dasbus` if D-Bus is truly needed, else `subprocess` |
| Hardcoded `/sys/class/hwmon/hwmon7/...` | hwmon numbers change between boots | Walk `/sys/class/hwmon/hwmon*/name` and match `"acer"` / `"coretemp"` |
| Pip-installed PyGObject | Needs matching system typelibs | `apt install python3-gi` |
| `GLib.timeout_add(2000, ...)` | Less power-friendly than the seconds variant | `GLib.timeout_add_seconds(2, ...)` |
## Version Compatibility / Distro Notes
| Concern | Ubuntu 24.04 (Noble, primary) | Debian 12 (Bookworm, secondary) |
|---------|-------------------------------|---------------------------------|
| Python | 3.12 system default | 3.11 system default |
| GTK 4 | 4.14.x | 4.8.x (some 4.10+ APIs missing) |
| libadwaita | 1.5.x | 1.2.x — **no** `Adw.Banner` (1.3), `Adw.AlertDialog`/`Adw.AboutDialog` (1.4), `Adw.NavigationView` (1.4), `Adw.ToolbarView` (1.4) |
| PyGObject | 3.48.x | 3.42.x |
| polkit | 124+ | 122+ |
| debhelper compat | 13 baseline, 14 available | 13 baseline |
| GNOME Shell | 46 with AppIndicator extension preinstalled | 43; extension available, user must enable |
| `gnome-shell-extension-appindicator` | Preinstalled, enabled | Available, opt-in |
- v1 targets Noble's libadwaita 1.5. Bookworm support is "best effort" — if the GUI sticks to widgets in 1.2 (CLAUDE.md UI mock only needs `ApplicationWindow`, `HeaderBar`, `PreferencesGroup`, `ActionRow`, `SwitchRow`, `StatusPage`, `Toast` — all 1.0/1.1), Bookworm works.
- `.deb` should declare Build-Depends on the Adwaita 1.x gir package by name, not by version. Runtime feature gating (`if hasattr(Adw, 'AlertDialog')`) is cheap.
## Confidence Summary
| Area | Confidence | Reason |
|------|-----------|--------|
| GTK4 + Adwaita + PyGObject stack identity | HIGH | Verified upstream via Context7 + decades-stable apt naming |
| Exact micro versions on Noble | MEDIUM-LOW | `packages.ubuntu.com` unreachable; not pinned here — roadmap must verify on target |
| Tray situation (GTK4 has no native tray) | HIGH | Verified via Context7 `/ayatanaindicators/libayatana-appindicator` |
| polkit `.policy` XML structure | HIGH | freedesktop spec, polkit 0.105+, stable for a decade |
| `auth_admin_keep` semantics | HIGH | polkit defaults schema |
| `Gio.Notification` requires matching `.desktop` + application ID | HIGH | Well-known footgun |
| `Adw.Toast` for in-app feedback | HIGH | Context7 `/gnome/libadwaita` |
| `GLib.timeout_add_seconds` (no thread) | HIGH | Sysfs read latency is sub-millisecond |
| debhelper compat 13 baseline | MEDIUM-HIGH | Compat 13 is Debian Policy baseline |
| `pyproject.toml` over `setup.py` | HIGH | setuptools upstream deprecation |
| `Type=oneshot` + `RemainAfterExit=yes` | HIGH | Context7 `/systemd/systemd` |
| Vendor unit `/usr/lib/systemd/system/`, admin `/etc/systemd/system/` | HIGH | Merged-usr + `dh_installsystemd` |
| `argparse` for CLI | HIGH | Stdlib + zero-deps |
| `subprocess` over `dasbus` | HIGH | Call frequency (3/lifetime) doesn't justify D-Bus |
## Installation (developer setup, one-time)
# Runtime + GUI dev
# Verify GTK4 + Adwaita reachable from Python
# Packaging toolchain
# Build the .deb (from repo root, with debian/ in place)
## Open Questions / Phase-Specific Research Needed
- Exact `apt-cache policy` versions on Noble for `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `debhelper-compat`, `libadwaita-1-0` — resolve in packaging phase on the target machine.
- If tray is in scope: GTK3-helper-process vs raw D-Bus `org.kde.StatusNotifierItem` — small spike phase.
- Debian 12 supported widget surface — only matters if Bookworm becomes a real target.
- `dh_icons` automatic behavior on compat 13 — confirm icon-cache regeneration triggers without an explicit `debian/acercontrol.postinst`.
## Sources
- **Context7 `/gnome/pygobject`** — install commands, `gi.require_version` patterns, `GLib.idle_add` cross-thread bridge.
- **Context7 `/gnome/libadwaita`** — `AdwAboutDialog`, `AdwToast` / `AdwToastOverlay`, deprecation of `Adw.AppNotification`.
- **Context7 `/ayatanaindicators/libayatana-appindicator`** — Ayatana AppIndicator builds against GTK3.
- **Context7 `/systemd/systemd`** — `RemainAfterExit` documentation.
- **Context7 `/hyprwm/hyprpolkitagent`** — polkit action-id / D-Bus signature reference.
- **freedesktop polkit specification** — `.policy` DTD, `<allow_active>`, `auth_admin_keep` semantics.
- **GNOME HIG icon guidelines** — hicolor theme, scalable + symbolic directories.
- **Debian Python Policy / debhelper documentation** — `dh-sequence-python3`, `pybuild`, `pybuild-plugin-pyproject`, compat 13 baseline.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
