#!/usr/bin/env python3
# tools/smoke_phase3.py
"""Phase 3 smoke runner — GUI shell + failure states + PPD banner (GUI-01..04, GUI-08).

Cross-platform. Exits 0 on all-pass. Mirrors tools/smoke_phase2.py.

Quick mode (--quick): XML well-formed, wrapper argv rejection, GUI module
ImportError/ValueError pattern, GUI-08 grep gate, bundler GTK-free regression,
verify_no_gtk sanity on gui.py.

Full mode (default): all of --quick plus features.py severity assertions
(Landmine #2 / Task 1 verification), acercontrol-gui entry-point check
(Landmine #4 — only when dev-install present), polkit policy exec.path
annotations point at the right wrapper basenames.
"""
from __future__ import annotations
import argparse
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.environ["ACERCONTROL_DEV"] = PROJECT_ROOT  # so resolve_wrapper finds libexec/

POLICY_PATH = Path(PROJECT_ROOT) / "data" / "org.acercontrol.policy"
WRAPPER_DISABLE_PPD = Path(PROJECT_ROOT) / "libexec" / "acercontrol-disable-ppd"
WRAPPER_RELOAD_WMI = Path(PROJECT_ROOT) / "libexec" / "acercontrol-reload-acer-wmi"
BUNDLE_INPUT_FILES = [
    Path(PROJECT_ROOT) / "acercontrol" / f"{m}.py"
    for m in ("profiles", "sysfs", "core", "features", "privilege", "cli")
]
GUI_MODULES = (
    "acercontrol.gui",
    "acercontrol.gui_window",
    "acercontrol.gui_status_pages",
    "acercontrol.gui_banner",
    "acercontrol.gui_about",
)
GUI_FILES = [
    Path(PROJECT_ROOT) / "acercontrol" / f"{m}.py"
    for m in ("gui", "gui_window", "gui_status_pages", "gui_banner", "gui_about")
]


def run(label, argv, *, expect_rc=0, env_extra=None, stdin=None,
        check_stdout_contains=None, check_stderr_contains=None):
    """Copy of tools/smoke_phase2.py:32-69's run() shape — adapt as needed.

    Returns True on PASS, False on FAIL. Prints diagnostics on failure.
    """
    print(f"-> {label}")
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=30, env=env, input=stdin)
    except Exception as e:  # noqa: BLE001 — runner must never raise
        print(f"  FAIL  runner exception: {type(e).__name__}: {e}")
        return False
    if expect_rc is not None and r.returncode != expect_rc:
        print(f"  FAIL  rc={r.returncode} (expected {expect_rc})")
        if r.stderr:
            print(f"        stderr: {r.stderr.strip()[:200]}")
        return False
    if check_stdout_contains and check_stdout_contains not in r.stdout:
        print(f"  FAIL  stdout missing: {check_stdout_contains!r}")
        return False
    if check_stderr_contains and check_stderr_contains not in r.stderr:
        print(f"  FAIL  stderr missing: {check_stderr_contains!r}")
        return False
    print("  PASS")
    return True


# ---- inline scenario functions (Python — not subprocess) ----

def scenario_policy_xml_well_formed():
    print("-> Polkit policy XML well-formed + 5 actions")
    try:
        tree = ET.parse(POLICY_PATH)
        actions = tree.getroot().findall("action")
        if len(actions) != 5:
            print(f"  FAIL  expected 5 <action> blocks, found {len(actions)}")
            return False
        action_ids = sorted(a.get("id") for a in actions)
        expected = sorted([
            "org.acercontrol.setprofile",
            "org.acercontrol.set-boot-profile",
            "org.acercontrol.manage-service",
            "org.acercontrol.disable-ppd",
            "org.acercontrol.reload-acer-wmi",
        ])
        if action_ids != expected:
            print(f"  FAIL  action IDs {action_ids} != expected {expected}")
            return False
        # Each new action's exec.path points at its wrapper
        wanted = {
            "org.acercontrol.disable-ppd": "/usr/libexec/acercontrol/acercontrol-disable-ppd",
            "org.acercontrol.reload-acer-wmi": "/usr/libexec/acercontrol/acercontrol-reload-acer-wmi",
        }
        for action in actions:
            aid = action.get("id")
            if aid in wanted:
                annot = action.find("annotate[@key='org.freedesktop.policykit.exec.path']")
                if annot is None or annot.text != wanted[aid]:
                    print(f"  FAIL  {aid} exec.path={annot.text if annot is not None else None!r}; want {wanted[aid]!r}")
                    return False
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL  XML parse: {type(e).__name__}: {e}")
        return False
    print("  PASS")
    return True


