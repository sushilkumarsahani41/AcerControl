# Research Summary — AcerControl

Synthesis of 4 parallel research dimensions: **STACK**, **FEATURES**, **ARCHITECTURE**, **PITFALLS**.
Target: Polished Linux GUI + CLI for Acer Predator/Nitro thermal/profile control on Ubuntu 24.04, distributed as a `.deb`.

---

## TL;DR — Decisions That Matter Most

1. **The CLAUDE.md `pkexec bash -c` example is broken** (P1). Shipped `.policy` would never take effect. Replace with a validator wrapper at `/usr/libexec/acercontrol/acercontrol-setprofile` registered via `org.freedesktop.policykit.exec.path` annotation.
2. **`power-profiles-daemon` will overwrite our writes** (P2) on every Ubuntu 24.04 install. PPD only speaks 3 profiles — that's literally why this tool needs to exist. First-run dialog → `pkexec systemctl mask --now power-profiles-daemon` + boot unit `Conflicts=power-profiles-daemon.service`.
3. **No background thread needed for sensor refresh.** Sysfs reads are sub-millisecond; `GLib.timeout_add_seconds(2, ...)` on the main loop eliminates a whole class of threading bugs (P3).
4. **No GTK4-native AppIndicator binding exists** — tray is GTK3-only via Ayatana. Either ship a separate helper process, speak D-Bus `StatusNotifierItem` directly, or defer tray. **Recommendation: defer tray to a post-foundation polish phase** behind a small spike.
5. **User-facing names ≠ kernel names** (P4). `KERNEL_TO_UI` reverse map in `core.py` is the single source of truth; raw values appear only in `acercontrol get --raw`.
6. **The user's v1 polish list is missing 4 table-stakes items** that must be added: read-back confirmation after every write, PPD detection banner, kernel `custom` profile handling, suspend/resume profile re-apply (logind hook).
7. **Build order is dependency-resolved** (8 phases) — see below. Do not reorder; specifically, packaging cannot be left until last because the boot unit's `Conflicts=` directive is the only reliable defence against PPD.

---

## Stack — Final Choices

| Decision | Choice | Anti-rec |
|---|---|---|
| GUI binding | `python3-gi` + `gir1.2-gtk-4.0` + `gir1.2-adw-1` (Ubuntu 24.04 apt) | pip PyGObject; Qt; Electron |
| Tray | **Defer to post-v1 phase**; if shipped → separate GTK3 helper process with `gir1.2-ayatanaappindicator3-0.1` | `Gtk.StatusIcon` (removed in GTK4); `gir1.2-appindicator3-0.1` (legacy Canonical) |
| Privilege | `pkexec` → `/usr/libexec/acercontrol/acercontrol-setprofile`, polkit `.policy` with `exec.path` annotation, `auth_admin_keep` | `pkexec bash -c '...'`; `sudo NOPASSWD`; long-lived elevated daemon |
| Notifications | `Gio.Notification` (system) + `Adw.Toast` + `Adw.ToastOverlay` (in-app) | `notify2`; `gi.repository.Notify`; deprecated `Adw.AppNotification` |
| Sensor refresh | `GLib.timeout_add_seconds(2, ...)` on main loop | Background thread (premature for sub-ms sysfs reads) |
| Packaging | Hand-written `debian/`, `debhelper-compat (= 13)`, `dh-sequence-python3`, `pybuild-plugin-pyproject` | `stdeb`; `debmake`; Poetry-shipped app |
| systemd unit | `Type=oneshot` + `RemainAfterExit=yes`. Vendor → `/usr/lib/systemd/system/`. Manual → `/etc/systemd/system/` | `Type=simple`; `ExecStart=` raw shell pipeline |
| Project layout | `pyproject.toml` (PEP 621, setuptools backend), `[project.scripts]` entry points | `setup.py` as primary config |
| Icon | `/usr/share/icons/hicolor/scalable/apps/acercontrol.svg` + `…/symbolic/apps/acercontrol-symbolic.svg` | PNG-only; `pixmaps/` |
| CLI | `argparse` (stdlib) | `click`, `typer`, `docopt` |
| systemd from GUI | `subprocess.run(["pkexec", "systemctl", ...])` | `dasbus`, `pydbus` |

