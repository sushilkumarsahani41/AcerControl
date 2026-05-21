---
phase: 4
slug: profile-control
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-22
---

# Phase 4 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Project smoke runners, no pytest dependency |
| Config file | `pyproject.toml`; no pytest config |
| Quick run command | `python3 tools/smoke_phase4.py --quick` |
| Full suite command | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py` |
| Estimated runtime | Less than 10 seconds for source/static smoke checks on this host |

---

## Sampling Rate

- After every task commit: run `python3 tools/smoke_phase4.py --quick` once Wave 0 creates it.
- After every plan wave: run `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py`.
- Before `$gsd-verify-work`: full suite must be green, then manual PHN16-72 UAT must cover GTK/polkit/LED/PPD scenarios.
- Max feedback latency: 10 seconds for automated source/static checks.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | GUI-05 | T-04-03 / T-04-04 | UI highlights only the actual read-back `Profile`; raw kernel values do not render in user-facing UI. | source smoke + manual GTK UAT | `python3 tools/smoke_phase4.py --quick` | no - Wave 0 creates it | pending |
| 04-01-02 | 01 | 1 | GUI-06 | T-04-01 / T-04-02 / T-04-05 | Profile write uses `run_privileged(["acercontrol-setprofile", PROFILES[...]])`; cancellation has no side effects. | source smoke + manual polkit UAT | `python3 tools/smoke_phase4.py --quick` | no - Wave 0 creates it | pending |
| 04-01-03 | 01 | 1 | GUI-07 | T-04-03 / T-04-04 | Mismatch re-renders actual profile state and forces the PPD banner visible. | source smoke + manual PPD UAT | `python3 tools/smoke_phase4.py --quick` | no - Wave 0 creates it | pending |

*Status values: pending, green, red, flaky.*

---

## Wave 0 Requirements

- [ ] `tools/smoke_phase4.py` - source/static smoke runner covering GUI-05..GUI-07.
- [ ] `tools/smoke_phase4.py --quick` - quick mode that can run after each task commit.
- [ ] Smoke checks for exact copy: `Awaiting authorisation...`, `Authorization cancelled`, `Profile not applied - power-profiles-daemon may be overriding writes` or the Unicode em dash source equivalent, and `Switched to `.
- [ ] Smoke checks for profile button order: `eco`, `quiet`, `balanced`, `performance`, `turbo`.
- [ ] Smoke checks for `Gtk.Button` use and absence of `Gtk.ToggleButton` in the profile-control module.
- [ ] Smoke checks for `run_privileged(["acercontrol-setprofile", ...])`, `GLib.timeout_add(250, ...)`, and `show_ppd_banner(force=True)`.
- [ ] Smoke checks preserving GUI-08: no user-facing raw kernel labels outside the profile mapping and diagnostics carve-out.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Every profile button switches the laptop profile and returns matching CLI state. | GUI-05, GUI-06 | Requires real PHN16-72 hardware, Linux sysfs, pkexec, and chassis LED behavior. | On PHN16-72, click `eco`, `quiet`, `balanced`, `performance`, `turbo`; after each click run `acercontrol get`. Confirm `turbo` makes the chassis LED blink and `performance` leaves it solid. |
| Polkit cancellation preserves previous highlight. | GUI-06 | Requires interactive polkit dialog. | Click a non-active profile, press Escape in polkit, confirm highlight remains on the previous actual profile, toast reads `Authorization cancelled` for 3 seconds, and `journalctl --user` has no traceback. |
| PPD overwrite path warns and re-surfaces banner. | GUI-07 | Requires Linux power-profiles-daemon running and timing with real sysfs writes. | Re-enable PPD, dismiss the banner if visible, click a profile that PPD overwrites, confirm warning toast text, actual profile highlight, and PPD banner reappears. |
| Custom/unknown profile state. | GUI-05 | Requires controlled sysfs state or test fixture on Linux. | Force `/sys/firmware/acpi/platform_profile` to `custom` or an unknown value where supported; GUI shows `Current profile: Custom`, no profile button is active, and known profile clicks follow the normal set flow. |

---

## Threat References

| ID | Threat | Mitigation |
|----|--------|------------|
| T-04-01 | Command injection through requested profile. | Pass an argv list to `run_privileged`; wrapper allowlists kernel values; no shell. |
| T-04-02 | Direct wrapper invocation by local process. | Wrapper requires effective uid 0 and validates argv; polkit policy pins `exec.path`. |
| T-04-03 | Misleading active profile UI. | Active highlight is derived only from `read_profile()` read-back state; no optimistic highlight. |
| T-04-04 | Raw kernel profile value exposure. | GUI-08 smoke gate and diagnostics-only carve-out. |
| T-04-05 | Auth cancellation causing side effects. | `PrivilegedResult.cancelled` routes to a no-readback, no-PPD-force cancellation path. |

---

## Validation Sign-Off

- [x] All phase requirements have automated smoke coverage planned or Wave 0 dependencies.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing automated references.
- [x] No watch-mode flags.
- [x] Feedback latency target is less than 10 seconds for automated checks.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-05-22