def scenario_gui_modules_import_cleanly():
    """Landmine #5 — gui modules must raise ImportError or ValueError when gi
    is missing OR typelibs are missing. On Linux with full GTK4 stack, import
    succeeds — that's also acceptable. The contract is "no spurious exception
    type."
    """
    print("-> GUI modules raise ImportError/ValueError (Landmine #5)")
    EXPECTED = (ImportError, ValueError)
    for mod in GUI_MODULES:
        # Force re-import to avoid sys.modules cache leak between runs
        if mod in sys.modules:
            del sys.modules[mod]
        try:
            importlib.import_module(mod)
        except EXPECTED:
            pass  # acceptable on macOS / no-typelibs Linux
        except Exception as exc:
            print(f"  FAIL  {mod} raised unexpected {type(exc).__name__}: {exc}")
            return False
    print("  PASS")
    return True


def scenario_gui08_grep_gate():
    """GUI-08 — raw kernel profile literals must not appear as string-literal
    tokens in gui.py / gui_window.py / gui_status_pages.py / gui_banner.py.
    gui_about.py is the exempt Diagnostics carve-out.
    """
    print("-> GUI-08 grep gate (raw kernel values not in user-facing UI files)")
    forbidden = ['"low-power"', '"balanced-performance"', '"performance"']
    files_to_check = [f for f in GUI_FILES if f.name != "gui_about.py"]
    failures = []
    for f in files_to_check:
        if not f.exists():
            print(f"  SKIP  {f.name} (not yet created)")
            continue
        # Skip comment lines via grep -v '^[[:space:]]*#'
        try:
            text = f.read_text()
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for token in forbidden:
                if token in line:
                    failures.append(f"{f.name}:{lineno}: {line.strip()[:120]}")
    if failures:
        print("  FAIL  forbidden raw-kernel-value literals found:")
        for ff in failures:
            print(f"        {ff}")
        return False
    print("  PASS")
    return True


def scenario_bundler_input_excludes_gui():
    """Landmine #6 — tools/bundle_cli.py BUNDLE_ORDER does not include any
    gui_* substring. Inspection of the bundler source.
    """
    print("-> Bundler input list excludes gui*.py (Landmine #6)")
    bundle_py = Path(PROJECT_ROOT) / "tools" / "bundle_cli.py"
    text = bundle_py.read_text()
    # Look only inside the BUNDLE_ORDER list, conservatively the whole file works
    if "gui_" in text or "gui.py" in text.replace("# ", ""):
        # Refine: strip comments and check
        non_comment = "\n".join(
            l for l in text.splitlines() if not l.lstrip().startswith("#")
        )
        if "gui_" in non_comment or "gui.py" in non_comment:
            print("  FAIL  bundler source contains gui_* reference outside comments")
            return False
    print("  PASS")
    return True


def scenario_dismiss_menu_entry_present():
    """D-04 dismissibility — HeaderBar primary menu must expose 'Hide PPD warning
    this session' wired to the `win.hide-ppd-banner` GAction. Grep gate against
    acercontrol/gui_window.py source (skipped if file not yet created, mirroring
    scenario_gui08_grep_gate)."""
    print("-> D-04 dismiss menu entry wired (Hide PPD warning this session)")
    target = Path(PROJECT_ROOT) / "acercontrol" / "gui_window.py"
    if not target.exists():
        print("  SKIP  gui_window.py (not yet created)")
        return True
    src = target.read_text()
    non_comment = "\n".join(
        l for l in src.splitlines() if not l.lstrip().startswith("#")
    )
    required = [
        '"Hide PPD warning this session"',  # the menu label
        '"hide-ppd-banner"',                 # the GAction name
        "hidden-when",                       # visibility predicate attribute
    ]
    missing = [tok for tok in required if tok not in non_comment]
    if missing:
        print(f"  FAIL  missing tokens in gui_window.py: {missing}")
        return False
    print("  PASS")
    return True


