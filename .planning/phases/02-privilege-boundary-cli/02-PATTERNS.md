# Phase 02: Privilege Boundary + CLI — Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 10 (9 new, 1 modified)
**Analogs found:** 8 / 10 with concrete repo analogs; 2 flagged "shape-only" or "no analog"

PATTERNS.md's value-add over RESEARCH.md is the cross-reference to *existing repo code* (acercontrol/, tools/) — not a restatement of the target skeletons. Verbatim target code lives in RESEARCH.md §Patterns 1–11; PATTERNS.md cites those by line number and pairs each new file with its closest in-repo analog and the lines to copy from.

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `acercontrol/privilege.py` (new) | helper module | argv → pick elevation → subprocess.run([pkexec\|sudo, wrapper, …]) → PrivilegedResult | `acercontrol/features.py` (frozen dataclass + `_ppd_active` subprocess pattern) | role-match (strong) |
| `acercontrol/cli.py` (new) | entry-point | argparse → subcommand dispatch → core/privilege calls → stdout/exit-code | `acercontrol/features.py::_print_report` + `acercontrol/__init__.py` re-exports | role-match (strong) |
| `libexec/acercontrol-setprofile` (new, +x) | privileged wrapper | argv → allowlist re-validate → `open(PROFILE_PATH, "w").write(value)` | `acercontrol/profiles.py` (allowlist source-of-truth) + `acercontrol/sysfs.py::_read_or_none` (inverted: read → write, same `OSError` discipline) | role-match |
| `libexec/acercontrol-set-boot-profile` (new, +x) | privileged wrapper | argv → allowlist → atomic `tempfile.mkstemp` + `os.rename` → `/etc/default/acercontrol` | same allowlist analog; **no codebase analog** for atomic write | partial |
| `libexec/acercontrol-manage-service` (new, +x) | privileged wrapper | argv → (action × service) allowlist → `subprocess.run(["systemctl", action, svc], timeout=20)` | `acercontrol/features.py::_ppd_active` (exact same `subprocess.run + timeout + FileNotFoundError + TimeoutExpired` triple) | exact (data flow) |
| `data/org.acercontrol.policy` (new) | config (XML) | static declaration → polkitd reads at install time | **no codebase analog** (no XML configs exist) | none — use RESEARCH Pattern 6 verbatim |
| `pyproject.toml` (modify) | build config | TOML metadata | existing `pyproject.toml` (Phase 1) | append-only delta |
| `tools/bundle_cli.py` (new) | build-tool | read 6 source files → strip intra-imports → concat → write `dist/acercontrol` + chmod 0o755 | `tools/smoke_phase1.py:24-29` (`PROJECT_ROOT` resolution); **no full analog** for concat/bundle | shape-only |
| `tools/verify_no_gtk.py` (new) | build-tool / gate | argv files → regex scan each line → exit 0/1 | `acercontrol/features.py::find_blacklist_entries` (near-exact: precompiled regex, multi-file iteration, line-accumulator return shape, OSError-tolerant) | exact |
| `tools/smoke_phase2.py` (new, +x) | smoke-runner | scenario list → subprocess.run each → failure accumulator → exit 0/1 | `tools/smoke_phase1.py` (entire file) | exact |

---

## Pattern Assignments

### `acercontrol/privilege.py` (helper, subprocess+dataclass)

**Analog A:** `acercontrol/features.py` lines 30–56 — frozen dataclass with computed properties; this is the shape `PrivilegedResult` should mirror.

```python
# acercontrol/features.py:30-56
@dataclass(frozen=True)
class FeatureCheck:
    """Single feature-probe result."""
    name: str
    present: bool
    detail: str = ""
    fix: str = ""
    severity: Severity = "blocking"


@dataclass(frozen=True)
class FeatureReport:
    """Full environment probe — consumed by CLI/GUI failure-mode dispatch."""
    checks: tuple[FeatureCheck, ...]
    blacklist_entries: tuple[tuple[str, str], ...] = ()  # (file_path, matched_line)

    @property
    def ok(self) -> bool:
        """True iff every 'blocking' check is present."""
        return all(c.present for c in self.checks if c.severity == "blocking")

    @property
    def first_blocking_failure(self) -> FeatureCheck | None:
        for c in self.checks:
            if c.severity == "blocking" and not c.present:
                return c
        return None
```

