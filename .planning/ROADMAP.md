# Roadmap: AcerControl

## Overview

AcerControl ships in eight dependency-resolved phases. Phases 1–2 build the privileged-write substrate end-to-end against the CLI alone, so the security model is provable before any GUI exists. Phase 3 stands up the Adwaita shell with failure-mode StatusPages and PPD detection *before* any happy-path UI is wired — failures are first-class. Phase 4 closes the core value loop (click profile → laptop switches → read-back confirms). Phase 5 adds live sensors and hysteresis-aware critical-temp notifications. Phase 6 makes the choice survive a cold boot via a templated systemd unit with `Conflicts=power-profiles-daemon` and a logind suspend/resume hook. Phase 7 adds the GTK3 tray helper as a Recommends-only side process. Phase 8 ships everything as a lintian-clean `.deb` (plus `install.sh` fallback) on Ubuntu 24.04. The research SUMMARY.md 8-phase build order is adopted verbatim — no deviation; each phase's success criteria are pulled from the PITFALLS.md verification column.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Shared `acercontrol/` package with sysfs reader, hwmon resolver, profile mapping, feature probe
- [ ] **Phase 2: Privilege Boundary + CLI** - Three pkexec helpers, polkit policy with `exec.path` annotation, full-surface CLI
- [ ] **Phase 3: GUI Shell + Failure States + PPD Banner** - Adw.Application + StatusPage routing + persistent PPD banner
- [ ] **Phase 4: Profile Control (core value loop)** - 5 profile buttons with read-back verification and revert-on-mismatch
- [ ] **Phase 5: Live Sensors + Notifications** - `GLib.timeout_add_seconds(2, …)` sensor refresh + hysteresis critical-temp notifier
- [ ] **Phase 6: Boot Persistence + Suspend/Resume** - Templated `acer-performance@.service` + service panel + login1 hook
- [ ] **Phase 7: Tray Helper + Hardware Compatibility** - Separate GTK3 `acercontrol-tray` process + degrade gracefully on non-PHN16-72
- [ ] **Phase 8: Packaging** - Hand-written `debian/` → lintian-clean `.deb` + `install.sh` fallback + bundled single-file CLI

## Phase Details

### Phase 1: Foundation
**Goal**: Stand up the `acercontrol/` Python package as the single source of truth for sysfs reads, hwmon discovery, profile name mapping, and feature detection. No privileged writes, no GUI, no CLI surface yet — pure library + structured `FeatureReport`.
**Depends on**: Nothing (first phase)
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06
**Success Criteria** (what must be TRUE):
  1. Profile name mapping is bidirectional and exhaustive — for every entry in PROFILES the round-trip `user → kernel → user` returns the original; `KERNEL_TO_UI.get("custom")` resolves to a documented "Custom" sentinel rather than raising.
  2. `sysfs.find_hwmon("acer", requires=("fan1_input", "temp1_input"))` returns a valid path regardless of `hwmonN` index drift across reboots; on a multi-`acer` tie the most-populated entry is chosen; `coretemp` resolution matches `Package id 0` and reports the max across packages on multi-die hardware.
  3. `features.probe()` returns a `FeatureReport` covering `acer_wmi` loaded, `predator_v4=Y`, `platform_profile` present, acer hwmon, coretemp hwmon, PPD active state, and `acer_wmi` blacklist detection in `/etc/modprobe.d/*.conf` — and no sysfs path raises `FileNotFoundError` past this layer.
  4. Renaming `/sys/firmware/acpi/platform_profile` while the library is loaded produces a degraded `FeatureReport` with a remediation hint, never an uncaught traceback.
**Pitfall mitigations**: P4 (profile names), P6 (hwmon drift), P13 (defensive probes), P16 (multi-package coretemp), P17 (blacklist detection).
**Plans:** 1 plan

Plans:
- [ ] 01-01-PLAN.md — Foundation library: profiles + sysfs + features + core + smoke runner (covers CORE-01..06)

