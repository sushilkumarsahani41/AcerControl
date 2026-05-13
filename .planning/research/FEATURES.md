# Feature Landscape

**Domain:** Linux laptop performance-control GUI for Acer `acer_wmi predator_v4` hardware
**Researched:** 2026-05-13
**Confidence:** HIGH (primary sources: PPD source code, kernel docs, asusctl/LACT/system76-power/tuxedo-control-center READMEs)

---

## TL;DR — How the user's v1 polish list scores

The user's polish list is good but **missing four table-stakes items**:

1. **PPD coexistence detection** — `power-profiles-daemon` writes the *same* sysfs file we do. Not detecting it on startup is a footgun.
2. **Read-back confirmation after write** — set, re-read, compare. Without this, users can't tell when a write silently failed (firmware refused, PPD raced us, polkit cancelled mid-flight).
3. **Handling the `custom` profile value** — the kernel core legitimately returns `"custom"` when multi-driver state diverges (kernel docs, `userspace-api/sysfs-platform_profile`). The UI must not crash or mis-highlight any of the 5 buttons.
4. **Suspend/resume re-apply** — verify whether `acer_wmi predator_v4` persists profile across S3/S2idle. If not, hook `org.freedesktop.login1.Manager.PrepareForSleep` like LACT does.

Everything else on the user's list (5 buttons, live 2s sensors, boot service mgmt, tray, notifications, `.svg` icon, polkit policy, `.desktop`, error states) is table-stakes-correct.

Three features the user wisely **deferred** — confirmed deferrable for v1:

- Temp history graph → v2 (Adwaita has no native chart widget; cairo work)
- AC/battery auto-switch → v2 (PPD already does this for its 3-profile vocabulary)
- Per-app profile rules → v2 (asusctl has it; complex, not table stakes)

A "kill switch revert to balanced on app crash" pattern is **not applicable** here: the kernel's `platform_profile` value is stored in firmware/embedded controller state, not in our process. If our app crashes mid-session the profile stays exactly where the user set it, and the boot service re-asserts the desired profile on next boot. No competitor in this space implements a kill switch for `platform_profile`.

---

## 1. Table Stakes

Everyone shipping in this domain has these. Missing one = users feel the tool is broken.

### TS-1. Profile switching with current-state visualization
**What:** 5 named buttons (eco / quiet / balanced / performance / turbo) with the active profile visually highlighted at all times.
**Why table stakes:** PredatorSense (Win), asusctl GUI, tuxedo-control-center, system76-power gnome-extension — all show "what is active now". A switcher that doesn't show the current state is unusable.
**Sysfs:** reads `/sys/firmware/acpi/platform_profile`, writes via `pkexec` to same path.
**Complexity:** **S**
**Dependencies:** TS-2 (read-back), TS-7 (auth), TS-8 (`custom` handling)
**v1:** YES — already on user's list.

### TS-2. Read-back confirmation after every write
**What:** After writing to `platform_profile`, immediately re-read and compare. If mismatch, mark the click as failed and re-highlight the actually-active profile. Surface a one-line error if mismatch.
**Why table stakes:** Without it, the GUI lies after silent failures — polkit cancel, PPD racing, firmware refusing the value, hwmon-name lookup drift after suspend. tuxedo-control-center, asusctl GUI, LACT all do this implicitly via their daemon model; we do it inline because we have no daemon.
**Sysfs:** `read("/sys/firmware/acpi/platform_profile")` after each write.
**Complexity:** **S**
**Dependencies:** TS-1
**v1:** YES — **missing from user's list, add it.**

### TS-3. Live sensor panel (CPU temp + fan RPMs)
**What:** Background thread reads every 2 s, GTK update via `GLib.idle_add`. Numeric value + horizontal progress bar. Color-coded thresholds (green <70 °C, yellow <85 °C, red ≥85 °C).
**Why table stakes:** Every Predator/ROG/Tuxedo GUI shows live thermals. The product loop ("click profile → see thermals change") doesn't close without this.
**Sysfs:** `/sys/class/hwmon/*/fan1_input`, `fan2_input` (located by `name == "acer"`); `/sys/class/hwmon/*/temp1_input` (located by `name == "coretemp"`). Only present when `acer_wmi predator_v4=1` is loaded.
**Complexity:** **M** (hwmon-by-name lookup + threading + idle_add + bar color logic)
**Dependencies:** None
**v1:** YES — already on user's list.