**Application ID:** `org.acercontrol.AcerControl`. `.desktop` filename and notifications depend on matching this exactly.

---

## Features — Table Stakes, Differentiators, Anti-features

### Table Stakes (v1 — MUST have)

1. **Profile switching with active-state visualization** — 5 buttons (eco/quiet/balanced/performance/turbo), active highlighted.
2. **Read-back confirmation after every write** — write → read → compare → toast. Detects PPD overwriting.
3. **Live thermal/fan refresh (≤2 s)** — temps, fan RPMs, color-coded bars (green<70°C, yellow<85°C, red≥85°C).
4. **Boot profile persistence** — systemd oneshot that applies a configured profile, settable via GUI.
5. **Feature probe on startup** — detect `acer_wmi`, `predator_v4`, sysfs paths, hwmon entries. Render `Adw.StatusPage` for failures.
6. **Polkit policy with proper action ID** — `org.acercontrol.setprofile` with `exec.path` annotation; clear auth message.
7. **PPD detection banner** — first-run dialog offering to mask `power-profiles-daemon`.
8. **Handle kernel `custom` profile value** — documented in kernel sysfs-platform_profile docs; map to "Custom" in UI.
9. **Suspend/resume re-apply** — hook `org.freedesktop.login1` `PrepareForSleep` (LACT pattern). Test whether `acer_wmi predator_v4` preserves `platform_profile` across S3 on PHN16-72 first.
10. **Working without root after install** — pkexec on action, not on launch.
11. **Stable hwmon resolution** — by `name` file, never index.
12. **Profile name discipline** — UI never renders kernel names.

### Differentiators (v1 — desirable polish)

- **D-1** System tray with current profile shown — *deferred to post-v1 or behind spike (tray complexity)*
- **D-2** Critical-temp notifications with hysteresis
- **D-3** Custom SVG app icon (color + symbolic variants)
- **D-11** About dialog with diagnostics export (sysfs paths, kernel, acer_wmi state, env)

### Differentiators (v2 — explicitly deferred)

- AC/battery-aware auto-switch — races PPD; needs daemon arch
- Temp history graph — no native Adwaita chart widget
- Keyboard-shortcut profile switching
- Per-app profile rules
- PPD D-Bus cooperative mode

### Anti-features (deliberate non-goals)

- Direct fan RPM control / curves — `acer_wmi` doesn't expose it; faking via PID loops is unsafe
- Fan curve editor — same reason
- Keyboard RGB / backlight / macro keys — different subsystem
- GPU overclocking — NVIDIA-specific, separate tooling
- Battery charge limits — separate subsystem
- Windows / cross-platform — sysfs is OS-specific
- Auto-applying turbo without consent — UX anti-pattern
- Persistent root / setuid binaries — polkit only
- Telemetry by default — privacy

---

## Architecture — Source Tree + Privilege Model

### Source tree

```
acercontrol/                     # repo root
  pyproject.toml
  acercontrol/                   # importable package (shared core)
    __init__.py
    core.py                      # sysfs read/write, profile mapping
    sysfs.py                     # path discovery (find_hwmon by name)
    profiles.py                  # PROFILES dict, KERNEL_TO_UI map
    features.py                  # probe() returning FeatureReport
    monitor.py                   # GLib.timeout_add_seconds tick
    privilege.py                 # pkexec invocation, sudo fallback
    cli.py                       # argparse entry point
    gui.py                       # Adw.Application entry point
  tools/
    bundle_cli.py                # concat stdlib-only modules → dist/acercontrol single-file
    verify_no_gtk.py             # CI guard: gi must never appear in CLI inputs
  data/
    org.acercontrol.AcerControl.desktop
    acer-performance@.service    # templated by profile name
    org.acercontrol.policy       # 3 actions, see below
    99-acer-wmi.conf             # modprobe.d snippet (predator_v4=1)
    icons/
      hicolor/scalable/apps/org.acercontrol.AcerControl.svg
      hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg
  helpers/
    acercontrol-setprofile       # validator wrapper, /usr/libexec/acercontrol/
    acercontrol-set-boot-profile
    acercontrol-manage-service
  debian/
    changelog control copyright rules
    acercontrol.install
    acercontrol.postinst
    source/format
  install.sh                     # manual fallback
```

