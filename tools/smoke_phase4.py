#!/usr/bin/env python3
# tools/smoke_phase4.py
"""Phase 4 smoke runner - profile controls (GUI-05..07).

Cross-platform source/static checks. This runner intentionally does not import
GTK or touch sysfs; live GTK/polkit behavior is covered by PHN16-72 UAT.

Quick mode is safe before acercontrol/gui_profiles.py exists: component-specific
checks report SKIP until the implementation file is present, then become strict.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.environ["ACERCONTROL_DEV"] = PROJECT_ROOT

GUI_PROFILES = Path(PROJECT_ROOT) / "acercontrol" / "gui_profiles.py"
GUI_WINDOW = Path(PROJECT_ROOT) / "acercontrol" / "gui_window.py"
GUI_FILES = [
    Path(PROJECT_ROOT) / "acercontrol" / name
    for name in (
        "gui.py",
        "gui_window.py",
        "gui_status_pages.py",
        "gui_banner.py",
        "gui_profiles.py",
    )
]


def run(label, argv, *, expect_rc=0):
    print(f"-> {label}")
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except Exception as exc:  # noqa: BLE001 - smoke runner must not raise
        print(f"  FAIL  runner exception: {type(exc).__name__}: {exc}")
        return False
    if expect_rc is not None and result.returncode != expect_rc:
        print(f"  FAIL  rc={result.returncode} (expected {expect_rc})")
        if result.stdout:
            print(f"        stdout: {result.stdout.strip()[:240]}")
        if result.stderr:
            print(f"        stderr: {result.stderr.strip()[:240]}")
        return False
    print("  PASS")
    return True


def _non_comment_text(path: Path) -> str:
    if not path.exists():
        return ""
    lines = []
    for line in path.read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _require_profile_source(label: str) -> str | None:
    if not GUI_PROFILES.exists():
        print(f"-> {label}")
        print("  SKIP  acercontrol/gui_profiles.py not yet created")
        return None
    return _non_comment_text(GUI_PROFILES)


def scenario_exact_phase4_copy():
    label = "Phase 4 exact copy strings present"
    src = _require_profile_source(label)
    if src is None:
        return True
    required = [
        "Performance Profile",
        "Current profile: Custom",
        "Click a profile to set a known Acer profile.",
        "Awaiting authorisation...",
        "Authorization cancelled",
        "Profile not applied — power-profiles-daemon may be overriding writes",
        "Profile change failed. See terminal for details.",
        "Switched to ",
    ]
    missing = [token for token in required if token not in src]
    if missing:
        print(f"  FAIL  missing copy tokens: {missing}")
        return False
    print("  PASS")
    return True


def scenario_profile_order():
    label = "Profile button order literal"
    src = _require_profile_source(label)
    if src is None:
        return True
    expected = 'ORDER = ("eco", "quiet", "balanced", "performance", "turbo")'
    if expected not in src:
        print(f"  FAIL  missing exact order literal: {expected}")
        return False
    print("  PASS")
    return True


def scenario_button_not_toggle():
    label = "Gtk.Button used; ToggleButton/set_active/toggled absent"
    src = _require_profile_source(label)
    if src is None:
        return True
    required = ["Gtk.Button"]
    forbidden = ["Gtk.ToggleButton", ".set_active(", '"toggled"', "'toggled'"]
    missing = [token for token in required if token not in src]
    found = [token for token in forbidden if token in src]
    if missing or found:
        print(f"  FAIL  missing={missing} forbidden={found}")
        return False
    print("  PASS")
    return True


def scenario_privileged_write_shape():
    label = "run_privileged setprofile argv shape"
    src = _require_profile_source(label)
    if src is None:
        return True
    required = 'run_privileged(["acercontrol-setprofile", PROFILES['
    if required not in src:
        print(f"  FAIL  missing token: {required}")
        return False
    forbidden = ["subprocess", "pkexec", "sudo"]
    found = [token for token in forbidden if token in src]
    if found:
        print(f"  FAIL  direct elevation/process tokens found: {found}")
        return False
    print("  PASS")
    return True


def scenario_readback_and_ppd_paths():
    label = "250 ms read-back and PPD mismatch path"
    src = _require_profile_source(label)
    if src is None:
        return True
    required = [
        "GLib.timeout_add(250,",
        "read_profile()",
        "show_ppd_banner(force=True)",
        "GLib.SOURCE_REMOVE",
    ]
    missing = [token for token in required if token not in src]
    if missing:
        print(f"  FAIL  missing tokens: {missing}")
        return False
    print("  PASS")
    return True


def scenario_cancel_timeout_path():
    label = "3-second cancel toast path"
    src = _require_profile_source(label)
    if src is None:
        return True
    required = ["Authorization cancelled", "timeout=3"]
    missing = [token for token in required if token not in src]
    if missing:
        print(f"  FAIL  missing tokens: {missing}")
        return False
    cancel_region = src[src.find("result.cancelled"):src.find("result.returncode")]
    forbidden = ["read_profile()", "show_ppd_banner(force=True)", "GLib.timeout_add"]
    found = [token for token in forbidden if token in cancel_region]
    if found:
        print(f"  FAIL  cancel branch contains side-effect tokens: {found}")
        return False
    print("  PASS")
    return True


def scenario_accessibility_and_focus():
    label = "Accessibility labels and focus restoration"
    src = _require_profile_source(label)
    if src is None:
        return True
    required = ["Set profile to ", "Current profile", ".grab_focus("]
    missing = [token for token in required if token not in src]
    if missing:
        print(f"  FAIL  missing tokens: {missing}")
        return False
    print("  PASS")
    return True


def scenario_raw_kernel_values_absent():
    print("-> GUI-08 raw kernel values absent from user-facing GUI files")
    forbidden = ['"low-power"', '"balanced-performance"']
    failures = []
    for path in GUI_FILES:
        if path.name == "gui_about.py" or not path.exists():
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for token in forbidden:
                if token in line:
                    failures.append(f"{path.name}:{lineno}: {line.strip()[:120]}")
    if failures:
        print("  FAIL  forbidden raw-kernel-value literals found:")
        for failure in failures:
            print(f"        {failure}")
        return False
    print("  PASS")
    return True


def scenario_gui_window_wiring():
    print("-> MainWindow wires ProfileControlPanel and removes placeholder main content")
    src = _non_comment_text(GUI_WINDOW)
    if "ProfileControlPanel" not in src:
        print("  FAIL  gui_window.py does not reference ProfileControlPanel")
        return False
    if "placeholder_ok(self)" in src:
        print("  FAIL  gui_window.py still appends placeholder_ok(self)")
        return False
    if "_main_banners" not in src or "_profile_panel" not in src:
        print("  FAIL  missing expected main-view wiring tokens")
        return False
    print("  PASS")
    return True


def scenario_toast_timeout_helper():
    print("-> MainWindow exposes timeout-capable toast helper")
    src = _non_comment_text(GUI_WINDOW)
    required = ["set_timeout(timeout)", "timeout=None", "Adw.Toast.new(message)"]
    missing = [token for token in required if token not in src]
    if missing:
        print(f"  FAIL  missing tokens: {missing}")
        return False
    print("  PASS")
    return True


def build_scenarios(quick: bool):
    scenarios = [
        ("inline", scenario_exact_phase4_copy),
        ("inline", scenario_profile_order),
        ("inline", scenario_button_not_toggle),
        ("inline", scenario_privileged_write_shape),
        ("inline", scenario_readback_and_ppd_paths),
        ("inline", scenario_cancel_timeout_path),
        ("inline", scenario_accessibility_and_focus),
        ("inline", scenario_raw_kernel_values_absent),
    ]
    if quick:
        return scenarios

    scenarios.extend([
        ("inline", scenario_gui_window_wiring),
        ("inline", scenario_toast_timeout_helper),
        ("run", "py_compile Phase 4 files", [
            sys.executable,
            "-m",
            "py_compile",
            str(GUI_PROFILES),
            str(GUI_WINDOW),
            str(Path(__file__).resolve()),
        ], {"expect_rc": 0}),
    ])
    return scenarios


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run quick gate only")
    args = parser.parse_args()

    failures = []
    scenarios = build_scenarios(args.quick)
    for scenario in scenarios:
        if scenario[0] == "inline":
            _, fn = scenario
            ok = fn()
            label = fn.__name__
        else:
            _, label, argv, opts = scenario
            ok = run(label, argv, **opts)
        if not ok:
            failures.append(label)

    passed = len(scenarios) - len(failures)
    mode = "quick" if args.quick else "full"
    print(f"--- Phase 4 smoke ({mode}): {passed}/{len(scenarios)} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