### Phase 2: Privilege Boundary + CLI
**Goal**: Establish the privilege boundary end-to-end with the CLI as the first consumer. Every privileged write goes through one of three real-binary wrappers at `/usr/libexec/acercontrol/`, each pinned to its polkit action via `org.freedesktop.policykit.exec.path`. CLI ships full status/get/set/list/temps/install surface, bundled as a single zero-dependency file by `tools/bundle_cli.py`.
**Depends on**: Phase 1
**Requirements**: PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07
**Success Criteria** (what must be TRUE):
  1. The polkit auth dialog triggered by `acercontrol set turbo` reads "Authentication is required to change the Acer performance profile" — not "Authentication is needed to run /usr/bin/bash" — confirming the `.policy` action ID matches the call site and `exec.path` resolves the wrapper binary.
  2. `acercontrol set <profile>` validates input against the user-name mapping, escalates via `pkexec` (or `sudo` when `$SSH_CONNECTION` is set), writes through the wrapper, reads back, and exits non-zero on mismatch; `acercontrol get` prints user-facing names while `acercontrol get --raw` prints the kernel value.
  3. Pressing Escape on the polkit dialog yields exit code 126 handled idempotently — the CLI prints "Authentication cancelled" and exits cleanly with no traceback; a second invocation within polkit's keep-alive window does not re-prompt (verifies `auth_admin_keep`).
  4. `tools/verify_no_gtk.py` exits zero against `dist/acercontrol` and the bundled single-file CLI imports only stdlib modules — a deliberately injected `import gi` in any bundled source fails the bundler.
**Pitfall mitigations**: P1 (real-binary wrapper + `exec.path`), P14 (SSH detection, cancel handling, no spin-retry).
**Plans**: TBD

### Phase 3: GUI Shell + Failure States + PPD Banner
**Goal**: Stand up the `Adw.Application` shell wired to single-instance, register the application ID, and make `features.probe()` the first thing that runs on `do_activate`. Each failed probe routes to a dedicated `Adw.StatusPage` with copy-able fix-it text and (where possible) one-click remediation. PPD active surfaces as a persistent `Adw.Banner` with `[Disable PPD]` / `[Learn more]`. No profile buttons, no sensors yet.
**Depends on**: Phase 2
**Requirements**: GUI-01, GUI-02, GUI-03, GUI-04, GUI-08
**Success Criteria** (what must be TRUE):
  1. Launching `acercontrol-gui` while a window is already open focuses the existing window instead of opening a duplicate (single-instance via `Adw.Application(application_id="org.acercontrol.AcerControl")`).
  2. With `acer_wmi` unloaded the GUI renders a full-window `Adw.StatusPage` titled "acer_wmi module not loaded" with a "Load module" button that invokes `pkexec` against the reload helper; with `predator_v4=N` the equivalent StatusPage offers "Reload with predator_v4=1"; with `platform_profile` missing the StatusPage explains the kernel-version requirement read-only.
  3. With `systemctl is-active power-profiles-daemon` returning active, the main view shows a persistent `Adw.Banner` "power-profiles-daemon is running and will overwrite profile changes" with `[Disable PPD]` invoking `pkexec systemctl mask --now power-profiles-daemon.service` and `[Learn more]` opening explanatory content.
  4. Grepping the GUI source for raw kernel values (`"low-power"`, `"balanced-performance"`, `"performance"`) outside the `profiles.py` mapping and About → Diagnostics returns no matches — raw values never leak into user-facing labels.
**Pitfall mitigations**: P2 (PPD detection + remediation), P9 (correct Adwaita window/application classes + `.desktop` basename match), P13 (probe-first surfacing).
**Plans**: TBD
**UI hint**: yes

