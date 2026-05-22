---
phase: 06-boot-persistence-suspend-resume
status: planned
created: 2026-05-23
requirements: [BOOT-01, BOOT-02, BOOT-03, BOOT-04, BOOT-05]
plans: [06-01, 06-02, 06-03]
---

# Phase 6 Validation Plan

## Source Audit

| Source | ID | Requirement / Finding | Plan | Status | Notes |
|--------|----|-----------------------|------|--------|-------|
| REQ | BOOT-01 | Ship templated systemd unit with required directives | 06-01 | COVERED | 06-01 creates both stable and templated units and gates directives in smoke. |
| REQ | BOOT-02 | Cold boot applies configured boot profile before GUI opens | 06-01 | COVERED | Unit/config substrate implemented in 06-01; PHN16-72 UAT required. |
| REQ | BOOT-03 | GUI service panel shows status, enable/disable, boot profile dropdown | 06-02 | COVERED | 06-02 adds `BootServicePanel` and wrapper-backed mutations. |
| REQ | BOOT-04 | GUI waits for boot unit before first profile write | 06-02 | COVERED | 06-02 adds `ensure_boot_service_ready()` and profile-click guard. |
| REQ | BOOT-05 | Subscribe to login1 PrepareForSleep and reapply on resume if needed | 06-03 | COVERED | 06-03 adds Gio D-Bus controller and MainWindow reapply hook. |
| CONTEXT | Phase 2 wrapper discipline | Privileged operations use wrappers and strict allowlists | 06-01, 06-02 | COVERED | Existing wrappers are extended rather than bypassed. |
| CONTEXT | Phase 5 page ownership | MainWindow owns shared page and order | 06-02 | COVERED | Boot panel appends after SensorPanel. |

## Plan Split

| Plan | Purpose | Why separate |
|------|---------|--------------|
| 06-01 | Systemd substrate and smoke runner | Boot units/wrapper allowlist are independently useful and must be correct before GUI calls them. |
| 06-02 | GUI boot panel and startup wait | User-facing controls depend on substrate and need Phase 4/5 GUI regression gates. |
| 06-03 | Suspend/resume reapply | login1 D-Bus behavior is distinct from boot-service status UI and can be verified separately. |

## Automated Gates

Run after each relevant plan:

- `python3 -m py_compile ...`
- `python3 tools/smoke_phase6.py --quick`
- `python3 tools/smoke_phase6.py`

Final chain:

```bash
python3 tools/smoke_phase1.py && \
python3 tools/smoke_phase2.py && \
python3 tools/smoke_phase3.py && \
python3 tools/smoke_phase4.py && \
python3 tools/smoke_phase5.py && \
python3 tools/smoke_phase6.py
```

## Required Smoke Scenarios

`tools/smoke_phase6.py` must be cross-platform and side-effect free:

- No `gi` import in the smoke runner.
- No real `systemctl start/enable/disable`, no `pkexec`, no `sudo`, no sysfs writes.
- Quick mode passes before new Phase 6 implementation files exist.
- Full mode becomes strict once files exist.

Scenarios:

1. Unit source contract for `data/acer-performance.service`.
2. Unit source contract for `data/acer-performance@.service`.
3. Service wrapper allowlist accepts stable service and allowed template instances while rejecting unrelated services.
4. `acercontrol/systemd.py` is stdlib-only and contains bounded subprocess timeouts.
5. `gui_boot.py` contains `BootServicePanel`, exact copy tokens, user-facing profile order, and no direct `pkexec`/`sudo`/mutating `systemctl`.
6. `gui_window.py` appends `BootServicePanel` after `SensorPanel`.
7. `gui_profiles.py` calls `ensure_boot_service_ready()` before privileged profile writes.
8. `gui_resume.py` subscribes to `PrepareForSleep`, ignores before-sleep, and handles after-resume.
9. `py_compile` covers new/modified Python files.

## Manual PHN16-72 UAT

Required after execution:

1. Install/copy unit files to the expected systemd path, run `systemctl daemon-reload`, enable boot service, set boot profile to `turbo`, power off fully, cold boot, and run `acercontrol get` before opening GUI. Expected: `turbo`.
2. Reboot a second time. Expected: same configured boot profile.
3. Open GUI immediately after login and click a different profile within 2 seconds. Expected: clicked profile remains active after 10 seconds.
4. Toggle boot service enable/disable in the GUI and verify `systemctl is-enabled acer-performance.service` matches the UI.
5. Change boot profile from GUI and verify `/etc/default/acercontrol` stores the kernel value while UI shows the user-facing name.
6. Suspend/resume. If firmware changes the profile, the GUI re-applies the last selected non-custom profile after resume.

## Threat Model

| Threat | Component | Mitigation |
|--------|-----------|------------|
| Arbitrary system service control | `acercontrol-manage-service` | Literal allowlist of stable service and known profile template instances only. |
| Raw kernel values leak to GUI | Boot panel | Map through `Profile`/`PROFILES`; smoke checks normal GUI source. |
| Boot unit runs before sysfs exists | systemd unit | `ConditionKernelModuleLoaded=acer_wmi` and `ConditionPathExists=/sys/firmware/acpi/platform_profile`. |
| PPD clobbers boot profile | systemd unit / existing warning | `Conflicts=power-profiles-daemon.service`; existing PPD banner remains. |
| GUI blocks forever during startup | startup wait | Short subprocess timeout and nonfatal return. |
| Resume subscription unavailable | resume controller | Silent degraded mode; no crash on macOS/non-systemd. |

## Plan Checker Result

Manual checker pass before writing plans:

- Every BOOT requirement maps to at least one plan.
- Plans have strict file ownership and sequential dependencies.
- Each plan has a smoke-runner task or smoke expansion task before implementation tasks.
- Manual UAT remains explicit because cold boot and suspend/resume cannot be proven on this macOS host.
