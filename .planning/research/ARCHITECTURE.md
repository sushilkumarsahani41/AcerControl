# Architecture Research

**Domain:** Linux desktop GUI for Acer Predator/Nitro WMI thermal/profile control
**Researched:** 2026-05-13
**Confidence:** HIGH (component boundaries, data flow, phase order) / MEDIUM (specific install paths, polkit XML, PPD coexistence details — web verification unavailable this session, training-data conventions used)

---

## TL;DR — Five Architectural Commitments

1. **One source of truth:** `acercontrol/` Python package. The CLI is built from it two ways (entry-point shim for `.deb`; concatenated single-file for manual install). No duplicate code.
2. **Privileged writes go through one helper:** `/usr/libexec/acercontrol/acercontrol-helper`, invoked via `pkexec` against named polkit actions. No `pkexec bash -c "echo ..."` shell-out anywhere.
3. **Three polkit actions, not one:** set-profile, manage-service, set-boot-profile. Each maps to one subcommand of the helper.
4. **Config is split by privilege scope:** `/etc/acercontrol/boot.conf` (root-readable, set via pkexec, used by boot service) vs. `~/.config/acercontrol/config.toml` (user prefs only).
5. **Failure-mode probe runs before main UI:** the GUI's first job is to verify the kernel surface and route to an `Adw.StatusPage` if anything is missing — *not* render the main view and discover failures piecemeal.

---

## Source Tree (development repository)

```
acercontrol/                          # git repo root
├── CLAUDE.md
├── README.md
├── PROJECT.md                        # via .planning/PROJECT.md
├── pyproject.toml                    # PEP 621 metadata + console_scripts
├── setup.cfg                         # optional, for older tooling
├── MANIFEST.in                       # include data/ in sdist
│
├── acercontrol/                      # the Python package (single source of truth)
│   ├── __init__.py                   # version, public re-exports
│   ├── sysfs.py                      # READ-ONLY layer: discover hwmon by name,
│   │                                 #   read platform_profile, parse temps/fans
│   ├── profiles.py                   # PROFILES dict, user↔kernel name mapping,
│   │                                 #   validation against platform_profile_choices
│   ├── features.py                   # feature detection: acer_wmi loaded?
│   │                                 #   predator_v4=Y? platform_profile writable?
│   │                                 #   PPD running? returns a FeatureReport dataclass
│   ├── privilege.py                  # pkexec/sudo invocation of the helper;
│   │                                 #   never writes sysfs directly
│   ├── service.py                    # systemctl is-enabled / enable / disable;
│   │                                 #   read/write /etc/acercontrol/boot.conf
│   ├── config.py                     # TOML read/write of ~/.config/acercontrol/config.toml
│   ├── monitor.py                    # SensorMonitor (threading.Thread + GLib.idle_add);
│   │                                 #   imports gi LAZILY so CLI never pulls it in
│   ├── cli.py                        # argparse → core functions (no GTK imports ever)
│   ├── gui.py                        # GTK4/Adwaita app — imports everything above
│   ├── tray.py                       # optional StatusIcon/AppIndicator
│   └── notifier.py                   # Gio.Notification wrapper
│
├── helper/
│   └── acercontrol-helper            # Python script, stdlib-only, runs as root via pkexec
│                                     #   subcommands: set-profile, set-boot-profile,
│                                     #   enable-service, disable-service, reload-module
│
├── data/
│   ├── applications/
│   │   └── acercontrol.desktop
│   ├── polkit/
│   │   └── org.acercontrol.policy    # three <action> entries
│   ├── systemd/
│   │   └── acer-performance.service  # Type=oneshot, RemainAfterExit=yes
│   ├── modprobe/
│   │   └── acer-wmi.conf             # options acer_wmi predator_v4=1
│   ├── metainfo/
│   │   └── org.acercontrol.AcerControl.metainfo.xml   # AppStream (optional)
│   └── icons/
│       ├── hicolor/scalable/apps/acercontrol.svg
│       └── hicolor/symbolic/apps/acercontrol-symbolic.svg
│
├── tools/
│   ├── bundle_cli.py                 # concatenates sysfs+profiles+privilege+features+cli
│   │                                 #   into dist/acercontrol (stdlib-only, no gi)
│   └── verify_no_gtk.py              # CI check: CLI bundle must not import gi
│
├── debian/                           # debhelper packaging
│   ├── changelog
│   ├── control                       # Depends: python3, python3-gi, gir1.2-gtk-4.0,
│   │                                 #          gir1.2-adw-1, policykit-1, systemd
│   ├── copyright
│   ├── rules                         # pybuild + dh_installsystemd + dh_installpolkit
│   ├── compat
│   ├── acercontrol.install           # maps data/ → installed paths
│   ├── acercontrol.links             # symlink /usr/libexec/.../helper if needed
│   ├── acercontrol.postinst          # daemon-reload, update-desktop-database, icon cache
│   ├── acercontrol.postrm
│   └── acercontrol.service           # OR placed via dh_installsystemd
│
├── dist/                             # build output, gitignored
│   └── acercontrol                   # bundled single-file CLI
│
└── install.sh                        # fallback for non-Debian; uses dist/acercontrol
```

