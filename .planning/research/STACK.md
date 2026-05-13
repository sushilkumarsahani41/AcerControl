# Stack Research — AcerControl

**Domain:** Linux desktop GUI for laptop hardware control (Acer Predator/Nitro `acer_wmi` thermal/profile UI)
**Target OS:** Ubuntu 24.04 LTS (primary), Debian 12 (secondary)
**Researched:** 2026-05-13
**Overall confidence:** HIGH for stack identity (package names, frameworks, patterns); MEDIUM-to-LOW for distro-pinned version *numbers* — these were deliberately not pinned and should be confirmed on the target machine with `apt-cache policy <pkg>` before being written into `debian/control`.

---

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

---

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

**Tray (optional, deferred):**

| Package | Provides |
|---------|----------|
| `gir1.2-ayatanaappindicator3-0.1` | Ayatana AppIndicator 3 (GTK3-flavored) |
| `gnome-shell-extension-appindicator` | Preinstalled bridge on Ubuntu 24.04 from GNOME 46 panel to AppIndicator/KStatusNotifierItem |

**Build / packaging:**

| Package | Provides |
|---------|----------|
| `debhelper-compat (= 13)` (build-dep) | Modern dh sequencer baseline on Noble |
| `dh-sequence-python3` | Drives `pybuild` from `dh $@` |
| `pybuild-plugin-pyproject` | Makes `pybuild` understand `pyproject.toml` |
| `python3-setuptools`, `python3-wheel` | PEP 517 build backend |
| `dpkg-dev`, `devscripts`, `lintian` | Source-package build + lint |

> **Caveat on micro-versions.** `packages.ubuntu.com` was unreachable during research. Package *names* are stable across Noble's lifetime; version *strings* were deliberately omitted. The roadmap "packaging setup" phase must run `apt-cache policy python3-gi gir1.2-gtk-4.0 gir1.2-adw-1` on the Noble target and record the actual versions in `debian/control`.

---

## Detailed Rationale

### 1. GTK4 + Adwaita binding

**Recommendation:** `python3-gi` + `gir1.2-gtk-4.0` + `gir1.2-adw-1` from Ubuntu 24.04 main archive.

**Rationale:**
- Adwaita 1.x has been the standard GNOME app look since 2022 and tracks GNOME release cadence (Adwaita 1.5 ships with GNOME 46 / Ubuntu 24.04; Adwaita 1.6 with GNOME 47). Noble ships GNOME 46.
- PyGObject's canonical install on Ubuntu/Debian is `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0` (verified, Context7 `/gnome/pygobject`).
- Required boilerplate:
  ```python
  import gi
  gi.require_version("Gtk", "4.0")
  gi.require_version("Adw", "1")
  from gi.repository import Gtk, Adw, GLib, Gio
  ```

**Debian 12 caveat:** Bookworm ships libadwaita 1.2.x. `Adw.Banner` (1.3), `Adw.AlertDialog` / `Adw.AboutDialog` (1.4), `Adw.NavigationView` (1.4), `Adw.ToolbarView` (1.4) are NOT available. For v1, target Noble; constrain to libadwaita 1.2 widgets (`ApplicationWindow`, `HeaderBar`, `PreferencesGroup`, `ActionRow`, `SwitchRow`, `Toast`/`ToastOverlay`, `StatusPage`) if Bookworm parity matters.

**Anti-recommendations:** Do not use GTK3 — Adwaita 1.x requires GTK4. Do not pip-install PyGObject — system `apt` is canonical because PyGObject needs matching system typelibs.

**Confidence:** HIGH on stack identity, MEDIUM on exact Noble micro versions.

---

### 2. System tray indicator

**Recommendation:** **Defer tray to a post-v1 polish phase.** If shipped, use `gir1.2-ayatanaappindicator3-0.1` in a separate helper process.

**Rationale:**
- GNOME 46 has no built-in tray. Ubuntu 24.04 ships `gnome-shell-extension-appindicator` preinstalled and enabled — AppIndicator icons render in the GNOME panel.
- There is **no GTK4-native AppIndicator binding.** `libayatana-appindicator` builds against GTK3 (Context7 `/ayatanaindicators/libayatana-appindicator` — `pkg-config gtk+-3.0 ayatana-appindicator3-0.1`). Using it from a GTK4 Python app means `gi.require_version('Gtk', '3.0')` somewhere — conflicts with `Gtk 4.0` in the same process.

  Workarounds:
  - **Option A (pragmatic):** Tray as a separate Python helper process using GTK3 + AppIndicator3, talking to the main GTK4 GUI over a UNIX socket / D-Bus.
  - **Option B (advanced):** Speak `org.kde.StatusNotifierItem` directly over D-Bus from the GTK4 process (~200 lines of boilerplate, no GTK3 dep).
  - **Option C (skip):** No tray for v1.

  Default to C for v1; reserve A or B for a later phase.
