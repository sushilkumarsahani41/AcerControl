---
phase: 02-privilege-boundary-cli
verified: 2026-05-15T00:00:00Z
status: human_needed
score: 11/11 must-haves verified
overrides_applied: 0
human_verification:
  - test: "PRIV-03 polkit dialog text: run `pkexec /usr/libexec/acercontrol/acercontrol-setprofile balanced` from a GNOME session on PHN16-72; observe the authentication dialog message."
    expected: "Dialog reads 'Authentication is required to change the Acer performance profile' — not a generic 'run /usr/libexec/...' message."
    why_human: "polkit dialog rendering requires a running GNOME session with polkit agent; cannot be automated in CI."
  - test: "PRIV-04 interactive cancel: run `acercontrol set turbo` from the GUI terminal on PHN16-72; when the polkit dialog appears, press Escape."
    expected: "CLI prints 'Authentication cancelled.' to stderr and exits 0 (not 1). No retry loop."
    why_human: "Requires interactive pkexec agent on the live desktop; cannot inject a keypress in CI."
  - test: "PRIV-04 keep-alive: after a successful `acercontrol set turbo` on PHN16-72, run `acercontrol set balanced` within ~5 minutes."
    expected: "Second invocation does NOT re-show the polkit dialog (auth_admin_keep caches for ~5 min). Profile changes silently."
    why_human: "polkit credential cache is per-session-agent; cannot simulate in CI per P2-NEW-05."
  - test: "CLI-03 real read-back mismatch: on PHN16-72 with PPD active, run `acercontrol set turbo`."
    expected: "If PPD overrides the write, CLI detects the mismatch and prints a warning rather than silently reporting success."
    why_human: "Requires PPD (power-profiles-daemon) running on PHN16-72 to produce the mismatch condition."
  - test: "CLI-06 root install: run `sudo acercontrol install` on PHN16-72."
    expected: "All four install steps complete (modprobe.d write, daemon-reload, service enable, update-initramfs). Files land in expected paths. Service activates on reboot."
    why_human: "Side effects (initramfs rebuild, systemd state) require the target hardware; cannot sandbox safely in CI."
  - test: "Bundle stack-trace usability: trigger an intentional error in the bundled dist/acercontrol (e.g., chmod 000 /sys/firmware/acpi/platform_profile, then run `dist/acercontrol set turbo`)."
    expected: "Stack trace lines reference source file names (profiles.py, sysfs.py, etc.) rather than opaque byte offsets, aiding debugging."
    why_human: "Requires restricted sysfs access on target hardware; usability is a human judgement call."
---

# Phase 2: Privilege Boundary + CLI Verification Report