def scenario_reload_wmi_unloaded_path():
    """BL-01 regression gate (03-VERIFICATION.md) — `acercontrol-reload-acer-wmi`
    must pre-probe `/sys/module/acer_wmi` before calling `modprobe -r`, so the
    unloaded-module path (SC#2 "Load module" CTA) does not short-circuit to
    EX_OSERR=71. Source-level assertion: the guard token is present AND the
    unconditional unload pattern is absent at the top of the try-block.

    Static-only — the live unloaded-module path requires root + Linux kmod and
    is covered by human UAT (03-VERIFICATION.md human_verification[2]).
    """
    print("-> reload-acer-wmi pre-probes /sys/module/acer_wmi (BL-01 regression)")
    wrapper = WRAPPER_RELOAD_WMI
    if not wrapper.exists():
        print(f"  FAIL  wrapper missing: {wrapper}")
        return False
    src = wrapper.read_text()
    # Strip comment-only lines so the guard-token check isn't satisfied by a docstring mention.
    non_comment = "\n".join(
        l for l in src.splitlines() if not l.lstrip().startswith("#")
    )
    # Required: the os.path.exists guard on /sys/module/acer_wmi (the post-fix shape).
    guard_token = 'os.path.exists("/sys/module/acer_wmi")'
    if guard_token not in non_comment:
        print(f"  FAIL  missing guard token: {guard_token!r}")
        print("        wrapper still uses unconditional `modprobe -r` — BL-01 not fixed")
        return False
    # Forbidden: an unconditional `[MODPROBE, "-r", MODULE]` call at top-of-try.
    # Heuristic: the `subprocess.run([MODPROBE, "-r", MODULE]` substring must appear
    # exactly once AND must be preceded (within a few lines) by the guard.
    needle = 'subprocess.run(\n            [MODPROBE, "-r", MODULE]'
    occurrences = non_comment.count(needle)
    if occurrences != 1:
        # Fall back to a looser check that doesn't depend on exact whitespace.
        loose = '[MODPROBE, "-r", MODULE]'
        n_loose = non_comment.count(loose)
        if n_loose != 1:
            print(f"  FAIL  expected exactly one `[MODPROBE, \"-r\", MODULE]` call; found {n_loose}")
            return False
    # Confirm the guard appears BEFORE the unload call in source order.
    guard_pos = non_comment.find(guard_token)
    unload_pos = non_comment.find('[MODPROBE, "-r", MODULE]')
    if guard_pos < 0 or unload_pos < 0 or guard_pos > unload_pos:
        print("  FAIL  guard token does not precede unload call in source order")
        return False
    print("  PASS")
    return True


def scenario_features_severity_post_patch():
    """Landmine #2 / Task 1 — features.py severities match Phase 3 routing."""
    print("-> features.py severity values post-patch")
    try:
        from acercontrol.features import probe
        report = probe()
        by_name = {c.name: c for c in report.checks}
        ok = True
        ah = by_name.get("acer hwmon (fan+temp)")
        if ah is None or ah.severity != "blocking":
            print(f"  FAIL  acer hwmon severity = {ah.severity if ah else 'MISSING'!r} (want 'blocking')")
            ok = False
        ct = by_name.get("coretemp hwmon")
        if ct is None or ct.severity != "warning":
            print(f"  FAIL  coretemp hwmon severity = {ct.severity if ct else 'MISSING'!r} (want 'warning')")
            ok = False
        bl = by_name.get("acer_wmi not blacklisted")
        if bl is None or bl.severity not in ("info", "warning"):
            print(f"  FAIL  blacklist severity = {bl.severity if bl else 'MISSING'!r} (want 'info' or 'warning')")
            ok = False
        if not ok:
            return False
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL  probe(): {type(e).__name__}: {e}")
        return False
    print("  PASS")
    return True


def scenario_entry_point_registered():
    """Landmine #4 — acercontrol-gui entry-point registered (only meaningful
    when dev-install is present; SKIP if not)."""
    print("-> acercontrol-gui console-script entry-point (Landmine #4)")
    try:
        import importlib.metadata as m
        eps = {ep.name for ep in m.entry_points(group="console_scripts")}
        if "acercontrol-gui" not in eps:
            # Acceptable if dev install hasn't been done; treat as SKIP not FAIL
            print("  SKIP  acercontrol-gui not in console_scripts (run `pip install -e . --force-reinstall`)")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL  importlib.metadata lookup: {type(e).__name__}: {e}")
        return False
    print("  PASS")
    return True