- Ubuntu 24.04 default desktop is Wayland — `Gtk.StatusIcon` (X11 system-tray protocol) is removed in GTK4 anyway.

**Anti-recommendations:**
- `Gtk.StatusIcon` — does not exist in GTK4.
- `gir1.2-appindicator3-0.1` (old Canonical/Unity `libappindicator`) — superseded by the Ayatana fork.
- Mixing GTK3 AppIndicator code inside the GTK4 process — produces confusing import-version errors.

**Confidence:** HIGH.

---

### 3. Privilege escalation

**Recommendation:** Ship a polkit `.policy` XML declaring `org.acercontrol.setprofile`. Invoke via `pkexec`. Use `<allow_active>auth_admin_keep</allow_active>`.

**Rationale:**
- polkit `.policy` XML (in `/usr/share/polkit-1/actions/`) is how applications **declare** auth-required actions. polkit `.rules` JS files (in `/etc/polkit-1/rules.d/`) are how sysadmins **override** those declarations. An app ships `.policy`; `.rules` is sysadmin-only.
- `auth_admin_keep` caches the credential for ~5 minutes — good UX for users flipping profiles. Still requires *admin* credentials.
- `auth_self_keep` requires the active user's own password (not admin). On a single-user laptop the user *is* admin, so functionally identical; we recommend `auth_admin_keep` because writing to `/sys/firmware/acpi/platform_profile` is fundamentally an admin action.
- `<allow_any>` and `<allow_inactive>` should be `auth_admin` (no `_keep`).

**`.policy` file shape:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD polkit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <vendor>AcerControl</vendor>
  <vendor_url>https://github.com/.../acercontrol</vendor_url>
  <action id="org.acercontrol.setprofile">
    <description>Set Acer platform performance profile</description>
    <message>Authentication is required to change the performance profile</message>
    <icon_name>acercontrol</icon_name>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol-setprofile</annotate>
  </action>
</policyconfig>
```

**Invocation pattern:**

```python
def set_profile_privileged(value: str) -> None:
    try:
        subprocess.run(
            ["pkexec", "/usr/libexec/acercontrol-setprofile", value],
            check=True, timeout=30,
        )
    except FileNotFoundError:
        subprocess.run(
            ["sudo", "tee", "/sys/firmware/acpi/platform_profile"],
            input=value.encode(), check=True,
        )