**Phase Goal:** Establish the privilege boundary end-to-end with the CLI as the first consumer. Every privileged write goes through one of three real-binary wrappers at /usr/libexec/acercontrol/, each pinned to its polkit action via org.freedesktop.policykit.exec.path. CLI ships full status/get/set/list/temps/install surface, bundled as a single zero-dependency file by tools/bundle_cli.py.
**Verified:** 2026-05-15T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Three named polkit actions (setprofile, set-boot-profile, manage-service) with exec.path annotations pinned to /usr/libexec/acercontrol/ wrappers exist in data/org.acercontrol.policy | ✓ VERIFIED | data/org.acercontrol.policy: 3 actions confirmed, each with `org.freedesktop.policykit.exec.path` annotation at /usr/libexec/acercontrol/<wrapper-name> |
| 2  | Three real-binary wrappers exist at libexec/ with #!/usr/bin/python3 shebangs and ALLOWED_KERNEL_VALUES / ALLOWED_ACTIONS allowlists hardcoded as literals (no acercontrol.* imports) | ✓ VERIFIED | libexec/acercontrol-setprofile (88 LOC), libexec/acercontrol-set-boot-profile (76 LOC), libexec/acercontrol-manage-service (67 LOC) — all verified: absolute shebang, hardcoded allowlists, no package imports |
| 3  | ALLOWED_KERNEL_VALUES in both sysfs-writing wrappers is a hardcoded tuple identical to tuple(PROFILES.values()) — drift gate enforced by smoke_phase2.py | ✓ VERIFIED | smoke_phase2.py `_drift_gate_check_src()` asserts equality; 28/28 smoke pass confirms no drift |
| 4  | privilege.py provides pick_elevation() that detects SSH_CONNECTION → sudo, pkexec → pkexec, else sudo; and PrivilegedResult dataclass consumed by cli.py | ✓ VERIFIED | privilege.py lines confirm SSH_CONNECTION check before shutil.which("pkexec"); PrivilegedResult frozen dataclass defined; cli.py cmd_set imports and uses run_privileged() |
| 5  | pkexec exit 126 (user cancelled) maps to PrivilegedResult.cancelled=True and CLI exits 0 with "Authentication cancelled" message — no retry | ✓ VERIFIED | privilege.py run_privileged(): `if result.returncode == 126: return PrivilegedResult(..., cancelled=True)`; cli.py cmd_set: `if result.cancelled: _emit(...); return 0` |
| 6  | polkit policy uses auth_admin_keep on allow_active and bare auth_admin on allow_any and allow_inactive | ✓ VERIFIED | data/org.acercontrol.policy: all 3 actions have `<allow_active>auth_admin_keep</allow_active>`, `<allow_any>auth_admin</allow_any>`, `<allow_inactive>auth_admin</allow_inactive>` |
| 7  | CLI exposes status/get/set/list/temps/install subcommands, each with --json; set and install have --dry-run; exit codes 0/1/2 | ✓ VERIFIED | cli.py 488 LOC: 6 subcommands confirmed; `dist/acercontrol get --json` → `{"profile":..., "kernel_value":...}`; `temps --json` → 6-key schema; `set turbo --dry-run --json` → correct shape |
| 8  | --json output schema is locked (append-only per CLI-05): get=2 keys, temps=6 keys, set=6 keys, status contains profile+sensors sub-objects, list=array | ✓ VERIFIED | cli.py `_emit()` / `_sensor_to_json()` confirmed; bundle runtime: `temps --json` produced all 6 keys (cpu_package_c, fan1_rpm, fan2_rpm, gpu_c, other_c, predator_v4_active) |
| 9  | tools/bundle_cli.py produces dist/acercontrol that is a standalone stdlib-only executable: no acercontrol.* imports, single from __future__ hoist, no per-source __main__ blocks, SELF_ALIASES bridge | ✓ VERIFIED | bundle_cli.py: BUNDLE_ORDER 6 files; _strip_intra_imports, _strip_future_imports, _strip_main_blocks, SELF_ALIASES block confirmed; bundle runtime `get --json`, `temps --json`, `set turbo --dry-run --json` all produced correct output |
| 10 | tools/verify_no_gtk.py rejects any source or bundle containing gi imports (including indented forms), returning exit 1; and bundler refuses to bundle GTK-importing sources pre-bundle | ✓ VERIFIED | verify_no_gtk.py uses `re.match(r"^\s*(import\s+gi(\b|\.)|from\s+gi(\b|\.))", line)` per line; smoke `_injected_gi_check_src()` confirms bundler fails non-zero on injected `import gi` |
| 11 | Every Phase 2 requirement (PRIV-01..05, CLI-01..07) has at least one automated smoke command runnable on macOS/CI OR an explicit Manual-Only justification in VALIDATION.md | ✓ VERIFIED | smoke_phase2.py 28 scenarios; 02-VALIDATION.md documents 6 Manual-Only items with justifications; 28/28 smoke pass confirmed |

