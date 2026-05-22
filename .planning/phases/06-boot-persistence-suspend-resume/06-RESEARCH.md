---
phase: 06-boot-persistence-suspend-resume
status: complete
created: 2026-05-23
sources:
  - https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html
  - https://www.freedesktop.org/software/systemd/man/latest/systemctl.html
  - https://www.freedesktop.org/software/systemd/man/org.freedesktop.login1.html
---

# Phase 6 Research - Boot Persistence + Suspend/Resume

## Goal

Make the selected Acer performance profile survive cold boot and resume without adding a privileged daemon or new runtime dependencies. Phase 6 must preserve the Phase 4/5 core loop and use the Phase 2 polkit wrapper model.

## Current Code Facts

- `libexec/acercontrol-setprofile` already writes `/sys/firmware/acpi/platform_profile` and validates kernel profile values.
- `libexec/acercontrol-set-boot-profile` already writes `/etc/default/acercontrol` atomically as `BOOT_PROFILE=<kernel-value>`.
- `libexec/acercontrol-manage-service` currently allows only `acer-performance.service`, with a carry-forward note that Phase 6 may need templated instances.
- `acercontrol.privilege.run_privileged()` already resolves wrappers and handles pkexec cancellation.
- `MainWindow` owns the shared `Adw.PreferencesPage`; Phase 5 appended `ProfileControlPanel` then `SensorPanel`.
- No `acercontrol/systemd.py`, no unit files, no boot panel, and no login1 subscription exist yet.

## External Facts Checked

- `systemd.unit` documents `ConditionKernelModuleLoaded=` and `ConditionPathExists=` for gating units on kernel module and sysfs availability.
- `systemctl is-active` returns success when a unit is active and prints the current state unless quiet. `--wait` support is systemctl-version-sensitive, so AcerControl should wrap it with a short subprocess timeout and tolerate nonzero/unsupported results.
- `org.freedesktop.login1.Manager.PrepareForSleep(bool start)` is emitted with `true` before suspend/hibernate and `false` after resume. The `false` signal is the correct trigger for profile reapply.

## Decisions

### 1. Ship stable service plus template

Ship both files in Phase 6:

- `data/acer-performance.service` - stable public unit for enable/disable/status and cold-boot application from `/etc/default/acercontrol`.
- `data/acer-performance@.service` - template used for immediate explicit apply after changing the boot profile.

Rationale:

- Requirements mention a templated unit, but current GUI/CLI copy and wrappers also refer to stable `acer-performance.service`.
- The stable service gives the boot panel one durable status target.
- The template lets the GUI run `acer-performance@<kernel-value>.service` immediately without rewriting the stable unit.

### 2. Store kernel values in config, show user names in UI

`/etc/default/acercontrol` already stores `BOOT_PROFILE=<kernel-value>`. Keep this. The GUI maps kernel values back to user names through `Profile`/`KERNEL_TO_UI` and never shows raw kernel values in normal UI.

### 3. Reuse the existing profile wrapper from systemd units

Both units should call:

```text
/usr/libexec/acercontrol/acercontrol-setprofile <kernel-value>
```

For the stable service, the kernel value comes from `Environment=BOOT_PROFILE=balanced` plus optional `EnvironmentFile=-/etc/default/acercontrol`. For the template, `%i` is the kernel value.

Do not create a root daemon. Do not write sysfs directly from a unit shell snippet.

### 4. Extend, do not loosen, the service wrapper allowlist

`acercontrol-manage-service` should accept:

- `acer-performance.service`
- `acer-performance@low-power.service`
- `acer-performance@quiet.service`
- `acer-performance@balanced.service`
- `acer-performance@balanced-performance.service`
- `acer-performance@performance.service`

It must continue rejecting arbitrary services such as `sshd.service` and arbitrary template instances.

### 5. Add `acercontrol/systemd.py` as a stdlib facade

Centralize systemd/config reads in one non-GUI module:

- `service_status()`
- `service_enabled()`
- `read_boot_profile()`
- `boot_instance_for_profile(profile_name)`
- `wait_for_boot_service(timeout=5)`

This keeps subprocess details out of GTK components and makes source smoke checks easier.

### 6. GUI boot panel uses wrappers for privileged operations

The panel may call `systemctl is-enabled` and `systemctl is-active` through `acercontrol.systemd` for read-only status. It must call privileged mutations through:

- `run_privileged(["acercontrol-set-boot-profile", kernel_value])`
- `run_privileged(["acercontrol-manage-service", "enable", "acer-performance.service"])`
- `run_privileged(["acercontrol-manage-service", "disable", "acer-performance.service"])`
- `run_privileged(["acercontrol-manage-service", "start", f"acer-performance@{kernel_value}.service"])`

No GUI file should contain direct `pkexec`, `sudo`, or raw `systemctl` mutation calls.

### 7. Startup race guard is bounded and best-effort

Implement a helper called by `MainWindow` when blockers pass and before a profile write can happen:

```text
systemctl is-active --wait acer-performance.service
```

Wrap it in `subprocess.run(..., timeout=5)`. If the host's systemctl does not support the combination or the unit is absent, return a structured non-ready result and allow the GUI to continue. This satisfies the race guard without making the app unusable on development hosts.

### 8. Use Gio D-Bus for login1

The GUI already imports `Gio`. Use `Gio.bus_get_sync(Gio.BusType.SYSTEM, None)` and `signal_subscribe()` for `PrepareForSleep` on `/org/freedesktop/login1`. This avoids adding `dasbus`/`pydbus` and keeps the implementation aligned with the no-new-runtime-dependencies constraint.

On signal `start=false`, re-read the actual profile and reapply the last non-custom user-selected profile if it differs.

## Risks

| Risk | Mitigation |
|------|------------|
| Template instance uses raw kernel values internally | Keep raw values out of visible UI; source smoke checks normal GUI strings. |
| `systemctl --wait` support varies | Bound with timeout and treat failure as nonfatal on unsupported hosts. |
| Resume signal unavailable outside Linux/systemd | Controller degrades silently; smoke checks source shape only on macOS. |
| Polkit prompt after resume could be annoying | Phase 6 preserves current security model; no-prompt policy is tracked separately in PROJECT.md as future/decimal work. |
| Stable service and template could drift | Smoke runner checks both unit files share critical unit directives and both call the setprofile wrapper. |

## Recommended Plan Shape

1. **06-01 systemd substrate** - smoke runner, unit files, `systemd.py`, manage-service allowlist.
2. **06-02 GUI boot panel + startup wait** - boot panel, MainWindow integration, profile write wait guard.
3. **06-03 resume reapply** - login1 subscription and after-resume profile reapply.

## Verification Strategy

Automated on this host:

- Source/static smoke for unit directives, wrapper allowlists, no GUI direct systemctl mutation, and login1 subscription tokens.
- `py_compile` for new Python modules.
- Existing Phase 1-5 smoke suites remain green.

Manual PHN16-72 UAT:

- Enable boot service, set boot profile, cold boot twice, verify `acercontrol get` before GUI launch.
- Launch GUI immediately after login and click profile quickly; verify boot unit does not overwrite it.
- Suspend/resume and verify last selected profile is restored if firmware changes it.