```

`/usr/libexec/acercontrol-setprofile` is a small validator script that confirms the input against `/sys/firmware/acpi/platform_profile_choices` then writes. Naming this helper lets the `.policy` reference it via `org.freedesktop.policykit.exec.path` (defense in depth) and avoids `pkexec`-of-a-shell-pipeline.

**Anti-recommendations:**
- `pkexec bash -c 'echo ... > /sys/...'` — env scrubbing / quoting footguns; action ID becomes generic `org.freedesktop.policykit.exec`, so the GNOME prompt reads "Authentication required to run /bin/bash". Use a named helper binary.
- `sudo NOPASSWD` for the profile path — bypasses polkit UX, security regression.
- Long-lived elevated daemon — unnecessary; profile writes are one-off events.

**Confidence:** HIGH.

---

### 4. Desktop notifications

**Recommendation:** `Gio.Notification` for system notifications (critical temp > 90 °C while window is unfocused). `Adw.Toast` + `Adw.ToastOverlay` for in-app feedback ("Switched to turbo").

**Rationale:**
- `Gio.Notification` is the GTK-native, freedesktop-spec-conformant API. Integrated with `Gtk.Application` — no extra deps.
- **Critical footgun:** `Gio.Notification` requires the `Gtk.Application` to have a registered `application_id` AND a matching `.desktop` file installed at `/usr/share/applications/<application_id>.desktop`. If the application ID is `org.acercontrol.AcerControl`, the desktop file must be `org.acercontrol.AcerControl.desktop`. Without this, notifications **silently fail**.
- `Adw.Toast` is the modern in-app feedback widget. Add an `Adw.ToastOverlay` as the root child of the window, then `overlay.add_toast(Adw.Toast(title="Switched to Turbo"))`.

**Anti-recommendations:**
- `notify2` (PyPI) — unmaintained, duplicates `Gio.Notification`.
- `pynotifier`, `plyer` — cross-platform abstractions, unnecessary on Linux-only.
- `gi.repository.Notify` (libnotify directly) — older C API; `Gio.Notification` is the successor.
- `Adw.AppNotification` / `.app-notification` style class — deprecated upstream.

**Confidence:** HIGH.

---

### 5. Background sensor refresh

**Recommendation:** `GLib.timeout_add_seconds(2, refresh_callback)` running directly on the GTK main loop. No thread needed.

**Rationale:**
- Reading `/sys/class/hwmon/hwmon*/temp1_input` is a synchronous kernel read; completes in well under 1 ms. The GTK main loop runs at 16 ms (60 fps); a sub-ms read every 2 s causes zero visible jank.
- Avoiding a thread eliminates an entire class of concurrency bugs.
- Callback returns `GLib.SOURCE_CONTINUE` / `True` to keep ticking, `GLib.SOURCE_REMOVE` / `False` to stop. Store the source ID and call `GLib.source_remove(id)` on window close.
- Use threading **only if** a future sensor genuinely blocks (e.g. IPMI/EC over LPC > 100 ms). At that point use the documented pattern: daemon `threading.Thread` + `GLib.idle_add(callback, data)`.

**Anti-recommendations:**
- `threading.Thread` upfront — over-engineering, racy shutdown if not joined.
- `asyncio` + GLib via `gbulb` — unnecessary cognitive load for a 2-second poll.
- `GLib.timeout_add(2000, ...)` — works, but the `_seconds` variant aligns to whole-second ticks (power-friendlier) and is GLib-recommended for intervals at least 1 s.

**Confidence:** HIGH.

---

### 6. `.deb` packaging

**Recommendation:** Hand-written `debian/` directory using `debhelper-compat (= 13)` and the `dh` sequencer with `dh-sequence-python3` (driving `pybuild`). Build with `dpkg-buildpackage -us -uc -b`.

**Rationale:**
- `debhelper` compat 13 is the canonical baseline on Noble.
- `dh-sequence-python3` is the modern shorthand — gives `dh $@` (no explicit `--with python3`) and auto-discovers `pyproject.toml` when `pybuild-plugin-pyproject` is present.
- Hand-written `debian/` gives clean `lintian` output without manual fixups.
- `stdeb` is for PyPI-to-deb glue; AcerControl is not on PyPI and ships polkit `.policy`, systemd unit, `.desktop`, icons, modprobe.d snippet — none fit `stdeb`'s model.

**Minimal layout:**

```
debian/
  changelog            # dch -i to bump
  control              # build/runtime deps
  copyright            # DEP-5 format
  rules                # executable; "#!/usr/bin/make -f" + "%: ; dh $@"
  acercontrol.install  # maps source paths to install paths
  source/format        # "3.0 (native)"
```

`debian/control` (sketch):

```
Source: acercontrol
Section: utils
Priority: optional
Maintainer: <you>
Build-Depends:
 debhelper-compat (= 13),
 dh-sequence-python3,
 pybuild-plugin-pyproject,
 python3-all,
 python3-setuptools,
Standards-Version: 4.6.2
Rules-Requires-Root: no

Package: acercontrol
Architecture: all
Depends:
 ${python3:Depends},
 ${misc:Depends},
 python3-gi,
 python3-gi-cairo,
 gir1.2-gtk-4.0,
 gir1.2-adw-1,
 policykit-1,
Recommends:
 gnome-shell-extension-appindicator
Description: Acer Predator/Nitro performance control
 GTK4 GUI and CLI for Acer laptops using the acer_wmi kernel module.