**Score:** 11/11 truths verified (automated)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `data/org.acercontrol.policy` | 3 polkit actions with exec.path annotations | ✓ VERIFIED | 47 LOC, 3 actions, exec.path to /usr/libexec/acercontrol/<name>, auth_admin_keep on allow_active |
| `libexec/acercontrol-setprofile` | Real binary wrapper, stdlib-only, sysexits | ✓ VERIFIED | 88 LOC, #!/usr/bin/python3, ALLOWED_KERNEL_VALUES tuple, EX_OK/EX_USAGE/EX_OSERR/EX_NOPERM |
| `libexec/acercontrol-set-boot-profile` | Real binary wrapper, atomic write to /etc/default/acercontrol | ✓ VERIFIED | 76 LOC, atomic tempfile.mkstemp+os.rename pattern confirmed |
| `libexec/acercontrol-manage-service` | Real binary wrapper, ALLOWED_ACTIONS + ALLOWED_SERVICES allowlists | ✓ VERIFIED | 67 LOC, ALLOWED_ACTIONS=("enable","disable","start","stop"), ALLOWED_SERVICES=("acer-performance.service",) |
| `acercontrol/privilege.py` | pick_elevation(), PrivilegedResult, run_privileged() | ✓ VERIFIED | 195 LOC, frozen dataclass, SSH_CONNECTION check, pkexec 126→cancelled=True, TimeoutExpired→124, FileNotFoundError→127 |
| `acercontrol/cli.py` | 6 subcommands, --json, --dry-run, exit codes 0/1/2 | ✓ VERIFIED | 488 LOC, all subcommands present, _emit() helper, PRIV-04 cancelled branch, JSON schemas confirmed |
| `tools/bundle_cli.py` | Concat bundler with GTK guard, import stripping, SELF_ALIASES | ✓ VERIFIED | 225 LOC, BUNDLE_ORDER 6 files, all strip functions, SELF_ALIASES + POST_PROFILES_ALIASES blocks |
| `tools/verify_no_gtk.py` | GTK import detector, exits 0/1/64 | ✓ VERIFIED | 68 LOC, word-boundary regex, per-line check skipping comments, correct exit codes |
| `tools/smoke_phase2.py` | 28 scenarios covering PRIV-01..05 + CLI-01..07 + drift gate | ✓ VERIFIED | 28/28 passed; contains PRIV-05 SSH check, drift gate, injected-gi rejection, all 12 requirement IDs |
| `dist/acercontrol` | Runnable stdlib-only bundle, no gi imports | ✓ VERIFIED | Runtime tests: get/temps/set --dry-run all produced correct JSON output; verify_no_gtk.py passes on bundle |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| cli.py cmd_set | privilege.run_privileged() | `from acercontrol.privilege import run_privileged` | ✓ WIRED | cli.py imports and calls run_privileged; result.cancelled branch present |
| privilege.run_privileged() | libexec wrappers | resolve_wrapper() → _WRAPPER_DIRS search | ✓ WIRED | privilege.py resolve_wrapper() searches /usr/libexec/acercontrol then /usr/local/libexec/acercontrol then ACERCONTROL_DEV |
| polkit action org.acercontrol.setprofile | libexec/acercontrol-setprofile | exec.path annotation in policy XML | ✓ WIRED | data/org.acercontrol.policy annotate key confirmed pointing to /usr/libexec/acercontrol/acercontrol-setprofile |
| polkit action org.acercontrol.set-boot-profile | libexec/acercontrol-set-boot-profile | exec.path annotation in policy XML | ✓ WIRED | Confirmed in policy XML |
| polkit action org.acercontrol.manage-service | libexec/acercontrol-manage-service | exec.path annotation in policy XML | ✓ WIRED | Confirmed in policy XML |
| bundle_cli.py | 6 acercontrol/*.py sources | BUNDLE_ORDER list + concat | ✓ WIRED | BUNDLE_ORDER = [profiles, sysfs, core, features, privilege, cli]; runtime tests confirm SELF_ALIASES bridge works |
| verify_no_gtk.py | dist/acercontrol (post-bundle) | subprocess.run in bundle_cli.py main() | ✓ WIRED | bundle_cli.py calls subprocess.run([sys.executable, str(verifier), str(OUTPUT)]) |
| smoke_phase2.py drift gate | PROFILES.values() vs ALLOWED_KERNEL_VALUES | _drift_gate_check_src() source parse | ✓ WIRED | Asserts both wrappers' allowlists == tuple(PROFILES.values()); 28/28 pass |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| cli.py cmd_get | profile, kernel_value | core.get_profile() → sysfs.read() → /sys/firmware/acpi/platform_profile | Yes (sysfs read) | ✓ FLOWING |
| cli.py cmd_temps | SensorReading list | features.probe() → sysfs.find_hwmon() → /sys/class/hwmon/hwmon*/temp1_input | Yes (sysfs walk) | ✓ FLOWING |
| cli.py cmd_set --dry-run | argv, elevation, wrapper | pick_elevation() + resolve_wrapper() (no sysfs write in dry-run) | Yes (real picker logic) | ✓ FLOWING |
| dist/acercontrol (bundle) | Same as cli.py | SELF_ALIASES bridge → same sysfs paths | Yes (runtime confirmed) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Smoke gate: 28/28 scenarios | `python3 tools/smoke_phase2.py` | `--- Phase 2 smoke: 28/28 passed ---` | ✓ PASS |
| Bundle get --json (6-key profile schema) | `dist/acercontrol get --json` | `{"profile": "custom", "kernel_value": "custom"}` | ✓ PASS |
| Bundle temps --json (6-key sensor schema) | `dist/acercontrol temps --json` | All 6 keys present (cpu_package_c, fan1_rpm, fan2_rpm, gpu_c, other_c, predator_v4_active) | ✓ PASS |
| Bundle set --dry-run --json (elevation/wrapper shape) | `dist/acercontrol set turbo --dry-run --json` | `{"dry_run":true, "profile":"turbo", "kernel_value":"performance", "elevation":"sudo", "argv":["acercontrol-setprofile","performance"]}` | ✓ PASS |
| Bundler rejects GTK-importing source | smoke _injected_gi_check_src() | bundler exits non-zero, dist/acercontrol removed | ✓ PASS |
| PRIV-05 SSH elevation detection | smoke _ssh_elevation_check_src() | set --dry-run --json with SSH_CONNECTION set → elevation=="sudo" | ✓ PASS |

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| PRIV-01 | Named polkit actions with exec.path annotations | ✓ SATISFIED | data/org.acercontrol.policy: 3 actions, exec.path to /usr/libexec/acercontrol/ |
| PRIV-02 | Wrappers validate argv against hardcoded allowlists; no acercontrol.* imports | ✓ SATISFIED | All 3 libexec wrappers: hardcoded tuples, no package imports, sysexits 64/71/77 |
| PRIV-03 | Polkit dialog shows named action message (automated portion) | ✓ SATISFIED (automated) / ? HUMAN NEEDED (dialog rendering) | policy XML message confirmed; dialog visual requires PHN16-72 GNOME session |
| PRIV-04 | pkexec cancel → exit 0, no retry | ✓ SATISFIED | privilege.py exit 126 → cancelled=True; cli.py cancelled branch → return 0; smoke confirms |
| PRIV-05 | SSH_CONNECTION → sudo instead of pkexec | ✓ SATISFIED | privilege.py pick_elevation() SSH_CONNECTION check; smoke _ssh_elevation_check_src() confirms |
| CLI-01 | Full subcommand surface: status/get/set/list/temps/install | ✓ SATISFIED | cli.py 488 LOC, all 6 subcommands present |
| CLI-02 | --json on every subcommand | ✓ SATISFIED | _emit() helper in cli.py; bundle runtime tests confirm |
| CLI-03 | Read-back verification after set (automated); mismatch detection (human for PPD case) | ✓ SATISFIED (automated) / ? HUMAN NEEDED (PPD mismatch) | cli.py cmd_set reads back after write; PPD mismatch requires live hardware |
| CLI-04 | Exit codes 0/1/2 taxonomy | ✓ SATISFIED | cli.py: 0=ok+cancelled, 1=runtime error, 2=usage (argparse default) |
| CLI-05 | --json schema locked (append-only) | ✓ SATISFIED | 6-key temps schema, 2-key get schema, 6-key set schema confirmed in runtime tests |
| CLI-06 | install subcommand (human for root side-effects on PHN16-72) | ✓ SATISFIED (code) / ? HUMAN NEEDED (root install) | cli.py cmd_install: 4-step install with subprocess; side-effects require hardware |
| CLI-07 | Bundled stdlib-only dist/acercontrol | ✓ SATISFIED | bundle_cli.py + dist/acercontrol; runtime tests pass; verify_no_gtk clean |