### TS-4. Set boot/login profile (persistence)
**What:** systemd unit (`acer-performance.service`) writes a configured profile on boot. GUI shows service state (enabled/disabled/failed) and lets user pick which profile applies at boot.
**Why table stakes:** asusctl, tuxedo-control-center, system76-power all persist across reboot. Without it the user sets turbo, reboots, gets balanced, files a bug.
**Sysfs:** Service is a `oneshot` writing to `/sys/firmware/acpi/platform_profile` with `After=multi-user.target`.
**Complexity:** **M** (service template + `pkexec systemctl enable --now` + change-boot-profile dropdown)
**Dependencies:** TS-7 (polkit auth for systemctl)
**v1:** YES — already on user's list.

### TS-5. Graceful degradation when feature is missing
**What:** At startup probe `acer_wmi` loaded? `predator_v4=Y`? `platform_profile` present? hwmon entries discoverable? Each missing feature gets an `Adw.StatusPage` (full-screen) or `Adw.Banner` (inline) with concrete fix command.
**Why table stakes:** asusctl shows "kernel patch required" when missing features. tuxedo-control-center refuses to run without `tuxedo-io`. Without this the GUI crashes or shows zeros and users blame the laptop.
**Sysfs:** existence checks on `/sys/module/acer_wmi`, `/sys/module/acer_wmi/parameters/predator_v4`, `/sys/firmware/acpi/platform_profile`, glob `/sys/class/hwmon/*`.
**Complexity:** **M** (probe logic + 4 error UIs + recovery action buttons)
**Dependencies:** None
**v1:** YES — already on user's list.

### TS-6. Polkit-based privilege escalation (sudo fallback)
**What:** Custom polkit action `org.acercontrol.setprofile` invoked via `pkexec`. Falls back to `sudo` if polkit unavailable. Never stores password.
**Why table stakes:** GNOME-native auth dialog (no shell prompt). asusctl, LACT, tuxedo-control-center all use polkit. `auth_admin_keep` for active session is the standard pattern (5-min cache).
**Sysfs:** authorizes writes to `/sys/firmware/acpi/platform_profile`.
**Complexity:** **S** (policy XML + helper wrapper) — already drafted in CLAUDE.md
**Dependencies:** None
**v1:** YES — already on user's list.

### TS-7. `power-profiles-daemon` (PPD) coexistence detection
**What:** On startup, check via D-Bus whether `org.freedesktop.UPower.PowerProfiles` is owned. If yes, show a one-line informational banner: "GNOME power-profiles-daemon is running. Switching profiles will be reflected in GNOME quick settings." Provide a "details" link explaining that PPD's battery-aware action *may* override your choice on AC/battery transitions, and how to disable that (`powerprofilesctl configure-battery-aware --disable`).
**Why table stakes:** PPD writes the **same** `/sys/firmware/acpi/platform_profile` file we do (verified in `ppd-driver-platform-profile.c`). PPD uses a `GFileMonitor` on that path — every write we make is broadcast to D-Bus, and GNOME's Quick Settings reflects it. **Coexistence is fine** (PPD's `Conflicts=` line in the unit only names `tuned/tlp/auto-cpufreq/system76-power`, not us). The single real hazard is PPD's `upower` battery-aware action re-writing the profile on AC unplug — surfacing this is table stakes.

**Why NOT auto-stop PPD:** LACT precedent — LACT (since 0.7.5 + PPD 0.30) connects via D-Bus and politely asks PPD to disable just the conflicting action (`amdgpu_dpm`). It doesn't kill PPD. Stopping PPD would break GNOME's quick-settings power chooser and Battery indicator behavior. We coexist.

**Sysfs / D-Bus:**
- D-Bus name check: `org.freedesktop.UPower.PowerProfiles`
- D-Bus method `GetAll` on `org.freedesktop.UPower.PowerProfiles` to read `ActiveProfile`, `Profiles`, and battery-aware state (PPD 0.30+).

**Complexity:** **S** (one D-Bus probe + one banner)
**Dependencies:** None
**v1:** YES — **missing from user's list, add it.**

