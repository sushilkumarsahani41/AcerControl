# Pitfalls Research — AcerControl

**Domain:** Linux desktop GUI for Acer Predator/Nitro WMI thermal/profile control (Python 3.10+, GTK4 + libadwaita, polkit, systemd, `.deb`)
**Researched:** 2026-05-13
**Overall confidence:** HIGH on verified items (GTK4 threading model, systemd conditions, polkit `pkexec` action-ID matching, hwmon dynamic numbering); MEDIUM on kernel-version specifics and lintian tag names.

**Sources:** GTK4 official threading docs (Context7 `/websites/gtk_gtk4`), libadwaita docs (Context7 `/gnome/libadwaita`), systemd directive list (Context7 `/websites/systemd_io`), `CLAUDE.md`, `.planning/PROJECT.md`.

---

## Pitfalls-at-a-glance

| # | Severity | Pitfall | Detection (warning signs) | Prevention summary | Bucket |
|---|----------|---------|---------------------------|--------------------|--------|
| P1 | CRITICAL | `pkexec bash -c "echo ..."` bypasses the custom `.policy` (action ID mismatch), strips env, shell-injectable | Polkit dialog says "Authentication is needed to run /usr/bin/bash"; shipped `.policy` has no effect | Ship a wrapper `acercontrol-setprofile` in `/usr/libexec/acercontrol/`, register via `org.freedesktop.policykit.exec.path` annotation, invoke `pkexec /usr/libexec/acercontrol/acercontrol-setprofile <profile>` | Foundation + GUI + Polish |
| P2 | CRITICAL | `power-profiles-daemon` (PPD) is active on Ubuntu 24.04 and overwrites `/sys/firmware/acpi/platform_profile` back to its 3-state value within seconds | Profile flips back to `balanced`/`performance` after a write; `systemctl is-active power-profiles-daemon` = active; GNOME power slider visible | Detect PPD; with consent `systemctl mask --now power-profiles-daemon.service`; boot unit declares `Conflicts=power-profiles-daemon.service` | Foundation + Persistence & packaging |
| P3 | CRITICAL | GTK widget writes from the background sensor thread crash or corrupt state | `Gtk-CRITICAL` lines in `journalctl --user`; intermittent crashes; torn values | Worker reads sysfs only; payload is a plain dict; main-thread update via `GLib.idle_add(callback, data)`; callback returns `False` | GUI + Polish |
| P4 | CRITICAL | Profile-name confusion: kernel `performance` = user "turbo" (LED blinks); user "performance" = kernel `balanced-performance` | Active-profile highlight on "performance" while LED is blinking | Single canonical mapping in `core.py` + reverse map `KERNEL_TO_UI`; UI never renders raw sysfs values | Foundation + CLI + GUI |
| P5 | CRITICAL | systemd boot unit fires before `acer_wmi` is loaded or `/sys/firmware/acpi/platform_profile` exists → silent no-op | `journalctl -u acer-performance` shows `inactive (dead)`; cold-boot profile reverts to kernel default | `ConditionKernelModuleLoaded=acer_wmi` + `ConditionPathExists=/sys/firmware/acpi/platform_profile` + `After=systemd-modules-load.service` + `Before=graphical.target` | Persistence & packaging |
| P6 | HIGH | hwmon index drift; multiple devices may share `name == "coretemp"`; sometimes two hwmon entries named `acer` | Sensors disappear or show wrong values after reboot/suspend; "fan = 0 RPM" alongside live "temp = 65 °C" | Resolve by `name` file at startup; require minimum set of files; pick most-populated candidate on tie | Foundation |
| P7 | HIGH | `predator_v4=1` cannot be flipped at runtime; module loads from initramfs | Status page shows `predator_v4: N` even after editing modprobe.d | `update-initramfs -u` after installing modprobe.d snippet; reload button uses `rmmod && modprobe` via wrapper; reboot required to pick up initramfs changes | Foundation + Persistence & packaging |
| P8 | HIGH | `.deb` post-install hooks not run → `.desktop` invisible, icon broken, polkit policy not effective, systemd unit not registered | Launcher icon missing or default cog; auth dialog generic; `systemctl status acer-performance` says "not-found" | `postinst` calls `update-desktop-database`, `gtk-update-icon-cache -f /usr/share/icons/hicolor`, `systemctl daemon-reload`; declare deps `python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, policykit-1, desktop-file-utils, hicolor-icon-theme` | Persistence & packaging |
| P9 | HIGH | Wrong main-window class: `Gtk.ApplicationWindow` (vs `Adw.ApplicationWindow`) breaks Adwaita styling; `Adw.Window` without `Adw.Application` breaks single-instance | Header bar looks off; `Adw.Dialog` parenting fails; double-launch opens two windows | `Adw.Application(application_id="org.acercontrol.AcerControl")` + `Adw.ApplicationWindow` + `Adw.ToolbarView`; `.desktop` filename matches application ID | GUI |
| P10 | HIGH | Critical-temp notification spam: every 2 s while temp >90 °C | Notification stack grows monotonically; users disable the app | Hysteresis (enter at ≥90 °C, leave at <85 °C); stable notification ID so OS replaces; 60s cooldown; suppress when window focused | GUI + Polish |
| P11 | MEDIUM | Vanilla GNOME (Fedora, Arch) has no system tray; Ubuntu only has it via the AppIndicator extension | Tray icon present on dev machine, vanishes on clean install | Detect `org.kde.StatusNotifierWatcher` on the session bus before creating indicator; progressive enhancement; `Recommends:` not `Depends:` | Polish (optional) |
| P12 | MEDIUM | Boot service vs GUI race within 1–2 s of login | "I clicked turbo and it switched to balanced by itself" | Boot unit is `Type=oneshot` + `Before=graphical.target`; GUI calls `systemctl is-active --wait acer-performance.service` before first write | Persistence & packaging + GUI |
| P13 | MEDIUM | Kernel update changes a sysfs path or hwmon `name`; app crashes with traceback | After `apt upgrade`, app fails to launch or shows "no sensors"; Python traceback on screen | `FeatureProbe` dataclass wrapping every sysfs check; `Adw.StatusPage` renders the first failed probe; no `FileNotFoundError` reaches the main loop | Foundation + GUI |
| P14 | MEDIUM | Polkit `auth_admin_keep` cache duration is short/configurable; auth fails entirely under SSH or in sessions with no agent | Sometimes no prompt; sometimes every click; SSH can't change profiles | Don't depend on cache timing; handle exit 126 = "cancelled" idempotently; detect `SSH_CONNECTION` → fall back to `sudo`; one failure = one toast + revert UI | GUI + Polish |
| P15 | MEDIUM | lintian errors block Launchpad PPA upload | `lintian acercontrol_*.deb` exits non-zero; `dput` rejects | Run `lintian --pedantic` early; fix errors (warnings tolerated); pre-empt: missing copyright header, missing `${python3:Depends}`, shipped `.pyc`, `.desktop` missing keys, missing manpage | Persistence & packaging |
| P16 | LOW | Multi-package coretemp on compatible hardware; single Package id 0 logic picks wrong die | Reported CPU temp ~30 °C lower than reality on multi-die systems | Match `Package id 0` from `tempN_label`; render max on multiple packages | Foundation |
| P17 | LOW | `acer_wmi` blacklisted or unloaded mid-session (TLP, thermald conflicts) | `predator_v4` parameter present at start, vanishes mid-session; `dmesg` shows unload | Detect blacklist files at startup (`/etc/modprobe.d/*.conf`); show remediation page; re-probe on sensor read errors | Foundation |