### Phase 4: Profile Control (core value loop)
**Goal**: Close the core value loop. Render five profile buttons (eco/quiet/balanced/performance/turbo), highlight the active one, and on click: show "Awaiting authorisation…" → invoke the pkexec helper → read back → on match show `Adw.Toast` "Switched to <profile>" and update highlight → on mismatch show "Profile not applied — power-profiles-daemon may be overriding writes", revert highlight, and re-surface the PPD banner.
**Depends on**: Phase 3
**Requirements**: GUI-05, GUI-06, GUI-07
**Success Criteria** (what must be TRUE):
  1. Clicking each of the 5 profile buttons in turn, then running `acercontrol get` from a separate terminal, returns the matching user-facing name; clicking "turbo" makes the chassis LED blink and clicking "performance" leaves it solid.
  2. With PPD intentionally re-enabled the GUI write succeeds, the 250ms read-back returns the PPD-overwritten value, the warning toast appears, the highlight reverts to the previously-active button, and the PPD banner re-surfaces if it had been dismissed.
  3. Pressing Escape on the polkit auth dialog leaves the highlight on the previously-active button (no flicker to the requested button and back), shows an "Authorization cancelled" toast for 3 seconds, and produces no entries in `journalctl --user` for the application.
**Pitfall mitigations**: P1 (helper call site), P2 (read-back detects PPD reverts), P4 (UI uses `current_profile_ui()` exclusively).
**Plans**: TBD
**UI hint**: yes

### Phase 5: Live Sensors + Notifications
**Goal**: Add the live thermal/fan panel. Per research SUMMARY.md decision #3, use `GLib.timeout_add_seconds(2, refresh)` on the main loop — sysfs reads are sub-millisecond and this design avoids an entire class of threading bugs (P3). Render color-coded thermal bars (green <70 °C, yellow 70–84 °C, red ≥85 °C) and fan RPM bars. Wire profile-change notifications (in-app `Adw.Toast` when focused, `Gio.Notification` when unfocused) and a hysteresis-aware critical-temp notifier (enter at ≥90 °C, leave at <85 °C, stable notification ID, suppressed while focused).
**Depends on**: Phase 4
**Requirements**: SENS-01, SENS-02, SENS-03, SENS-04, NOTI-01, NOTI-02
**Success Criteria** (what must be TRUE):
  1. Leaving the GUI open for ≥30 minutes with the live panel active produces zero `Gtk-CRITICAL` or `Gtk-WARNING` lines in `journalctl --user --since "30 min ago"` and the temperature bars update at ≥0.4 Hz without visible flicker.
  2. Temporarily renaming an `acer` hwmon `temp2_input` file mid-session causes only that one bar to render `—` while every other reading continues to refresh; restoring the file restores the value within one tick because the resolver re-runs once on `OSError`.
  3. `stress-ng --cpu 0 --timeout 90s` while the GUI is unfocused produces exactly one `Gio.Notification` "CPU temperature critical" at the >90 °C crossing and exactly one "back to normal" notification at the <85 °C crossing — never any in between; the same stress run with the GUI focused produces zero `Gio.Notification` instances (toasts only).
  4. Changing a profile from a focused window produces an `Adw.Toast` and no system notification; changing it via the CLI while the GUI is unfocused produces a single `Gio.Notification` whose stable ID replaces (not stacks) any previous profile-change notification.
**Pitfall mitigations**: P3 (avoided by design — main-loop timer, no thread), P10 (hysteresis + stable ID + focus suppression).
**Plans**: TBD
**UI hint**: yes

