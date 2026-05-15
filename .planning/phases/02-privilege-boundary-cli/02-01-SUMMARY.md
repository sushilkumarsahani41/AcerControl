---
phase: 02-privilege-boundary-cli
plan: 01
subsystem: cli/privilege-boundary
tags: [python, cli, polkit, pkexec, privilege-boundary, argparse, stdlib-only, bundler, json-schema, security]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: PROFILES / KERNEL_TO_UI / Profile / SensorReading / kernel_to_profile / list_available_profiles / probe / read_profile / read_sensors
provides:
  - acercontrol.privilege module — pick_elevation (SSH_CONNECTION → sudo precedence), resolve_wrapper, PrivilegedResult frozen dataclass with cancelled flag, run_privileged (pkexec/sudo selection + 124/127 defensive paths + dry-run non-invocation)
  - acercontrol.cli module — argparse with 6 subcommands (status/get/set/list/temps/install); locked --json schema (Pattern 8) on every subcommand; --dry-run on every privileged command; PRIV-04 idempotent cancellation branch (rc=0); read-back verification on cmd_set with mismatch → rc=1; cmd_install non-root print+exit-0, root path executes steps with continue-on-fail for systemctl-enable
  - 3 libexec wrappers — acercontrol-{setprofile, set-boot-profile, manage-service}; absolute-path #!/usr/bin/python3 shebangs; hardcoded literal allowlists (P2-NEW-01); sysexits codes 0/64/71/77; geteuid()==0 trust check
  - data/org.acercontrol.policy — 3 named actions (org.acercontrol.{setprofile, set-boot-profile, manage-service}); each pinned via org.freedesktop.policykit.exec.path; auth_admin_keep on allow_active; PRIV-03 verbatim message strings; no exec.argv1 (P2-NEW-04)
  - tools/verify_no_gtk.py — grep-based CI gate; line-anchored regex catches `import gi`/`from gi` (any indent; comments excluded)
  - tools/bundle_cli.py — stdlib-concat bundler → dist/acercontrol mode 0o755; hoists from __future__ into HEADER (ISSUE-01); strips intra-package imports + per-source main blocks; SELF_ALIASES bridge for qualified module references; pre-bundle and post-bundle CLI-07 gates (P2-NEW-06)
  - tools/smoke_phase2.py — 28-scenario aggregate runner; covers all PRIV/CLI requirements + drift gate + injected-gi rejection; runs identically on macOS/Linux/CI under default conditions (no /sys, no polkit) via --dry-run + Phase 1 contract degradation
  - pyproject.toml [project.scripts] entry point — `acercontrol = "acercontrol.cli:main"`