### TS-8. Handle the `custom` profile sysfs value
**What:** `cat /sys/firmware/acpi/platform_profile` can return `custom` (kernel docs, "Multiple driver support" + "'Custom' profile support"). This happens when sub-driver class profiles diverge from the core. The GUI must not crash or arbitrarily highlight one of the 5 buttons. Show "Modified externally / custom" indicator; highlight no button; offer "click any profile to set a known value".
**Why table stakes:** Documented kernel behavior. Easy to trigger in testing. Crash here = release blocker.
**Sysfs:** `/sys/firmware/acpi/platform_profile` returning literal string `custom`.
**Complexity:** **S** (one extra branch in the profile-state model)
**Dependencies:** TS-1
**v1:** YES — **missing from user's list, add it.**

### TS-9. Profile re-apply on suspend/resume
**What:** Verify whether `acer_wmi predator_v4` preserves `platform_profile` across S3/s2idle. If it does NOT, subscribe to `org.freedesktop.login1.Manager.PrepareForSleep(false)` D-Bus signal (resume event) and re-write the user's chosen profile. LACT does exactly this for GPU settings.
**Why table stakes:** Users set turbo, suspend laptop, wake up, find themselves on balanced. Reproducible bug report magnet. Even if `acer_wmi` does persist, the verification needs to be done explicitly during build.
**Sysfs / D-Bus:** D-Bus `org.freedesktop.login1.Manager` `PrepareForSleep` signal, plus same sysfs write path.
**Complexity:** **S** (one D-Bus subscription + reapply call) — assuming hardware doesn't preserve. **None** if hardware does preserve (just an investigation note).
**Dependencies:** TS-1
**v1:** YES (investigation), conditional implementation — **missing from user's list, add it.**

### TS-10. Sensor read failure shows "—" (not crash, not zero)
**What:** If a hwmon read returns `EIO`, `ENOENT`, or the hwmon index rotated between boots and we haven't re-resolved by name, render `—` in that cell. Don't crash. Don't show `0 RPM` (which looks like a stuck fan and panics users).
**Why table stakes:** hwmon index numbering is unstable across boots (kernel docs + CLAUDE.md confirms). Every monitoring GUI handles this gracefully (psensor, GNOME sensors, lm-sensors front-ends).
**Sysfs:** `/sys/class/hwmon/*/name` resolution must happen on every read attempt, not cached forever.
**Complexity:** **S** (try/except around each read + name re-resolution on stale handle)
**Dependencies:** TS-3
**v1:** YES — already implied by user's CLAUDE.md error table.

### TS-11. No persistent root
**What:** The CLI auto-escalates *at the moment of the write* and drops. The GUI uses `pkexec` per action. No setuid binaries. No long-lived root helper daemon for v1.
**Why table stakes:** Modern Linux security baseline. Every reference tool (asusctl uses a polkit-gated D-Bus daemon, tuxedo-control-center uses a polkit-gated `tccd` service; both still authenticate per-action for state-changing calls). For our scope (just 2 sysfs paths) a polkit'd `pkexec` wrapper is enough.
**Sysfs:** N/A — security architecture.
**Complexity:** **S** — design constraint, not an implementation cost.
**Dependencies:** TS-6
**v1:** YES — already implicit in user's polkit choice.

### TS-12. Working without root after install
**What:** Once installed (which requires root for `cp`, `systemctl enable`, `modprobe.d`), the GUI launches and reads sensors without root. Only profile-set and service-enable/disable actions trigger polkit. Sensor reads are world-readable in `/sys`.
**Why table stakes:** No competitor requires "always launch with sudo". A GUI that won't even draw without root would be hostile.
**Sysfs:** All hwmon reads + `platform_profile` reads are world-readable. Only writes need root.
**Complexity:** **S** — confirm read perms in install.sh; nothing to build.
**Dependencies:** None
**v1:** YES — implicit.

---

## 2. Differentiators

Features that distinguish a polished tool from a minimum-viable one. Each tagged for v1 vs v2.