### Structure Rationale

- **`acercontrol/` package is the only place logic lives.** The CLI does not live as a parallel `acercontrol.py` at the repo root — that would create two sources of truth and break the "shared core" requirement.
- **`sysfs.py` is strictly read-only.** All writes go through `privilege.py` → helper. This is the single most important architectural invariant: a grep for `open(..., "w")` in the package (outside `config.py` for user TOML) should return nothing.
- **`monitor.py` and `gui.py` import `gi` lazily** so `cli.py` (and the bundled CLI) never pull a GTK dependency.
- **`helper/acercontrol-helper` is a separate Python file**, *not* part of the package. It must be readable from a root context that doesn't import the user's GUI dependencies. It depends on stdlib only and re-implements just enough of `sysfs.py`/`profiles.py` to validate input — or, more cleanly, imports from the installed package (the package itself has no GTK at import time, so root can `from acercontrol import sysfs, profiles` safely).
- **`data/` mirrors the installed tree's subdirectories** so `debian/install` is a near-1:1 mapping.

---

## Installed Tree (Debian/Ubuntu, FHS-compliant)

| Artifact | Installed Path | Owner | Confidence |
|---|---|---|---|
| Python package | `/usr/lib/python3/dist-packages/acercontrol/` | dh_python3 | HIGH |
| `acercontrol` CLI shim | `/usr/bin/acercontrol` | console_scripts | HIGH |
| `acercontrol-gui` shim | `/usr/bin/acercontrol-gui` | console_scripts | HIGH |
| Privileged helper | `/usr/libexec/acercontrol/acercontrol-helper` | root:root, 0755 | MEDIUM |
| polkit policy | `/usr/share/polkit-1/actions/org.acercontrol.policy` | root:root, 0644 | MEDIUM |
| systemd unit | `/lib/systemd/system/acer-performance.service` | root:root, 0644 | MEDIUM |
| `.desktop` launcher | `/usr/share/applications/acercontrol.desktop` | root:root, 0644 | HIGH |
| Scalable icon | `/usr/share/icons/hicolor/scalable/apps/acercontrol.svg` | root:root, 0644 | HIGH |
| Symbolic icon | `/usr/share/icons/hicolor/symbolic/apps/acercontrol-symbolic.svg` | root:root, 0644 | MEDIUM |
| AppStream metainfo | `/usr/share/metainfo/org.acercontrol.AcerControl.metainfo.xml` | root:root, 0644 | MEDIUM |
| modprobe options | `/etc/modprobe.d/acer-wmi.conf` | root:root, 0644 | HIGH |
| Boot profile config | `/etc/acercontrol/boot.conf` | root:root, 0644 | HIGH |
| User config | `$XDG_CONFIG_HOME/acercontrol/config.toml` (i.e. `~/.config/acercontrol/config.toml`) | user, 0644 | HIGH |

> **Confidence note:** specific install paths flagged MEDIUM are stable freedesktop/Debian conventions but were not re-verified against current docs this session (WebSearch/WebFetch denied). Phase 1 implementation should spot-check against `man polkit`, `man systemd.unit`, and `lintian` warnings.

### Why `/usr/libexec/acercontrol/` for the helper

- Not on `$PATH` — users shouldn't invoke it directly.
- Polkit's `org.freedesktop.policykit.exec.path` annotation pins the action to this exact path; the policy will refuse to authorize a tampered binary at a different location.
- FHS reserves `/usr/libexec/` for internal binaries invoked by other programs.

---

## Component Boundaries

