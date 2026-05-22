#!/usr/bin/env python3
# tools/smoke_phase5.py
"""Phase 5 smoke runner - live sensors and notifications (SENS/NOTI).

Cross-platform source/static checks. This runner intentionally avoids GTK
imports, desktop services, privilege prompts, and sysfs writes; live GTK/Gio
behavior is covered by PHN16-72 UAT.

Quick mode is safe while Phase 5 files are being created: implementation-file
checks report SKIP until the relevant file exists, then become strict.
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

PHASE_DIR = Path(PROJECT_ROOT) / ".planning" / "phases" / "05-live-sensors-notifications"
UI_SPEC = PHASE_DIR / "05-UI-SPEC.md"

GUI_WINDOW = Path(PROJECT_ROOT) / "acercontrol" / "gui_window.py"
GUI_PROFILES = Path(PROJECT_ROOT) / "acercontrol" / "gui_profiles.py"
GUI_NOTIFICATIONS = Path(PROJECT_ROOT) / "acercontrol" / "gui_notifications.py"
GUI_SENSORS = Path(PROJECT_ROOT) / "acercontrol" / "gui_sensors.py"
PHASE5_GUI_FILES = [
    GUI_WINDOW,
    GUI_PROFILES,
    GUI_NOTIFICATIONS,
    GUI_SENSORS,
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


def _require_source(path: Path, label: str) -> str | None:
    if not path.exists():
        rel = path.relative_to(Path(PROJECT_ROOT))
        print(f"-> {label}")
        print(f"  SKIP  {rel} not yet created")
        return None
    return _non_comment_text(path)


def scenario_ui_spec_exists():
    print("-> Phase 5 UI contract exists")
    if not UI_SPEC.exists():
        print(f"  FAIL  missing {UI_SPEC.relative_to(Path(PROJECT_ROOT))}")
        return False
    text = UI_SPEC.read_text()
    required = [
        "Live refresh: 2 s",
        "CPU Package",
        "profile-change",
        "critical-temp",
        "GLib.timeout_add_seconds(2,",
    ]
    missing = [token for token in required if token not in text]
    if missing:
        print(f"  FAIL  UI spec missing expected tokens: {missing}")
        return False
    print("  PASS")
    return True


def _runtime_token_check(paths: list[Path], label: str) -> bool:
    print(f"-> {label}")
    forbidden = [
        "threading.Thread",
        "GLib.idle_add",
        "time.sleep(",
        "notify2",
        "gi.repository.Notify",
    ]
    failures = []
    for path in paths:
        if not path.exists():
            continue
        src = _non_comment_text(path)
        for token in forbidden:
            if token in src:
                failures.append(f"{path.relative_to(Path(PROJECT_ROOT))}: {token}")
    if failures:
        print("  FAIL  forbidden tokens found:")
        for failure in failures:
            print(f"        {failure}")
        return False
    print("  PASS")
    return True


def scenario_new_modules_forbidden_runtime_tokens_absent():
    return _runtime_token_check(
        [GUI_NOTIFICATIONS, GUI_SENSORS],
        "New Phase 5 GUI modules avoid blocking/threaded notification patterns",
    )


def scenario_all_phase5_forbidden_runtime_tokens_absent():
    return _runtime_token_check(
        PHASE5_GUI_FILES,
        "All Phase 5 GUI modules avoid blocking/threaded notification patterns",
    )


def scenario_no_direct_hwmon_access():
    print("-> Phase 5 GUI modules do not walk hwmon directly")
    forbidden = ['"/sys/class/hwmon"', "'/sys/class/hwmon'"]
    failures = []
    for path in PHASE5_GUI_FILES:
        if not path.exists():
            continue
        src = _non_comment_text(path)
        for token in forbidden:
            if token in src:
                failures.append(f"{path.relative_to(Path(PROJECT_ROOT))}: {token}")
    if failures:
        print("  FAIL  direct hwmon path tokens found:")
        for failure in failures:
            print(f"        {failure}")
        return False
    print("  PASS")
    return True


def scenario_sensor_panel_source():
    label = "SensorPanel source contract"
    src = _require_source(GUI_SENSORS, label)
    if src is None:
        return True
    required = [
        "SensorPanel",
        "TEMP_WARM_C = 70",
        "TEMP_HOT_C = 85",
        "FAN_MAX_RPM = 8000",
        "Sensors",
        "Live refresh: 2 s",
        "CPU Package",
        "Acer Temp 1",
        "Acer Temp 2",
        "Acer Temp 3",
        "Fan 1",
        "Fan 2",
        "sensor-ok",
        "sensor-warm",
        "sensor-hot",
        "Gtk.CssProvider",
        "#2ec27e",
        "#e5a50a",
        "#e01b24",
        '"-"',
    ]
    missing = [token for token in required if token not in src]
    if "Gtk.ProgressBar" not in src and "Gtk.LevelBar" not in src:
        missing.append("Gtk.ProgressBar or Gtk.LevelBar")
    forbidden = [
        '"/sys/class/hwmon"',
        "'/sys/class/hwmon'",
        "find_hwmon(",
        "threading.Thread",
        "GLib.idle_add",
        "time.sleep(",
    ]
    found = [token for token in forbidden if token in src]
    if missing or found:
        print(f"  FAIL  missing={missing} forbidden={found}")
        return False
    print("  PASS")
    return True


def scenario_notification_source():
    label = "Notification source contract"
    src = _require_source(GUI_NOTIFICATIONS, label)
    if src is None:
        return True
    required = [
        "ProfileChangeNotifier",
        "CriticalTempNotifier",
        'PROFILE_NOTIFICATION_ID = "profile-change"',
        'CRITICAL_NOTIFICATION_ID = "critical-temp"',
        'CRITICAL_NORMAL_NOTIFICATION_ID = "critical-temp-normal"',
        "CRITICAL_ENTER_C = 90",
        "CRITICAL_EXIT_C = 85",
        "Gio.Notification",
        'send_notification("profile-change"',
        'send_notification("critical-temp"',
        'send_notification("critical-temp-normal"',
        "_critical_active",
        ">= CRITICAL_ENTER_C",
        "< CRITICAL_EXIT_C",
        "window.show_toast",
    ]
    missing = [token for token in required if token not in src]
    forbidden = [
        "threading.Thread",
        "time.sleep(",
        "notify2",
        "gi.repository.Notify",
    ]
    found = [token for token in forbidden if token in src]
    if missing or found:
        print(f"  FAIL  missing={missing} forbidden={found}")
        return False
    print("  PASS")
    return True


def scenario_window_refresh_wiring():
    print("-> MainWindow live refresh and notification wiring")
    src = _non_comment_text(GUI_WINDOW)
    required = [
        "GLib.timeout_add_seconds(2,",
        "GLib.source_remove",
        "read_sensors()",
        "_sensor_source_id",
        "_sensor_panel",
        "_last_seen_profile_name",
        "notify_profile_change",
        "ProfileChangeNotifier",
        "CriticalTempNotifier",
        "ProfileControlPanel(self)",
        "SensorPanel(self)",
    ]
    missing = [token for token in required if token not in src]
    if missing:
        print(f"  FAIL  missing tokens: {missing}")
        return False
    print("  PASS")
    return True


def scenario_main_page_order():
    print("-> MainWindow appends profile panel before sensor panel")
    src = _non_comment_text(GUI_WINDOW)
    required = ["Gtk.ScrolledWindow", "Adw.PreferencesPage", "_main_page.add"]
    missing = [token for token in required if token not in src]
    profile_idx = src.find("ProfileControlPanel(self)")
    sensor_idx = src.find("SensorPanel(self)")
    if profile_idx == -1 or sensor_idx == -1 or profile_idx > sensor_idx:
        print(
            "  FAIL  expected ProfileControlPanel(self) before SensorPanel(self)"
        )
        return False
    if missing:
        print(f"  FAIL  missing shared page tokens: {missing}")
        return False
    print("  PASS")
    return True


def scenario_profiles_notification_handoff():
    print("-> Profile success path delegates notification routing")
    src = _non_comment_text(GUI_PROFILES)
    required = [
        "notify_profile_change",
        'hasattr(self._window, "notify_profile_change")',
        "Switched to ",
        "Authorization cancelled",
        "Profile change failed. See terminal for details.",
        "Profile not applied — power-profiles-daemon may be overriding writes",
    ]
    missing = [token for token in required if token not in src]
    success_region = src[src.find("if actual.value == requested_value:"):src.find("else:", src.find("if actual.value == requested_value:"))]
    if "notify_profile_change" not in success_region:
        missing.append("notify_profile_change in read-back success branch")
    if missing:
        print(f"  FAIL  missing tokens: {missing}")
        return False
    print("  PASS")
    return True


def build_scenarios(quick: bool):
    scenarios = [
        ("inline", scenario_ui_spec_exists),
        ("inline", scenario_new_modules_forbidden_runtime_tokens_absent),
        ("inline", scenario_no_direct_hwmon_access),
        ("inline", scenario_sensor_panel_source),
        ("inline", scenario_notification_source),
    ]
    if quick:
        return scenarios

    py_compile_files = [
        Path(__file__).resolve(),
        GUI_WINDOW,
        GUI_PROFILES,
        GUI_NOTIFICATIONS,
        GUI_SENSORS,
    ]
    py_compile_existing = [str(path) for path in py_compile_files if path.exists()]
    scenarios.extend([
        ("inline", scenario_all_phase5_forbidden_runtime_tokens_absent),
        ("inline", scenario_window_refresh_wiring),
        ("inline", scenario_main_page_order),
        ("inline", scenario_profiles_notification_handoff),
        ("run", "py_compile Phase 5 files", [
            sys.executable,
            "-m",
            "py_compile",
            *py_compile_existing,
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
    print(f"--- Phase 5 smoke ({mode}): {passed}/{len(scenarios)} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