### Anti-Patterns Found

| File | Location | Pattern | Severity | Impact |
|------|----------|---------|----------|--------|
| `data/org.acercontrol.policy` | exec.path annotations | exec.path covers /usr/libexec/acercontrol/ only; install.sh deploys to /usr/local/libexec/ | ⚠️ WARNING (WR-01) | install.sh path gets generic "run /usr/local/libexec/..." dialog instead of named action message. .deb path (canonical) is unaffected. UX defect, not security defect. |
| `tools/bundle_cli.py` | _MAIN_BLOCK regex (~line 128) | `_MAIN_BLOCK` regex stops at blank lines inside __main__ blocks | ⚠️ WARNING (WR-02) | Latent: no current source has a blank line inside __main__; would leak trailing code into bundle if one is added. |
| `libexec/acercontrol-manage-service` | line 62 | `return result.returncode if result.returncode == 0 else EX_OSERR` — collapses all non-zero systemctl exits to 71 | ⚠️ WARNING (WR-03) | Phase 3 GUI cannot distinguish "unit not installed" (systemctl exit 4) from "operation refused" (exit 1). Actionable before Phase 3. |
| `tools/bundle_cli.py` | _check_no_gtk() (~line 172) | Pre-bundle check uses `r"^(import\s+gi|from\s+gi(\.|\s))"` — misses indented `import gi` (inside try:, functions) | ⚠️ WARNING (WR-04) | post-bundle verify_no_gtk.py catches it; belt-and-braces still works. Early rejection message won't fire for indented imports. |
| `acercontrol/cli.py` | imports | Unused imports: `asdict`, `Any`, `KERNEL_TO_UI`, `kernel_to_profile` | ℹ️ INFO (IN-01) | Dead code; no functional impact. |
| `tools/bundle_cli.py` | line 35 | Unused `import shutil` | ℹ️ INFO (IN-02) | Dead code; no functional impact. |
| `tools/verify_no_gtk.py` | N/A | `--json` mode emits human prose to stderr AND JSON to stdout | ℹ️ INFO (IN-03) | Design question; not a bug. Callers can ignore stderr. |
| `data/org.acercontrol.policy` | vendor URL comment | Placeholder vendor URL returns HTTP 404 | ℹ️ INFO (IN-04) | No runtime impact. |
| `acercontrol/privilege.py` | run_privileged() | `dry_run=True` branch unreachable from current callers (cmd_set has its own dry-run path) | ℹ️ INFO (IN-05) | Dead branch; no functional impact. |

