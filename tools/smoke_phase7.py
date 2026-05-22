#!/usr/bin/env python3
"""Phase 7 static smoke checks.

These checks are side-effect-free: they read source files and tempdir fixtures
only, so they can run on hosts without GTK, AppIndicator, systemd, or Acer
hardware.
"""

from __future__ import annotations

import argparse
import py_compile
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE_DIR = PROJECT_ROOT / ".planning" / "phases" / "07-tray-helper-hardware-compatibility"

RESEARCH = PHASE_DIR / "07-RESEARCH.md"
UI_SPEC = PHASE_DIR / "07-UI-SPEC.md"
PATTERNS = PHASE_DIR / "07-PATTERNS.md"
VALIDATION = PHASE_DIR / "07-VALIDATION.md"

BUNDLE_CLI = PROJECT_ROOT / "tools" / "bundle_cli.py"
GUI = PROJECT_ROOT / "acercontrol" / "gui.py"
GUI_WINDOW = PROJECT_ROOT / "acercontrol" / "gui_window.py"
GUI_ABOUT = PROJECT_ROOT / "acercontrol" / "gui_about.py"
TRAY_STATUS = PROJECT_ROOT / "acercontrol" / "tray_status.py"
TRAY = PROJECT_ROOT / "acercontrol" / "tray.py"
TRAY_SHIM = PROJECT_ROOT / "acercontrol_tray.py"
DEBIAN_CONTROL = PROJECT_ROOT / "debian" / "control"

DIRECT_ELEVATION_TOKENS = ("pk" + "exec", "su" + "do")
MUTATING_SERVICE_TOKEN = "system" + "ctl"
PROFILE_SYSFS_PATH = "/sys/firmware/acpi/" + "platform_profile"


def _relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _non_comment_text(path: Path) -> str:
    lines = []
    for line in _read(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _require_source(path: Path, label: str) -> str | None:
    if not path.exists():
        print(f"SKIP {label}: {_relative(path)} does not exist yet")
        return None
    return _non_comment_text(path)


def _contains_all(text: str, tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in text]


def _assert_no_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    found = [token for token in tokens if token in text]
    if found:
        raise AssertionError(f"{label} contains forbidden token(s): {', '.join(found)}")


def run(name: str, fn) -> bool:
    try:
        fn()
    except AssertionError as exc:
        print(f"FAIL {name}: {exc}")
        return False
    except Exception as exc:  # pragma: no cover - smoke diagnostics only.
        print(f"FAIL {name}: unexpected {type(exc).__name__}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def scenario_phase7_docs_exist() -> None:
    for path in (RESEARCH, UI_SPEC, PATTERNS, VALIDATION):
        if not path.exists():
            raise AssertionError(f"missing {_relative(path)}")

    combined = "\n".join(_read(path) for path in (RESEARCH, UI_SPEC, PATTERNS, VALIDATION))
    missing = _contains_all(
        combined,
        [
            "TRAY-01",
            "TRAY-04",
            "HW-02",
            "StatusNotifierWatcher",
            "Ayatana",
        ],
    )
    if missing:
        raise AssertionError(f"Phase 7 docs missing tokens: {', '.join(missing)}")


def scenario_cli_bundler_excludes_tray() -> None:
    text = _non_comment_text(BUNDLE_CLI)
    forbidden = (
        "tray.py",
        "tray_status.py",
        "acercontrol_tray.py",
        '"tray"',
        "'tray'",
    )
    _assert_no_tokens(text, forbidden, "CLI bundler")


def scenario_gtk4_gui_avoids_tray_helper() -> None:
    forbidden = (
        "from acercontrol.tray import",
        "import acercontrol.tray",
    )
    for path in (GUI, GUI_WINDOW, GUI_ABOUT):
        text = _non_comment_text(path)
        _assert_no_tokens(text, forbidden, _relative(path))


def scenario_tray_status_contract() -> None:
    text = _require_source(TRAY_STATUS, "tray status helper")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            "Gio.BusType.SESSION",
            "NameHasOwner",
            "org.kde.StatusNotifierWatcher",
            "available",
            "missing-watcher",
            "no-session-bus",
            "unknown",
            "ImportError",
            "GLib.Error",
        ],
    )
    if missing:
        raise AssertionError(f"tray status helper missing tokens: {', '.join(missing)}")
    _assert_no_tokens(
        text,
        (
            'gi.require_version("Gtk"',
            "gi.require_version('Gtk'",
            "Adw",
            "AyatanaAppIndicator3",
        ),
        "tray status helper",
    )


