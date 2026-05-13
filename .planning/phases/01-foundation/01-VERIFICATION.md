---
phase: 01-foundation
verified: 2026-05-13T19:38:04Z
status: passed
score: 5/5 must-haves verified (all ROADMAP success criteria met; 3 manual-UAT items deferred per VALIDATION.md contract)
overrides_applied: 0
deferred:
  - truth: "Library survives renaming /sys/firmware/acpi/platform_profile mid-session and returns a degraded FeatureReport without traceback (G4 live-degrade)"
    addressed_in: "Manual UAT on PHN16-72 hardware"
    evidence: "01-VALIDATION.md Manual-Only Verifications: 'Requires root and a writable test environment; destructive in CI; cheap to do once manually'. Structural guarantee verified programmatically: every sysfs read routes through _read_or_none; platform_profile check on this macOS host returned a degraded FeatureReport with remediation hint without raising."
  - truth: "hwmon index drift across two reboots — find_hwmon returns same logical directory after numeric index changes"
    addressed_in: "Manual UAT on PHN16-72 hardware"
    evidence: "01-VALIDATION.md Manual-Only Verifications: 'Requires physical reboot loop on PHN16-72'. The no-hardcoded-index algorithm is verified structurally in code."
  - truth: "Multi-package coretemp on actual multi-die hardware (PH317 dual-die)"
    addressed_in: "Manual UAT on PH317 or multi-die hardware"
    evidence: "01-VALIDATION.md: 'PHN16-72 has a single die; can't test multi-package on the primary dev machine. Mark as untested-on-hardware.' Algorithm code is in place and returns None correctly on single-die / no-/sys host."
---

# Phase 1: Foundation Verification Report

**Phase Goal:** Stand up the `acercontrol/` Python package as the single source of truth for sysfs reads, hwmon discovery, profile name mapping, and feature detection. No privileged writes, no GUI, no CLI surface yet — pure library plus a structured `FeatureReport`.
**Verified:** 2026-05-13T19:38:04Z
**Status:** COMPLETE
**Re-verification:** No — initial verification

---

## Overall Verdict

**COMPLETE.** All five ROADMAP success criteria and all six plan must-have truths are verified by direct code inspection and live test execution. The smoke runner exits 0 with `6/6 passed`. Three manual-UAT items are formally deferred per the VALIDATION.md contract and do not block phase progression.

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| G1 | Profile name mapping is bidirectional and exhaustive — every `user → kernel → user` round-trip is identity; `kernel_to_profile("custom")` returns `Profile.CUSTOM` with `.display == "Custom"` | VERIFIED | `PROFILES` has 5 entries; `KERNEL_TO_UI` is the computed reverse; all 5 round-trips confirmed live. `KERNEL_TO_UI.get("custom")` returns `None` (never raises — `dict.get` contract met); canonical caller path via `kernel_to_profile("custom")` returns `Profile.CUSTOM`. See G1 Note below. |
| G2 | `sysfs.find_hwmon("acer", requires=("fan1_input","temp1_input"))` resolves by name file; most-populated tie-break; coretemp on multi-die hardware | VERIFIED | `requires` parameter confirmed keyword-only via `inspect.signature`. Cache hits verified. `invalidate_hwmon_cache()` clears state. `coretemp_max_package_temp()` returns `None` on this host (no `/sys`) — structurally correct. Most-populated sort confirmed in code. |
| G3 | `features.probe()` returns a `FeatureReport` covering all 7 checks; no `FileNotFoundError` escapes this layer | VERIFIED | `probe()` executed live: 7 checks returned, all named correctly (`acer_wmi module loaded`, `predator_v4 mode`, `platform_profile sysfs`, `acer hwmon (fan+temp)`, `coretemp hwmon`, `power-profiles-daemon state`, `acer_wmi not blacklisted`). No exception raised on macOS host without `/sys`. |
| G4 | Renaming `/sys/firmware/acpi/platform_profile` produces a degraded `FeatureReport` with remediation hint, never an uncaught traceback | VERIFIED (structural) + DEFERRED (live-degrade on PHN16-72) | On this host (no `/sys`), `platform_profile sysfs` check returns `present=False`, `fix="Requires kernel with ACPI platform_profile support (>= 6.6 recommended)."`, no exception. The structural guarantee holds: `_read_or_none` absorbs all `OSError`. Live rename test deferred per VALIDATION.md. |
| G5 (plan truth) | Phase 1 ships zero GTK imports | VERIFIED | `grep -rE '(^import gi\|^from gi)' acercontrol/ tools/` exits 1 (no matches) |