```

**Anti-recommendations:**
- `stdeb` — doesn't handle polkit/systemd/desktop data files.
- `debmake` — auto-generated output needs manual cleanup anyway.
- Vendoring Python deps into the `.deb` — runtime constraint says "Ubuntu-shipped packages only".
- `compat` file vs. `Build-Depends: debhelper-compat` — both work; the latter (single source of truth in `control`) is current.

**Confidence:** MEDIUM-HIGH on the path; LOW-ish on the exact compat-level number without a fresh check on Noble.

---

### 7. systemd unit

**Recommendation:** `Type=oneshot` with `RemainAfterExit=yes`. `.deb` installs to `/usr/lib/systemd/system/acer-performance.service`; `install.sh` writes to `/etc/systemd/system/`.

**Rationale:**
- The boot service does one thing: write a configured profile string to `/sys/firmware/acpi/platform_profile` after `acer_wmi` is loaded, then exit. `Type=oneshot` matches exactly. `RemainAfterExit=yes` makes systemd treat the unit as "active" after the process exits, so `systemctl is-active` reports correctly.
- Vendor-installed units belong in `/usr/lib/systemd/system/` on merged-usr distros. Ubuntu 24.04 is merged-usr; `/lib/systemd/system/` is a compatibility symlink. `dh_installsystemd` writes to `/usr/lib/...`.
- Sysadmin/local units belong in `/etc/systemd/system/`. The CLAUDE.md `install.sh` uses `/etc/systemd/system/` — correct for manual install.

**Unit sketch:**

```ini
[Unit]
Description=Apply Acer performance profile at boot
After=systemd-modules-load.service
Requires=systemd-modules-load.service
ConditionPathExists=/sys/firmware/acpi/platform_profile

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/libexec/acercontrol-setprofile turbo
EnvironmentFile=-/etc/default/acercontrol

[Install]
WantedBy=multi-user.target
```

Store the desired profile in `/etc/default/acercontrol` (a `PROFILE=turbo` line). The GUI's "change boot profile" button writes that file via pkexec and re-runs `systemctl start acer-performance` without editing the unit itself.

**Anti-recommendations:**
- `Type=simple` — marks the unit failed when the script exits.
- Writing to `/sys/...` directly inside `ExecStart` without a wrapper — TOCTOU/quoting issues.
- Installing to `/lib/systemd/system/` from a `.deb` on Noble — works via symlink, but canonical is `/usr/lib/...`.

**Confidence:** HIGH.

---

### 8. Project layout

**Recommendation:** `pyproject.toml` (PEP 621, `setuptools` backend) with the GUI as an installable package. `.deb` build drives via `debian/rules` + `pybuild`.

**Layout:**

```
acercontrol/                     # repo root
  pyproject.toml                 # PEP 621 [project] table
  acercontrol/                   # importable package
    __init__.py
    core.py
    cli.py                       # entry point: acercontrol
    gui.py                       # entry point: acercontrol-gui
    monitor.py
    systemd_helper.py
  data/
    acercontrol.desktop
    acer-performance.service
    org.acercontrol.policy
    99-acer-wmi.conf             # modprobe.d snippet
    icons/
      scalable/apps/acercontrol.svg
      symbolic/apps/acercontrol-symbolic.svg
  debian/
  install.sh