**Apply:** `PrivilegedResult` uses the same `@dataclass(frozen=True)` discipline with `tuple[str, ...]` (not list) for `argv`, plus a derived/computed `cancelled` bool (set at construction since callers don't recompute it like `ok` is).

**Analog B:** `acercontrol/features.py` lines 82–96 — `_ppd_active`. This is the subprocess-with-timeout-and-defensive-exception pattern that `run_privileged` extends.

```python
# acercontrol/features.py:82-96
def _ppd_active() -> bool | None:
    """Returns True/False if systemctl was reachable; None if systemctl is missing.

    Per SUMMARY.md decision #1 / pitfall P2: PPD detection is a probe input,
    not a write trigger. Phase 1 only reports state.
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "power-profiles-daemon.service"],
            capture_output=True, text=True, timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    # systemctl is-active exits 0 only when active.
    return result.returncode == 0
```

**Apply:** `run_privileged` uses the same `try / subprocess.run(capture_output=True, text=True, timeout=…) / except (FileNotFoundError, subprocess.TimeoutExpired)` triple. Extension: `run_privileged` distinguishes `TimeoutExpired` (returncode=124) from `FileNotFoundError` (returncode=127) and adds the pkexec 126 → `cancelled=True` translation (see RESEARCH §Pattern 1 exit-code table, lines 418–432).

**Target skeleton:** RESEARCH §Pattern 1 lines 223–416 — full verbatim source (don't re-quote; planner reads RESEARCH directly).

---

### `acercontrol/cli.py` (entry-point, argparse)

**Analog A:** `acercontrol/features.py` lines 203–229 — `_print_report`. This is the existing precedent for "human-aligned text + 0/1/2 exit-code taxonomy" that `cmd_status` reuses.

```python
# acercontrol/features.py:203-229
def _print_report(report: FeatureReport) -> int:
    """Human-readable smoke output for `python3 -m acercontrol.features`.

    Returns shell exit code: 0 (clean), 1 (degraded), 2 (blocking failure).
    Phase 1 callers don't depend on the exit code — it's a convenience for
    UAT.
    """
    sev_glyph = {"blocking": "[!]", "warning": "[~]", "info": "[i]"}
    print(f"AcerControl FeatureReport  (ok={report.ok})")
    print("-" * 60)
    for c in report.checks:
        mark = "OK " if c.present else sev_glyph[c.severity]
        print(f"  {mark}  {c.name}")
        if c.detail:
            print(f"         detail: {c.detail}")
        if not c.present and c.fix:
            print(f"         fix:    {c.fix}")
    if report.blacklist_entries:
        print()
        print("Blacklist entries detected:")
        for path, line in report.blacklist_entries:
            print(f"  {path}: {line}")
    if not report.ok:
        return 2
    if any(c.severity == "warning" and not c.present for c in report.checks):
        return 1
    return 0
```

**Apply:** `cmd_status` reuses this exit-code taxonomy verbatim (0 clean / 1 degraded / 2 blocking) and the severity-glyph rendering shape. `cmd_status --json` emits the same `report.checks` data through `json.dumps`.

**Analog B:** `acercontrol/__init__.py` lines 14–45 — the package re-export pattern. `cli.py`'s import block at the top mirrors this exactly.

```python
# acercontrol/__init__.py:14-45
from acercontrol.profiles import (
    Profile,
    PROFILES,
    KERNEL_TO_UI,
    kernel_to_profile,
    current_profile_ui,
    available_profiles,
)
from acercontrol.sysfs import (
    find_hwmon,
    find_all_hwmon,
    invalidate_hwmon_cache,
    coretemp_max_package_temp,
    read_acer_sensors,
)
from acercontrol.features import (
    FeatureCheck,
    FeatureReport,
    probe,
    find_blacklist_entries,
)
from acercontrol.core import (
    PROFILE_PATH,
    PROFILE_CHOICES_PATH,
    HWMON_BASE,
    PREDATOR_V4_PARAM,
    MODPROBE_D,
    SensorReading,
    read_profile,
    list_available_profiles,
    read_sensors,
)
```

**Apply:** `cli.py` imports the same names through the package root (`from acercontrol import …`), as RESEARCH §Pattern 2 lines 456–471 shows. This keeps a single source of truth — if `__init__.py` re-exports something, `cli.py` uses it via the root namespace.

**Target skeleton:** RESEARCH §Pattern 2 lines 442–823.

---

### `libexec/acercontrol-setprofile` (privileged wrapper, write)

**Analog A:** `acercontrol/profiles.py` lines 13–19 — the canonical `PROFILES` dict whose `.values()` *is* the allowlist literal the wrapper duplicates.

```python
# acercontrol/profiles.py:13-19
# CLAUDE.md profile mapping — verbatim. Do not edit without updating tests.
PROFILES: dict[str, str] = {
    "eco":         "low-power",
    "quiet":       "quiet",
    "balanced":    "balanced",
    "performance": "balanced-performance",
    "turbo":       "performance",
}
```

**Apply:** The wrapper hardcodes `ALLOWED_KERNEL_VALUES = ("low-power", "quiet", "balanced", "balanced-performance", "performance")` — the literal duplication is **intentional defense-in-depth** per RESEARCH §P2-NEW-01 (pkexec scrubs PYTHONPATH; `from acercontrol.profiles import PROFILES` would fail until the .deb installs to `/usr/lib/python3/dist-packages/`). The drift gate in VALIDATION.md table catches edits that don't keep both in lockstep.

**Analog B:** `acercontrol/sysfs.py` lines 22–31 — `_read_or_none`. This is the *inverted* version of what the wrapper does (read vs. write, but the same `try / open() / except OSError` discipline).

```python
# acercontrol/sysfs.py:22-31
def _read_or_none(path: Path) -> Optional[str]:
    """Read text from a sysfs path, stripped. Returns None on OSError.

    Sysfs reads of small attribute files are atomic at the VFS layer —
    a single read() call sees a consistent snapshot.
    """
    try:
        return path.read_text().strip()
    except OSError:
        return None
```

**Apply:** wrapper inverts to `try: open(PROFILE_PATH, "w").write(value); except OSError as exc: → return EX_OSERR (71)`. Same defensive scoping; never raises into systemd/polkit.

**Target skeleton:** RESEARCH §Pattern 3 lines 837–922. Shebang note (line 924): `#!/usr/bin/python3` absolute, not `/usr/bin/env python3` — pkexec rebuilds PATH from a minimal safe environment.

---

### `libexec/acercontrol-set-boot-profile` (privileged wrapper, atomic file write)

**Analog A:** same as `acercontrol-setprofile` (allowlist literal duplicates `acercontrol/profiles.py:13-19`).

**No codebase analog** for the atomic write pattern (`tempfile.mkstemp` in target dir → `os.write` → `os.chmod 0o644` → `os.rename` over target). This is genuinely new — flag for the planner: copy RESEARCH §Pattern 4 lines 978–993 verbatim.

**Apply (delta from setprofile):** writes to `/etc/default/acercontrol` (regular file, atomic-rename safe) instead of `/sys/firmware/acpi/platform_profile` (sysfs, no atomicity needed since kernel does its own validation). Returns the same EX_* exit-code set (0/64/71/77).

**Target skeleton:** RESEARCH §Pattern 4 lines 932–1002.

---

### `libexec/acercontrol-manage-service` (privileged wrapper, systemctl)

**Analog:** `acercontrol/features.py` lines 82–96 — `_ppd_active`. **This is an exact data-flow match.** The wrapper does the same `subprocess.run(["systemctl", action, service], capture_output=True, text=True, timeout=…)` and handles `(FileNotFoundError, subprocess.TimeoutExpired)` defensively.

```python
# acercontrol/features.py:82-96  (re-quoted — this is the canonical pattern)
def _ppd_active() -> bool | None:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "power-profiles-daemon.service"],
            capture_output=True, text=True, timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.returncode == 0
```

**Apply (delta):** the wrapper:
1. validates `action ∈ ("enable", "disable", "start", "stop")` and `service ∈ ("acer-performance.service",)` BEFORE the subprocess call (defense-in-depth, RESEARCH §Pattern 5 lines 1037–1056);
2. uses `timeout=20` (systemctl operations can be slower than `is-active`);
3. forwards `result.stdout` / `result.stderr` to the caller's stdout/stderr (so polkit-elevated stderr reaches the CLI);
4. exits with `result.returncode` on success, EX_OSERR (71) on `FileNotFoundError`/`TimeoutExpired`.

**Target skeleton:** RESEARCH §Pattern 5 lines 1010–1074.

**Carry-forward warning (OQ-01):** if Phase 6 ships `acer-performance@.service` (templated, per REQUIREMENTS.md BOOT-01), this allowlist must be revisited. See VALIDATION.md "Carry-forward into PLAN.md".

---

### `data/org.acercontrol.policy` (polkit XML config)

**No codebase analog.** No XML configs exist in the repo today. Use RESEARCH §Pattern 6 lines 1084–1131 verbatim — the DOCTYPE line is the verbatim freedesktop polkit DTD; the three `<action>` elements are the exact ones PRIV-02 locks; the `<message>` strings come from ROADMAP success criterion 1 verbatim.

**Install location:** `/usr/share/polkit-1/actions/org.acercontrol.policy`, mode `0644 root:root` (RESEARCH §Pattern 6 line 1133). Phase 2 ships it at `data/org.acercontrol.policy`; Phase 8 packaging installs to the polkit path.

---

### `pyproject.toml` (modify — append `[project.scripts]`)

**Existing file:** `/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml` (verified — lines 1–30 are Phase 1 scope, no `[project.scripts]` slot yet).

**Apply:** append, do not rewrite:

```toml
[project.scripts]
acercontrol = "acercontrol.cli:main"
# acercontrol-gui = "acercontrol.gui:main"   # Phase 3 adds this
```

This is the slot Phase 1 RESEARCH lines 921–959 left open. Phase 3 will add the GUI entry. Append-only — no edits to the existing `[project]`, `[build-system]`, or `[tool.setuptools]` blocks.

---

### `tools/bundle_cli.py` (build-tool, concat bundler)

**Analog (shape-only):** `tools/smoke_phase1.py` lines 24–29 — the `PROJECT_ROOT` resolution + `sys.path` bootstrap. Bundler uses the same idiom.

```python
# tools/smoke_phase1.py:24-29
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Ensure imports resolve regardless of how the runner is invoked.
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

**Apply:** bundler uses `REPO = Path(__file__).resolve().parent.parent` (RESEARCH §Pattern 9 line 1291). The 6-file `BUNDLE_ORDER` and the post-bundle `subprocess.run(verify_no_gtk.py)` invocation are new — no full analog. Use RESEARCH §Pattern 9 lines 1264–1374 verbatim.

**Note:** the regex `_INTRA_IMPORT` strips intra-package imports (`from acercontrol.X import …`) so the concatenated single-file works without a package context. Comments rather than deletes (line numbers preserved for stack traces) — see RESEARCH §Pattern 9 lines 1320–1327.

---

### `tools/verify_no_gtk.py` (build-tool, regex gate)

**Analog:** `acercontrol/features.py` lines 25–27 + 59–79 — `find_blacklist_entries`. This is a **near-exact analog**: precompiled regex at module scope, multi-file iteration, line-by-line scan, `OSError`-tolerant, returns a `list[tuple[…]]` accumulator. The new tool's `check()` function is structurally identical.

```python
# acercontrol/features.py:25-27 (regex precompile at module scope)
_BLACKLIST_RE = re.compile(
    r"^\s*(blacklist\s+acer_wmi|install\s+acer_wmi\s+/bin/(?:true|false))\s*(#.*)?$"
)
```

```python
# acercontrol/features.py:59-79
def find_blacklist_entries(
    pattern: str = "/etc/modprobe.d/*.conf",
) -> list[tuple[str, str]]:
    """Scan modprobe.d for entries blacklisting acer_wmi (CORE-05).

    Returns list of (file_path, matched_line). Lines after a '#' comment
    are stripped before matching. Caller may pass a custom pattern (used
    by tests pointing at /tmp/test-blacklist.conf).
    """
    hits: list[tuple[str, str]] = []
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for raw_line in f:
                    # Strip inline comments BUT keep the matched line for display
                    code = raw_line.split("#", 1)[0]
                    if _BLACKLIST_RE.match(code):
                        hits.append((path, raw_line.rstrip("\n")))
        except OSError:
            continue
    return hits
```

**Apply:** `verify_no_gtk.check(path)` returns `list[tuple[int, str]]` (line number + content) with the same:
- module-scope precompiled regex (`_GTK_IMPORT`),
- per-file `try / open() / for line / except OSError → continue` discipline,
- comment-stripping logic (`stripped.startswith("#")` skip — same intent as `raw_line.split("#", 1)[0]` here),
- accumulator return shape.

**Difference:** the analog scans for blacklist *content*; `verify_no_gtk` scans for `^\s*(import\s+gi(\.|\s)|from\s+gi(\.|\s))`. Exit-code translation (`bad > 0` → exit 1) is the wrapper's responsibility, identical to the smoke runner pattern.

**Target skeleton:** RESEARCH §Pattern 10 lines 1387–1451.

---

### `tools/smoke_phase2.py` (smoke-runner)

**Analog:** `tools/smoke_phase1.py` — **the entire file is the analog.** Smoke phase 2 is the same shape: subprocess each scenario, catch all runner exceptions, accumulate failures, exit 0 if empty.

Key lines to copy verbatim:

```python
# tools/smoke_phase1.py:92-122 — the canonical run_check() shape
def run_check(label: str, description: str, payload: str) -> bool:
    """Run a single CORE-NN smoke command in a subprocess.

    Returns True on PASS (returncode == 0), False on FAIL. Never raises:
    any internal exception is caught and reported as a structured FAIL.
    """
    print(f"-> {label}: {description}")
    try:
        env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}
        result = subprocess.run(
            [sys.executable, "-c", payload],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except Exception as exc:  # noqa: BLE001 — runner must never raise
        print(f"  FAIL  runner exception: {type(exc).__name__}: {exc}")
        return False

    if result.returncode == 0:
        out = result.stdout.strip()
        print(f"  PASS  {out}")
        return True

    print(f"  FAIL  rc={result.returncode}")
    if result.stdout:
        print(f"    stdout: {result.stdout.rstrip()}")
    if result.stderr:
        print(f"    stderr: {result.stderr.rstrip()}")
    return False
```

```python
# tools/smoke_phase1.py:125-179 — main() outer-guard + failure accumulator
def main() -> int:
    failures: list[str] = []
    checks_run = 0
    # … per-scenario loop …
    for label, description, payload in plan:
        checks_run += 1
        if not run_check(label, description, payload):
            failures.append(label)
    # …
    passed = max(0, checks_run - len(failures))
    total = 6
    print(f"--- Phase 1 smoke: {passed}/{total} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Apply:** `tools/smoke_phase2.py` keeps the same `run` helper (renamed `run`, takes `argv: list[str]` directly rather than `payload: str` since Phase 2 mostly invokes `python3 -m acercontrol.cli <args>` rather than `python3 -c <payload>`). Adds two extras over Phase 1:
- `expect_rc` parameter — Phase 1 always expected 0; Phase 2 expects 64 for "rejects bad value" wrapper scenarios and `None` for "any rc OK as long as stdout parses" (e.g. `cli status` on macOS where probe rc varies).
- `check_json_parses: bool` — for `--json` scenarios; calls `json.loads(r.stdout)` post-run.

**Target skeleton:** RESEARCH §Pattern 11 lines 1464–1597.

---

## Shared Patterns

Cross-cutting patterns that apply to multiple new files. Each has a concrete in-repo analog.

### Shared 1 — Frozen dataclass with Optional/tuple fields, never-raises contract

**Source:** `acercontrol/core.py:50-58` (`SensorReading`) + `acercontrol/features.py:30-56` (`FeatureCheck` / `FeatureReport`).

```python
# acercontrol/core.py:50-58
@dataclass(frozen=True)
class SensorReading:
    """One snapshot of all sensors. Each field is Optional — None = unavailable."""
    cpu_package_c: Optional[float]
    fan1_rpm:      Optional[int]
    fan2_rpm:      Optional[int]
    acer_temp1_c:  Optional[float]
    acer_temp2_c:  Optional[float]
    acer_temp3_c:  Optional[float]
```

**Apply to:** `acercontrol/privilege.py::PrivilegedResult`. Frozen dataclass; `tuple[str, ...]` for `argv` (not list); `str` (not Optional) for stdout/stderr defaults to `""`.

### Shared 2 — `subprocess.run` + `timeout` + `(FileNotFoundError, TimeoutExpired)` triple

**Source:** `acercontrol/features.py:82-96` (`_ppd_active`).

**Apply to:**
- `acercontrol/privilege.py::run_privileged` (handles pkexec/sudo; extends with 126 → cancelled, 124 → timeout)
- `libexec/acercontrol-manage-service` (handles `systemctl <action> <service>`; same `timeout=20` + `except (FileNotFoundError, subprocess.TimeoutExpired)` pattern)
- `tools/smoke_phase2.py::run` (timeout=15 per scenario; never raises)
- `tools/bundle_cli.py` (post-bundle `subprocess.run([sys.executable, verifier, OUTPUT])` invocation — simpler, no timeout)

### Shared 3 — `OSError`-as-fail-soft for sysfs / file IO

**Source:** `acercontrol/sysfs.py:22-31` (`_read_or_none`).

**Apply to:**
- `libexec/acercontrol-setprofile` — inverted (`try: open(path, "w").write(value); except OSError → return EX_OSERR(71)`)
- `libexec/acercontrol-set-boot-profile` — same inversion, with extra `tempfile.mkstemp` + `os.rename` for atomicity
- `tools/verify_no_gtk.py::check` — same defensive read pattern, `errors="replace"` to never explode on weird encodings

### Shared 4 — Sysexits-style wrapper exit codes (64 / 71 / 77)

**Source:** **No in-repo analog.** The CLI uses argparse exit 2; Phase 1 has no wrapper precedent. Cite RESEARCH §Pattern 1 lines 418–432 (exit-code mapping table) verbatim.

| Code | Constant | Wrapper Usage |
|---|---|---|
| 0 | EX_OK | Success |
| 64 | EX_USAGE | Allowlist reject / bad argv |
| 71 | EX_OSERR | sysfs / file / systemctl IO failure |
| 77 | EX_NOPERM | euid != 0 (defensive — should never trigger via pkexec) |

**Apply to:** all three `libexec/*` wrappers — same `EX_OK / EX_USAGE / EX_OSERR / EX_NOPERM` literals at module top (RESEARCH §Pattern 3 lines 877–880, Pattern 4 lines 956–959, Pattern 5 lines 1031–1034). The drift gate in VALIDATION.md catches mismatches.

### Shared 5 — Module-scope precompiled regex

**Source:** `acercontrol/features.py:25-27` + `acercontrol/sysfs.py:16-17`.

```python
# acercontrol/features.py:25-27
_BLACKLIST_RE = re.compile(
    r"^\s*(blacklist\s+acer_wmi|install\s+acer_wmi\s+/bin/(?:true|false))\s*(#.*)?$"
)

# acercontrol/sysfs.py:16-17
_INPUT_RE = re.compile(r"^(fan|temp|in|curr|power)\d+_input$")
_PACKAGE_LABEL_RE = re.compile(r"Package id (\d+)")
```

**Apply to:**
- `tools/verify_no_gtk.py` — `_GTK_IMPORT = re.compile(r"(^|\n)\s*(import\s+gi(\.|\s)|from\s+gi(\.|\s))")`
- `tools/bundle_cli.py` — `_INTRA_IMPORT = re.compile(r"^(from\s+acercontrol(\.\w+)?\s+import\s+.+|import\s+acercontrol(\.\w+)?\s*(as\s+\w+)?)\s*$", re.MULTILINE)`

### Shared 6 — `PROJECT_ROOT` resolution + `PYTHONPATH` bootstrap for tools/

**Source:** `tools/smoke_phase1.py:24-29`.

**Apply to:** both new `tools/*.py` files (`bundle_cli.py`, `smoke_phase2.py`) and `tools/verify_no_gtk.py` (verifier doesn't need PYTHONPATH, but uses `Path(__file__).resolve().parent.parent` for repo-relative arg defaults if no argv).

---

## No Analog Found

Files / sub-patterns with no close repo precedent. Planner uses RESEARCH.md skeletons directly.

| New File / Pattern | Why No Analog | Direction |
|---|---|---|
| `data/org.acercontrol.policy` | No XML configs in repo today; polkit DOCTYPE + action element structure is freedesktop-prescribed | Use RESEARCH §Pattern 6 lines 1084–1131 verbatim (DOCTYPE is freedesktop's, must not be paraphrased) |
| `libexec/*` directory itself | New top-level directory — `libexec/` doesn't exist yet. Wrappers' allowlist + IO patterns *do* have analogs; the *directory* and the polkit-action-pinned-wrapper *structure* are new | Wave 0 creates `libexec/` per VALIDATION.md |
| Atomic tempfile-rename write (`set-boot-profile`) | `_read_or_none` only covers reads; no existing write site uses `tempfile.mkstemp` + `os.rename` | Use RESEARCH §Pattern 4 lines 978–993 verbatim |
| Sysexits 64/71/77 in wrappers | Phase 1 has no wrapper layer; argparse-based CLI uses exit 2 only | Use RESEARCH §Pattern 1 exit-code table (lines 418–432) + Patterns 3/4/5 EX_* literals |
| `pkexec`/`sudo`/`SSH_CONNECTION` elevation selection | Phase 1 has no privileged paths | Use RESEARCH §Pattern 1 `pick_elevation()` lines 284–302 |
| Bundler intra-import stripping | First single-file bundle in the repo | Use RESEARCH §Pattern 9 lines 1320–1327 |
| pkexec exit-126 → `cancelled=True` translation | New | RESEARCH §Pattern 1 line 412 |

---

## Metadata

**Analog search scope:** `acercontrol/*.py` (5 files), `tools/*.py` (1 file), `pyproject.toml` (1 file). The repo currently has no `libexec/`, no `data/`, no `dist/`.

**Files scanned:** 7 source files (full read), plus RESEARCH.md §Patterns 1–11 (targeted reads at lines 217–823, 1260–1610).

**Pattern extraction date:** 2026-05-15

**Verified analogs cited:**
- `acercontrol/features.py:25-27` (regex precompile)
- `acercontrol/features.py:30-56` (frozen dataclass + computed properties)
- `acercontrol/features.py:59-79` (regex-based file scanner accumulator)
- `acercontrol/features.py:82-96` (subprocess.run + timeout + defensive exceptions)
- `acercontrol/features.py:203-229` (`_print_report` exit-code taxonomy + human text)
- `acercontrol/sysfs.py:16-17` (module-scope precompiled regex)
- `acercontrol/sysfs.py:22-31` (`_read_or_none` OSError-as-fail-soft)
- `acercontrol/profiles.py:13-19` (`PROFILES` source-of-truth dict for allowlist)
- `acercontrol/core.py:50-58` (`SensorReading` frozen dataclass with Optional fields)
- `acercontrol/__init__.py:14-45` (package re-export pattern)
- `tools/smoke_phase1.py:24-29` (`PROJECT_ROOT` + `PYTHONPATH` bootstrap)
- `tools/smoke_phase1.py:92-122` (`run_check` never-raises subprocess shape)
- `tools/smoke_phase1.py:125-179` (`main()` failure accumulator + outer guard)

**Carry-forward to PLAN.md:** Shared 4 (sysexits codes) and the "No Analog Found" rows are the items where the planner should reference RESEARCH.md skeletons verbatim rather than infer from in-repo precedent.