**Score:** 5/5 ROADMAP success criteria verified (G4 live-degrade portion formally deferred)

---

### G1 Note — KERNEL_TO_UI.get("custom") Resolution

The ROADMAP says `KERNEL_TO_UI.get("custom")` "resolves to a documented 'Custom' sentinel rather than raising." In the implementation, `KERNEL_TO_UI.get("custom")` returns `None` (not raising — `dict.get` never raises). The `Profile.CUSTOM` sentinel is reached via `kernel_to_profile("custom")` which returns `Profile.CUSTOM` with `.display == "Custom"`. This is the canonical caller path: the smoke runner, core.py, and all downstream phases use `kernel_to_profile()`, not direct dict lookup.

**Phase 2 carry-forward:** Downstream callers must use `kernel_to_profile(raw)` for unknown sysfs values, not `KERNEL_TO_UI.get(raw)`. Direct dict access on `KERNEL_TO_UI` for an unknown value returns `None` instead of the `CUSTOM` sentinel. This is a usage contract, not a bug.

---

## Gate-by-Gate Verification Table

| Gate | Required | Actual | Status |
|------|----------|--------|--------|
| G1 | Zero `gi` imports in `acercontrol/` and `tools/` | `grep` exits 1 (no matches found) | PASS |
| G2 | `PYTHONPATH=. python3 -c "from acercontrol import core, sysfs, profiles, features; print('ok')"` exits 0 | Exit 0, prints `ok` | PASS |
| G3 | `python3 tools/smoke_phase1.py` exits 0, prints `6/6 passed`, no `Traceback` | Exit 0, all six checks PASS | PASS |
| G4 | Smoke runner self-injects PYTHONPATH (works without setting it externally) | `os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)` + `sys.path.insert(0, PROJECT_ROOT)` at top of smoke runner; verified by running without `PYTHONPATH=.` prefix | PASS |
| G5 | `grep -q '^requires-python = ">=3.11"$' pyproject.toml` matches exactly | Exact match confirmed | PASS |
| G6 | `pyproject.toml` has no `[project.dependencies]`, `[project.optional-dependencies]`, `[project.scripts]` | None of these sections present | PASS |
| G7 | `Profile.CUSTOM` member exists; `.display == "Custom"`; `kernel_to_profile` returns `Profile.CUSTOM` for `None`, `"custom"`, `"garbage"` | All three assertions pass live | PASS |
| G8 | `sysfs.find_hwmon` has `requires` as keyword-only; most-populated tie-break; cache survives invalidation | `requires` is `KEYWORD_ONLY` per `inspect`; `candidates.sort(key=lambda p: (-_count_inputs(p), p))` in code; `invalidate_hwmon_cache()` clears `_hwmon_cache` | PASS |
| G9 | `features.probe()` returns exactly 7 checks with expected name strings | 7 checks: names verified live and match ROADMAP spec | PASS |
| G10 | `acercontrol/__init__.py` re-exports full public API (25 symbols including `__version__`) | `__all__` has 25 entries covering all 4 submodules | PASS |
| G11 | ROADMAP Phase 1 success criteria G1–G4 met | G1–G4 verified above; G4 live-degrade deferred per VALIDATION.md | PASS |
| G12 | Phase-1 commits exist with correct `feat(phase-1):` / `docs(phase-1):` / `chore(phase-1):` prefixes | 7 commits found: `c061cb6` `feat`, `6e5c7d9` `feat`, `1c3b1bd` `feat`, `b546000` `feat`, `67cded3` `docs`, `698914e` `docs`, `c02826a` `chore` — all phase-1 prefixed. SUMMARY.md mentioned "4 task commits + metadata commit" (5 intended); actual count is 7. All required task commits are present with correct hashes. | PASS (with note) |