---

## Detailed pitfall notes (CRITICAL and HIGH)

### P1 — `pkexec bash -c "echo X > sysfs"` defeats the custom polkit policy

**What goes wrong.** The example in `CLAUDE.md` recommends:

```python
subprocess.run(["pkexec", "bash", "-c", f"echo {value} > {PROFILE_PATH}"], check=True, timeout=30)
```

Four compounding reasons this is wrong:

1. **Action ID mismatch.** `pkexec <command>` triggers polkit action `org.freedesktop.policykit.exec`, NOT the custom `org.acercontrol.setprofile`. The shipped `.policy` is consulted only when an action matching its `id` is invoked. The custom policy file does nothing.
2. **Environment stripping.** `pkexec` deliberately resets `PATH`, `LANG`, `LC_ALL`, `LD_*`. `echo` is a shell builtin so this works, but any external command would resolve against `pkexec`'s sanitized PATH.
3. **Shell injection.** `value` is interpolated with no quoting. If profile names ever flow from anywhere user-influenced, this is RCE-as-root.
4. **Auth message is wrong.** Users see "run /usr/bin/bash" — alarming for a thermal tool.

**Prevention.** Ship a real binary wrapper:

```sh
# /usr/libexec/acercontrol/acercontrol-setprofile
#!/bin/sh
set -eu
PROFILE="${1:-}"
case "$PROFILE" in
    low-power|quiet|balanced|balanced-performance|performance) ;;
    *) echo "invalid profile: $PROFILE" >&2; exit 64 ;;
esac
printf '%s' "$PROFILE" > /sys/firmware/acpi/platform_profile
```

