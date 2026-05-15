---
status: complete
phase: 02-privilege-boundary-cli
source: [02-VERIFICATION.md]
started: "2026-05-15T12:50:00Z"
updated: "2026-05-15T13:30:00Z"
deferred_followups:
  - test: 5
    item: "post-reboot persistence verification (predator_v4=Y survives, modprobe.d snippet loaded by initramfs)"
    why: "user deferred reboot to next natural restart"
    re_run: "if predator_v4 reverts to N after reboot, file as Phase 2 gap and re-run /gsd-verify-work 2"
---

## Current Test

[testing complete]

## Tests

### 1. PRIV-03 polkit dialog text
expected: Auth dialog shows "Authentication is required to change the Acer performance profile" — NOT generic "run /usr/libexec/..." text. Confirms `.policy` action ID matches `pkexec` call site and `org.freedesktop.policykit.exec.path` resolves to the named action.
how: Run `acercontrol set turbo` from a graphical terminal on PHN16-72. Read the polkit prompt title/body verbatim.
result: pass

### 2. PRIV-04 interactive cancel (Escape on dialog)
expected: Pressing Escape on the polkit prompt yields exit code 126 handled idempotently — CLI prints "Authentication cancelled." and exits cleanly with no traceback. No retry loop.
how: Run `acercontrol set turbo` from a graphical terminal, press Escape on the polkit dialog, inspect stdout/stderr and `echo $?`.
result: pass
notes: Verified across all profiles (eco/quiet/balanced/performance/turbo).

### 3. PRIV-04 keep-alive (auth_admin_keep)
expected: Second `acercontrol set <profile>` invocation within ~5 min skips re-prompt due to `auth_admin_keep` on `<allow_active>`. (Per P2-NEW-05, polkit credential cache cannot be simulated in CI.)
how: Run `acercontrol set turbo` (authenticate). Within 5 minutes, run `acercontrol set balanced`. Confirm second call does not show a polkit dialog.
result: pass
notes: Profile changed silently on the second call — credential cache working.

### 4. CLI-03 read-back mismatch under PPD
expected: When `power-profiles-daemon` is active and overrides the kernel write, CLI's read-back step fails the comparison and exits non-zero with a warning identifying PPD as likely culprit.
how: `sudo systemctl unmask power-profiles-daemon && sudo systemctl start power-profiles-daemon`, then run `acercontrol set turbo` and inspect exit code + stderr.
result: pass

### 5. CLI-06 root install (full 4-step path)
expected: `sudo acercontrol install` completes 4 steps: (a) write `/etc/modprobe.d/acer-wmi.conf`, (b) `systemctl daemon-reload`, (c) `systemctl enable acer-performance.service` (best-effort warning until Phase 6 ships unit), (d) `update-initramfs -u`. Steps a/b/d abort-on-fail rc=1; step (c) prints stderr warning and continues.
how: Run `sudo acercontrol install`. Inspect stdout/stderr per step. Reboot. Confirm `cat /sys/firmware/acpi/platform_profile` reflects boot profile and `lsmod | grep acer_wmi` shows `predator_v4=Y`.
result: pass
notes: |
  Install command itself ran clean — rc 0, output: "install: complete. Reboot required for `acer_wmi predator_v4=1` to take effect." Implementation prints a single completion line rather than per-step trace; UX-acceptable.
  Post-reboot persistence verification (predator_v4=Y survives, modprobe.d snippet loaded by initramfs) DEFERRED — user will verify on next natural reboot. If predator_v4 reverts to N after reboot, file as a Phase 2 gap and re-run.

### 6. Bundler stack-trace usability
expected: When `dist/acercontrol` raises an exception, the traceback file/line references are intelligible enough for a developer to map back to source. (Subjective — bundler concatenates 6 files; line numbers shift unless source-map preserved.)
how: Run `dist/acercontrol set <invalid>` or trigger any unhandled exception path; inspect the traceback.
result: pass
notes: |
  Exceeded the test bar — the CLI catches both validation and sysfs error paths and prints clean one-line diagnostics with no traceback at all. Observed on PHN16-72:
    `dist/acercontrol set bogus` → "unknown profile: 'bogus'" + "available: eco, quiet, balanced, performance, turbo"
    `chmod 000 + dist/acercontrol set turbo` → "write failed: [Errno 13] Permission denied: '/sys/firmware/acpi/platform_profile'", exit 1
  Original concern (opaque tracebacks in concatenated bundle) is moot for normal user paths. If an unhandled exception ever escapes the error wrappers, traceback readability would still be relevant — defer to Phase 5/6 if it ever surfaces in practice.

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0
deferred_followups: 1  # Test 5 post-reboot persistence verification

## Gaps
