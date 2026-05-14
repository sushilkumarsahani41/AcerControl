---
phase: 02
slug: privilege-boundary-cli
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-15
---

# Phase 02 — Validation Strategy

> Per-phase validation contract. Seeded from `02-RESEARCH.md` §Validation Architecture (lines 1813–1876).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — stdlib `subprocess.run` + `python3 -c` aggregate runner (same approach as Phase 1) |
| **Config file** | none — see Wave 0 |
| **Quick run command** | `python3 tools/smoke_phase2.py` |
| **Full suite command** | `python3 tools/smoke_phase2.py` |
| **Estimated runtime** | ~5 s on macOS dev; ~10 s on PHN16-72 (real elevation paths skipped via `--dry-run` by default) |

---

## Sampling Rate

- **After every task commit:** `python3 tools/smoke_phase2.py` (full runner — checks are cheap)
- **After every plan wave:** `python3 tools/smoke_phase2.py`
- **Before `/gsd-verify-work`:** full smoke green on macOS dev box AND on PHN16-72; all Manual-Only items below checked off
- **Max feedback latency:** ~10 s

**macOS / CI smoke contract:** every smoke must exit 0 on macOS / CI under default conditions. No `if sys.platform != "linux": skip` branches — `--dry-run` for elevation paths, Phase 1 contracts (`Profile.CUSTOM`, all-`None` sensors) cover the no-`/sys` case.

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| PRIV-01 | Three real-binary wrappers exist and are executable | unit (file existence) | `test -x libexec/acercontrol-setprofile && test -x libexec/acercontrol-set-boot-profile && test -x libexec/acercontrol-manage-service && echo OK` | ❌ Wave 0 | ⬜ pending |
| PRIV-01 | Wrapper actually performs sysfs write (real elevation path) | hardware smoke (PHN16-72) | `python3 tools/smoke_phase2.py PRIV-01-write` — invokes wrapper as root, reads `/sys/firmware/acpi/platform_profile` after | ❌ manual | ⬜ pending |
| PRIV-02 | `org.acercontrol.policy` is well-formed XML and declares exactly the 3 expected action IDs | unit | `python3 -c "import xml.etree.ElementTree as ET; t = ET.parse('data/org.acercontrol.policy'); ids = sorted(a.get('id') for a in t.findall('action')); assert ids == ['org.acercontrol.manage-service','org.acercontrol.set-boot-profile','org.acercontrol.setprofile'], ids; print('PRIV-02 ok')"` | ❌ Wave 0 | ⬜ pending |
| PRIV-02 | `<defaults>` uses `auth_admin_keep` for `<allow_active>` on all 3 actions; `<allow_any>`/`<allow_inactive>` = `auth_admin` (no `_keep`); each action has `<annotate key="org.freedesktop.policykit.exec.path">` pointing to the matching wrapper | unit | `python3 tools/smoke_phase2.py PRIV-02-defaults` | ❌ Wave 0 | ⬜ pending |
| PRIV-03 | polkit auth dialog displays configured human message ("Authentication is required to change the Acer performance profile"), never the `pkexec` generic fallback | manual UAT (PHN16-72) | Run `acercontrol set turbo`; visually confirm dialog text | ❌ manual | ⬜ pending |
| PRIV-04 | `pkexec` exit 126 → CLI prints "Authentication cancelled" + exits 0 (idempotent) | manual UAT (PHN16-72) | Run `acercontrol set turbo`, press Escape on auth dialog. Expect: "Authentication cancelled" on stdout, `echo $?` = 0 | ❌ manual | ⬜ pending |
| PRIV-04 | `auth_admin_keep` keep-alive — second invocation within window does NOT re-prompt | manual UAT (PHN16-72) | Run `acercontrol set turbo`, complete auth. Within 60 s run `acercontrol set balanced`. Expect: no second dialog (cannot be smoke-tested per RESEARCH P2-NEW-05) | ❌ manual | ⬜ pending |
| PRIV-05 | `$SSH_CONNECTION` set → CLI selects `sudo`, not `pkexec` | unit (via `--dry-run`) | `SSH_CONNECTION='1.2.3.4 22 5.6.7.8 22' python3 -m acercontrol.cli set turbo --dry-run --json \| python3 -c "import json,sys; d=json.load(sys.stdin); assert d['elevation']=='sudo', d; print('PRIV-05 ok')"` | ❌ Wave 0 | ⬜ pending |
| CLI-01 | `acercontrol status --json` emits a dict with keys `probe`, `profile`, `list`, `temps`; default invocation exits cleanly (rc 0/1/2 acceptable on non-PHN16 host) | unit | `python3 -m acercontrol.cli status > /dev/null; rc=$?; test $rc -eq 0 -o $rc -eq 1 -o $rc -eq 2` AND `python3 -m acercontrol.cli status --json \| python3 -c "import sys,json; d=json.load(sys.stdin); assert {'probe','profile','list','temps'} <= set(d); print('CLI-01 ok')"` | ❌ Wave 0 | ⬜ pending |
| CLI-02 | `acercontrol get` prints user-name; `get --raw` prints kernel value; `--json` exposes both | unit | `python3 -m acercontrol.cli get --json \| python3 -c "import sys,json; d=json.load(sys.stdin); assert {'profile','kernel_value'} <= set(d); print('CLI-02 ok')"` AND check that `acercontrol get --raw` and `acercontrol get` produce different strings when profile ≠ "balanced" | ❌ Wave 0 | ⬜ pending |
| CLI-03 | `acercontrol set <profile> --dry-run --json` validates input, prints would-be wrapper path + kernel value; bad profile → argparse exit 2 | unit | `python3 -m acercontrol.cli set turbo --dry-run --json \| python3 -c "import sys,json; d=json.load(sys.stdin); assert d['dry_run'] and d['kernel_value']=='performance' and d['wrapper'].endswith('acercontrol-setprofile'); print('CLI-03 ok')"` AND `python3 -m acercontrol.cli set zzzz 2>/dev/null; test $? -eq 2` | ❌ Wave 0 | ⬜ pending |
| CLI-03 | Real set + read-back + mismatch → exit 1 | hardware UAT (PHN16-72) | On PHN16-72 with PPD unmasked: `sudo systemctl unmask --now power-profiles-daemon; acercontrol set turbo; echo $?` — expect 1 because PPD overrides the write on read-back | ❌ manual | ⬜ pending |
| CLI-04 | `acercontrol list --json` includes `profiles` (list) and `active` (string) | unit | `python3 -m acercontrol.cli list --json \| python3 -c "import sys,json; d=json.load(sys.stdin); assert 'profiles' in d and 'active' in d; print('CLI-04 ok')"` | ❌ Wave 0 | ⬜ pending |
| CLI-05 | `acercontrol temps --json` includes all 6 numeric keys (nullable) | unit | `python3 -m acercontrol.cli temps --json \| python3 -c "import sys,json; d=json.load(sys.stdin); assert {'cpu_package_c','fan1_rpm','fan2_rpm','acer_temp1_c','acer_temp2_c','acer_temp3_c'} <= set(d); print('CLI-05 ok')"` | ❌ Wave 0 | ⬜ pending |
| CLI-06 | `acercontrol install` non-root: prints steps and exits 0 | unit | `python3 -m acercontrol.cli install; test $? -eq 0` (non-root assumed in macOS/CI) | ❌ Wave 0 | ⬜ pending |
| CLI-06 | `acercontrol install` root: actually executes (modprobe.d snippet written, systemctl enable issued, update-initramfs run) | hardware UAT (PHN16-72) | `sudo python3 -m acercontrol.cli install` on PHN16-72; verify `/etc/modprobe.d/acer-wmi.conf` contains `predator_v4=1` and `systemctl is-enabled acer-performance.service` reports `enabled` | ❌ manual | ⬜ pending |
| CLI-07 | Zero non-stdlib imports in any bundled source (pre-bundle check) | unit | `python3 tools/verify_no_gtk.py acercontrol/profiles.py acercontrol/sysfs.py acercontrol/core.py acercontrol/features.py acercontrol/privilege.py acercontrol/cli.py libexec/acercontrol-setprofile libexec/acercontrol-set-boot-profile libexec/acercontrol-manage-service` | ❌ Wave 0 | ⬜ pending |
| CLI-07 | Bundler produces a single-file `dist/acercontrol`, gi-free post-bundle, `--help` runs | unit | `python3 tools/bundle_cli.py && python3 tools/verify_no_gtk.py dist/acercontrol && dist/acercontrol --help > /dev/null` | ❌ Wave 0 | ⬜ pending |
| CLI-07 (injected import gate) | Deliberately injected `import gi` fails the bundler | unit | Add `import gi` to a copy of `acercontrol/core.py` in a tempdir, point bundler at it, expect exit 1; restore (test owns its own state) | ❌ Wave 0 | ⬜ pending |
| Wrapper-allowlist drift gate | Wrapper allowlist literal == `tuple(PROFILES.values())` (catches Phase 1 PROFILES drift) | unit | `python3 -c "from acercontrol.profiles import PROFILES; import ast,pathlib; tree=ast.parse(pathlib.Path('libexec/acercontrol-setprofile').read_text()); allowlist=[n.value for stmt in tree.body if isinstance(stmt, ast.Assign) and any(t.id=='_ALLOWED' for t in stmt.targets) for n in stmt.value.elts]; assert sorted(allowlist) == sorted(PROFILES.values()), (allowlist, list(PROFILES.values())); print('drift ok')"` | ❌ Wave 0 | ⬜ pending |
| Bundler stack-trace usability | `dist/acercontrol` traceback references useful line numbers | manual UAT | Patch `cli.py` to `raise RuntimeError("test")`, rebundle, run `dist/acercontrol get`, observe traceback points at a `dist/acercontrol` line near the original `cli.py` location | ❌ manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