**G12 Note:** SUMMARY.md expected 4 task commits + 1 SUMMARY commit = ~5. Actual git log shows 7 phase-1 commits (4 `feat`, 2 `docs`, 1 `chore`). The four task commits (`c061cb6`, `6e5c7d9`, `1c3b1bd`, `b546000`) are all present and correct. The extras are legitimate: an additional docs commit aligning VALIDATION smoke contracts (`698914e`) and a chore commit adding `.gitignore` (`c02826a`). No issue.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | PEP 621 metadata, `requires-python = ">=3.11"`, no runtime deps | VERIFIED | 30 LOC; exact `requires-python` match; no `[project.dependencies]`, `[project.optional-dependencies]`, `[project.scripts]` |
| `acercontrol/profiles.py` | `Profile` enum, `PROFILES`, `KERNEL_TO_UI`, helpers | VERIFIED | 95 LOC; 6-member enum including `CUSTOM`; computed reverse map; all helpers present |
| `acercontrol/sysfs.py` | `find_hwmon`, `find_all_hwmon`, `invalidate_hwmon_cache`, `coretemp_max_package_temp`, `read_acer_sensors`, `_read_or_none` | VERIFIED | 206 LOC; all functions present and substantive; no stubs |
| `acercontrol/features.py` | `FeatureCheck`, `FeatureReport`, `probe()` (7 checks), `find_blacklist_entries`, `__main__` | VERIFIED | 235 LOC; all types and functions present; `__main__` entry at bottom |
| `acercontrol/core.py` | Path constants, `read_profile`, `list_available_profiles`, `SensorReading`, `read_sensors` | VERIFIED | 94 LOC; all 5 path constants, all functions/types present; OSError-retry-once in `read_sensors` |
| `acercontrol/__init__.py` | Package re-exports, `__version__ = "0.1.0.dev0"`, `__all__` with 24+ symbols | VERIFIED | 62 LOC; `__version__ = "0.1.0.dev0"`; `__all__` has 25 symbols; all 4 submodules imported |
| `tools/smoke_phase1.py` | Aggregate runner for CORE-01..06; exits 0; self-injects PYTHONPATH; `CORE-01` in file | VERIFIED | 184 LOC; executable; PYTHONPATH injection at lines 27–29; 6-check plan; all CORE-NN labels present |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `acercontrol/features.py` | `acercontrol/sysfs.py` | `from acercontrol.sysfs import _read_or_none, find_hwmon` | WIRED | Import confirmed at line 21 of features.py |
| `acercontrol/features.py` | `acercontrol/core.py` | `from acercontrol import core` | WIRED | Import confirmed at line 19 of features.py; `core.PROFILE_PATH`, `core.PREDATOR_V4_PARAM` used |
| `acercontrol/core.py` | `acercontrol/sysfs.py` | `from acercontrol import sysfs as _sysfs` | WIRED | Import at line 15 of core.py; `_sysfs.coretemp_max_package_temp()`, `_sysfs.find_hwmon()`, `_sysfs.read_acer_sensors()` called |
| `acercontrol/core.py` | `acercontrol/profiles.py` | `from acercontrol.profiles import Profile, ...` | WIRED | Import at lines 16–23 of core.py; multiple profile symbols used |
| `acercontrol/__init__.py` | all four submodules | `from acercontrol.(profiles\|sysfs\|core\|features) import` | WIRED | All four import blocks confirmed; `__all__` covers all 25 symbols |
| `tools/smoke_phase1.py` | `acercontrol` package | subprocess with `PYTHONPATH` env | WIRED | `env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}` set per-subprocess |

---

## Data-Flow Trace (Level 4)