### Human Verification Required

These items cannot be verified programmatically. All require PHN16-72 hardware with GNOME desktop session. Per `02-VALIDATION.md`, these must be checked before the phase is marked Complete.

#### 1. PRIV-03: polkit dialog renders named action message

**Test:** Install policy file to /usr/share/polkit-1/actions/ on PHN16-72. Run `pkexec /usr/libexec/acercontrol/acercontrol-setprofile balanced` from a GNOME terminal. Observe the authentication dialog.
**Expected:** Dialog title/message reads "Authentication is required to change the Acer performance profile" — NOT a generic "Authentication is required to run /usr/libexec/acercontrol/acercontrol-setprofile".
**Why human:** polkit dialog rendering requires a running GNOME session with polkit agent (gnome-polkit or similar). Cannot automate dialog text inspection in CI.

**Note (WR-01):** If testing via `install.sh` path (deploys to /usr/local/libexec/), the dialog WILL show the generic message because exec.path only covers /usr/libexec/acercontrol/. Test via .deb install path or manual copy to /usr/libexec/acercontrol/ for this check.

#### 2. PRIV-04: Interactive cancel exits 0 with "Authentication cancelled"

**Test:** Run `acercontrol set turbo` from the GNOME terminal on PHN16-72 (not already root). When the polkit authentication dialog appears, press Escape or click Cancel.
**Expected:** CLI prints "Authentication cancelled." to stderr and exits with code 0. No retry loop. Next prompt is the shell.
**Why human:** Requires interactive pkexec agent responding to user input. Cannot inject a keypress in CI.