### D-1. System tray indicator with profile in icon
**What:** Persistent tray icon showing current profile (5 SVG variants, one per profile, or a single icon with overlaid emblem). Right-click menu: 5 profile entries (one checked) + "Open AcerControl" + "Quit". Left-click optionally opens main window.
**Why differentiator:** PredatorSense lives in tray. asusctl's `rog-control-center` ships a tray. tuxedo-control-center docks to tray. Users on GNOME (no native tray) need `gnome-shell-extension-appindicator` or use the GNOME 47+ quick-settings tile.
**Caveat for GNOME:** native GNOME has no XEmbed tray. Use `AyatanaAppIndicator3` (via `gir1.2-ayatanaappindicator3-0.1`) which works in KDE, XFCE, Cinnamon, and GNOME-with-extension. Document the extension dependency.
**Sysfs:** None directly; uses TS-1 state.
**Complexity:** **M** (icon variants + AppIndicator wiring + state sync with main window)
**Dependencies:** TS-1
**v1:** YES — on user's list. Recommend documenting the GNOME extension caveat in install.

### D-2. Desktop notifications on profile change + critical temp
**What:** `Gio.Notification` toast on each profile change ("Switched to Turbo — LED will blink"). Critical-temp toast when CPU package crosses 90 °C (rate-limited to one toast per 60 s to prevent spam).
**Why differentiator:** asusctl GUI uses notifications. tuxedo-control-center has a notification daemon. Distinguishes a "polished tool" from a "control panel that does things silently".
**Sysfs:** Reads same temp sensors as TS-3; no new sysfs.
**Complexity:** **S** (3 `Gio.Notification` calls + rate-limit counter)
**Dependencies:** TS-1, TS-3
**v1:** YES — on user's list.

### D-3. PPD-aware D-Bus integration (beyond just detection)
**What:** Beyond TS-7 (banner), publish *our* profile changes to PPD's D-Bus interface OR subscribe to PPD's `ProfileChanged` signal so the main window updates instantly when GNOME's quick-settings tile is used to change profile.
**Why differentiator:** A user switching profile from GNOME's panel should see our GUI update without polling latency. Today TS-1 + TS-2 will pick this up within 2 s (next sensor poll). Subscribing to PPD's `PropertiesChanged` signal makes it instant.
**Sysfs / D-Bus:** Subscribe `org.freedesktop.UPower.PowerProfiles` `PropertiesChanged`.
**Complexity:** **S** (one D-Bus subscription)
**Dependencies:** TS-7
**v1:** **NO — defer to v2.** Polling at 2 s is good enough for v1.

### D-4. Keyboard shortcut for profile cycling
**What:** Global desktop shortcut (or main-window shortcut via `Gtk.Shortcut`) to cycle profile (eco → quiet → balanced → performance → turbo → eco) or jump to a specific profile.
**Why differentiator:** asusctl supports `Fn` key actions through its daemon. Power users want to tap a key, not click a button. Most laptops have a "performance mode" hardware key already wired to the embedded controller — verify if PHN16-72's mode key emits an evdev event we can hook.
**Sysfs:** None new; consumes TS-1.
**Complexity:** **M** (global shortcut registration via GNOME settings vs in-app `Gtk.Shortcut`; cross-desktop story is messy)
**Dependencies:** TS-1
**v1:** **NO — defer to v2.** In-app `Gtk.Shortcut` only (e.g. `1`–`5` keys when window focused) would be S complexity and could squeeze in if scope permits, but is not required.

### D-5. AC/battery-aware auto-switching
**What:** Detect AC unplug via upower / `/sys/class/power_supply/AC*/online` and auto-switch to a user-configured "on battery" profile (typically eco). Vice versa on plug.
**Why differentiator:** asusctl does it via a daemon. auto-cpufreq's whole purpose is this for CPU governor. tuxedo-control-center has full profile-per-power-source config.

**Why DEFER for v1 (advisor-confirmed):**
- **PPD already does this** for its 3-profile vocabulary, and PPD is installed by default on Ubuntu 24.04. If we *also* react to upower events we'll race PPD on the same sysfs file.
- Doing this correctly requires a long-lived background process (daemon or autostart). v1 architecture is "GUI app + boot service", no daemon.
- Boot-profile (TS-4) is the v1 substitute: pick `balanced` as your boot value and accept that battery-mode switching needs a manual click in v1.