### Phase 6: Boot Persistence + Suspend/Resume
**Goal**: Make the user's choice survive a cold boot. Ship a templated `acer-performance@.service` (`Type=oneshot`, `ConditionKernelModuleLoaded=acer_wmi`, `ConditionPathExists=/sys/firmware/acpi/platform_profile`, `After=systemd-modules-load.service`, `Conflicts=power-profiles-daemon.service`, `Before=graphical.target`). Add a service panel that shows status, toggles enable/disable, and changes the boot profile via `/etc/default/acercontrol` + `systemctl start acer-performance@<profile>`. Subscribe to `org.freedesktop.login1` `PrepareForSleep` and re-apply on resume if the kernel reports a different value than the user's selection. Eliminate the GUI/boot race with `systemctl is-active --wait` (bounded timeout) before the first profile write.
**Depends on**: Phase 5
**Requirements**: BOOT-01, BOOT-02, BOOT-03, BOOT-04, BOOT-05
**Success Criteria** (what must be TRUE):
  1. After a full power-off cold boot and graphical login, `acercontrol get` (run from a terminal **before** opening the GUI) returns exactly the configured boot profile, and `journalctl -u acer-performance.service -b` shows the unit reached `active (exited)` before `graphical.target`.
  2. Selecting "turbo" in the boot-profile dropdown, entering the polkit credential once, then rebooting twice in succession — `acercontrol get` returns "turbo" both times — with PPD masked (`systemctl is-active power-profiles-daemon` = `inactive` or `masked`) and the kernel module reload requirement satisfied (predator_v4 = Y).
  3. Suspending the laptop (closing the lid or `systemctl suspend`) and resuming, then running `acercontrol get` within 5 s of unlock, returns the user's last-selected profile — either preserved by the firmware across S3 or re-applied by the `PrepareForSleep(false)` handler.
  4. Launching the GUI within 2 s of `graphical.target` and immediately clicking a profile button results in the click succeeding and the boot unit *not* clobbering the user's choice afterwards (verified by reading sysfs 10 s later) — confirms `systemctl is-active --wait` gates the first write.
**Pitfall mitigations**: P5 (kernel module + sysfs conditions + ordering), P7 (predator_v4 reload helper + initramfs guidance), P12 (boot/GUI race guard).
**Plans**: TBD
**UI hint**: yes

### Phase 7: Tray Helper + Hardware Compatibility
**Goal**: Ship `acercontrol-tray` as a separate GTK3 + `gir1.2-ayatanaappindicator3-0.1` long-lived helper process — there is no GTK4-native AppIndicator binding, so the tray is intentionally isolated to avoid pinning the main GUI's toolkit. The helper talks to the main GUI/CLI over D-Bus and exits cleanly when `org.kde.StatusNotifierWatcher` is absent on the session bus. AppIndicator is declared as `Recommends:` (not `Depends:`) so minimal/non-GNOME installs aren't forced into it. Verify hardware compatibility paths: PHN16-72 (primary UAT) and graceful degradation on other `predator_v4` laptops where individual sysfs paths may be missing.
**Depends on**: Phase 6
**Requirements**: TRAY-01, TRAY-02, TRAY-03, TRAY-04, HW-01, HW-02
**Success Criteria** (what must be TRUE):
  1. On a stock Ubuntu 24.04 GNOME session with the AppIndicator extension installed, `acercontrol-tray` runs as a separate process, displays an icon that reflects the current profile, exposes a right-click quick-switch menu for all five user-facing profiles, and offers a "Show AcerControl" action that raises (or launches) the main window.
  2. Disabling the AppIndicator extension and restarting the session — `acercontrol-tray` queries `org.kde.StatusNotifierWatcher`, finds it absent, exits with code 0 within 5 seconds, and the main GUI About dialog mentions tray unavailability without throwing.
  3. On the user's PHN16-72 (Ubuntu 24.04, kernel 6.14+) the full happy-path UAT checklist from PITFALLS.md passes — every profile button works, sensors update, boot service persists, suspend/resume preserves profile.
  4. On a compatible laptop where the `acer` hwmon exposes only `fan1_input` (no `fan2_input`) and only two `temp*_input` files, the GUI renders with the missing controls/bars replaced by `—` placeholders, no traceback is logged, and disabled controls are visually distinguished from active ones.
**Pitfall mitigations**: P11 (StatusNotifierWatcher detection + Recommends-only dependency).
**Plans**: TBD
**UI hint**: yes