```

- `[project.scripts]` maps `acercontrol = "acercontrol.cli:main"` and `acercontrol-gui = "acercontrol.gui:main"`.
- Non-Python data installs via `debian/acercontrol.install` — **not** setuptools `package_data` — keeps the Python package clean.
- The "single-file copyable CLI" path: a thin shim that does `from acercontrol.cli import main; main()`, or a bundler concatenating stdlib-only modules into `dist/acercontrol`.

**Anti-recommendations:**
- `setup.py` as primary config — deprecated.
- Poetry — adds runtime tooling, `pybuild` doesn't grok `tool.poetry`.
- Hatch / flit — fine for PyPI-first, but `pybuild-plugin-pyproject` is best tested against `setuptools`.

**Confidence:** HIGH.

---

### 9. App icon

**Recommendation:** SVG at `/usr/share/icons/hicolor/scalable/apps/acercontrol.svg` (full-color) + monochrome at `/usr/share/icons/hicolor/symbolic/apps/acercontrol-symbolic.svg` (tray, list contexts).

**Rationale:**
- GNOME HIG specifies `hicolor` as the install location. `scalable/apps/` is the catch-all for SVG; size-specific raster fallbacks no longer required.
- Symbolic icons use `currentColor` so GNOME re-tints them by context. Must live under `symbolic/apps/` and end in `-symbolic.svg`. HIG expects a 16x16 conceptual viewBox.
- `.desktop` `Icon=` field uses the basename without extension: `Icon=acercontrol`.
- The `.deb` postinst should run `gtk-update-icon-cache /usr/share/icons/hicolor`; `dh_icons` does this automatically when icons are installed under hicolor.

**Anti-recommendations:**
- PNG-only — doesn't scale on HiDPI.
- `pixmaps/` — legacy GNOME 2 location.

**Confidence:** HIGH.

---

### 10. CLI library

**Recommendation:** `argparse` from the standard library.

**Rationale:**
- Zero-deps constraint is non-negotiable for the single-file CLI.
- Surface is small: `status | get | set <profile> | list | temps | install`. `argparse` handles this in ~50 lines.
- `click` and `typer` are PyPI deps; `typer` additionally pulls `click` + `rich`.

**Anti-recommendations:**
- `click` / `typer` — violate zero-deps single-file constraint.
- `docopt` — abandoned upstream.

**Confidence:** HIGH.

---

### ++ Systemd interaction from the GUI

**Recommendation:** `subprocess.run(["pkexec", "systemctl", "<verb>", "acer-performance.service"])`. Skip `dasbus` / `pydbus` / `python-systemd`.

**Rationale:**
- GUI hits systemd ~3 times in its entire lifetime: `is-enabled`, `enable --now`, `disable --now`. No event subscription, no transient units.
- `subprocess` keeps the dep surface at zero new packages.
- `python-systemd` is the right answer for journal logging — not applicable here.
- D-Bus (systemd1) is the right answer for unit-state-change subscriptions — not needed.

**Anti-recommendations:**
- `dasbus` — fine library, overkill. PROJECT.md's "via `dasbus` or subprocess" should be resolved as subprocess.
- `pydbus` — unmaintained as of 2023.

**Confidence:** HIGH.

---

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

---

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

---

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

**Roadmap implications:**
- v1 targets Noble's libadwaita 1.5. Bookworm support is "best effort" — if the GUI sticks to widgets in 1.2 (CLAUDE.md UI mock only needs `ApplicationWindow`, `HeaderBar`, `PreferencesGroup`, `ActionRow`, `SwitchRow`, `StatusPage`, `Toast` — all 1.0/1.1), Bookworm works.
- `.deb` should declare Build-Depends on the Adwaita 1.x gir package by name, not by version. Runtime feature gating (`if hasattr(Adw, 'AlertDialog')`) is cheap.

---

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

---

## Installation (developer setup, one-time)

```bash
# Runtime + GUI dev
sudo apt update
sudo apt install \
  python3 python3-gi python3-gi-cairo \
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-glib-2.0 \
  policykit-1

# Verify GTK4 + Adwaita reachable from Python
python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); from gi.repository import Gtk, Adw; print(Gtk._version, Adw._version)"

# Packaging toolchain
sudo apt install \
  debhelper-compat dh-python python3-setuptools python3-wheel \
  pybuild-plugin-pyproject \
  dpkg-dev devscripts lintian fakeroot

# Build the .deb (from repo root, with debian/ in place)
dpkg-buildpackage -us -uc -b
sudo apt install ../acercontrol_*.deb
```

---

## Open Questions / Phase-Specific Research Needed

- Exact `apt-cache policy` versions on Noble for `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `debhelper-compat`, `libadwaita-1-0` — resolve in packaging phase on the target machine.
- If tray is in scope: GTK3-helper-process vs raw D-Bus `org.kde.StatusNotifierItem` — small spike phase.
- Debian 12 supported widget surface — only matters if Bookworm becomes a real target.
- `dh_icons` automatic behavior on compat 13 — confirm icon-cache regeneration triggers without an explicit `debian/acercontrol.postinst`.

---

## Sources

- **Context7 `/gnome/pygobject`** — install commands, `gi.require_version` patterns, `GLib.idle_add` cross-thread bridge.
- **Context7 `/gnome/libadwaita`** — `AdwAboutDialog`, `AdwToast` / `AdwToastOverlay`, deprecation of `Adw.AppNotification`.
- **Context7 `/ayatanaindicators/libayatana-appindicator`** — Ayatana AppIndicator builds against GTK3.
- **Context7 `/systemd/systemd`** — `RemainAfterExit` documentation.
- **Context7 `/hyprwm/hyprpolkitagent`** — polkit action-id / D-Bus signature reference.
- **freedesktop polkit specification** — `.policy` DTD, `<allow_active>`, `auth_admin_keep` semantics.
- **GNOME HIG icon guidelines** — hicolor theme, scalable + symbolic directories.
- **Debian Python Policy / debhelper documentation** — `dh-sequence-python3`, `pybuild`, `pybuild-plugin-pyproject`, compat 13 baseline.

> **Unable to verify (denied / unreachable in research session):** `packages.ubuntu.com/noble`, WebSearch, Brave. Ubuntu 24.04 package version strings deliberately omitted. The roadmap step "packaging setup" must run `apt-cache policy` on a Noble target and record results in `debian/control`.