Register it in `/usr/share/polkit-1/actions/org.acercontrol.policy`:

```xml
<action id="org.acercontrol.setprofile">
  <description>Set Acer performance profile</description>
  <message>Authentication is required to change the Acer performance profile</message>
  <defaults>
    <allow_any>auth_admin</allow_any>
    <allow_inactive>auth_admin</allow_inactive>
    <allow_active>auth_admin_keep</allow_active>
  </defaults>
  <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-setprofile</annotate>
</action>
```

With the `exec.path` annotation, `pkexec` consults the custom action ID and shows the custom auth message.

**Bucket:** Foundation (wrapper + CLI) + GUI (call site) + Polish (auth-UX verification).

---

### P2 — `power-profiles-daemon` overwrites your writes

**What goes wrong.** Ubuntu 24.04 enables `power-profiles-daemon.service` by default. PPD owns `/sys/firmware/acpi/platform_profile`; after you write `performance` (turbo), PPD re-writes its own state within seconds. PPD exposes only 3 profiles via D-Bus — quiet and kernel-`performance` (LED-blinking turbo) are unreachable through it.

**Prevention.** Be opinionated for a personal tool:

1. On startup: `systemctl is-active power-profiles-daemon` (rc=0 → active).
2. First-run dialog: "AcerControl needs to disable power-profiles-daemon to access all 5 Acer profiles. GNOME Settings → Power slider will be removed. Continue?"
3. On consent: `pkexec systemctl mask --now power-profiles-daemon.service`. Masking (not just `disable`) prevents anything from `Requires=`-ing it back up.
4. Boot unit declares `Conflicts=power-profiles-daemon.service` as belt-and-braces.