### Phase 8: Packaging
**Goal**: Produce a clean Debian package distributable as `apt install ./acercontrol_*.deb` on Ubuntu 24.04, and a parallel `install.sh` for non-Debian / manual flows. Hand-write `debian/` using `debhelper-compat (= 13)`, `dh-sequence-python3`, and `pybuild-plugin-pyproject`. Ship the modprobe.d snippet, the templated systemd unit, the polkit policy, the templated `.desktop` (basename matching application ID), and color+symbolic icons. Run `lintian` early; resolve all errors. Confirm no `.pyc` files are shipped.
**Depends on**: Phase 7
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05, PKG-06, PKG-07, PKG-08, PKG-09, PKG-10, PKG-11
**Success Criteria** (what must be TRUE):
  1. On a clean Ubuntu 24.04 VM, `dpkg-buildpackage -us -uc -b` produces `acercontrol_*.deb`, `apt install ./acercontrol_*.deb` resolves all declared dependencies without error, and the "AcerControl" launcher tile appears in GNOME Activities without logging out and back in.
  2. `lintian acercontrol_*.deb` exits with zero errors (warnings reviewed and acceptable); `dpkg -c acercontrol_*.deb | grep '\.pyc$'` produces no output; the polkit `.policy` is found at `/usr/share/polkit-1/actions/org.acercontrol.policy` with mode 0644 root:root.
  3. After install, `/etc/modprobe.d/99-acer-wmi.conf` contains `options acer_wmi predator_v4=1` and the postinst output (or README) makes clear that `update-initramfs -u` followed by a reboot is required for the parameter to take effect; `update-desktop-database` and `gtk-update-icon-cache -f /usr/share/icons/hicolor` have run on `configure`.
  4. Running `install.sh` on a non-Debian system (or a Debian system without the `.deb`) copies binaries to `/usr/local/bin/`, writes the modprobe.d snippet, registers the systemd unit, runs `update-initramfs -u`, and `acercontrol status` succeeds after reboot with `predator_v4: Y`.
**Pitfall mitigations**: P8 (postinst hooks for desktop/icon/systemd refresh + correct Depends), P15 (lintian-clean from the start), P7 (initramfs guidance in install.sh + postinst).
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/1   | Not started | - |
| 2. Privilege Boundary + CLI | 0/TBD | Not started | - |
| 3. GUI Shell + Failure States + PPD Banner | 0/TBD | Not started | - |
| 4. Profile Control (core value loop) | 0/TBD | Not started | - |
| 5. Live Sensors + Notifications | 0/TBD | Not started | - |
| 6. Boot Persistence + Suspend/Resume | 0/TBD | Not started | - |
| 7. Tray Helper + Hardware Compatibility | 0/TBD | Not started | - |
| 8. Packaging | 0/TBD | Not started | - |

## Coverage Summary

**Total v1 requirements: 54** (the REQUIREMENTS.md "52 total" footer was a miscount; reconciled in this revision — REQUIREMENTS.md now states 54 explicitly with category breakdown).

| Category | REQ count | Phase mapping |
|----------|-----------|---------------|
| CORE-01..06 | 6 | Phase 1 |
| PRIV-01..05 | 5 | Phase 2 |
| CLI-01..07 | 7 | Phase 2 |
| GUI-01..04, GUI-08 | 5 | Phase 3 |
| GUI-05..07 | 3 | Phase 4 |
| SENS-01..04, NOTI-01..02 | 6 | Phase 5 |
| BOOT-01..05 | 5 | Phase 6 |
| TRAY-01..04, HW-01..02 | 6 | Phase 7 |
| PKG-01..11 | 11 | Phase 8 |
| **Total mapped** | **54** | **8 phases** |

Coverage: 54/54 v1 requirements mapped to exactly one phase. Zero orphans, zero duplicates.

## Deferred / Out of Scope (reference)

v2 requirements (SENS2-*, PROF2-*, PKG2-*, HW2-*) are tracked in REQUIREMENTS.md but excluded from this roadmap. Anti-features (fan PWM, RGB, GPU overclock, battery limits, Windows support, automated CI) remain in PROJECT.md Out of Scope.