```
┌────────────────────────────────────────────────────────────────────────┐
│                          USER-FACING LAYER                              │
│   ┌─────────────────────────┐         ┌──────────────────────────────┐  │
│   │  gui.py  (GTK4/Adw)     │         │  cli.py  (argparse)          │  │
│   │  - profile buttons      │         │  - get/set/list/temps/status │  │
│   │  - sensor bars          │         │  - install                    │  │
│   │  - status pages         │         │                               │  │
│   │  - service panel        │         │                               │  │
│   │  - tray, notifier       │         │                               │  │
│   └────────┬───────┬────────┘         └────────────┬──────────────────┘  │
│            │       │                               │                     │
│            ▼       ▼                               ▼                     │
│   ┌─────────────────────┐               (same downward arrows)           │
│   │ monitor.py          │                                                │
│   │ (thread, lazy gi)   │                                                │
│   └──────────┬──────────┘                                                │
└──────────────┼──────────────────────────────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       CORE / DOMAIN LAYER                               │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐   │
│   │ sysfs.py │  │profiles  │  │features  │  │ service  │  │ config  │   │
│   │ READONLY │  │ mapping  │  │detection │  │  status  │  │ (TOML)  │   │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘   │
│        │             │             │             │             │        │
└────────┼─────────────┼─────────────┼─────────────┼─────────────┼────────┘
         │             │             │             │             │
         │ (read)      │ (validate)  │ (probe)     │             │
         ▼             ▼             ▼             │             │
┌────────────────────────────────────────────┐    │             │
│              KERNEL SURFACE                 │    │             │
│   /sys/firmware/acpi/platform_profile       │    │             │
│   /sys/firmware/acpi/platform_profile_      │    │             │
│       choices                               │    │             │
│   /sys/class/hwmon/hwmon*/                  │    │             │
│   /sys/module/acer_wmi/parameters/          │    │             │
│       predator_v4                           │    │             │
└─────────────────────────────────────────────┘    │             │
                                                    │             │
         (writes never go directly here)            │             │
                                                    │             │
┌────────────────────────────────────────────────────────────────────────┐
│                       PRIVILEGE BOUNDARY                                │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │ privilege.py                                                     │  │
│   │   - subprocess.run(["pkexec", HELPER, "set-profile", value])    │  │
│   │   - fallback: ["sudo", HELPER, ...] if pkexec missing           │  │
│   │   - catches CalledProcessError, returns Result(ok/err/cancelled)│  │
│   └────────────────────────────────┬────────────────────────────────┘  │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │  pkexec ↑ polkit auth dialog
                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  ROOT-PRIVILEGED HELPER (separate process)              │
│   /usr/libexec/acercontrol/acercontrol-helper                           │
│     subcommands:                                                        │
│       set-profile <user_name>                                           │
│           ↳ validates against platform_profile_choices                  │
│           ↳ maps user_name → kernel value via profiles.py               │
│           ↳ writes /sys/firmware/acpi/platform_profile                  │
│       set-boot-profile <user_name>                                      │
│           ↳ atomically rewrites /etc/acercontrol/boot.conf              │
│       enable-service / disable-service                                  │
│           ↳ systemctl enable/disable --now acer-performance.service     │
│       reload-module                                                     │
│           ↳ rmmod acer_wmi && modprobe acer_wmi predator_v4=1           │
│     exits 0/non-zero; prints structured one-line status to stdout       │
└────────────────────────────────────────────────────────────────────────┘
```

### Who-talks-to-whom Rules

| Caller | May call | Must NOT call |
|---|---|---|
| `gui.py` | `monitor`, `privilege`, `service`, `config`, `features`, `profiles`, `sysfs` (read), `notifier`, `tray` | sysfs writes; `subprocess` directly for privileged ops |
| `cli.py` | `privilege`, `service`, `config` (limited), `features`, `profiles`, `sysfs` (read) | `gi`, `gui`, `monitor`, `notifier`, `tray` |
| `monitor.py` | `sysfs` (read) | writes, privilege layer (monitor is read-only) |
| `privilege.py` | `subprocess` → helper only | sysfs reads/writes itself |
| `helper` | sysfs writes, `systemctl`, `modprobe`, `/etc/acercontrol/*` | importing `gi`, reading user `$HOME` |
| `sysfs.py` | filesystem reads under `/sys` only | writes; subprocess |

### Reconciling the Single-File CLI Constraint

PROJECT.md requires the CLI to remain a single-file zero-dependency script suitable for `cp /usr/local/bin/`. PROJECT.md also requires shared core logic. Resolution:

**Two build outputs from one source:**

1. **Package install (`.deb`):** `pyproject.toml` declares two `console_scripts`:
   ```
   [project.scripts]
   acercontrol     = "acercontrol.cli:main"
   acercontrol-gui = "acercontrol.gui:main"
   ```
   Both shims are 1-line entry points generated by setuptools at install time. The package is installed to `/usr/lib/python3/dist-packages/acercontrol/`.

2. **Manual install (`install.sh`):** Build-time tool `tools/bundle_cli.py` walks the package, concatenates `sysfs.py + profiles.py + features.py + privilege.py + config.py + service.py + cli.py` (in dependency order), prepends `#!/usr/bin/env python3`, and writes `dist/acercontrol`. `install.sh` copies `dist/acercontrol → /usr/local/bin/acercontrol`.

**Hard invariants for the bundler:**
- Refuses to bundle if any input file contains `import gi` or `from gi` (enforced by `tools/verify_no_gtk.py` in CI/pre-commit).
- Refuses to bundle if any input file has a non-stdlib `import`.
- Strips `from acercontrol.X import Y` rewrites to local references during concatenation.

**Why not just ship the package both ways?** `cp ... /usr/local/bin/` is the user expectation for a CLI — bundler preserves it. Trying to make `cli.py` import-free at runtime is hostile to the package model the GUI needs.

---

## Data Flow

### Flow 1: Profile Click (GUI)

```
[user clicks "Turbo" button]
        │
        ▼
gui.py: on_profile_button_clicked("turbo")
        │
        ▼
profiles.user_to_kernel("turbo") → "performance"
        │
        ▼
privilege.set_profile("turbo")
        │
        ▼  subprocess.run(["pkexec",
        │     "/usr/libexec/acercontrol/acercontrol-helper",
        │     "set-profile", "turbo"])
        ▼
─────────── polkit auth dialog ───────────
        │
        ▼  (user authenticates)
helper: validate "turbo" → "performance" in platform_profile_choices
        │
        ▼
write "performance" → /sys/firmware/acpi/platform_profile
        │
        ▼  exit 0
privilege.set_profile returns Result(ok=True)
        │
        ▼
gui.py: re-read sysfs.read_profile() → "performance"
        │
        ▼
gui.py: highlight_active_button("turbo") + Adw.Toast("Profile: Turbo")
        │
        ▼
notifier.notify("Profile changed to Turbo")  (Gio.Notification)
```

