# AcerControl

## What This Is

A Linux desktop application (GTK4 + libadwaita) that controls Acer Predator/Nitro laptop performance via the `acer_wmi` kernel module. Provides a polished GUI — profile switching, live temperature/fan monitoring, system tray indicator, boot-time persistence — plus a CLI tool sharing the same core logic, distributed as a `.deb` package for Ubuntu/Debian.

## Core Value

**Click a profile button → laptop switches profile → see thermal state in real time.** Everything else (tray, notifications, boot service, packaging) supports this loop. If profile control or live sensors fail, the product has failed.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

**Foundation**
- [ ] Shared core library (`acercontrol/core.py`) that reads/writes `platform_profile`, locates `hwmon` by name, parses temps/fans
- [ ] Profile mapping abstraction (user names eco/quiet/balanced/performance/turbo ↔ kernel values)
- [ ] Feature detection on startup (`acer_wmi` loaded? `predator_v4=1`? `platform_profile` writable? hwmon entries present?) with graceful degradation when features are missing

**CLI tool**
- [ ] `acercontrol status | get | set <profile> | list | temps | install` commands
- [ ] Auto-escalation via `pkexec` (preferred) or `sudo` (fallback) when writing requires root

**GTK4 GUI app**
- [ ] Main window with 5 profile buttons; active profile is visually highlighted; click switches immediately via polkit
- [ ] Live sensor panel refreshing every 2s via background thread + `GLib.idle_add` — CPU package temp, fan 1 RPM, fan 2 RPM, hwmon temps
- [ ] Color-coded thermal bars (green <70 °C, yellow <85 °C, red ≥85 °C)
- [ ] Boot service section: show `acer-performance.service` status, toggle enable/disable, change boot profile
- [ ] Error states via `Adw.StatusPage` (module not loaded, `predator_v4` missing, `platform_profile` missing, service not installed) with fix guidance
- [ ] Adwaita-native look (`Adw.ApplicationWindow`, `Adw.PreferencesGroup`, `Adw.ActionRow`)

**Polish & integration**
- [ ] System tray indicator: shows current profile, right-click quick-switch menu
- [ ] Desktop notifications via `Gio.Notification` on profile change and on critical temperature events (>90 °C)
- [ ] Custom `.svg` app icon visible in launcher, taskbar, About dialog
- [ ] Polkit policy (`org.acercontrol.setprofile`) for clean GNOME auth UX; sudo only as fallback
- [ ] `.desktop` launcher entry installed into the system applications menu

**Persistence & packaging**
- [ ] `systemd` service (`acer-performance.service`) that applies a configured boot profile at startup
- [ ] `modprobe.d` snippet to load `acer_wmi` with `predator_v4=1`
- [ ] Installable `.deb` for Ubuntu 24.04 (`apt install ./acercontrol_*.deb` works cleanly, depends on `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`)
- [ ] `install.sh` fallback for non-Debian or manual installs

### Out of Scope

<!-- Explicit boundaries. Reasoning prevents re-adding later. -->

- **Direct fan RPM control / custom fan curves** — `acer_wmi` does not expose fan PWM writes; faking control with userspace PID loops would be unsafe and contradict the kernel driver's contract.
- **Keyboard RGB / per-key backlight / macro keys** — different subsystem (USB HID + vendor protocols), large independent project; orthogonal to thermal/performance control.
- **GPU overclocking** — NVIDIA-specific, requires separate tooling (`nvidia-smi`, MSI-Afterburner-equivalents); not part of `acer_wmi` scope.
- **Battery charge limits / health features** — even if `acer_wmi` eventually exposes them, they're a separate user concern from performance control; would muddy the scope.
- **Windows / cross-platform support** — Linux-only by design; reading `/sys/firmware/acpi/...` is OS-specific and no abstraction layer is justified.
- **Automated test suite / CI** — bar for v1 is "polished personal tool"; manual UAT on PHN16-72 is acceptable. Re-evaluate if the project goes public.

## Context