#### 3. PRIV-04: auth_admin_keep — second invocation skips re-prompt

**Test:** Successfully run `acercontrol set turbo` on PHN16-72 (complete the polkit auth). Within ~5 minutes, run `acercontrol set balanced`.
**Expected:** Second invocation does NOT re-show the polkit dialog. Profile changes silently to balanced.
**Why human:** polkit credential cache is per-session-agent, per-seat. Cannot simulate agent state in CI. (P2-NEW-05 explicitly documents this as Manual-Only.)

#### 4. CLI-03: PPD read-back mismatch warning

**Test:** On PHN16-72 with power-profiles-daemon running and active, run `acercontrol set turbo`.
**Expected:** If PPD overrides the write, CLI detects that the read-back value does not match the requested kernel value and prints a warning (e.g., "Warning: profile may not have applied — read back X, expected Y").
**Why human:** Requires PPD active on the target hardware to produce the mismatch condition. Cannot simulate sysfs override in CI without hardware-specific kernel module interaction.

#### 5. CLI-06: Root install on PHN16-72

**Test:** Run `sudo acercontrol install` on PHN16-72.
**Expected:** All four install steps complete cleanly:
- (a) /etc/modprobe.d/acer-wmi.conf written with `options acer_wmi predator_v4=1`
- (b) `systemctl daemon-reload` completes
- (c) `systemctl enable --now acer-performance.service` enables and starts the service
- (d) `update-initramfs -u` completes without error
Service is active on next reboot; profile is applied at boot.
**Why human:** Side effects (initramfs rebuild, systemd unit state, sysfs write on reboot) require the target hardware and cannot be safely sandboxed in CI.

#### 6. Bundle stack-trace usability

**Test:** On PHN16-72, temporarily make platform_profile unreadable (`sudo chmod 000 /sys/firmware/acpi/platform_profile`). Run `dist/acercontrol get`. Then restore permissions.
**Expected:** Stack trace (if any) references source file names in `# === BEGIN <file>.py ===` sections (e.g., `sysfs.py line 42`), not opaque byte offsets into the concatenated bundle. Error message is informative.
**Why human:** Requires restricted sysfs access on target hardware. "Usability" is a human judgement call per VALIDATION.md.

### Gaps Summary

No automated gaps. All 11 must-have truths are VERIFIED by code inspection and behavioral spot-checks. The smoke runner confirms 28/28 scenarios pass.

Six items require human verification on the PHN16-72 target hardware before the phase can be fully signed off per the sampling rule in `02-VALIDATION.md`:

> "Before /gsd-verify-work: full smoke green on macOS dev box AND on PHN16-72; all Manual-Only items below checked off"

Four warnings from code review (WR-01 through WR-04) are documented above. WR-03 (manage-service collapses non-zero exits to EX_OSERR=71) should be resolved before Phase 3 (GUI service management) to avoid masking error distinctions.

---

_Verified: 2026-05-15T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