**Sysfs / D-Bus:** `/sys/class/power_supply/AC*/online` polling OR upower `org.freedesktop.UPower` `PropertiesChanged` for `OnBattery`.
**Complexity:** **L** (daemon architecture + per-state profile config + PPD coordination)
**Dependencies:** TS-1, TS-7
**v1:** **NO — explicit v2.**

### D-6. Temperature history graph (last N minutes)
**What:** Line chart of CPU package temp + fan RPM over the last 5/15/60 minutes. Optional CSV export.
**Why differentiator:** LACT has "Historical data" charts (CSV export). tuxclocker had graphs in 0.1.x. asusctl GUI shows a sensor history pane.

**Why DEFER for v1 (advisor-confirmed):**
- **No native Adwaita chart widget.** Means either custom Cairo drawing in a `Gtk.DrawingArea` (a few hundred lines) or pulling in a Python chart library (matplotlib is heavy and ships its own backend; `pycairo` direct draw is fastest path but is work).
- Differentiator, not table stakes. v2 candidate.

**Sysfs:** Just keeps a rolling buffer of TS-3's readings.
**Complexity:** **M** (Cairo path) to **L** (with controls + export + zoom)
**Dependencies:** TS-3
**v1:** **NO — explicit v2.**

### D-7. Per-app / per-profile rules ("when game X launches → turbo")
**What:** Background watcher that, when configured executables run, swaps profile and reverts on exit. Mirrors `powerprofilesctl launch <cmd>` semantics or asusctl's process-monitoring.
**Why differentiator:** asusctl has this. LACT has "automatic profile activation based on running processes or gamemode status". PredatorSense has "PredatorSense for games".
**Sysfs:** TS-1 only.
**Complexity:** **L** (process-watch daemon, config UI, race against PPD)
**Dependencies:** TS-1, TS-7, persistent background process
**v1:** **NO — v2 or later.** Falls outside the "polished personal tool" v1 bar.