- **Primary hardware**: Acer Predator Helios Neo 16 PHN16-72 (i9-14900HX / RTX 4070), Ubuntu 24.04 LTS, kernel 6.14+.
- **Compatible hardware**: All `acer_wmi` laptops where `predator_v4=1` works — PHN16-71/72, PHN18-71, PH315-xx, PH317-xx, Nitro V series. Auto-detect features at runtime; degrade gracefully (hide turbo/LED on classic `acer_wmi`, but classic `acer_wmi` itself is **out of scope** for v1 — only `predator_v4` paths are officially supported).
- **Kernel interface**:
  - `/sys/firmware/acpi/platform_profile` and `/sys/firmware/acpi/platform_profile_choices` for profile control
  - `/sys/class/hwmon/hwmon*/` (find by `name == "acer"` and `name == "coretemp"`) for sensors
  - `/sys/module/acer_wmi/parameters/predator_v4` to verify mode
- **Profile mapping nuance**: kernel uses `performance` to mean turbo on Predator hardware (LED blinks). GUI exposes `eco / quiet / balanced / performance / turbo` where `performance` → kernel `balanced-performance` and `turbo` → kernel `performance`.
- **Privilege model**: profile writes need root; prefer `pkexec` with a polkit policy (GNOME-native auth dialog) and fall back to `sudo` only when polkit is unavailable.
- **Reference UI**: PredatorSense on Windows is the spiritual mental model — instant profile switching with live thermals visible.
- **Why this exists**: there is no first-class Linux GUI for Acer Predator performance control; existing options are CLI-only or rely on vendor-specific Windows software.

## Constraints

- **OS**: Ubuntu 24.04 LTS (and Debian 12+) — primary target. Other distros may work but are not the v1 priority.
- **Language**: Python 3.10+ (matches Ubuntu 24.04 system Python; avoids a runtime install).
- **GUI stack**: GTK4 + `libadwaita` only — no Qt, no Electron. Adwaita is mandated for native GNOME feel.
- **Dependencies**: keep runtime deps to what ships in Ubuntu's repos — `python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`. No pip-only packages for the GUI.
- **Privilege**: never store credentials; always escalate at the moment of action via polkit/sudo.
- **Single-file CLI**: `acercontrol` CLI must remain a zero-dependency single-file script suitable for `cp /usr/local/bin/`. GUI can use the package.
- **Compatibility**: hwmon index numbers change between boots — always locate sensors by `name` file content, never by hardcoded `hwmon7`.
- **Distribution**: `.deb` is the v1 distribution channel; `install.sh` is the fallback only.
- **Quality bar**: polished personal tool — manual UAT on PHN16-72, decent error UX, `.deb` installs cleanly. No automated tests required for v1.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Full rebuild from scratch (CLI + GUI + service + packaging in one repo) | Existing CLI in `CLAUDE.md` is described but not present in the repo; cleaner to build cohesively with shared `core.py` than to retrofit | — Pending |
| GTK4 + Adwaita (not Qt, not Electron) | Native GNOME look, low dependency footprint, ships with Ubuntu, modern toolkit | — Pending |
| `.deb` as primary distribution channel | Targets the actual user environment (Ubuntu 24.04); easier than Flatpak permission model for sysfs access | — Pending |
| Polkit policy as primary auth, `sudo` fallback | GNOME-native auth dialog; `sudo` fallback keeps the tool usable on non-GNOME desktops | — Pending |
| `predator_v4` hardware only for official v1 support | Auto-detect, but don't officially support classic `acer_wmi` (no turbo, no LED) — keeps test surface small | — Pending |
| Linux-only forever | Sysfs paths are OS-specific; abstraction would add complexity without benefit | ✓ Good |
| No automated tests for v1 | Scope is "polished personal tool"; hardware-dependent tests are expensive to maintain; manual UAT is enough at this scale | — Pending |
| User-facing profile names differ from kernel names | `performance` (kernel) = turbo (LED blinks); exposing kernel names would confuse users | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-13 after initialization*