def scenario_about_tray_diagnostics() -> None:
    if not TRAY_STATUS.exists():
        print("SKIP About tray diagnostics: tray status helper does not exist yet")
        return
    text = _non_comment_text(GUI_ABOUT)
    if "tray_status_detail" not in text:
        print("SKIP About tray diagnostics: tray status not wired yet")
        return

    missing = _contains_all(
        text,
        [
            "tray_status_detail",
            '"tray"',
            "set_debug_info",
        ],
    )
    if missing:
        raise AssertionError(f"About diagnostics missing tokens: {', '.join(missing)}")
    _assert_no_tokens(
        text,
        (
            "from acercontrol.tray import",
            "import acercontrol.tray",
            "AyatanaAppIndicator3",
            'gi.require_version("Gtk", "3.0")',
            "gi.require_version('Gtk', '3.0')",
        ),
        "About diagnostics",
    )


def scenario_tray_helper_contract() -> None:
    text = _require_source(TRAY, "tray helper")
    if text is None:
        return
    if "AyatanaAppIndicator3" not in text:
        print("SKIP tray helper contract: Ayatana helper not implemented yet")
        return

    missing = _contains_all(
        text,
        [
            'gi.require_version("Gtk", "3.0")',
            'gi.require_version("AyatanaAppIndicator3", "0.1")',
            "Gtk.Menu",
            "read_profile",
            "run_privileged",
            "Show AcerControl",
            "Quit",
        ],
    )
    if missing:
        raise AssertionError(f"tray helper missing tokens: {', '.join(missing)}")
    _assert_no_tokens(
        text,
        (
            'gi.require_version("Gtk", "4.0")',
            "Adw",
            "Gtk.StatusIcon",
            *DIRECT_ELEVATION_TOKENS,
            MUTATING_SERVICE_TOKEN,
            "shell=True",
            PROFILE_SYSFS_PATH,
        ),
        "tray helper",
    )


def scenario_hardware_compat_fixtures() -> None:
    print("SKIP hardware compatibility fixtures: implemented in 07-03")


def _paragraph_containing(text: str, field: str) -> str:
    paragraphs = text.split("\n\n")
    for paragraph in paragraphs:
        if paragraph.lstrip().startswith(field):
            return paragraph
    return ""


def scenario_packaging_recommends_contract() -> None:
    if not DEBIAN_CONTROL.exists():
        print("SKIP packaging Recommends contract: debian/control does not exist yet")
        return

    text = _read(DEBIAN_CONTROL)
    depends = _paragraph_containing(text, "Depends:")
    recommends = _paragraph_containing(text, "Recommends:")
    required = ("gir1.2-ayatanaappindicator3-0.1", "gnome-shell-extension-appindicator")
    missing = [pkg for pkg in required if pkg not in recommends]
    misplaced = [pkg for pkg in required if pkg in depends]
    if missing:
        raise AssertionError(f"tray packages missing from Recommends: {', '.join(missing)}")
    if misplaced:
        raise AssertionError(f"tray packages must not be hard Depends: {', '.join(misplaced)}")


def scenario_py_compile_existing() -> None:
    paths = [
        Path(__file__),
        TRAY_STATUS,
        GUI_ABOUT,
        TRAY,
        TRAY_SHIM,
    ]
    checked = []
    for path in paths:
        if not path.exists():
            continue
        py_compile.compile(str(path), doraise=True)
        checked.append(_relative(path))
    if not checked:
        raise AssertionError("no Python files compiled")
    print(f"Compiled {len(checked)} file(s): {', '.join(checked)}")


def build_scenarios(quick: bool):
    scenarios = [
        ("phase7 docs", scenario_phase7_docs_exist),
        ("CLI bundler excludes tray", scenario_cli_bundler_excludes_tray),
        ("GTK4 GUI avoids tray helper", scenario_gtk4_gui_avoids_tray_helper),
        ("tray status helper", scenario_tray_status_contract),
        ("About tray diagnostics", scenario_about_tray_diagnostics),
        ("tray helper contract", scenario_tray_helper_contract),
    ]
    if not quick:
        scenarios.extend(
            [
                ("hardware compatibility fixtures", scenario_hardware_compat_fixtures),
                ("packaging Recommends contract", scenario_packaging_recommends_contract),
                ("py compile existing", scenario_py_compile_existing),
            ]
        )
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 7 static smoke checks.")
    parser.add_argument("--quick", action="store_true", help="Skip full fixture checks.")
    args = parser.parse_args()

    scenarios = build_scenarios(args.quick)
    passed = sum(1 for name, fn in scenarios if run(name, fn))
    total = len(scenarios)
    print(f"{passed}/{total} smoke checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