### D-8. Fan curve VISUALIZATION (read-only)
**What:** Show the current fan curve as a static line graph (RPM vs CPU temp) for the active profile, so users understand *why* the fan is loud right now. Read-only; we don't write fan PWM (out of scope per PROJECT.md).
**Why differentiator:** asusctl/rog-control-center has a fan curve editor for supported laptops. LACT has fan curve editor. A read-only view is a friendly compromise that respects our "no fan PWM" constraint.
**Sysfs:** Would need a built-in table of known Predator curves per profile (no kernel API exposes the EC's fan curve). Or sample (RPM, temp) over time and infer.
**Complexity:** **L** (data needs research + a real graph widget)
**Dependencies:** TS-3
**v1:** **NO — v2 or later.** Likely never, given no kernel API to read the actual curve.

### D-9. Telemetry export to log/CSV
**What:** Optional "Log to file" button that appends `(timestamp, profile, cpu_temp, fan1, fan2)` per sample to `~/.local/share/acercontrol/sensors.csv`. Off by default.
**Why differentiator:** LACT has CSV export. Useful for thermal debugging your laptop on a forum thread.
**Sysfs:** TS-1 + TS-3.
**Complexity:** **S** (toggle in UI + append-only file writer)
**Dependencies:** TS-3
**v1:** **NO — v2.** Nice-to-have, low cost when revisited.

### D-10. CPU/GPU utilization alongside temps
**What:** Show `%` CPU and `%` GPU utilization in the sensor panel.
**Why differentiator:** PredatorSense shows it. tuxedo-control-center "Systemmonitor" tab shows it. Closes the loop "turbo + 90% CPU = expected; turbo + 5% CPU = stuck somewhere".
**Sysfs:** CPU usage from `/proc/stat` deltas. GPU usage from `nvidia-smi --query-gpu=utilization.gpu` or via NVML (`pynvml`). NVML adds a runtime dep.
**Complexity:** **M** (CPU is trivial; GPU adds `nvidia-smi` subprocess every 2 s or NVML binding)
**Dependencies:** TS-3
**v1:** **NO — v2 if value confirmed.** Could be CPU-only in v1 as a cheap add (S).

### D-11. About dialog with hardware diagnostic dump
**What:** Help → About → "Copy diagnostic" button that copies a paste-ready text block of: kernel version, `acer_wmi` parameters, `platform_profile_choices`, hwmon names found, PPD status, service status. Lets users file bug reports with one click.
**Why differentiator:** asusctl has `asusctl --supported-functions`. Distinguishes a polished tool. Trivial to implement once feature-probe (TS-5) is built.
**Complexity:** **S** (reuse TS-5 probe output + clipboard write)
**Dependencies:** TS-5
**v1:** **YES (cheap add).** Worth squeezing in.

---

## 3. Anti-Features

Polished thermal tools deliberately do NOT do these.

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| **Direct fan PWM / RPM writes** | `acer_wmi` does not expose fan PWM. Userspace PID loops fight the EC's own logic and cause thermal-runaway or fan oscillation. Bricking risk on some firmware. | Profile-based control only. Document in README that fan speed is a function of profile + EC, not user input. (PROJECT.md already excludes this — keep it excluded.) |
| **Bypassing polkit / setuid binary** | Persistent root in a GUI is a CVE waiting to happen. No competitor does this (asusctl daemon is polkit-gated, tuxedo's `tccd` is polkit-gated, LACT's daemon checks `wheel`/`sudo` group). | `pkexec` per privileged action. Polkit policy with `auth_admin_keep` for active sessions (5-min cache is the GNOME-standard UX). |
| **Telemetry / analytics by default** | This is a Linux system tool; users will absolutely never accept silent telemetry. Will get banned from distro repos. | No telemetry. If D-9 (CSV export) is added, it's opt-in and writes to a local file only. |
| **Auto-applying turbo without explicit consent** | "Boost-on-launch" or "always-turbo" defaults cause thermal throttling complaints, battery drain on portable use, and shorten EC fan life. PredatorSense's Auto mode is widely criticized for this reason. | Default boot profile = `balanced`. Turbo is always a deliberate user action. |
| **Stopping `power-profiles-daemon` automatically** | PPD owns the GNOME quick-settings power chooser. Killing it breaks the host desktop's power UI. LACT precedent: connect via D-Bus, ask politely, don't kill. | TS-7: detect via D-Bus, show informational banner, leave PPD running. Coexistence works because PPD's `Conflicts=` does not list us. |
| **Fighting the EC on thermal limits** | Some Windows tools "unlock" turbo by writing higher limits. On Linux/`acer_wmi` we don't have that interface, and even if we did, exceeding firmware-set thermal envelope risks hardware damage and voids warranty. | Stay strictly within `platform_profile_choices` returned by the kernel. |
| **Writing PMU undervolt / GPU OC** | Out of scope per PROJECT.md, and confuses scope (LACT covers GPU; this tool covers platform_profile + thermals). | Link to LACT in README's "Related Tools" section. |
| **Custom polkit policy that allows non-admin users to set profile without auth** | `allow_active=yes` would let any logged-in user (including a malicious local process) flip turbo, drain battery, or DoS the cooling system. | `allow_active=auth_admin_keep` is correct (already in CLAUDE.md draft). |
| **Persistent background helper as root daemon** | Adds attack surface for a tool that does at most a few writes per session. asusctl & tuxedo both ship daemons but they have far more interactive features (RGB, fan curves, MUX). We don't need one. | Stateless: GUI launches, talks to `pkexec` per action, exits clean. `systemctl` service is `oneshot` not long-running. |
| **"Kill switch" to revert profile on app crash** | Not applicable: kernel/EC retains `platform_profile` value regardless of our process state. Trying to "revert on crash" requires a daemon we don't have, and has no precedent in this domain. | Trust the EC. The boot service (TS-4) handles the only state the user actually wants persisted. |

---

## 4. Competitor Comparison

What each comparable tool exposes. "✓" = present, "—" = absent, "∼" = partial/conditional.

| Capability | **AcerControl v1** | PredatorSense (Win) | asusctl + rog-control-center | tuxedo-control-center | system76-power | LACT | auto-cpufreq | PPD + GNOME QS |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Named profile switcher | ✓ (5) | ✓ (4) | ✓ (4) | ✓ (custom N) | ✓ (3) | — | — | ✓ (3) |
| Current profile shown | ✓ | ✓ | ✓ | ✓ | ✓ | n/a | n/a | ✓ |
| Boot/login persistence | ✓ | ✓ | ✓ (daemon) | ✓ (daemon) | ✓ (daemon) | n/a | ✓ | ✓ (state.ini) |
| Live CPU temp | ✓ | ✓ | ✓ | ✓ | — | ✓ (GPU only) | ✓ | — |
| Live fan RPM | ✓ | ✓ | ✓ | ✓ | — | ✓ (GPU fan) | — | — |
| GPU temp | ∼ (if hwmon) | ✓ | ∼ | ∼ | — | ✓ | — | — |
| System tray icon | ✓ | ✓ | ✓ | ✓ | ∼ (extension) | ✓ | ∼ | n/a (host) |
| Desktop notifications | ✓ | ✓ | ✓ | ✓ | — | — | — | — |
| Polkit-gated writes | ✓ | n/a | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Fan curve editor (write) | **✗ (anti-feat.)** | ✓ | ✓ (supported HW) | ✓ | — | ✓ (GPU) | — | — |
| AC/battery auto-switch | v2 | ✓ | ✓ | ✓ | ✓ (via gnome ext.) | — | ✓ (its purpose) | ✓ (its purpose) |
| Per-app profile rules | v2+ | ∼ (games tab) | ✓ | — | — | ✓ (process+gamemode) | — | n/a |
| Temp history graph | v2 | ∼ | ✓ | ✓ | — | ✓ + CSV export | ∼ | — |
| Keyboard RGB | **✗ (out of scope)** | ✓ | ✓ | ✓ | — | — | — | — |
| GPU OC / undervolt | **✗ (out of scope)** | ✓ | — | — | ✓ (graphics mode) | ✓ | — | — |
| Battery charge limit | **✗ (out of scope)** | ✓ | ✓ | ✓ | — | — | ✓ | — |
| Suspend/resume re-apply | TS-9 (v1) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Coexists w/ PPD | ✓ (banner) | n/a | ∼ (recommend disable) | ∼ | **conflicts** | ✓ (since 0.7.5) | **conflicts** | n/a |

**Key cross-checks against the user's v1 list:**

- AcerControl is the **only** entry in this table without a fan curve editor — that's intentional (anti-feature) but worth calling out in marketing copy so users don't expect it.
- AcerControl is unique in **explicitly coexisting** with PPD as a banner (LACT does it but only for amdgpu). This is a clean design win.
- AcerControl's 5-profile vocabulary is **richer than PPD's 3** and matches the kernel exposed choices on `predator_v4` hardware. This is the *reason* the tool needs to exist alongside PPD — PPD can't reach `quiet` or `balanced-performance`.

---

## 5. Feature Dependencies

Visual dependency tree for v1:

```
TS-5 (feature probe / error states)
   │
   ├─→ TS-7 (PPD detection banner)
   ├─→ TS-6 (polkit auth)
   │      │
   │      └─→ TS-1 (profile switch buttons)
   │             │
   │             ├─→ TS-2 (read-back confirmation)
   │             ├─→ TS-8 (handle "custom" value)
   │             ├─→ D-2 (notifications on change)
   │             ├─→ D-1 (tray indicator)
   │             ├─→ TS-9 (re-apply on resume)
   │             └─→ TS-4 (boot service mgmt)
   │
   ├─→ TS-3 (live sensors)
   │      │
   │      ├─→ TS-10 (sensor read-failure → "—")
   │      └─→ D-2 (critical-temp notification path)
   │
   └─→ D-11 (about/diagnostic dump)

TS-11 (no persistent root) ← cross-cutting design constraint
TS-12 (works without root) ← cross-cutting design constraint
```

Build order suggestion (independent of phase structure, just dependencies):
1. TS-5 + TS-6 (probe + polkit) — foundation
2. TS-1 + TS-2 + TS-8 + TS-10 (profile state model is correct)
3. TS-3 (live sensors) — orthogonal, can be parallel to step 2
4. TS-4 (boot service) — uses TS-6
5. TS-7 + TS-9 (PPD + resume) — D-Bus subscriptions
6. D-1 + D-2 + D-11 (polish layer)

---

## 6. MVP Recommendation (the answer for v1)

**Must include (table stakes — adjust user's v1 list):**

- All of TS-1 through TS-12 from §1.
- The user already has TS-1, TS-3, TS-4, TS-5, TS-6, TS-10, TS-11, TS-12 on their list.
- **Add to user's v1 list:** TS-2 (read-back), TS-7 (PPD banner), TS-8 (custom handling), TS-9 (suspend/resume re-apply, investigation + conditional impl).

**Include as differentiator polish (already user-committed):**

- D-1 (tray indicator) — caveat the GNOME extension dependency.
- D-2 (notifications) — rate-limit critical-temp toasts.
- D-11 (about + diagnostic copy) — cheap to add; massive support-cost reduction.

**Defer to v2 (advisor-confirmed):**

- D-3 (D-Bus push integration with PPD) — polling at 2 s is fine for v1.
- D-4 (keyboard cycling shortcut) — except in-app `1`–`5` keys (cheap, optional).
- D-5 (AC/battery auto-switching) — races with PPD; requires daemon arch.
- D-6 (temp history graph) — needs Cairo or chart lib work.
- D-7 (per-app profile rules) — daemon needed.
- D-8 (fan curve view) — no kernel API to read the curve.
- D-9 (CSV telemetry export) — opt-in, cheap when revisited.
- D-10 (CPU/GPU utilization) — CPU-only could squeeze into v1 (S complexity); GPU needs NVML dep.

**Never:**

- Everything in §3 Anti-Features. Particularly: don't auto-stop PPD, don't write fan PWM, no telemetry by default, no persistent root, no kill-switch (not applicable).

---

## Sources

All primary sources, verified by direct fetch on 2026-05-13:

- **power-profiles-daemon README** (freedesktop.org/upower) — confirms 3-profile vocabulary, file-monitor on `platform_profile`, `configure-battery-aware` toggle:
  https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/README.md
- **PPD platform_profile driver source** (`ppd-driver-platform-profile.c`) — confirms it writes the same `/sys/firmware/acpi/platform_profile` we do, maps quiet→power-saver, balanced-performance→balanced:
  https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/src/ppd-driver-platform-profile.c
- **PPD systemd unit `Conflicts=`** — confirms PPD does NOT conflict with us (only with tuned/tlp/auto-cpufreq/system76-power):
  https://gitlab.freedesktop.org/upower/power-profiles-daemon/-/raw/main/data/power-profiles-daemon.service.in
- **Linux kernel sysfs-platform_profile docs** — confirms `custom` value semantics, multi-driver behavior:
  https://www.kernel.org/doc/html/latest/userspace-api/sysfs-platform_profile.html
- **asusctl + rog-control-center README** — confirms tray, notifications, fan curves, AC/battery switching, per-app profiles, daemon arch:
  https://raw.githubusercontent.com/flukejones/asusctl/main/README.md
- **system76-power README** — confirms 3-profile, switchable graphics, no live thermals, PPD-conflicting service:
  https://raw.githubusercontent.com/pop-os/system76-power/master/README.md
- **tuxedo-control-center README** — confirms Electron+Angular stack with systemmonitor, custom profiles, fan curves, AC/battery:
  https://raw.githubusercontent.com/AaronErhardt/tuxedo-control-center/master/README.md
- **LACT README** — confirms PPD-coexistence pattern (D-Bus block-action), historical charts + CSV export, polkit, suspend/resume re-apply via login1:
  https://raw.githubusercontent.com/ilya-zlobintsev/LACT/master/README.md
- **auto-cpufreq README** — confirms CPU governor scope (separate from platform_profile), AC/battery-driven, conflicts with PPD:
  https://raw.githubusercontent.com/AdnanHodzic/auto-cpufreq/master/README.md
- **tuxclocker README** — confirms historical graphs deferred between versions; common deferral pattern:
  https://raw.githubusercontent.com/Lurkki14/tuxclocker/master/README.md

Confidence by area:
- PPD coexistence story: **HIGH** (read PPD source directly).
- `custom` profile semantics: **HIGH** (kernel docs).
- Suspend/resume behavior for `acer_wmi predator_v4` specifically: **MEDIUM** — needs an on-device check during implementation; defaulted to "assume it persists, hook login1 if it doesn't".
- Competitor feature parity table: **MEDIUM** — based on each project's README at time of fetch; the matrix is accurate for *advertised* features but specific HW support varies.
- AC/battery PPD-race risk: **HIGH** (PPD source + PPD README's `configure-battery-aware` doc).