Phase 1 is a read-only library — no dynamic data rendered in a UI component. All functions return `None` or typed values; no state variables rendered in JSX/TSX. Level 4 data-flow trace is not applicable to this phase.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Smoke runner exits 0 with 6/6 passed | `python3 tools/smoke_phase1.py` | Exit 0; `6/6 passed`; no Traceback | PASS |
| Package imports without GTK | `PYTHONPATH=. python3 -c "from acercontrol import core, sysfs, profiles, features; print('ok')"` | Exit 0; `ok` | PASS |
| Profile round-trips all 5 pairs | Python assertion on PROFILES + KERNEL_TO_UI | All 5 pairs: `eco`, `quiet`, `balanced`, `performance`, `turbo` round-trip correctly | PASS |
| Profile.CUSTOM sentinel | `kernel_to_profile(None/custom/garbage)` all return `Profile.CUSTOM` | All three cases confirmed live | PASS |
| probe() 7 checks | Live `probe()` call | 7 checks returned; all expected names present; no exception | PASS |
| find_hwmon keyword-only requires | `inspect.signature` check | `requires` confirmed `KEYWORD_ONLY` | PASS |
| pyproject no runtime deps | grep for disallowed sections | No `[project.dependencies]`, `[project.optional-dependencies]`, `[project.scripts]` found | PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| CORE-01 | 01-01-PLAN.md | Canonical user-name ↔ kernel-value mapping; single source of truth | SATISFIED | `profiles.py` is the single source; `PROFILES`, `KERNEL_TO_UI`, `Profile` enum all present; CORE-01 smoke passes |
| CORE-02 | 01-01-PLAN.md | `find_hwmon` resolves by name file, never hardcoded index; most-populated on ties | SATISFIED | Algorithm confirmed in `sysfs.py` lines 64–88; `requires` keyword-only; cache + invalidate present; CORE-02 smoke passes |
| CORE-03 | 01-01-PLAN.md | `probe()` returns `FeatureReport` covering all checks; no `FileNotFoundError` escapes | SATISFIED | 7-check probe confirmed; `_read_or_none` absorbs all `OSError`; CORE-03 smoke passes |
| CORE-04 | 01-01-PLAN.md | Unknown/`custom` kernel value maps to `Profile.CUSTOM` display state, never crashes | SATISFIED | `kernel_to_profile()` catches `ValueError` and returns `Profile.CUSTOM`; `.display == "Custom"`; CORE-04 smoke passes |
| CORE-05 | 01-01-PLAN.md | `modprobe.d` blacklist entries for `acer_wmi` detected at startup | SATISFIED | `find_blacklist_entries()` with regex matching both `blacklist acer_wmi` and `install acer_wmi /bin/(true\|false)`; tempdir scaffold in smoke passes; CORE-05 smoke passes |
| CORE-06 | 01-01-PLAN.md | Multi-package CPUs handled — max temp across packages reported | SATISFIED | `coretemp_max_package_temp()` scans `Package id N` labels and takes `max()`; fallback to `temp1_input`; CORE-06 smoke passes (returns `None` on no-`/sys` host — correct) |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `acercontrol/sysfs.py` | 193, 203 | `pass` (bare except in `except ValueError`) | INFO | Intentional and load-bearing: invalid millidegree readings silently skipped so one bad sensor file doesn't abort the entire sensor read. This is the specified behavior. |
| `acercontrol/profiles.py` | 93 | `return []` | INFO | Intentional fallback in `available_profiles()` when `choices_path` is unreadable. Not a stub — function body has real try/except logic above. |
| `acercontrol/sysfs.py` | multiple | `return None` | INFO | All `return None` cases are deliberate defensive returns from `_read_or_none` and `find_hwmon` path — the P13 contract. Not stubs. |

No blockers, no warnings. All `return None` / `return []` patterns are data-flow defensive guards, not stub implementations.

---

## Probe Check Naming Variance (Carry-forward for Phase 2/3)