def build_scenarios(quick: bool):
    """Return list of (callable_or_subprocess_spec, ...). For subprocess
    scenarios, use run() with the appropriate argv + expect_rc."""
    s = []

    # --- Always-run (quick) ---
    s.append(("inline", scenario_policy_xml_well_formed))
    # Wrapper argv rejection — disable-ppd
    s.append(("run", "disable-ppd: bad action (start)", [
        sys.executable, str(WRAPPER_DISABLE_PPD), "start", "power-profiles-daemon.service",
    ], {"expect_rc": 64}))
    s.append(("run", "disable-ppd: bad service (other.service)", [
        sys.executable, str(WRAPPER_DISABLE_PPD), "mask", "other.service",
    ], {"expect_rc": 64}))
    s.append(("run", "disable-ppd: no argv", [
        sys.executable, str(WRAPPER_DISABLE_PPD),
    ], {"expect_rc": 64}))
    s.append(("run", "disable-ppd: both bad", [
        sys.executable, str(WRAPPER_DISABLE_PPD), "start", "other.service",
    ], {"expect_rc": 64}))
    # Wrapper argv rejection — reload-acer-wmi (argv-less; any extra → EX_USAGE)
    s.append(("run", "reload-acer-wmi: unexpected argv", [
        sys.executable, str(WRAPPER_RELOAD_WMI), "unexpected",
    ], {"expect_rc": 64}))
    s.append(("run", "reload-acer-wmi: two extra args", [
        sys.executable, str(WRAPPER_RELOAD_WMI), "reload", "extra",
    ], {"expect_rc": 64}))

    s.append(("inline", scenario_gui_modules_import_cleanly))
    s.append(("inline", scenario_gui08_grep_gate))
    s.append(("inline", scenario_bundler_input_excludes_gui))
    s.append(("inline", scenario_dismiss_menu_entry_present))
    s.append(("inline", scenario_reload_wmi_unloaded_path))  # BL-01 regression gate

    # Bundler / verify_no_gtk regression — bundler input list still GTK-free
    s.append(("run", "verify_no_gtk on bundler input list", [
        sys.executable, str(Path(PROJECT_ROOT) / "tools" / "verify_no_gtk.py"),
        *[str(p) for p in BUNDLE_INPUT_FILES],
    ], {"expect_rc": 0}))
    # Sanity — verify_no_gtk reports gui.py as gtk-tainted (exit != 0)
    s.append(("run", "verify_no_gtk SANITY on gui.py (must report tainted)", [
        sys.executable, str(Path(PROJECT_ROOT) / "tools" / "verify_no_gtk.py"),
        str(Path(PROJECT_ROOT) / "acercontrol" / "gui.py"),
    ], {"expect_rc": 1}))

    if quick:
        return s

    # --- Full (post-Task 1) ---
    s.append(("inline", scenario_features_severity_post_patch))
    s.append(("inline", scenario_entry_point_registered))

    # Bundler post-build still GTK-free (only run in full mode — bundler invocation costs ~1s)
    s.append(("run", "bundler produces GTK-free dist/acercontrol", [
        sys.executable, str(Path(PROJECT_ROOT) / "tools" / "bundle_cli.py"),
    ], {"expect_rc": 0}))
    s.append(("run", "verify_no_gtk on dist/acercontrol", [
        sys.executable, str(Path(PROJECT_ROOT) / "tools" / "verify_no_gtk.py"),
        str(Path(PROJECT_ROOT) / "dist" / "acercontrol"),
    ], {"expect_rc": 0}))

    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run quick gate only (~2s)")
    args = parser.parse_args()

    failures = []
    total = 0
    try:
        scenarios = build_scenarios(quick=args.quick)
        total = len(scenarios)
        for scenario in scenarios:
            if scenario[0] == "inline":
                _, fn = scenario
                label = fn.__name__
                ok = fn()
            else:
                _, label, argv, opts = scenario
                ok = run(label, argv, **opts)
            if not ok:
                failures.append(label)
    except Exception as exc:  # noqa: BLE001 — outer guard
        print(f"FATAL: runner top-level exception: {type(exc).__name__}: {exc}")
        return 1

    passed = total - len(failures)
    print(f"--- Phase 3 smoke ({'quick' if args.quick else 'full'}): {passed}/{total} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