These files must be created in Wave 0 of the Phase 2 plan before the per-task smokes can run:

- [ ] `acercontrol/privilege.py` — elevation helper (RESEARCH Pattern 1)
- [ ] `acercontrol/cli.py` — main CLI entry (RESEARCH Pattern 2)
- [ ] `libexec/acercontrol-setprofile` — wrapper 1 (RESEARCH Pattern 3)
- [ ] `libexec/acercontrol-set-boot-profile` — wrapper 2 (RESEARCH Pattern 4)
- [ ] `libexec/acercontrol-manage-service` — wrapper 3 (RESEARCH Pattern 5)
- [ ] `data/org.acercontrol.policy` — polkit policy XML (RESEARCH Pattern 6)
- [ ] `pyproject.toml` — add `[project.scripts] acercontrol = "acercontrol.cli:main"` (RESEARCH Pattern 7)
- [ ] `tools/bundle_cli.py` — stdlib-only concatenation bundler (RESEARCH Pattern 8)
- [ ] `tools/verify_no_gtk.py` — pre-/post-bundle import gate (RESEARCH Pattern 9)
- [ ] `tools/smoke_phase2.py` — aggregate smoke runner (RESEARCH Pattern 10)

No external test framework install — same stdlib-only approach as Phase 1.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| polkit auth dialog text matches `<message>` element | PRIV-03 | Visual check of GNOME polkit dialog; cannot be smoke-tested without a polkit agent | On PHN16-72: `acercontrol set turbo`, observe the dialog headline reads "Authentication is required to change the Acer performance profile", NOT "Authentication is needed to run /usr/bin/bash" |
| `pkexec` cancel (exit 126) → idempotent CLI exit 0 + "Authentication cancelled" message | PRIV-04 | Requires interactive Escape press on real polkit dialog | On PHN16-72: `acercontrol set turbo`, press Escape on dialog. Expect: stdout shows "Authentication cancelled", `echo $?` = 0 |
| `auth_admin_keep` second-invocation within ~5min skips re-prompt | PRIV-04 | The keep-alive lives inside polkitd; we cannot observe it from smoke (Pitfall P2-NEW-05) | On PHN16-72: run `acercontrol set turbo`, complete auth; within 60 s run `acercontrol set balanced`; expect: no second auth dialog |
| Real wrapper sysfs write succeeds (the actual elevation path) | PRIV-01, CLI-03 | macOS/CI have no `/sys/firmware/acpi/platform_profile` and no polkit | On PHN16-72: `acercontrol set turbo && cat /sys/firmware/acpi/platform_profile` → expect `performance` |
| `acercontrol set` read-back mismatch produces exit 1 | CLI-03 | Requires a kernel-side override (e.g., PPD active) to deterministically force mismatch | On PHN16-72: `sudo systemctl unmask --now power-profiles-daemon; acercontrol set turbo; echo $?` — expect 1 |
| `acercontrol install` as root actually performs side effects | CLI-06 | Modifies `/etc/modprobe.d/`, enables systemd unit, runs `update-initramfs -u` | On PHN16-72: `sudo python3 -m acercontrol.cli install`; verify `/etc/modprobe.d/acer-wmi.conf` has `predator_v4=1`; `systemctl is-enabled acer-performance.service` reports `enabled`. (Note: `acer-performance.service` unit file ships in Phase 6 — until then this UAT step shows the systemctl call but the enable will fail gracefully.) |
| `dist/acercontrol` traceback usability | (build-quality) | Stack trace inspection is a judgement call | Patch `cli.py` to `raise RuntimeError("test")`, rebundle, run `dist/acercontrol get`, confirm traceback line numbers are in the bundled file and resolvable to original source |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (10 files listed above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10 s
- [ ] `nyquist_compliant: true` set in frontmatter (planner flips this once every requirement in the table has an executable smoke OR an explicit Manual-Only justification)

**Approval:** pending

---

## Carry-forward into PLAN.md

- **Defense-in-depth rule:** wrapper allowlists are hardcoded literals (not `from acercontrol.profiles import …`) because `pkexec` scrubs `PYTHONPATH` (RESEARCH P2-NEW-01). The wrapper-allowlist drift gate above catches Phase 1 PROFILES edits that haven't been mirrored into wrappers.
- **Exit-code taxonomy:** CLI uses argparse (0 success, 2 argparse error); wrappers use sysexits (0 ok, 64 EX_USAGE allowlist reject, 71 EX_OSERR sysfs write fail, 77 EX_NOPERM); pkexec passes through 126 cancel, 127 not found. `privilege.PrivilegedResult.cancelled` carries the 126 case into the CLI's idempotent-exit-0 handler.
- **`--dry-run` semantics:** must compose with `--json`; emits `{"dry_run": true, "elevation": "pkexec"|"sudo", "wrapper": "<abs path>", "argv": [...], "kernel_value": "<value>"}`. The PRIV-05 smoke depends on this shape.
- **`OQ-01` (Phase 6 boundary):** Phase 2's `manage-service` wrapper allowlist contains the literal `("acer-performance.service",)`. If Phase 6 chooses templated `acer-performance@.service`, the allowlist needs updating. Flagged in RESEARCH §Open Questions, deferred to Phase 6 planning.