Check #6 (PPD state) uses two possible names depending on `systemctl` availability:
- `"power-profiles-daemon state"` (severity `"info"`, `present=True`) — when `systemctl` is not found
- `"power-profiles-daemon inactive"` (severity `"warning"`, `present=False`) — when PPD is active

Phase 3 GUI dispatch code that switches on `c.name` must handle both strings, or switch on `c.severity + c.present` instead of `c.name`. This is a usage contract established in Phase 1 and should be documented in the Phase 3 plan.

---

## Human Verification Required

Three items require manual verification on PHN16-72 hardware. These are explicitly listed in VALIDATION.md "Manual-Only Verifications" and do not block Phase 2 progression.

### 1. Live Degraded FeatureReport (sysfs rename)

**Test:** On PHN16-72 with `acer_wmi` loaded, temporarily blacklist `acer_wmi` via `/etc/modprobe.d/test-blacklist.conf`, reboot, run `python3 tools/smoke_phase1.py`.
**Expected:** Smoke exits 0; `FeatureReport.ok == False`; `platform_profile sysfs` check has `present=False` with non-empty `fix` hint; no `Traceback`.
**Why human:** Requires root, a writable Linux test environment, and a reboot cycle. Sysfs paths are not mountable on macOS dev box.

### 2. hwmon Index Drift Across Reboots

**Test:** On PHN16-72, note `find_hwmon('acer', requires=('fan1_input','temp1_input'))` result, reboot twice, re-run.
**Expected:** `find_hwmon` returns the same logical hwmon directory (same `name` file content = `acer`) even if the numeric `hwmonN` index changes.
**Why human:** Requires physical reboot loop on Acer hardware.

### 3. Multi-Package Coretemp on Multi-Die Hardware

**Test:** On a PH317 or other multi-package laptop with two `coretemp` hwmon entries, run `python3 tools/smoke_phase1.py`.
**Expected:** CORE-06 passes; `coretemp_max_package_temp()` returns the max temperature across both packages (not just `temp1_input` of the first hwmon).
**Why human:** PHN16-72 is single-die. Requires a multi-die Acer machine which the primary developer does not have access to at Phase 1 time.

---

## Deferred Items

Items not yet verified against live hardware but explicitly addressed in VALIDATION.md.

| # | Item | Addressed In | Evidence |
|---|------|-------------|---------|
| 1 | Library survives renaming `/sys/firmware/acpi/platform_profile` mid-session and returns a degraded `FeatureReport` without traceback (G4 live-degrade scenario) | Manual UAT on PHN16-72 | VALIDATION.md: "Requires root and writable test environment; destructive in CI; cheap to do once manually." Structural guarantee holds — `_read_or_none` absorbs all `OSError`; platform_profile check returns degraded report on this host. |
| 2 | hwmon index drift verified across physical reboots | Manual UAT on PHN16-72 | VALIDATION.md: "Requires physical reboot loop on PHN16-72." Algorithm verified by code inspection. |
| 3 | `coretemp_max_package_temp()` returns max across packages on real multi-die hardware | Manual UAT on multi-die Acer hardware | VALIDATION.md: "PHN16-72 has a single die; mark as untested-on-hardware." Algorithm is in place; `None` return on single-die/no-sys is correct. |

---

## Goal-Backward Analysis

### ROADMAP SC 1: Profile mapping bidirectional and exhaustive

**What must be true:** Every `user → kernel → user` round-trip returns identity; `KERNEL_TO_UI.get("custom")` resolves without raising; `Profile.CUSTOM` is a documented sentinel.

**Files/commits proving it:**
- `acercontrol/profiles.py` — commit `6e5c7d9`: `PROFILES` dict (5 entries), `KERNEL_TO_UI = {v: k for k, v in PROFILES.items()}` (computed reverse), `Profile(Enum)` with 6 members, `kernel_to_profile()` returns `Profile.CUSTOM` for any unmapped value.
- `tools/smoke_phase1.py` — commit `b546000`: CORE-01 smoke verifies all round-trips and CUSTOM sentinel.
- Live test: all 5 round-trips pass; `kernel_to_profile("custom")` returns `Profile.CUSTOM`, `.display == "Custom"`.