### Installed paths (FHS + Debian policy)

| Source | Installed |
|--------|-----------|
| `acercontrol/` package | `/usr/lib/python3/dist-packages/acercontrol/` |
| `helpers/acercontrol-*` | `/usr/libexec/acercontrol/` (root:root 755) |
| `data/org.acercontrol.policy` | `/usr/share/polkit-1/actions/` |
| `data/acer-performance@.service` | `/usr/lib/systemd/system/` |
| `data/*.desktop` | `/usr/share/applications/` |
| `data/icons/hicolor/...` | `/usr/share/icons/hicolor/...` |
| `data/99-acer-wmi.conf` | `/etc/modprobe.d/` |
| `[project.scripts]` shims | `/usr/bin/acercontrol`, `/usr/bin/acercontrol-gui` |

### Privilege boundary (single rule)

**Every privileged write goes through one of three named helpers**, invoked via `pkexec`:

| Helper | Polkit action | Use |
|---|---|---|
| `acercontrol-setprofile <profile>` | `org.acercontrol.setprofile` | GUI/CLI profile change |
| `acercontrol-set-boot-profile <profile>` | `org.acercontrol.set-boot-profile` | Writes `/etc/default/acercontrol` + runs `systemctl start acer-performance@<profile>` |
| `acercontrol-manage-service <enable\|disable>` | `org.acercontrol.manage-service` | systemctl enable/disable acer-performance.service |

Each `.policy` action sets `<annotate key="org.freedesktop.policykit.exec.path">…</annotate>` pinning to the wrapper path. `auth_admin_keep` chains actions without re-prompting within session.

The same helpers are invoked **without pkexec** by the systemd boot service (already running as root) and by the install.sh path. Single binary, three call modes.

### Config split (by privilege scope)

- `/etc/acercontrol/boot.conf` (or `/etc/default/acercontrol`) — root-readable; set via pkexec helper; read by boot service. Holds `PROFILE=turbo`.
- `~/.config/acercontrol/config.toml` — user prefs (tray on/off, notification thresholds, theme). Boot service can't read this — that's the architectural reason for the split.

### CLI single-file vs GUI package

Resolved via the bundler: `tools/bundle_cli.py` concatenates stdlib-only modules (`core.py`, `sysfs.py`, `profiles.py`, `features.py`, `privilege.py`, `cli.py`) into `dist/acercontrol`. CI guard (`tools/verify_no_gtk.py`) hard-fails if `gi` ever leaks into a CLI-bundled module.

`.deb` ships `console_scripts` entry-point shims (no bundling needed). `install.sh` copies the bundled single-file.

### Failure-mode flow

```
GUI launch
   └── features.probe() returns FeatureReport
            │
            ├── all OK            → main UI (profile buttons + sensor panel + service panel)
            ├── acer_wmi missing  → Adw.StatusPage "modprobe acer_wmi predator_v4=1"
            ├── predator_v4=N     → Adw.StatusPage "edit /etc/modprobe.d/acer-wmi.conf,
            │                                       sudo update-initramfs -u, reboot"
            ├── platform_profile missing → Adw.StatusPage "kernel 6.6+ required"
            ├── hwmon missing     → main UI but sensors disabled with "—" placeholders
            └── PPD active        → main UI + persistent Adw.Banner "AcerControl needs to
                                    disable power-profiles-daemon. [Disable] [Learn more]"
```

---

## 8-Phase Build Order (dependency-resolved)

This is the **recommended phase structure for the roadmap.** Do not reorder.