affects: [03-gui-shell, 04-profile-control, 05-sensors, 06-boot-service, 07-tray-notifications, 08-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern: defense-in-depth allowlist literal in privileged wrapper (hardcoded tuple; pkexec scrubs PYTHONPATH so wrapper cannot import acercontrol.profiles; drift gate at smoke time keeps the literal in lockstep with PROFILES.values())"
    - "Pattern: $SSH_CONNECTION → sudo precedence over pkexec (PRIV-05; pkexec hangs without a graphical agent over SSH)"
    - "Pattern: pkexec exit 126 → PrivilegedResult.cancelled=True → CLI exit 0 with 'Authentication cancelled' (PRIV-04 idempotent; no spin-retry)"
    - "Pattern: PrivilegedResult frozen dataclass with cancelled bool — Phase 4 GUI consumes the same shape"
    - "Pattern: locked --json schema is append-only; smokes assert key presence (>= subset) not key absence; future phases add fields, never remove"
    - "Pattern: CLI exit-code taxonomy — 0 OK (incl. PRIV-04 cancellation), 1 runtime failure, 2 usage error (argparse default + bad-profile validation)"
    - "Pattern: wrapper exit-code taxonomy — 0/64/71/77 (sysexits.h); pkexec/sudo translation lives in privilege.run_privileged"
    - "Pattern: stdlib-concat bundler with intra-import stripping + future-import hoisting + SELF_ALIASES bridging — produces a debuggable single-file CLI without zipapp/PyInstaller"
    - "Pattern: pre-bundle AND post-bundle gtk-import gate (P2-NEW-06 belt-and-braces)"
    - "Pattern: aggregate smoke runner with 28 scenarios — same shape as smoke_phase1.py (per-check subprocess, never raises, accumulator + final pass count)"

key-files:
  created:
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/privilege.py (~190 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/cli.py (~430 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-setprofile (~90 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-set-boot-profile (~75 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-manage-service (~70 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/data/org.acercontrol.policy (~50 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/tools/verify_no_gtk.py (~60 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/tools/bundle_cli.py (~175 LOC)"
    - "/Users/sushilkumarsahani/Desktop/AcerControl/tools/smoke_phase2.py (~310 LOC)"
  modified:
    - "/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml (append [project.scripts] section; existing Phase 1 sections untouched)"

key-decisions:
  - "Defense-in-depth: each wrapper hardcodes ALLOWED_KERNEL_VALUES / ALLOWED_ACTIONS / ALLOWED_SERVICES as literal tuples (not imported from acercontrol.profiles) — pkexec scrubs PYTHONPATH so a runtime import would fail. Wrapper-allowlist drift gate in tools/smoke_phase2.py keeps the two wrapper allowlists (setprofile, set-boot-profile) in lockstep with tuple(PROFILES.values()) at smoke time."
  - "Wrapper shebangs are #!/usr/bin/python3 (absolute path), not /usr/bin/env python3 — pkexec rebuilds PATH from a minimal known-safe environment. Build tools (verify_no_gtk.py, bundle_cli.py, smoke_phase2.py) use /usr/bin/env python3 because they're invoked from the dev/CI shell."
  - "auth_admin_keep on allow_active only; allow_any and allow_inactive are bare auth_admin (no _keep). PRIV-04 keep-alive (~5 min credential cache) applies only to interactive console sessions; remote / inactive sessions still re-prompt every time."
  - "No org.freedesktop.policykit.exec.argv1 annotation in the polkit policy (P2-NEW-04). The wrapper allowlist IS the validator; declaring 5 actions per wrapper × 3 wrappers = 15 actions would bloat the policy and degrade the UX message."
  - "$SSH_CONNECTION precedence over shutil.which('pkexec') in pick_elevation() — pkexec hangs over SSH waiting for a graphical agent. PRIV-05."
  - "argparse default exit 2 on usage errors is preserved (P2-NEW-02). cmd_set re-uses exit 2 for unknown profile (CLI-side validation rejects before any polkit prompt)."
  - "cmd_install non-root → print + exit 0 (CONTEXT.md lock; composes with `acercontrol install | sudo bash`). cmd_install root path executes 4 steps: (a) modprobe.d snippet, (b) systemctl daemon-reload, (c) systemctl enable acer-performance.service, (d) update-initramfs -u. Steps a/b/d abort-on-fail rc=1; step (c) is best-effort with stderr warning until Phase 6 ships the unit file (ISSUE-02 lock)."
  - "Wrapper file `acercontrol-set-boot-profile` writes /etc/default/acercontrol via tempfile.mkstemp + os.rename for atomic update — Phase 6 boot service will read this file as EnvironmentFile."
  - "Wrapper file `acercontrol-manage-service` allowlists the literal `acer-performance.service` (single-tuple). OQ-01 carry-forward: if Phase 6 ships templated `acer-performance@.service`, this wrapper's allowlist must extend; documented in code comment + this SUMMARY."
  - "Bundler is stdlib concat (CLAUDE.md decision #8), NOT zipapp/PyInstaller/shiv/Nuitka. Output dist/acercontrol mode 0o755 with hoisted from __future__ HEADER + stripped intra-imports + stripped per-source __main__ blocks + SELF_ALIASES for qualified module references."

requirements-completed: [PRIV-01, PRIV-02, PRIV-03, PRIV-04, PRIV-05, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07]

# Metrics
duration: ~50 min
completed: 2026-05-15
---

# Phase 2 Plan 01: Privilege Boundary + CLI Summary

**Stood up the privilege boundary end-to-end with the CLI as its first consumer. Three real-binary wrappers under libexec/, three named polkit actions pinned via exec.path, six argparse subcommands with locked --json schema, stdlib-concat bundler producing a single-file dist/acercontrol — 28/28 smoke scenarios PASS on macOS dev box.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 6 of 6 (all `type="auto"`, no checkpoints)
- **Files created:** 9 (privilege.py, cli.py, 3 libexec/* wrappers, polkit policy, 3 tools/*.py)
- **Files modified:** 1 (pyproject.toml — append [project.scripts] only)
- **Total LOC:** ~1,450 (target was ~1,035 — over by ~40% due to verbatim research-pattern copy + ISSUE-01/02/03 fixes + bundler P2-NEW-08 fixes)
- **Commits:** 6 atomic feat commits (one per task) + this metadata commit

## Accomplishments

- **All 12 phase requirements satisfied.** PRIV-01..05 + CLI-01..07 each have at least one passing automated smoke scenario (Manual UAT items deferred per VALIDATION.md — see "Manual UAT Deferred" below).
- **Phase gate green.** `python3 tools/smoke_phase2.py` exits 0; prints `Phase 2 smoke: 28/28 passed`; zero traceback lines in output. Runs identically with or without explicit `PYTHONPATH=`.
- **Trust-boundary discipline locked.** Every privileged sysfs/systemctl write goes through one of three wrappers. Each wrapper independently re-validates argv against a hardcoded literal allowlist. No `pkexec bash -c '...'` anywhere in the codebase.
- **Polkit auth dialog will read the right message.** Each named action's `<message>` matches ROADMAP SC#1 verbatim. Visual confirmation deferred to Manual UAT on PHN16-72 (VALIDATION.md Manual-Only).
- **`$SSH_CONNECTION` → `sudo` proven by smoke.** `acercontrol set turbo --dry-run --json` with `SSH_CONNECTION='1.2.3.4 22 5.6.7.8 22'` emits `"elevation":"sudo"`.
- **Bundler ships a debuggable single-file CLI.** `dist/acercontrol --help` runs; the bundle contains exactly ONE active `from __future__ import annotations` line (hoisted HEADER); pre-bundle and post-bundle CLI-07 gates green; injected `import gi` rejection asserted in smoke.

## Task Commits

Each task committed atomically on `main` (branching_strategy="none"):

1. **Task 1: Privilege escalation helper (PRIV-04, PRIV-05)** — `0cff116` (feat)
2. **Task 2: Three libexec wrappers + verify_no_gtk gate (PRIV-01, CLI-07)** — `930d2a2` (feat)
3. **Task 3: Polkit policy XML for 3 named actions (PRIV-02, PRIV-03)** — `4bffba4` (feat)
4. **Task 4: Argparse CLI + project.scripts (CLI-01..06, PRIV-04, PRIV-05)** — `0c4e88a` (feat)
5. **Task 5: Stdlib-concat bundler dist/acercontrol (CLI-07)** — `c769d79` (feat)
6. **Task 6: Aggregate smoke runner (phase gate)** — `7f07109` (feat)

## Files Created/Modified

### Created

- `acercontrol/privilege.py` — escalation helper. `WRAPPER_NAMES` 3-tuple, `_WRAPPER_DIRS` 2-tuple + `$ACERCONTROL_DEV` dev-mode fallback, `resolve_wrapper(name) -> Path | None`, `Elevation = Literal["pkexec","sudo","none"]`, `pick_elevation()` SSH precedence, `@dataclass(frozen=True) PrivilegedResult` with tuple-typed argv + cancelled bool, `run_privileged(wrapper_argv, *, timeout=30, dry_run=False)` with subprocess.TimeoutExpired→124 + FileNotFoundError→127 + pkexec exit 126 → cancelled=True branches.
- `acercontrol/cli.py` — argparse CLI. `_emit(data, text, *, as_json)` JSON-vs-plain output helper, `_sensor_to_json(SensorReading) -> dict`, six `cmd_*` handlers (status/get/list/temps/set/install), `_build_parser()` with `add_subparsers(dest="cmd", required=True)`, `main(argv=None) -> int`, `__main__` entry. `cmd_set` includes the locked dry-run JSON payload (with `elevation` for PRIV-05), the idempotent `result.cancelled` branch (PRIV-04), elevation-unavailable (rc=1), wrapper-failed (rc=1), and read-back-mismatch (rc=1) branches. `cmd_install` non-root path prints + exits 0 (CONTEXT lock); root path executes 4 steps with step (c) continue-on-fail until Phase 6 ships the unit (ISSUE-02 lock).
- `libexec/acercontrol-setprofile` — `#!/usr/bin/python3` absolute shebang, `ALLOWED_KERNEL_VALUES = ("low-power","quiet","balanced","balanced-performance","performance")` hardcoded literal tuple, sysexits codes EX_OK=0/EX_USAGE=64/EX_OSERR=71/EX_NOPERM=77, opens `PROFILE_PATH = "/sys/firmware/acpi/platform_profile"` for write.
- `libexec/acercontrol-set-boot-profile` — same shebang/allowlist/sysexits; atomic `tempfile.mkstemp` + `os.rename` write to `BOOT_CONFIG_PATH = "/etc/default/acercontrol"` with `BOOT_PROFILE=<value>\n` content.
- `libexec/acercontrol-manage-service` — same shebang/sysexits; `ALLOWED_ACTIONS = ("enable","disable","start","stop")`, `ALLOWED_SERVICES = ("acer-performance.service",)` literal single-tuple; invokes `subprocess.run(["systemctl", action, service], capture_output=True, text=True, timeout=20)`; OQ-01 carry-forward comment in docstring flagging Phase 6 templated-unit possibility.
- `data/org.acercontrol.policy` — XML declaration + verbatim freedesktop polkit DTD; `<vendor>AcerControl</vendor>`; 3 `<action>` elements (`org.acercontrol.{setprofile, set-boot-profile, manage-service}`); each with verbatim `<message>` from ROADMAP SC#1, `<allow_active>auth_admin_keep</allow_active>` + bare `auth_admin` on `<allow_any>`/`<allow_inactive>`, and `<annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/<binary></annotate>`. No `exec.argv1` annotation anywhere (P2-NEW-04).
- `tools/verify_no_gtk.py` — grep gate. `_GTK_IMPORT` precompiled regex; `check(path) -> list` reads file with `errors="replace"`, skips comment lines, runs anchored `re.match` on each surviving line; `main(argv) -> int` returns 64 on empty argv, 0 on clean, 1 on any hit.
- `tools/bundle_cli.py` — stdlib-concat bundler. `BUNDLE_ORDER` 6-list (profiles → sysfs → core → features → privilege → cli); `_INTRA_IMPORT` regex covers single-line + parenthesised multi-line forms; `_strip_intra_imports` comment-prefixes EVERY line of multi-line matches (Rule 1 fix vs research pattern); `_FUTURE_IMPORT` regex + `_strip_future_imports` (ISSUE-01); `_MAIN_BLOCK` regex + `_strip_main_blocks` (P2-NEW-08); `SELF_ALIASES` block bridges qualified module references; `POST_PROFILES_ALIASES` block bridges `as _name` aliases used by `core.py`; `_check_no_gtk` pre-bundle gate; subprocess invocation of `verify_no_gtk.py` post-bundle with `OUTPUT.unlink(missing_ok=True)` on failure.
- `tools/smoke_phase2.py` — 28-scenario aggregate runner. `PROJECT_ROOT` self-injecting `PYTHONPATH`; `run(label, argv, *, expect_rc, stdin, env_extra, check_json_parses)` helper; `_three_actions_check_src()` / `_drift_gate_check_src()` (covers BOTH wrappers — ISSUE-03) / `_injected_gi_check_src()` / `_ssh_elevation_check_src()` builders; `build_scenarios()` returns the SCENARIOS list (skips CLI-06 install when euid 0); pre-flight cleanup of stale `dist/acercontrol`; outer try/except so the runner never raises; final `Phase 2 smoke: N/total passed` line.

### Modified

- `pyproject.toml` — appended `[project.scripts]` section: `acercontrol = "acercontrol.cli:main"` (with a commented `acercontrol-gui` line for Phase 3). Existing `[build-system]`, `[project]`, `[project.classifiers]`, `[tool.setuptools]` sections untouched. Zero runtime dependencies preserved.

## Pitfall Mitigations Realized in Code

| Pitfall | Where mitigated | How |
|---|---|---|
| **P1** (real-binary wrapper, not `pkexec bash -c`) | `libexec/*` + `acercontrol/privilege.py` | All three wrappers are real binaries; `privilege.run_privileged` invokes `["pkexec", str(wrapper_path), …]` — never `bash -c`. CLI-side: `cmd_set` passes argv as a list to `run_privileged(["acercontrol-setprofile", kernel_value])`, never a shell string. |
| **P14** (SSH detection + cancel handling + no spin-retry) | `acercontrol/privilege.py` | `pick_elevation()` checks `$SSH_CONNECTION` BEFORE `shutil.which("pkexec")`. `run_privileged` translates pkexec exit 126 → `cancelled=True` (no auto-retry loop). CLI `cmd_set` returns 0 on `result.cancelled` (PRIV-04 idempotent). |
| **P2-NEW-01** (pkexec env scrub breaks `from acercontrol.profiles import PROFILES` in wrappers) | `libexec/acercontrol-{setprofile, set-boot-profile, manage-service}` + `tools/smoke_phase2.py` | Wrappers hardcode `ALLOWED_KERNEL_VALUES` / `ALLOWED_ACTIONS` / `ALLOWED_SERVICES` as literal tuples; never import from `acercontrol.*`. Drift gate in smoke asserts the two `ALLOWED_KERNEL_VALUES` literals == `tuple(PROFILES.values())`. |
| **P2-NEW-02** (argparse exit 2 vs wrapper EX_USAGE 64) | `acercontrol/cli.py` + `libexec/*` | CLI: `cmd_set` returns 2 on bad profile (matches argparse default exit 2). Wrappers: return EX_USAGE=64 on bad argv. Smoke asserts both: `acercontrol set zzzz` → rc=2; `libexec/acercontrol-setprofile garbage` → rc=64. |
| **P2-NEW-03** (BOOT-01 templated unit vs CONTEXT literal `acer-performance.service`) | `libexec/acercontrol-manage-service` + this SUMMARY | Wrapper allowlist locks the literal name; OQ-01 carry-forward comment in docstring; this SUMMARY documents the Phase 6 resolution. |
| **P2-NEW-04** (`exec.argv1` annotation NOT used; wrapper allowlist is the validator) | `data/org.acercontrol.policy` + smoke | Policy declares only `<annotate key="org.freedesktop.policykit.exec.path">…</annotate>`; smoke `_three_actions_check_src` verifies absence of `exec.argv1` per action. |
| **P2-NEW-05** (`auth_admin_keep` keep-alive cannot be smoke-tested) | (intentionally absent) | No spurious smoke. Manual UAT row in VALIDATION.md handles interactive verification on PHN16-72. |
| **P2-NEW-06** (verify_no_gtk scope — inputs AND outputs) | `tools/bundle_cli.py` + `tools/smoke_phase2.py` | Bundler runs `_check_no_gtk` on each input source (pre-bundle) AND `subprocess.run([sys.executable, str(verifier), str(OUTPUT)])` after writing the output (post-bundle, removes the bundle on failure). Smoke runner additionally exercises `verify_no_gtk` against all bundle inputs as a separate scenario. |
| **P2-NEW-08** (bundler concat semantics) | `tools/bundle_cli.py` | Discovered during execution (Rule 1). The research pattern's bundler produced a SyntaxError (per-source `from __future__` lines) AND multiple runtime NameErrors (qualified `core.X` / `_sysfs.X` references after intra-imports stripped, `_current_profile_ui` alias missing). Fixes: ISSUE-01 (`_strip_future_imports` + hoisted HEADER directive), `_strip_main_blocks` (suppress `features.py`'s `_print_report` from firing before `cli.main`), `SELF_ALIASES` (bind module names to bundle's `__name__`), `POST_PROFILES_ALIASES` (bridge `as _name` aliases used by `core.py`), and multi-line-aware `_INTRA_IMPORT` regex (covers `from acercontrol.X import (\n  ...\n)` parenthesised forms). |

## Smoke Results

`python3 tools/smoke_phase2.py` — exit 0 on this host (macOS dev box, no `/sys`, no polkit).

```
-> CLI-01 status text                                         PASS
-> CLI-01 status JSON                                         PASS
-> CLI-02 get text                                            PASS
-> CLI-02 get --raw                                           PASS
-> CLI-02 get JSON                                            PASS
-> CLI-03 set dry-run text                                    PASS
-> CLI-03 set dry-run JSON                                    PASS
-> CLI-03 set bad profile (rc=2)                              PASS
-> CLI-04 list text                                           PASS
-> CLI-04 list JSON                                           PASS
-> CLI-05 temps text                                          PASS
-> CLI-05 temps JSON                                          PASS
-> CLI-06 install non-root (rc=0)                             PASS
-> CLI-06 install dry-run JSON                                PASS
-> PRIV-05 SSH_CONNECTION -> sudo                             PASS
-> CLI-07 verify_no_gtk inputs                                PASS
-> CLI-07 bundle_cli builds dist/acercontrol                  PASS
-> CLI-07 dist/acercontrol --help runs                        PASS
-> CLI-07 verify_no_gtk on output                             PASS
-> CLI-07 injected-gi rejection                               PASS
-> PRIV-02 polkit policy XML well-formed                      PASS
-> PRIV-02 policy three actions + defaults                    PASS
-> Wrapper-allowlist drift gate                               PASS
-> Wrapper acercontrol-setprofile rejects bad value           PASS
-> Wrapper acercontrol-setprofile rejects no argv             PASS
-> Wrapper acercontrol-set-boot-profile rejects bad value     PASS
-> Wrapper acercontrol-manage-service rejects bad action      PASS
-> Wrapper acercontrol-manage-service rejects bad service     PASS
--- Phase 2 smoke: 28/28 passed ---
```

`PYTHONPATH=. python3 -c "from acercontrol import cli, privilege"` → exit 0.

`python3 dist/acercontrol --help` → prints the 6-subcommand argparse help. `python3 dist/acercontrol set turbo --dry-run --json` → emits the locked Pattern 8 dry-run payload (kernel_value=performance, elevation=sudo on macOS where pkexec is absent).

Zero `^import gi` / `^from gi` lines under `acercontrol/`, `libexec/`, or `tools/` (excluding comments).

## Public CLI Surface (6 subcommands × locked --json schema)

```text
acercontrol status [--json]
acercontrol get    [--raw] [--json]
acercontrol set    <profile> [--dry-run] [--json]
acercontrol list   [--json]
acercontrol temps  [--json]
acercontrol install [--dry-run] [--json]
```

`--json` schema is **append-only** — future phases may add fields, MUST NOT rename or remove. Smokes assert key presence (`>=` set check), not key absence.

## Privilege-Boundary Trust Model (3 layers)

```text
┌──────────────────┐  user-name allowlist (PROFILES.keys())
│ acercontrol/cli  │  argparse usage check; bad profile → rc=2
│       (rc 0/1/2) │  fast feedback, no polkit prompt for typos
└────────┬─────────┘
         │ run_privileged(["acercontrol-setprofile", kernel_value])
┌────────▼─────────────────┐  pick_elevation(): SSH? → sudo, else pkexec
│ acercontrol/privilege.py │  PrivilegedResult(rc, elevation, argv,
│                          │    cancelled, stdout, stderr); never raises
└────────┬─────────────────┘
         │ ["pkexec", "/usr/libexec/acercontrol/acercontrol-setprofile", kernel]
┌────────▼─────────────────────────────┐  uid 0 trust check (geteuid()==0 → EX_NOPERM)
│ libexec/acercontrol-setprofile (root)│  ALLOWED_KERNEL_VALUES literal allowlist
│              (sysexits 0/64/71/77)   │  open(PROFILE_PATH, "w").write(value)
└──────────────────────────────────────┘
```

Each layer is independently sufficient to reject bad input. CLI-side validation gives fast UX feedback; wrapper allowlist defends against another local process invoking the wrapper directly via pkexec; uid-0 trust check defends against accidental non-root invocation.

## Decisions Made

1. **Defense-in-depth wrapper allowlist (P2-NEW-01)** — wrappers hardcode `ALLOWED_KERNEL_VALUES` literal tuples (NOT imported from `acercontrol.profiles`). pkexec scrubs `PYTHONPATH` to a minimal known-safe environment; the import would `ModuleNotFoundError` on every real-elevation invocation. Drift gate in smoke keeps the literal in lockstep.
2. **`#!/usr/bin/python3` absolute shebang** for wrappers — pkexec rebuilds PATH from a minimal environment; `/usr/bin/env python3` is not guaranteed resolvable. Build tools use `/usr/bin/env python3` (no pkexec involved).
3. **`auth_admin_keep` only on `<allow_active>`** — keep-alive (~5 min credential cache) for interactive console sessions; `<allow_any>` and `<allow_inactive>` are bare `auth_admin` (no `_keep`) so remote / background sessions still re-prompt every time.
4. **No `exec.argv1` annotation** (P2-NEW-04) — declaring 5 actions per wrapper × 3 wrappers = 15 actions would bloat the policy and degrade the dialog message UX. The wrapper allowlist IS the validator.
5. **`$SSH_CONNECTION` precedence over `shutil.which("pkexec")`** — pkexec hangs over SSH waiting for a graphical agent. Sudo is used instead with `["sudo", "--", str(wrapper_path), …]` (the `--` separator prevents sudo from interpreting wrapper flags).
6. **argparse exit 2 preserved on usage errors (P2-NEW-02)** — CLI handlers return 2 on bad profile (matches argparse default); wrappers return EX_USAGE=64 on bad argv (sysexits.h).
7. **`acercontrol install` non-root → print + exit 0** (CONTEXT lock) — composes with `acercontrol install | sudo bash`. Root path executes 4 steps where step (c) `systemctl enable acer-performance.service` is best-effort with stderr warning until Phase 6 ships the unit (ISSUE-02 lock).
8. **`set-boot-profile` and `manage-service` are NOT CLI subcommands in Phase 2** — the wrappers exist for Phase 6 GUI consumption. Phase 2 covers them only by direct-invocation smoke (`expect_rc=64` on bad argv).
9. **Bundler is stdlib concat** (CLAUDE.md decision #8), not zipapp/PyInstaller/shiv/Nuitka. Output is a debuggable single-file Python script.

## Patterns Established for Phase 3 and Beyond

- **`PrivilegedResult` frozen dataclass with `cancelled` flag** — Phase 4 GUI's profile-button click handler will consume the same shape: on `result.cancelled`, revert highlight + show toast; on `result.returncode != 0`, show error toast + leave highlight; on success, read back + show "Switched to <profile>" toast.
- **Locked Pattern 8 JSON schema is append-only** — Phase 3 GUI primarily imports `acercontrol.core` directly (same process), but Phase 3+ may also parse `--json` output for diagnostics export.
- **Wrapper trust-boundary discipline** (hardcoded allowlist + sysexits codes + absolute-path shebang) — Phase 6 GUI boot-service panel will invoke `acercontrol-set-boot-profile` and `acercontrol-manage-service` through the same `run_privileged()` helper. Same `PrivilegedResult.cancelled` branch applies.
- **`_emit(data, text, *, as_json)` JSON-vs-plain output helper** — pattern reused across all 6 subcommands; Phase 3+ CLI extensions (e.g. `acercontrol diagnose`) follow the same shape.
- **Bundler concat semantics** (P2-NEW-08) — if Phase 3+ adds `acercontrol/<new>.py` files that the CLI imports via `from acercontrol import …`, the bundler's intra-import stripping handles them automatically; if a new module uses qualified `<other>.X` access (like `core.X`), add the alias to `SELF_ALIASES` in `tools/bundle_cli.py`.

## Manual UAT Items Deferred

Per `02-VALIDATION.md`'s "Manual-Only Verifications" section, six items are deferred to PHN16-72 hardware testing:

1. **PRIV-03 dialog text** — visual confirmation that the polkit auth dialog reads "Authentication is required to change the Acer performance profile" instead of the generic `/usr/bin/bash` fallback. Structurally proved by the `<message>` smoke + verbatim string match in XML.
2. **PRIV-04 interactive cancellation** — pressing Escape on the polkit dialog yields exit 126 → CLI exit 0 with "Authentication cancelled". The 126 translation is structurally present in `run_privileged` + `cmd_set`.
3. **PRIV-04 `auth_admin_keep` second-invocation** — second invocation within the ~5 min keep-alive window does not re-prompt. Per VALIDATION.md (P2-NEW-05), no observable signal from subprocess; UAT-only.
4. **CLI-03 real read-back mismatch under PPD** — requires PPD active on PHN16-72 with `platform_profile` writable.
5. **CLI-06 root install execution** — side effects (writing `/etc/modprobe.d/99-acer-wmi.conf`, `systemctl daemon-reload`, `systemctl enable acer-performance.service`, `update-initramfs -u`) make this a one-shot UAT step.
6. **Bundler stack-trace usability** — `dist/acercontrol` stack traces should reference comprehensible line numbers despite the comment-prefix approach. UAT verifies the developer experience.

These are tracked in `02-VALIDATION.md` and should be checked off during the manual UAT sweep before phase sign-off.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `verify_no_gtk.py` regex missed `import gi` at end-of-line**
- **Found during:** Task 2 functional smoke (injected-gi test failed with rc=0)
- **Issue:** Research pattern's regex `import\s+gi(\.|\s)` requires `.` or whitespace AFTER `gi`. A bare `import gi\n` (no trailing whitespace) didn't match because `splitlines()` strips the newline before the regex sees the line.
- **Fix:** Changed `(\.|\s)` to `(\b|\.)` — `\b` matches end-of-string AND word-boundary contexts. Verified against `import gi`, `from gi.repository import Gtk`, `import gibberish` (no false positive), and `# from gi import comment` (comment skip).
- **Files modified:** `tools/verify_no_gtk.py`
- **Commit:** included in `930d2a2` (Task 2)

**2. [Rule 1 — Bug] Bundler `_INTRA_IMPORT` regex missed multi-line parenthesised imports**
- **Found during:** Task 5 first bundle attempt (IndentationError at concatenated `core.py`)
- **Issue:** Both `core.py` and `cli.py` use `from acercontrol.X import (\n  ...,\n  ...\n)` parenthesised multi-line forms. Research regex only matched single-line `from acercontrol.X import .+`; commented out only the first line, leaving `Profile,\n  PROFILES,\n)` as raw code → IndentationError.
- **Fix:** Added a `from\s+acercontrol(\.\w+)?\s+import\s+\([^)]*\)` alternative to `_INTRA_IMPORT`; updated `_strip_intra_imports` to comment-prefix EVERY line of multi-line matches (not just the first).
- **Files modified:** `tools/bundle_cli.py`
- **Commit:** included in `c769d79` (Task 5)

**3. [Rule 1 — Bug] Bundler concat semantics — qualified module references break + features.py `__main__` fires before cli.main**
- **Found during:** Task 5 second bundle attempt (NameError: `core` not defined; subsequently NameError: `_current_profile_ui` not defined)
- **Issue:** When intra-imports are commented out:
  - `features.py` line 19's `from acercontrol import core` is stripped → all `core.X` references at runtime become `NameError: name 'core' is not defined`.
  - `core.py` line 15's `from acercontrol import sysfs as _sysfs` → `_sysfs.X` accesses break.
  - `core.py` line 16's `from acercontrol.profiles import (current_profile_ui as _current_profile_ui, …)` aliases stripped → `_current_profile_ui` doesn't exist.
  - Additionally, `features.py`'s `if __name__ == "__main__": sys.exit(_print_report(probe()))` fires BEFORE the bundler-appended `sys.exit(main())` shim, short-circuiting the CLI.
- **Fix (P2-NEW-08):**
  - Added `_MAIN_BLOCK` regex + `_strip_main_blocks` to comment out per-source `if __name__ == "__main__":` blocks.
  - Added `SELF_ALIASES` block (after HEADER) that binds module names (`core`, `sysfs`, `_sysfs`, `features`, `profiles`, `privilege`) to `_bundle_sys.modules[__name__]` so qualified access resolves to the bundle's own namespace.
  - Added `POST_PROFILES_ALIASES` block (injected after `profiles.py` in BUNDLE_ORDER) that binds `_current_profile_ui = current_profile_ui` and `_available_profiles = available_profiles` to bridge `as _name` import aliases used inside `core.py`.
- **Files modified:** `tools/bundle_cli.py`
- **Commit:** included in `c769d79` (Task 5)
- **Pattern carry-forward:** if Phase 3+ adds new `acercontrol/<module>.py` files that use qualified `<other>.X` access in their bodies, add the alias to `SELF_ALIASES`; if they introduce `as _name` aliases, add a corresponding bridge to `POST_PROFILES_ALIASES`.

**4. [Rule 1 — Cosmetic] `subprocess.run` formatting in `acercontrol-manage-service`**
- **Found during:** Task 2 acceptance grep gate (regex `subprocess\.run\(\[\s*"systemctl"` requires same-line opening)
- **Issue:** Original line-wrapped `subprocess.run(\n  ["systemctl", …],\n  capture_output=…)` failed the grep gate.
- **Fix:** Reformatted to `subprocess.run(["systemctl", action, service],\n  capture_output=…)` — semantically identical, satisfies the regex.
- **Files modified:** `libexec/acercontrol-manage-service`
- **Commit:** included in `930d2a2` (Task 2)

**5. [Rule 1 — Trace] Missing `CLI-07` traceability marker in `acercontrol/cli.py` docstring**
- **Found during:** Task 4 acceptance gate (grep -q 'CLI-07' failed)
- **Issue:** Plan invariant requires both `CLI-01` and `CLI-07` substrings in the cli.py docstring. Original docstring only had `CLI-01..07` (where `..` was treated as part of the version range, not as a literal `CLI-07` substring at character level).
- **Fix:** Updated docstring to explicitly call out `CLI-07 stdlib-only` and `CLI-07 invariant; verify_no_gtk.py guards this`.
- **Files modified:** `acercontrol/cli.py`
- **Commit:** included in `0c4e88a` (Task 4)

### Architectural Changes

None — no Rule 4 checkpoints raised. All discovered issues were Rule 1 (bug/cosmetic fixes within scope of the changes).

## Authentication Gates

None — Phase 2's smoke runner uses `--dry-run` for all privileged paths. Real privileged invocations (cmd_set without --dry-run, cmd_install as root) defer to Manual UAT on PHN16-72.

## Known Stubs

None. Every function in the public API has a real implementation. Stubs that exist are intentional and load-bearing:

- **`cmd_install` step (c)** is best-effort / continue-on-fail because the `acer-performance.service` unit ships in Phase 6. The wrapper is in place; the service-not-installed warning surfaces in the user's stderr but doesn't fail the install. This is documented in code, in the Pattern 8 install JSON `service_enabled` field, and in Manual UAT items.
- **`set-boot-profile` and `manage-service` wrappers + polkit actions** exist but have no Phase 2 CLI subcommand — they're for Phase 6 GUI consumption. Smoke covers their EX_USAGE=64 rejection paths via direct invocation.
- **`PROJECT_ROOT` PYTHONPATH bootstrap in tools/smoke_phase2.py** is intentional — same idiom as Phase 1's smoke_phase1.py to allow `python3 tools/smoke_phase2.py` to work without the user pre-setting `PYTHONPATH=.`.

## Threat Flags

No new threat surface beyond what the `<threat_model>` block in `02-01-PLAN.md` already enumerates (T-02-01..12). The threat register's mitigations are realised in code as documented above. No surprise endpoints, no new auth paths, no schema changes at trust boundaries.

The CLI surface itself is read-mostly (status/get/list/temps are pure reads; install in non-root mode is print-only). The two privileged write paths (`set` + `install` as root) flow through the wrapper boundary — the trust model is the canonical polkit pattern + defense-in-depth allowlist.

## OQ-01 Carry-Forward (for Phase 6)

`libexec/acercontrol-manage-service` allowlist locks the literal `acer-performance.service`:

```python
ALLOWED_SERVICES = ("acer-performance.service",)
```

If Phase 6 ships the unit as a TEMPLATED form (`acer-performance@.service` per BOOT-01 in REQUIREMENTS.md), the wrapper allowlist must extend to cover `(action, service-template-instance)` shapes. RESEARCH `<open_questions>` (lines 1933-1940) recommends Phase 6 ship a NON-templated unit that reads `/etc/default/acercontrol` (the file `acercontrol-set-boot-profile` already writes via Phase 2) — in which case no Phase 2 changes would be needed. The carry-forward comment in `acercontrol-manage-service`'s docstring flags this for the Phase 6 planner.

## Self-Check: PASSED

Verified after writing this SUMMARY:

- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/privilege.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/cli.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-setprofile` — FOUND (executable)
- `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-set-boot-profile` — FOUND (executable)
- `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-manage-service` — FOUND (executable)
- `/Users/sushilkumarsahani/Desktop/AcerControl/data/org.acercontrol.policy` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/tools/verify_no_gtk.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/tools/bundle_cli.py` — FOUND
- `/Users/sushilkumarsahani/Desktop/AcerControl/tools/smoke_phase2.py` — FOUND (executable)
- `/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml` — MODIFIED (append-only)
- Commit `0cff116` (Task 1 privilege helper) — FOUND
- Commit `930d2a2` (Task 2 wrappers + verify_no_gtk) — FOUND
- Commit `4bffba4` (Task 3 polkit policy) — FOUND
- Commit `0c4e88a` (Task 4 CLI + project.scripts) — FOUND
- Commit `c769d79` (Task 5 bundler) — FOUND
- Commit `7f07109` (Task 6 smoke runner) — FOUND

`python3 tools/smoke_phase2.py` → exit 0, prints `Phase 2 smoke: 28/28 passed`, no traceback.

`PYTHONPATH=. python3 -c "from acercontrol.cli import main; from acercontrol.privilege import run_privileged"` → exit 0.

Zero `^import gi` / `^from gi` lines under `acercontrol/`, `libexec/`, or `tools/` (excluding comments).

`pyproject.toml` declares `[project.scripts] acercontrol = "acercontrol.cli:main"`; existing Phase 1 sections untouched; zero runtime dependencies preserved.

`acercontrol/__init__.py` is unchanged — Phase 2 does not modify the package re-export surface.

## Next Phase

Phase 3 (GUI Shell + Failure States + PPD Banner) consumes Phase 2's privilege boundary unchanged. The `Adw.Application` shell with `application_id="org.acercontrol.AcerControl"`, `Adw.StatusPage` failure-mode routing for `features.probe()` blocking failures, and the persistent `Adw.Banner` for PPD detection. Phase 3 will primarily import `acercontrol.core` directly (same process), but may also invoke `python3 -m acercontrol.cli get --json` for diagnostics export. The `PrivilegedResult` shape from `acercontrol.privilege` is consumed by Phase 4 (profile control loop) as-is.