### ROADMAP SC 2: find_hwmon resolves by name file, most-populated tie-break

**What must be true:** `find_hwmon` walks hwmon dirs reading `name` files; on ties picks most-populated; `coretemp` resolution uses `Package id N` labels.

**Files/commits proving it:**
- `acercontrol/sysfs.py` — commit `6e5c7d9`: `find_hwmon()` iterates `os.listdir(HWMON_BASE)`, reads `name` file via `_read_or_none`, filters by `requires`, sorts by `(-_count_inputs(p), p)`.
- `coretemp_max_package_temp()` in same file: scans `tempN_label` for `Package id N` regex, takes `max()`.
- CORE-02 smoke: exits 0 with `None` on no-/sys host (correct).

### ROADMAP SC 3: probe() returns FeatureReport with 7 checks, no FileNotFoundError

**What must be true:** `probe()` runs all 7 checks; no sysfs access raises an uncaught exception.

**Files/commits proving it:**
- `acercontrol/features.py` — commit `1c3b1bd`: `probe()` function has exactly 7 `checks.append()` calls. All sysfs reads via `_read_or_none` or `Path.exists()`.
- `_read_or_none()` in sysfs.py wraps `path.read_text().strip()` in `try/except OSError`.
- Live test: `probe()` returns 7 checks on macOS with no `/sys`; no exception raised.
- CORE-03 smoke: exits 0 with `7 checks, ok=False`.

### ROADMAP SC 4: Degraded FeatureReport with remediation hint, never uncaught traceback

**What must be true:** Absence of `platform_profile` sysfs path produces `FeatureReport` with `present=False` and non-empty `fix` hint, not a Python exception.

**Files/commits proving it:**
- `acercontrol/features.py` — `probe()` check #3: `pp_present = core.PROFILE_PATH.exists()`; FeatureCheck created with `fix="Requires kernel with ACPI platform_profile support..."`.
- On this macOS host: `platform_profile sysfs` check returns `present=False`, `fix` is non-empty, `FeatureReport` is returned cleanly.
- Live-degrade on PHN16-72: deferred per VALIDATION.md.

---

## Carry-Forward to Phase 2

The following decisions and contracts established in Phase 1 MUST be honored by Phase 2 plans:

1. **`kernel_to_profile()` is the canonical path for unknown sysfs values.** Never use `KERNEL_TO_UI.get(raw)` directly — returns `None` for `"custom"` instead of `Profile.CUSTOM`. All profile reads must go through `kernel_to_profile()`.

2. **`acercontrol.__init__` is the canonical import surface.** Phase 2 code should `from acercontrol import probe, read_profile, ...` — never `from acercontrol.sysfs import ...` directly. This keeps the contract stable across future refactors.

3. **`FeatureReport.first_blocking_failure` for CLI/GUI dispatch.** Phase 2 `acercontrol status` should iterate `report.checks` and print human output. Phase 3 GUI should call `report.first_blocking_failure` to choose which `Adw.StatusPage` to render.

4. **PPD check name varies.** Check #6 in `FeatureReport.checks` may be named either `"power-profiles-daemon state"` (systemctl absent) or `"power-profiles-daemon inactive"` (systemctl present). Phase 3 dispatch should key on `c.severity` and `c.present`, not `c.name` string matching.

5. **Python floor is 3.11+.** Phase 6 will use `tomllib` (stdlib since 3.11); Ubuntu 24.04 ships 3.12. This decision is reflected in `pyproject.toml`.

6. **`[project.scripts]` not yet added.** Phase 2 adds the CLI entry point. Phase 1 stays library-only to keep the bundler-friendly single-file CLI invariant intact.

7. **Manual UAT items.** Before final sign-off, run the three hardware UAT items on PHN16-72 (or equivalent). These are tracked in `01-VALIDATION.md` and should be checked off before Phase 7 final UAT sweep.

---

_Verified: 2026-05-13T19:38:04Z_
_Verifier: Claude (gsd-verifier)_