| # | Phase | Goal | Key deliverables | Pitfalls addressed |
|---|---|---|---|---|
| **1** | **Foundation: core + sysfs + profile mapping** | Shared `core.py` with feature probe, hwmon resolution, profile mapping, sysfs read | `core.py`, `sysfs.py`, `profiles.py`, `features.py`. CLI not yet — just library. | P4 profile names, P6 hwmon drift, P13 defensive probes, P16 multi-package coretemp, P17 blacklist detection |
| **2** | **Privilege boundary: helpers + polkit + CLI** | All privileged writes go through `/usr/libexec/acercontrol/acercontrol-*` helpers. CLI uses them. polkit `.policy` registered. | 3 helper scripts, `.policy` file, `privilege.py`, `cli.py` (full surface: status/get/set/list/temps/install) | P1 pkexec wrapper, P14 polkit edge cases (SSH/cancel) |
| **3** | **GUI shell + failure-mode StatusPages** | Window opens, `features.probe()` dispatches to either StatusPage (failure) or main UI shell (no functionality yet). PPD banner. | `gui.py`, `Adw.Application(application_id="org.acercontrol.AcerControl")`, StatusPage variants, PPD detection banner | P2 PPD detect, P9 window class, P13 probe surfacing |
| **4** | **Profile buttons (closes core value loop)** | 5 buttons. Click → pkexec → write → read-back → toast → highlight active. | Profile button row, `privilege.set_profile()`, read-back verification, profile name mapping | P1 (call site), P4 (call site), P2 (PPD warning if write reverts) |
| **5** | **Live sensor panel + monitor** | `GLib.timeout_add_seconds(2, refresh)` reads sensors, updates color-coded bars. Hysteresis-aware critical-temp notifier. | `monitor.py`, sensor widgets, `CritTempNotifier`, `Gio.Notification`, `Adw.Toast` | P3 threading (avoided by design), P10 notification hysteresis |
| **6** | **Boot service + service panel** | Templated systemd unit `acer-performance@.service` with all conditions. GUI panel shows status, toggle enable/disable, change boot profile. | Unit file, `acercontrol-set-boot-profile` helper, service panel UI, `wait_for_boot_unit()` on GUI startup | P5 systemd ordering, P7 predator_v4 reload, P12 boot/GUI race |
| **7** | **Polish: notifications, suspend/resume, About** | Suspend/resume hook (logind), About dialog with diagnostics export. Optional tray spike. | `org.freedesktop.login1` `PrepareForSleep` hook, About dialog | (suspend/resume re-apply was tagged TS-9 in features) |
| **8** | **Packaging: .deb + manual install path** | `dpkg-buildpackage` produces a clean `lintian`-passing `.deb`. `install.sh` works as fallback. Bundler produces single-file CLI. | `debian/` tree, `postinst`, bundler, install.sh | P8 postinst, P15 lintian |

**Why not later phases first:** Phase 6 (boot unit) is the only reliable defence against PPD overwriting writes. Phase 8 (packaging) consolidates artifacts from all prior phases. Phase 1 owns the profile-name mapping that prevents UI corruption across every later phase.

**Optional tray phase (post-v1):** GTK3-helper-process vs raw D-Bus `org.kde.StatusNotifierItem` — small spike (~1–2 day exploration) before committing.

---

## Top 17 Pitfalls — Severity Summary