Cooperative mode (write via PPD's D-Bus API for the 3 profiles it knows, direct-write for quiet/turbo) is technically possible but race-prone. Not worth complexity for v1.

**Bucket:** Foundation (detection) + Persistence & packaging (boot unit `Conflicts=`).

---

### P3 — GTK4 widget access from the sensor thread

**What goes wrong.** GTK4 mandates that widget API calls occur in the main thread. Per `docs.gtk.org/gtk4/section-threading.html`: "Most GTK objects are not threadsafe ... must be used exclusively from the main thread." Calling `label.set_text(...)` from the worker is undefined behaviour — usually a crash within seconds.

**Prevention.**

```python
class SensorMonitor:
    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                data = core.read_sensors()
            except OSError as e:
                data = {"error": str(e)}
            GLib.idle_add(self._deliver, data)

    def _deliver(self, data):
        self.window.refresh_from(data)
        return False
```

Rules: (a) worker thread never imports `gi.repository.Gtk` or `Adw`; (b) payload is a plain dict, never a widget; (c) `_deliver` returns `False`.

**Note:** Stack research recommends `GLib.timeout_add_seconds` on main thread instead of a worker thread — sysfs reads are sub-millisecond. P3 prevention still applies if a thread is used for any future expensive reads (IPMI, EC over LPC).

**Bucket:** GUI.

---

### P4 — Profile-name confusion (kernel "performance" ≠ user "performance")

**What goes wrong.** Kernel uses `performance` to mean turbo on Predator hardware (LED blinks). UX uses "performance" to mean "high performance without LED" (kernel: `balanced-performance`). Any code path rendering raw sysfs values mislabels turbo as performance and vice versa.

**Prevention.** Single source of truth in `core.py`:

```python
PROFILES = {            # user_name -> kernel_value
    "eco":         "low-power",
    "quiet":       "quiet",
    "balanced":    "balanced",
    "performance": "balanced-performance",
    "turbo":       "performance",
}
KERNEL_TO_UI = {v: k for k, v in PROFILES.items()}

def current_profile_ui() -> str | None:
    raw = read_text(PROFILE_PATH)
    return KERNEL_TO_UI.get(raw)
```

UI calls `current_profile_ui()` exclusively. Raw values appear only in `acercontrol get --raw`. At startup assert `PROFILES.values()` is a subset of `read_text(PROFILE_CHOICES_PATH).split()`.

**Bucket:** Foundation (mapping) + CLI + GUI.

---

### P5 — systemd boot unit races sysfs availability

**What goes wrong.** A naive unit fires before `acer_wmi` is loaded or `/sys/firmware/acpi/platform_profile` exists. The unit succeeds (`exit 0`) but the write went nowhere.

**Prevention.** Verified-available systemd directives (Context7 `/websites/systemd_io`):

```ini
[Unit]
Description=Apply Acer performance profile at boot
After=systemd-modules-load.service
ConditionKernelModuleLoaded=acer_wmi
ConditionPathExists=/sys/firmware/acpi/platform_profile
Conflicts=power-profiles-daemon.service
Before=graphical.target

[Service]
Type=oneshot
ExecStart=/usr/libexec/acercontrol/acercontrol-setprofile %i
RemainAfterExit=no

[Install]
WantedBy=graphical.target
```

Use the templated form `acer-performance@<profile>.service` so the boot profile lives in the unit name. `Before=graphical.target` defeats P12.

**Bucket:** Persistence & packaging.

---

### P6 — hwmon index drift and duplicate `name` entries

**What goes wrong.** `/sys/class/hwmon/hwmonN` is allocated in module-load order. Boot variance, suspend/resume, or loading an unrelated module renumbers it. Hardcoding `hwmon7` is a guaranteed regression. Some kernels create two devices named `acer` (WMI device + EC device, only one has fan inputs); `coretemp` produces one hwmon per CPU package.

**Prevention.**

```python
HWMON = "/sys/class/hwmon"

def find_hwmon(target_name, *, requires=()):
    candidates = []
    for entry in os.listdir(HWMON):
        path = os.path.join(HWMON, entry)
        try:
            with open(os.path.join(path, "name")) as f:
                if f.read().strip() != target_name:
                    continue
            if all(os.path.exists(os.path.join(path, r)) for r in requires):
                candidates.append(path)
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda p: -len(os.listdir(p)))
    return candidates[0]

ACER_HWMON     = find_hwmon("acer",     requires=("fan1_input", "temp1_input"))
CORETEMP_HWMON = find_hwmon("coretemp", requires=("temp1_input",))
```

Resolve once at startup; cache the path. On a sensor-read `OSError`, re-resolve once. Never store the integer `N`.

**Bucket:** Foundation.

---

### P7 — `predator_v4` runtime change requires module reload + initramfs

**What goes wrong.** `predator_v4` is a `modprobe`-time parameter. Editing `/etc/modprobe.d/acer-wmi.conf` doesn't change a running module. On Ubuntu, `acer_wmi` is usually loaded from initramfs — even `rmmod`+`modprobe`+reboot won't pick up the new param until `update-initramfs -u` runs.

**Prevention.** Install script already runs `update-initramfs -u` — keep that. For an in-app "reload module" button:

```sh
# /usr/libexec/acercontrol/acercontrol-reload-module
#!/bin/sh
set -eu
modprobe -r acer_wmi || true
modprobe acer_wmi predator_v4=1
```

Gate the button behind an "Advanced" disclosure. Re-probe `/sys/module/acer_wmi/parameters/predator_v4` afterwards.

**Bucket:** Foundation + Persistence & packaging.

---

### P8 — `.deb` post-install hook misses

**Prevention.** `debian/postinst`:

```sh
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    update-desktop-database -q || true
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
    fi
    systemctl daemon-reload || true
fi
#DEBHELPER#
```

`debian/control` `Depends:`:

```
Depends: ${python3:Depends}, ${misc:Depends},
         python3-gi (>= 3.42),
         gir1.2-gtk-4.0,
         gir1.2-adw-1,
         policykit-1,
         desktop-file-utils,
         hicolor-icon-theme
Recommends: gnome-shell-extension-appindicator
```

Don't ship `.pyc` files (lintian flags it — P15).

**Bucket:** Persistence & packaging.

---

### P9 — Adwaita main-window / Application choice

**Prevention.**

```python
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio

APP_ID = "org.acercontrol.AcerControl"

class AcerControlApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(application=self)
        win.present()

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.set_default_size(640, 480)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        toolbar.set_content(self._build_body())
        self.set_content(toolbar)
```

Match `.desktop` basename to application ID: `org.acercontrol.AcerControl.desktop`. Icon path: `/usr/share/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg`.

**Theme breakage under non-GNOME** is by design — libadwaita applies its own stylesheet. Document, don't fight.

**Bucket:** GUI.

---

### P10 — Critical-temp notification spam without hysteresis

**Prevention.**

```python
class CritTempNotifier:
    def __init__(self, app):
        self.app = app
        self.in_critical = False

    def update(self, temp_c):
        if not self.in_critical and temp_c >= 90:
            self.in_critical = True
            self._notify(f"CPU temperature critical: {temp_c:.0f} °C", urgent=True)
        elif self.in_critical and temp_c < 85:
            self.in_critical = False
            self._notify(f"CPU temperature back to normal: {temp_c:.0f} °C")

    def _notify(self, body, *, urgent=False):
        n = Gio.Notification.new("AcerControl")
        n.set_body(body)
        if urgent:
            n.set_priority(Gio.NotificationPriority.URGENT)
        self.app.send_notification("acercontrol-thermal", n)
```

Suppress notifications when the GUI window has focus.

**Bucket:** GUI + Polish.

---

## Medium / lower-severity detail

### P11 — System tray on modern GNOME (detection + degrade)

Detect at startup whether `org.kde.StatusNotifierWatcher` exists on the session bus; if not, skip tray creation, log once, mention in About. `Gtk.StatusIcon` is unavailable in GTK4; use `AyatanaAppIndicator3` (`gi.require_version("AyatanaAppIndicator3", "0.1")`) — `gir1.2-ayatanaappindicator3-0.1` on Ubuntu.

### P12 — Boot service vs GUI race

Fixed primarily by P5 (`Before=graphical.target` + `Type=oneshot`). GUI safety net:

```python
def wait_for_boot_unit():
    res = subprocess.run(
        ["systemctl", "show", "-p", "ActiveState",
         "acer-performance.service"],
        capture_output=True, text=True,
    )
    if "ActiveState=activating" in res.stdout:
        subprocess.run(
            ["systemctl", "is-active", "--wait",
             "acer-performance.service"],
            timeout=5,
        )
```

### P13 — Kernel update breakage / defensive feature detection

```python
@dataclass
class FeatureProbe:
    name: str
    present: bool
    detail: str = ""
    fix: str = ""

def probe_environment():
    return [
        FeatureProbe("acer_wmi loaded",
            os.path.exists("/sys/module/acer_wmi"),
            fix="sudo modprobe acer_wmi predator_v4=1"),
        FeatureProbe("predator_v4 mode",
            _read_or_none(PREDATOR_V4_PARAM) == "Y",
            fix="Add 'options acer_wmi predator_v4=1' to "
                "/etc/modprobe.d/acer-wmi.conf, sudo update-initramfs -u, reboot"),
        FeatureProbe("platform_profile sysfs",
            os.path.exists(PROFILE_PATH) and os.access(PROFILE_PATH, os.R_OK),
            fix="Ensure kernel 6.6+ with ACPI platform_profile support"),
        FeatureProbe("acer hwmon",
            find_hwmon("acer", requires=("fan1_input", "temp1_input")) is not None),
        FeatureProbe("coretemp hwmon",
            find_hwmon("coretemp", requires=("temp1_input",)) is not None),
    ]
```

GUI renders first failed probe; CLI prints as status table.

### P14 — Polkit cache duration, Wayland, SSH

- Don't depend on `auth_admin_keep` cache timing — varies.
- Never spin-retry on `pkexec` failure. Exit 126 = cancelled = revert UI + `Adw.Toast` "Authentication cancelled."
- Detect SSH: `if os.environ.get("SSH_CONNECTION"): ...` → fall back to `sudo`.

### P15 — lintian errors block PPA uploads

Typical offenders: missing/malformed `debian/copyright`, missing `${python3:Depends}`, `.desktop` missing `Type=Application`, polkit `.policy` action ID outside package namespace, missing manpage for binaries in `/usr/bin`, shipped `.pyc`. Run `lintian --pedantic` early.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode `hwmon7` | One less resolution line | First reboot breaks CLI | Never |
| `pkexec bash -c` instead of wrapper | "Works" for first commit | Custom polkit policy never takes effect; injection risk | Never |
| Skip PPD detection | Faster v0.1 | First user filing "profile flips back" within minutes | Internal dev build only |
| Read sensors on main thread with 2s timer | Avoids threading complexity | Sysfs reads occasionally block; UI stutter | Acceptable: sysfs reads <1 ms; revisit on stutter |
| Skip `.policy`, rely on `sudo` only | One less file | UX broken for GNOME users | install.sh fallback path only |
| No hysteresis on critical-temp | One conditional | Users disable the app within a day | Never |

---

## "Looks Done But Isn't" Manual UAT Checklist

Highest-ROI verification items for this stack. Run before declaring a milestone done.

- [ ] **Polkit policy file:** `/usr/share/polkit-1/actions/org.acercontrol.policy` exists, mode `644 root:root`, action ID `org.acercontrol.setprofile` byte-for-byte equal to Python call site.
- [ ] **Polkit auth dialog text:** click a profile button → dialog says "Authentication is required to change the Acer performance profile", NOT "Authentication is needed to run /usr/bin/bash".
- [ ] **Desktop entry visible:** GNOME Activities shows "AcerControl" without logout/login.
- [ ] **Icon resolves:** launcher tile shows the AcerControl SVG, not default cog.
- [ ] **Cold-boot persistence:** full power-off, boot, log in. **Before opening the GUI**, `acercontrol get` must match configured boot profile.
- [ ] **PPD not racing:** `systemctl is-active power-profiles-daemon` returns `inactive` or `masked`. Set turbo; wait 30 s; still turbo.
- [ ] **hwmon resolution survives a renumber:** reboot a few times. Sensor values present and plausible.
- [ ] **Threading safety:** leave GUI open 30 minutes with live panel. `journalctl --user --since "30 min ago" | grep -i gtk` is empty.
- [ ] **Profile name consistency:** click each button; `acercontrol get` returns matching user name. "turbo" → LED blinks. "performance" → LED solid.
- [ ] **Critical-temp hysteresis:** `stress-ng --cpu 0` → exactly one critical notification. Cool down → exactly one "back to normal".
- [ ] **Auth-cancel UX:** Escape on polkit dialog → button reverts highlight, toast shows "Authentication cancelled", no traceback.
- [ ] **SSH fallback:** `ssh laptop acercontrol set turbo` uses `sudo`, not `pkexec`.
- [ ] **lintian clean:** `lintian acercontrol_*.deb` exits 0 errors.
- [ ] **No `.pyc` shipped:** `dpkg -c acercontrol_*.deb | grep '\.pyc$'` is empty.
- [ ] **Module-blacklist detection:** adding `blacklist acer_wmi` produces remediation status page, not traceback.
- [ ] **Multi-launch single-instance:** click launcher twice → one window.

---

## Pitfall → Bucket mapping (for roadmap)

| Pitfall | Bucket | Verification |
|---------|--------|--------------|
| P1 pkexec wrapper | Foundation, GUI, Polish | Auth dialog shows custom message |
| P2 PPD conflict | Foundation, Persistence & packaging | After mask+reboot, sysfs writes stick >60 s |
| P3 GTK threading | GUI | 30-min soak, no `Gtk-CRITICAL` |
| P4 profile mapping | Foundation, CLI, GUI | Each button → CLI `get` returns user name |
| P5 systemd ordering | Persistence & packaging | Cold-boot `acercontrol get` matches configured profile |
| P6 hwmon drift | Foundation | Sensors survive `rmmod`/`modprobe` of unrelated drivers |
| P7 predator_v4 runtime | Foundation, Persistence & packaging | Post-install+reboot, `predator_v4 == Y` |
| P8 `.deb` postinst | Persistence & packaging | Launcher + icon appear without logout |
| P9 main window class | GUI | Double-launch focuses existing window |
| P10 notification spam | GUI, Polish | Stress test → exactly one hot + one normal notification |
| P11 tray detection | Polish | App runs cleanly with extension disabled |
| P12 boot/GUI race | Persistence & packaging, GUI | GUI write within 2 s of login not clobbered |
| P13 kernel-update defence | Foundation, GUI | Renaming `platform_profile` → StatusPage, not traceback |
| P14 polkit edge cases | GUI, Polish | SSH-launched CLI uses `sudo` |
| P15 lintian | Persistence & packaging | `lintian` exits 0 errors |
| P16 multi-package coretemp | Foundation | Not testable on PHN16-72 — flag for compatible-hardware UAT |
| P17 module blacklist | Foundation | Blacklist entry produces remediation page |