**Cancellation path:** if `pkexec` returns 126/127 (user cancelled), `privilege.py` returns `Result(cancelled=True)`. GUI shows toast "Authorization cancelled" and reverts visual state to the previously active button (no sysfs reread needed because nothing was written).

### Flow 2: Sensor Refresh Tick (every 2s)

```
[GLib.timeout_add never used here — monitor thread instead]

monitor.SensorMonitor._run() loop:
  while not stop_event.wait(2.0):
        │
        ▼
    data = sysfs.read_sensors()
        │  (read each hwmon by name lookup;
        │   read coretemp temp1_input;
        │   read acer fan1_input, fan2_input, temp1/2/3_input)
        ▼
    if previous read failed for a sensor: data[k] = None
        │
        ▼
    GLib.idle_add(self.callback, data)
        │  (marshals back to GTK main thread)
        ▼
gui.py: on_sensor_update(data)
  - update temp bars (color by threshold)
  - update fan RPM bars
  - if any temp >= 90°C and not already alerted in last 30s:
        notifier.notify("Critical temperature: …")
  - return False  (one-shot idle callback)
```

**Why a thread, not `GLib.timeout_add`?** PROJECT.md mandates a background thread + `GLib.idle_add` — that pattern survives slow sysfs reads (rare but possible on hwmon repopulation after suspend) without freezing the UI. A `GLib.timeout_add` callback runs on the main loop and would block paint.

### Flow 3: Boot Application

```
[system boot, multi-user.target reached]
        │
        ▼
systemd starts acer-performance.service
  Type=oneshot, RemainAfterExit=yes
  After=systemd-modules-load.service
  ExecStart=/usr/libexec/acercontrol/acercontrol-helper apply-boot
        │
        ▼
helper "apply-boot":
  - read /etc/acercontrol/boot.conf  (key=value, "profile=turbo")
  - validate profile against platform_profile_choices
  - write kernel value → /sys/firmware/acpi/platform_profile
  - exit 0 (or non-zero if config malformed; service shows as failed)
        │
        ▼
systemd marks unit active(exited)
```

**Why the service runs the same helper:** zero code duplication, identical validation path, and the unit file doesn't need shell quoting. Service runs as root by default (no `User=` line) — it does *not* go through pkexec; pkexec is only for the interactive desktop session.

### Flow 4: Change Boot Profile from GUI

```
[user picks "balanced" in boot profile dropdown]
        │
        ▼
gui.py: on_boot_profile_changed("balanced")
        │
        ▼
privilege.set_boot_profile("balanced")
        │
        ▼  pkexec helper set-boot-profile balanced
        ▼
─────────── polkit auth dialog ───────────
        │
        ▼
helper: validate, atomically rewrite /etc/acercontrol/boot.conf
        │       (tmpfile → fsync → rename)
        ▼
gui.py: re-read service.read_boot_config() and update dropdown label
```

### Flow 5: Service Enable/Disable

```
gui.py: on_service_toggle(True)
        │
        ▼
privilege.enable_service("acer-performance.service")
        │
        ▼  pkexec helper enable-service
        ▼
helper: systemctl enable --now acer-performance.service
        │
        ▼  exit 0
gui.py: service.is_enabled() → True; update switch label
```

### Flow 6: Startup Feature Probe

```
[GUI launches]
        │
        ▼
gui.py: build Adw.Application, on activate:
        │
        ▼
features.probe() returns FeatureReport:
  - acer_wmi_loaded: bool       (Path("/sys/module/acer_wmi").exists())
  - predator_v4: bool|None      (read PREDATOR_V4_PARAM)
  - profile_path_present: bool
  - profile_path_writable: bool (test write? NO — use stat() and uid 0 check
                                  via lsmod, not actual write)
  - hwmon_acer_found: bool
  - hwmon_coretemp_found: bool
  - ppd_active: bool            (systemctl is-active power-profiles-daemon)
        │
        ▼
gui.py: dispatch on report
  - acer_wmi_loaded == False → push Adw.StatusPage("module-not-loaded")
  - predator_v4 != True       → push Adw.StatusPage("predator-v4-missing")
  - profile_path_present==F   → push Adw.StatusPage("profile-path-missing")
  - ppd_active == True        → main view + Adw.Banner with "Disable PPD" action
  - else                      → push main view
```

---

## Configuration & State Storage

### The Split: Why Two Files

The boot service runs as root in early boot. It cannot read `~/.config` (no specific user yet, possibly home dir not mounted/unlocked). So:

| What | Where | Who writes | Who reads |
|---|---|---|---|
| **Boot profile** (which profile to apply on boot) | `/etc/acercontrol/boot.conf` | helper via pkexec (`set-boot-profile`) | systemd helper at boot; GUI to display current setting |
| **User preferences** (notification threshold, show-tray, refresh interval, last-selected-tab, etc.) | `~/.config/acercontrol/config.toml` | GUI directly (user-owned file) | GUI on startup |
| **Polkit authorization cache** | system-managed | polkit | polkit |