| # | Severity | Pitfall | Mitigated by phase |
|---|---|---|---|
| P1 | CRITICAL | `pkexec bash -c` defeats custom polkit policy | Phase 2 |
| P2 | CRITICAL | `power-profiles-daemon` overwrites writes | Phase 3 (detect) + Phase 6 (`Conflicts=`) |
| P3 | CRITICAL | GTK widget access from sensor thread | Phase 5 (avoided by design — main-loop timer) |
| P4 | CRITICAL | Kernel `performance` ≠ user "performance" | Phase 1 |
| P5 | CRITICAL | systemd unit races sysfs availability | Phase 6 |
| P6 | HIGH | hwmon index drift | Phase 1 |
| P7 | HIGH | `predator_v4` runtime change requires initramfs | Phase 1 + Phase 8 (install.sh) |
| P8 | HIGH | `.deb` postinst hooks missing | Phase 8 |
| P9 | HIGH | Wrong Adwaita window/application class | Phase 3 |
| P10 | HIGH | Critical-temp notification spam | Phase 5 |
| P11 | MEDIUM | Vanilla GNOME has no tray | Phase 7 (post-v1) |
| P12 | MEDIUM | Boot service vs GUI race | Phase 6 |
| P13 | MEDIUM | Kernel update breaks sysfs paths | Phase 1 |
| P14 | MEDIUM | Polkit cache + SSH edge cases | Phase 2 |
| P15 | MEDIUM | lintian errors block PPA upload | Phase 8 |
| P16 | LOW | Multi-package coretemp picks wrong die | Phase 1 |
| P17 | LOW | acer_wmi blacklisted | Phase 1 |

---

## Quality Gate per Phase (manual UAT)

From the 16-item checklist in PITFALLS.md; mapped to phases:

| Phase | Must verify |
|---|---|
| 1 | Profile name mapping bidirectional; hwmon resolved by name; feature probe returns plausible report |
| 2 | Polkit dialog says "change the Acer performance profile" (NOT /usr/bin/bash); SSH→sudo fallback works |
| 3 | Double-launch focuses existing window (not two windows); PPD banner appears when PPD active |
| 4 | Click each button → CLI `get` returns matching user name; turbo LED blinks; performance LED solid |
| 5 | 30-min soak → no `Gtk-CRITICAL` lines in journal; stress test → exactly one critical + one normal notification |
| 6 | Cold-boot `acercontrol get` matches configured boot profile; PPD masked; write sticks >60s |
| 7 | Suspend/resume → profile preserved or re-applied; About dialog shows diagnostics |
| 8 | `lintian` exits 0 errors; `apt install ./acercontrol_*.deb` works on clean Noble VM; launcher icon appears without logout |

---

## Open Questions to Resolve During Implementation

1. **Does `acer_wmi predator_v4=1` preserve `platform_profile` across S3/s2idle on PHN16-72?** Test during Phase 7. If yes, the login1 hook is belt-and-braces. If no, it's required.
2. **Does PHN16-72's hardware "performance mode" key emit a usable evdev event?** Defer to v2 (D-4 keyboard shortcut).
3. **Exact Ubuntu 24.04 micro versions** for `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `debhelper-compat` — pin during Phase 8 via `apt-cache policy` on target. NOT pinned in research.
4. **PPD's `configure-battery-aware` behavior on AC/battery transitions** — surface in PPD detection banner. Confidence MEDIUM.
5. **Tray architecture** if scoped in: separate GTK3 helper process vs raw D-Bus `StatusNotifierItem`. Decide via small spike before Phase 7.
6. **Python version floor:** PROJECT.md says 3.10+, but `tomllib` requires 3.11+. Ubuntu 24.04 ships 3.12 so narrowing to 3.11+ is cost-free; alternative is INI/configparser for user config. Decide at Phase 1.
7. **AppArmor default Ubuntu 24.04 profiles** — do they restrict pkexec'd binaries writing `/sys/firmware/`? Spot-check during Phase 2 (`journalctl -k | grep -i apparmor` after a helper write).

---

## Sources

- **STACK.md** — Stack decisions, Ubuntu 24.04 apt package list, polkit XML structure, debhelper compat, systemd unit form, `pyproject.toml` layout.
- **FEATURES.md** — Table stakes (12), differentiators (11), anti-features (10), competitor matrix (LACT, system76-power, tuxedo-control-center, asusctl, PPD GNOME quick settings, PredatorSense), PPD coexistence analysis, dependency tree.
- **ARCHITECTURE.md** — Source tree, installed tree, component boundaries, 6 data-flow diagrams, polkit policy XML with three actions, Debian build/install/postinst sequence, 8-phase build order, 12 failure conditions matrix.
- **PITFALLS.md** — 17 pitfalls with severity, detection, prevention, phase mapping, code snippets, 16-item manual UAT checklist.
