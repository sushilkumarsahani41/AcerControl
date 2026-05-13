---
phase: 1
slug: foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Note:** REQUIREMENTS.md `Out of Scope` excludes an automated pytest suite for v1 (quality bar: polished personal tool, manual UAT). This validation plan uses **smoke commands** — stdlib-only `python3 -c` invocations that execute the library and assert observable behavior. They are scriptable, deterministic, and require no test framework. Each plan task embeds its smoke command in `<acceptance_criteria>`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none (smoke commands via `python3 -c` — no pytest in v1 per REQUIREMENTS.md) |
| **Config file** | n/a |
| **Quick run command** | `python3 tools/smoke_phase1.py` (single script that runs every smoke command and exits 0/1) |
| **Full suite command** | same — Phase 1 has only smoke commands |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run that task's `<automated>` smoke command
- **After every plan wave:** Run `python3 tools/smoke_phase1.py` (aggregate runner)
- **Before `/gsd-verify-work`:** Aggregate runner must exit 0; manual UAT on PHN16-72 hardware separately
- **Max feedback latency:** ~2 seconds (sysfs reads are sub-millisecond)

---

## Per-Task Verification Map

Tasks will be filled in by the planner; this is the requirement → smoke-command contract that each task must inherit. The planner MUST embed the listed command into `<acceptance_criteria>` for the task that fulfills each requirement.

| Requirement | Behavior | Smoke command | Pitfall ref |
|---|---|---|---|
| CORE-01 | Profile mapping is bidirectional and exhaustive; `Profile.CUSTOM` is a real sentinel | `python3 -c "from acercontrol.profiles import Profile, PROFILES, KERNEL_TO_UI; assert all(KERNEL_TO_UI[v.value] is v for v in Profile if v is not Profile.CUSTOM); assert Profile.from_kernel('custom') is Profile.CUSTOM; assert Profile.from_kernel('garbage') is Profile.CUSTOM; print('CORE-01 OK')"` | P4 |
| CORE-02 | `find_hwmon` resolves by `name` file; survives index drift; on ties picks most-populated | `python3 -c "from acercontrol.sysfs import find_hwmon; p = find_hwmon('coretemp', requires=('temp1_input',)); assert p is None or p.startswith('/sys/class/hwmon/hwmon'); print('CORE-02 OK', p)"` (runs against host kernel; passes when `coretemp` is loaded, returns None and prints OK otherwise) | P6, P16 |
| CORE-03 | `features.probe()` returns a structured `FeatureReport`; no FileNotFoundError escapes | `python3 -c "from acercontrol.features import probe; r = probe(); assert hasattr(r, 'checks') and len(r.checks) >= 6; print('CORE-03 OK', len(r.checks), 'checks')"` | P13 |
| CORE-04 | Unknown / kernel `custom` profile maps to `Profile.CUSTOM` display state | `python3 -c "from acercontrol.profiles import Profile; assert Profile.from_kernel('custom') is Profile.CUSTOM; assert Profile.from_kernel('unknown-future-mode') is Profile.CUSTOM; assert Profile.CUSTOM.display == 'Custom'; print('CORE-04 OK')"` | P4 |
| CORE-05 | `acer_wmi` blacklist entries in `/etc/modprobe.d/*.conf` surfaced via probe | `python3 -c "from acercontrol.features import probe; r = probe(); blacklist_check = [c for c in r.checks if c.name == 'acer_wmi_not_blacklisted']; assert len(blacklist_check) == 1; print('CORE-05 OK', blacklist_check[0])"` | P17 |
| CORE-06 | Multi-package coretemp: matches `Package id 0`, reports max across packages | `python3 -c "from acercontrol.sysfs import read_cpu_package_temp; t = read_cpu_package_temp(); assert t is None or (0 < t < 120); print('CORE-06 OK', t)"` (on multi-package host, exercises the max-across-packages path) | P16 |

---

## Wave 0 Requirements

- [ ] `tools/smoke_phase1.py` — aggregate smoke runner, calls each of the six smoke commands above, prints PASS/FAIL per requirement, exits non-zero on any failure
- [ ] No test framework install — stdlib only, satisfies REQUIREMENTS.md "no automated tests" out-of-scope clause while still giving deterministic feedback

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Library survives renaming `/sys/firmware/acpi/platform_profile` mid-session and returns a degraded FeatureReport, never a traceback | CORE-03 (resilience clause) | Requires root and a writable test environment; destructive in CI; cheap to do once manually | 1. `sudo mv /sys/firmware/acpi/platform_profile /sys/firmware/acpi/platform_profile.bak` (won't work — sysfs is read-only). 2. Alternative: temporarily blacklist `acer_wmi` via `/etc/modprobe.d/test-blacklist.conf`, reboot, run smoke. 3. Restore. |
| hwmon index drift across two reboots | CORE-02 | Requires physical reboot loop on PHN16-72 | 1. Note `find_hwmon('acer')` result. 2. Reboot. 3. Re-run. 4. Confirm path resolves and `name` file content is `acer`. 5. Repeat once. |
| Multi-package coretemp on actual multi-die hardware | CORE-06 | PHN16-72 has a single die; can't test multi-package on the primary dev machine. Test only if another compatible laptop is available, otherwise mark as untested-on-hardware. | Run smoke on a PH317 or similar multi-package laptop; confirm `read_cpu_package_temp()` returns the max across packages and `tempN_label` matching `Package id 0..N` is used. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` smoke command or are listed in Manual-Only Verifications above
- [ ] Sampling continuity: every requirement maps to at least one smoke command runnable in <2s
- [ ] Wave 0 covers `tools/smoke_phase1.py` aggregate runner
- [ ] No watch-mode flags (smoke commands are one-shot)
- [ ] Feedback latency <2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