### `/etc/acercontrol/boot.conf` format

```ini
# AcerControl boot configuration
# Written by acercontrol-gui via pkexec; do not edit by hand
profile = turbo
```

- INI-style, one key per line, comments allowed.
- Written atomically (write tmp → fsync → rename).
- Owned by root:root, 0644 — world-readable so non-root processes can display the current value without privilege.
- Default value if file missing: `balanced` (helper falls back, no failure).

### `~/.config/acercontrol/config.toml` format

```toml
[general]
refresh_interval_seconds = 2

[notifications]
enabled = true
critical_temp_celsius = 90
profile_change = true

[tray]
enabled = true
show_temperature = false

[ui]
last_window_width = 640
last_window_height = 480
```

- Standard XDG location (`$XDG_CONFIG_HOME` with fallback to `~/.config`).
- Python 3.11+ has `tomllib` in stdlib for reading; writing uses a simple custom emitter (don't pull `tomli-w` — keeps zero-deps).
- Missing keys fall back to defaults; corrupt file is renamed `config.toml.broken-YYYYMMDD` and defaults are used.

### Why not `Gio.Settings` / GSchema?

- Requires compiling the schema in `postinst` (`glib-compile-schemas`).
- Schema files at `/usr/share/glib-2.0/schemas/`, must register in `debian/postinst` and `debian/postrm`.
- Adds review burden, no real benefit at this scale.
- TOML is human-readable, scriptable, debuggable — fits the "polished personal tool" bar.

### Why not just `/etc/acercontrol/` for everything?

- User preferences should not require root to change. Notification threshold doesn't need pkexec.
- Mixing user prefs with system config in `/etc` violates FHS.

---

## Polkit Policy — Three Actions

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
  "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <vendor>AcerControl</vendor>
  <vendor_url>https://github.com/.../acercontrol</vendor_url>

  <action id="org.acercontrol.setprofile">
    <description>Change the performance profile</description>
    <message>Authentication is required to change the performance profile</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-helper</annotate>
  </action>

  <action id="org.acercontrol.manage-service">
    <description>Manage the AcerControl boot service</description>
    <message>Authentication is required to enable or disable the boot service</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-helper</annotate>
  </action>

  <action id="org.acercontrol.set-boot-profile">
    <description>Change the boot-time performance profile</description>
    <message>Authentication is required to change the boot-time performance profile</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-helper</annotate>
  </action>
</policyconfig>
```

`auth_admin_keep`: the active user authenticates once, and authorization is cached for ~5 minutes (polkit default). Means setting profile, then setting boot profile, then enabling service does *not* prompt three times in a row.

**XML schema syntax flagged MEDIUM confidence** — verify against `man polkit` or `/usr/share/polkit-1/actions/*.policy` on the target system during phase 1.

---

## Build / Install Order (Debian)

```
build phase
   1. `dh_auto_build` → pybuild reads pyproject.toml, byte-compiles the package
   2. `tools/bundle_cli.py` → generates dist/acercontrol (single-file CLI)
      (called from debian/rules override_dh_auto_build)
   3. `tools/verify_no_gtk.py` runs against dist/acercontrol — fails build if
      it imports gi or non-stdlib modules

install phase (driven by debian/acercontrol.install)
   data/applications/acercontrol.desktop          usr/share/applications
   data/polkit/org.acercontrol.policy             usr/share/polkit-1/actions
   data/systemd/acer-performance.service          lib/systemd/system
   data/modprobe/acer-wmi.conf                    etc/modprobe.d
   data/icons/hicolor/scalable/apps/...           usr/share/icons/hicolor/...
   data/metainfo/...                              usr/share/metainfo
   helper/acercontrol-helper                      usr/libexec/acercontrol

   (pybuild puts the package in /usr/lib/python3/dist-packages/acercontrol)
   (console_scripts shims placed in /usr/bin by setuptools/dh_python3)

postinst phase
   1. systemctl daemon-reload                    (new unit visible)
   2. update-desktop-database -q                 (.desktop registered)
   3. gtk-update-icon-cache -q /usr/share/icons/hicolor || true
   4. mkdir -p /etc/acercontrol; create default boot.conf if missing
   5. depmod -a                                  (modprobe.d recognized)
   6. systemctl enable acer-performance.service  (handled by dh_installsystemd
                                                  with appropriate maintscript)
   7. policy file is picked up automatically — no action needed

postrm phase (on purge)
   1. systemctl disable acer-performance.service (handled by dh_installsystemd)
   2. systemctl daemon-reload
   3. rm -f /etc/modprobe.d/acer-wmi.conf
   4. rm -rf /etc/acercontrol/
   5. update-desktop-database -q
```

`debian/control` Depends line:
```
Depends: ${python3:Depends}, ${misc:Depends},
         python3-gi, gir1.2-gtk-4.0 (>= 4.6),
         gir1.2-adw-1, policykit-1, systemd
Recommends: gir1.2-appindicator3-0.1 | gir1.2-ayatanaappindicator3-0.1
Conflicts: power-profiles-daemon
```

> **`Conflicts: power-profiles-daemon`** is a design choice, not a default. The advisor's reconcile call would be: do you want to forcibly displace PPD on install (`Conflicts:`), or coexist and warn (no `Conflicts:`, runtime banner). **Recommend coexist+warn** for v1 — `Conflicts:` is aggressive and surprises users who installed AcerControl as a "try it" tool. Flag this as a phase-time decision.

---

## Build Order — Implementation Phases

Dependency-resolved sequence. Each phase requires the previous; the roadmap should not reorder.

| Phase | Deliverable | Why this order |
|---|---|---|
| **1. Core extraction** | `acercontrol/{sysfs,profiles,features,config}.py` extracted from existing `acercontrol.py`; unit-callable functions; CLI rewired to import from package; `tools/bundle_cli.py` restores single-file CLI; CI guard against `gi` imports in CLI inputs. | The existing CLI in CLAUDE.md is the only working code; we must not break it while refactoring. Everything downstream depends on the core layer. |
| **2. Privilege boundary + helper + polkit policy** | `acercontrol/privilege.py`, `helper/acercontrol-helper`, `data/polkit/org.acercontrol.policy`. CLI's `acercontrol set <profile>` now goes through helper. End-to-end pkexec dialog working. | Establishes the security model end-to-end with one consumer (CLI). When GUI arrives, it just calls the same `privilege.set_profile`. |
| **3. Failure-mode probe + Adw.StatusPage routing** | `acercontrol/features.py` returns `FeatureReport`; minimal GUI shell that *only* runs probe and routes to a StatusPage for each failure (no main view yet). | Forces us to think about every failure before any happy-path UI exists. Trying to bolt error states onto an existing happy path produces inconsistent UX. |
| **4. GUI main view: profile buttons** | `acercontrol/gui.py` main view with 5 profile buttons, active highlight, click → `privilege.set_profile`, toast on result. No sensors yet. | Closes the core value loop ("click profile → laptop switches") with the minimum surface. Validates the whole privilege stack from a real GUI. |
| **5. Sensor monitor thread + live bars** | `acercontrol/monitor.py`; live temp/fan bars with color thresholds; thread cleanly stops on window close. | Now the read path can be added; it's independent of the write path. |
| **6. Boot service panel** | `acercontrol/service.py` (read-only status + boot.conf I/O); `data/systemd/acer-performance.service`; helper `apply-boot`/`set-boot-profile`/`enable-service`/`disable-service`. GUI shows status, toggles enable, picks boot profile. | Depends on helper (phase 2) and probe (phase 3) being in place. |
| **7. Notifications + tray** | `acercontrol/notifier.py` (Gio.Notification on profile change, on critical temp); `acercontrol/tray.py` (AppIndicator with quick-switch). | Optional per PROJECT.md; pure additions, can't destabilize earlier phases. |
| **8. Packaging** | `debian/` tree, `debian/rules` with pybuild + bundler + dh_installsystemd + dh_installpolkit; `metainfo.xml`; `.desktop`; icons; lintian clean. Manual `install.sh` parallel path. | Packaging last, after all artifacts exist. Doing it earlier means re-cutting paths every phase. |

**Phase 0 (not counted): clear out / rebuild.** PROJECT.md key decision "Full rebuild from scratch" is still Pending. If kept Pending too long, phase 1 starts from a clean repo rather than refactoring; either is fine, but a decision should be made before phase 1 starts.

---

## Failure-Mode Architecture

Every failure has: (1) detection point, (2) UI presentation, (3) remediation action exposed to user. Always.

| Condition | Detection | UI Presentation | Remediation in UI |
|---|---|---|---|
| `acer_wmi` not loaded | `Path("/sys/module/acer_wmi").exists() == False` | Full-window `Adw.StatusPage`, icon=`software-update-urgent-symbolic`, title="acer_wmi module not loaded" | Button: "Load module" → `pkexec helper reload-module`. Also shows copy-able command. |
| `predator_v4=N` | Read `/sys/module/acer_wmi/parameters/predator_v4` | `Adw.StatusPage`, title="predator_v4 mode not enabled" | Button: "Reload with predator_v4=1" → `pkexec helper reload-module`. Shows command to make persistent (`/etc/modprobe.d/acer-wmi.conf`). |
| `platform_profile` missing | `Path("/sys/firmware/acpi/platform_profile").exists() == False` | `Adw.StatusPage`, title="Kernel does not expose platform_profile" | Read-only: text explaining kernel version needed (≥6.14 for this hardware), no auto-fix. |
| hwmon `acer` not found | `features.probe()` returns `hwmon_acer_found=False` | Main view renders, but sensor section shows `Adw.StatusPage` (compact) where bars would be | Button: "Retry detection" → re-probe (hwmon can appear late after module load). |
| hwmon `coretemp` not found | as above | CPU temp bar shows "—" | Silent — non-critical. |
| polkit auth cancelled | `privilege.set_profile()` returns `Result(cancelled=True)` | `Adw.Toast` "Authorization cancelled" (3s); button state reverts to previous active | No remediation — silent fail per PROJECT.md. |
| pkexec returns non-zero (helper error) | Helper exit code ≠ 0, stderr captured | `Adw.Toast` with first line of stderr; details available via "Show details" expander | If stderr contains "Invalid value", revert button state; otherwise leave (sysfs may have partial state — reread to confirm). |
| Sensor read raises `OSError` | try/except in `sysfs.read_sensors`; returns `None` for that key | UI bar shows "—" for that reading only; doesn't crash the panel | Auto-recovers on next 2s tick. |
| Service not installed (no unit file) | `systemctl is-enabled` returns "not-found" / exit 1 | Service section shows "Boot service not installed" | Button: "Install boot service" → manual instructions or, if package is present, hint to run `acercontrol install`. |
| **power-profiles-daemon active** (CRITICAL) | `systemctl is-active power-profiles-daemon` returns "active" | Persistent `Adw.Banner` at top of main view: "power-profiles-daemon is running and will overwrite profile changes" | Button: "Mask power-profiles-daemon" → `pkexec systemctl mask --now power-profiles-daemon`. Secondary: "Coexist" (dismisses banner for this session). |
| Sensor refresh thread dies | Thread caught by monitor's outer `except Exception` → emits error event | `Adw.Toast` "Sensor monitor stopped"; button "Restart monitor" | One-click recovery. |
| `boot.conf` malformed | helper's `apply-boot` exits non-zero; systemd marks unit failed | Service status row shows "failed (boot.conf invalid)"; expanded shows journal hint | Button: "Reset boot config to balanced" → `pkexec helper set-boot-profile balanced`. |

### PPD Interaction — Why It Deserves Top-Level Treatment

Ubuntu 24.04 ships `power-profiles-daemon` (PPD) and it is active by default. PPD also writes `/sys/firmware/acpi/platform_profile`. If both are running:

- Whoever writes last wins. AcerControl writes on click; PPD writes whenever the user toggles GNOME's power menu, on AC/battery transition, on system suspend/resume.
- Symptom: user clicks "Turbo", LED blinks for 30s, then PPD writes "balanced" on a battery event and the LED stops. User thinks AcerControl is broken.

Architecture response: detect at startup, present persistent banner with one-click mask. This is the only "warning" surface in the main view — everything else is either a StatusPage (blocking) or a Toast (transient).

> **MEDIUM confidence:** specific PPD behaviors and write timing not re-verified this session. Phase 3 implementation should test: with PPD active, does AcerControl's write to `platform_profile` succeed but get reverted? Confirm and document.

---

## Anti-Patterns

### Anti-Pattern 1: `pkexec bash -c "echo X > /sys/..."`

**What people do:** the CLAUDE.md draft shows this. Looks tempting; one line.
**Why it's wrong:**
- Shell-quoting the value is bug-prone.
- Can't define a polkit action for "echo to a path" — it must be one specific binary at one specific path (`exec.path` annotation). `bash` doesn't qualify; the policy can't be tightened beyond "let user run arbitrary bash as root."
- No input validation against `platform_profile_choices` — typoing "perfomance" gets `EINVAL` from the kernel with no friendly error.
- Can't be reused by the systemd unit; that's separate code.
**Do this instead:** named helper binary at `/usr/libexec/acercontrol/acercontrol-helper`, polkit action pinned to that exact path, subcommand router, input validated against the choices file.

### Anti-Pattern 2: Two source files at repo root + a package

**What people do:** keep `acercontrol.py` and `acercontrol_gui.py` as top-level scripts and the `acercontrol/` package alongside.
**Why it's wrong:** three sources of truth. Bug fixes drift. The CLI works one way installed from `.deb`, another way from `cp acercontrol.py`. Onboarding contributors is harder.
**Do this instead:** one package, two build outputs (entry-point shims for `.deb`, bundler-produced single-file for manual install).

### Anti-Pattern 3: `GLib.timeout_add` doing sysfs reads on the main loop

**What people do:** `GLib.timeout_add(2000, refresh_sensors)` reads hwmon directly on the GTK main loop.
**Why it's wrong:** sysfs reads are usually instant, but can stall after suspend/resume or hwmon repopulation. A stalled read on the main loop = frozen UI.
**Do this instead:** background `threading.Thread`, `time.sleep`/`Event.wait` for cadence, `GLib.idle_add` to marshal back. Already specified in PROJECT.md.

### Anti-Pattern 4: Reading user `~/.config` from the boot service

**What people do:** store boot profile choice in `~/.config/acercontrol/config.toml` (the same place as UI prefs) and have the service "figure out" which user.
**Why it's wrong:** at multi-user.target there is no logged-in user; home may not be mounted; on systems with multiple users, which one wins? Setting `User=` on the unit doesn't help because the user might not be present at boot.
**Do this instead:** root-owned `/etc/acercontrol/boot.conf`, GUI writes it via pkexec. System config separated from user preferences.

### Anti-Pattern 5: Caching sudo password / running GUI as root

**What people do:** `gksu acercontrol-gui` or storing a password.
**Why it's wrong:** GTK apps must not run as root (security, broken theming, X server hostility on Wayland). Caching credentials = security incident waiting to happen.
**Do this instead:** GUI runs as user; pkexec at moment of action, polkit caches authorization (not credentials) for 5 minutes via `auth_admin_keep`.

### Anti-Pattern 6: Hardcoding `hwmon7`

**What people do:** `/sys/class/hwmon/hwmon7/temp1_input`.
**Why it's wrong:** hwmon numbering is not stable across boots, kernel updates, module load order.
**Do this instead:** `sysfs.find_hwmon_by_name("acer")` scans `/sys/class/hwmon/hwmon*/name` and returns the matching directory. Cached for the session, re-probed if a read fails.

---

## Integration Points

### External Services / Subsystems

| Subsystem | Integration | Notes |
|---|---|---|
| `acer_wmi` kernel module | sysfs r/w via helper | Only via `predator_v4=1` path for v1 |
| polkit | XML policy + pkexec | Three actions; helper at `/usr/libexec/...` |
| systemd | unit file + `systemctl` shell-out | `Type=oneshot, RemainAfterExit=yes`; helper does the work |
| GTK4 / libadwaita | Python gi bindings | GUI process only; never imported by CLI bundle |
| AppIndicator / StatusNotifier | optional, via `gir1.2-appindicator3-0.1` | `Recommends:` not `Depends:` — tray is optional |
| Gio.Notification | freedesktop notifications | Requires `.desktop` file installed (uses app ID) |
| `power-profiles-daemon` | conflict-detection only | NOT a dependency; detect-and-warn at runtime |

### Internal Boundaries

| Boundary | Communication | Direction |
|---|---|---|
| `gui.py` ↔ `monitor.py` | callback + `GLib.idle_add` | monitor → gui (data); gui → monitor (start/stop) |
| `gui.py` / `cli.py` ↔ `privilege.py` | function call returning `Result` | one-way |
| `privilege.py` ↔ helper | subprocess + JSON-or-line stdout | one-way invocation |
| `helper` ↔ kernel | direct sysfs writes | one-way |
| `gui.py` ↔ `config.py` | function call, TOML I/O | bidirectional |
| `service.py` ↔ `/etc/acercontrol/boot.conf` | read-only direct; writes go through helper | mostly one-way |

---

## Scaling Considerations

Not applicable in the user/RPS sense — this is a single-user desktop tool. Real scaling considerations:

| Dimension | At v1 (PHN16-72) | Compat broadening (other Predator/Nitro) | Multi-distro |
|---|---|---|---|
| **Profile mapping** | Hardcoded `PROFILES` dict | Read `platform_profile_choices` at runtime, fall back to dict for naming | Same; sysfs interface is kernel, not distro |
| **Hwmon discovery** | Find by name `acer` + `coretemp` | Same; add tolerance for missing temp3 etc. | Same |
| **Packaging** | Single `.deb` | Same `.deb`, add `Recommends` for optional bits | Add Fedora/RPM (`.spec`), Arch (`PKGBUILD`), Flatpak |
| **Feature detection** | Probe `predator_v4` | Add classic-acer-wmi path (out of scope for v1 per PROJECT.md) | Same |
| **Privilege model** | polkit + pkexec | Same | Distros without polkit: sudo fallback is already designed |

Bottlenecks in priority order:

1. **First bottleneck:** profile mapping diverges on different hardware revisions. Solution: validate against `platform_profile_choices` at runtime, hide buttons whose kernel value isn't supported.
2. **Second bottleneck:** non-polkit desktops (some XFCE, i3 setups). Solution: sudo fallback is already in `privilege.py`; document.
3. **Third bottleneck:** Flatpak distribution wants no sysfs access. Solution: out of scope for v1; would require a system-level companion service.

---

## Sources

Primary inputs:
- `/Users/sushilkumarsahani/Desktop/AcerControl/.planning/PROJECT.md` — scope, constraints, key decisions
- `/Users/sushilkumarsahani/Desktop/AcerControl/CLAUDE.md` — initial draft, sysfs paths, profile mapping, GUI requirements

Conventions referenced from training data (NOT re-verified this session; flagged MEDIUM in tables above):
- Freedesktop polkit policy XML schema and `org.freedesktop.policykit.exec.path` annotation
- Freedesktop `.desktop` file install location (`/usr/share/applications/`)
- Freedesktop icon theme spec (`/usr/share/icons/hicolor/scalable/apps/`)
- Debian policy: systemd units in `/lib/systemd/system/`, polkit actions in `/usr/share/polkit-1/actions/`
- FHS: `/usr/libexec/` for internal helper binaries
- XDG Base Directory: `$XDG_CONFIG_HOME` with `~/.config` fallback

Spot-check during phase 1 implementation:
- `man polkit` and `man polkit.conf` for current action/rule syntax on Ubuntu 24.04
- `man systemd.unit` and `/lib/systemd/system/*.service` examples for unit conventions
- `lintian` warnings on initial `.deb` build to catch path violations

---

*Architecture research for: Linux desktop GUI for Acer Predator/Nitro WMI thermal/profile control*
*Researched: 2026-05-13*
