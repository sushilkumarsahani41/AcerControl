#!/usr/bin/env python3
"""Phase 6 static smoke checks.

The checks are intentionally source-level and non-mutating so they can run on
development hosts without Acer hardware, systemd, polkit, or GTK installed.
"""

from __future__ import annotations

import argparse
import py_compile
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PHASE_DIR = PROJECT_ROOT / ".planning" / "phases" / "06-boot-persistence-suspend-resume"

RESEARCH = PHASE_DIR / "06-RESEARCH.md"
VALIDATION = PHASE_DIR / "06-VALIDATION.md"
PATTERNS = PHASE_DIR / "06-PATTERNS.md"
UI_SPEC = PHASE_DIR / "06-UI-SPEC.md"

STABLE_UNIT = PROJECT_ROOT / "data" / "acer-performance.service"
TEMPLATE_UNIT = PROJECT_ROOT / "data" / "acer-performance@.service"
SYSTEMD_FACADE = PROJECT_ROOT / "acercontrol" / "systemd.py"
GUI_BOOT = PROJECT_ROOT / "acercontrol" / "gui_boot.py"
GUI_WINDOW = PROJECT_ROOT / "acercontrol" / "gui_window.py"
GUI_PROFILES = PROJECT_ROOT / "acercontrol" / "gui_profiles.py"
GUI_RESUME = PROJECT_ROOT / "acercontrol" / "gui_resume.py"
MANAGE_SERVICE = PROJECT_ROOT / "libexec" / "acercontrol-manage-service"

DIRECT_ELEVATION_TOKENS = ("pk" + "exec", "su" + "do")


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
    except Exception as exc:  # pragma: no cover - keeps smoke diagnostics readable.
        print(f"FAIL {name}: unexpected {type(exc).__name__}: {exc}")
        return False
    print(f"PASS {name}")
    return True


def scenario_phase6_docs_exist() -> None:
    for path in (RESEARCH, VALIDATION, PATTERNS, UI_SPEC):
        if not path.exists():
            raise AssertionError(f"missing {_relative(path)}")

    combined = "\n".join(_read(path) for path in (RESEARCH, VALIDATION, PATTERNS, UI_SPEC))
    missing = _contains_all(
        combined,
        [
            "Boot Service",
            "PrepareForSleep",
            "acer-performance@.service",
            "BOOT-01",
            "BOOT-05",
        ],
    )
    if missing:
        raise AssertionError(f"Phase 6 docs missing tokens: {', '.join(missing)}")


def _assert_stable_unit_contract(text: str) -> None:
    missing = _contains_all(
        text,
        [
            "ConditionKernelModuleLoaded=acer_wmi",
            "ConditionPathExists=/sys/firmware/acpi/platform_profile",
            "After=systemd-modules-load.service",
            "Conflicts=power-profiles-daemon.service",
            "Before=graphical.target",
            "Type=oneshot",
            "RemainAfterExit=yes",
            "Environment=BOOT_PROFILE=balanced",
            "EnvironmentFile=-/etc/default/acercontrol",
            "ExecStart=/usr/libexec/acercontrol/acercontrol-setprofile ${BOOT_PROFILE}",
            "WantedBy=graphical.target",
        ],
    )
    if missing:
        raise AssertionError(f"stable unit missing tokens: {', '.join(missing)}")
    _assert_no_tokens(text, ("bash", "/bin/sh", "tee", "echo"), "stable unit")


def _assert_template_unit_contract(text: str) -> None:
    missing = _contains_all(
        text,
        [
            "ConditionKernelModuleLoaded=acer_wmi",
            "ConditionPathExists=/sys/firmware/acpi/platform_profile",
            "After=systemd-modules-load.service",
            "Conflicts=power-profiles-daemon.service",
            "Before=graphical.target",
            "Type=oneshot",
            "RemainAfterExit=yes",
            "ExecStart=/usr/libexec/acercontrol/acercontrol-setprofile %i",
            "%i",
        ],
    )
    if missing:
        raise AssertionError(f"template unit missing tokens: {', '.join(missing)}")
    _assert_no_tokens(text, ("bash", "/bin/sh", "tee", "echo"), "template unit")


def scenario_units_contract() -> None:
    any_checked = False

    stable_text = _require_source(STABLE_UNIT, "stable unit contract")
    if stable_text is not None:
        _assert_stable_unit_contract(stable_text)
        any_checked = True

    template_text = _require_source(TEMPLATE_UNIT, "template unit contract")
    if template_text is not None:
        _assert_template_unit_contract(template_text)
        any_checked = True

    if not any_checked:
        print("SKIP unit contracts: Phase 6 units do not exist yet")


def scenario_systemd_facade() -> None:
    text = _require_source(SYSTEMD_FACADE, "systemd facade")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            'BOOT_CONFIG_PATH = Path("/etc/default/acercontrol")',
            'BOOT_SERVICE = "acer-performance.service"',
            'BOOT_TEMPLATE_PREFIX = "acer-performance@"',
            "BOOT_WAIT_TIMEOUT = 5",
            "def read_boot_profile(",
            "def boot_instance_for_profile(",
            "def service_enabled(",
            "def service_active(",
            "def wait_for_boot_service(",
            "subprocess.run",
            "timeout=",
            '["systemctl", "is-active", "--wait", BOOT_SERVICE]',
        ],
    )
    if missing:
        raise AssertionError(f"systemd facade missing tokens: {', '.join(missing)}")
    _assert_no_tokens(text, ("gi", "Gtk", "Adw"), "systemd facade")


def scenario_manage_service_allowlist() -> None:
    text = _require_source(MANAGE_SERVICE, "service wrapper allowlist")
    if text is None:
        return
    if not STABLE_UNIT.exists() or not TEMPLATE_UNIT.exists() or not SYSTEMD_FACADE.exists():
        print("SKIP service wrapper allowlist: boot service substrate not complete yet")
        return

    missing = _contains_all(
        text,
        [
            '"acer-performance.service"',
            '"acer-performance@low-power.service"',
            '"acer-performance@quiet.service"',
            '"acer-performance@balanced.service"',
            '"acer-performance@balanced-performance.service"',
            '"acer-performance@performance.service"',
            "ALLOWED_SERVICES",
        ],
    )
    if missing:
        raise AssertionError(f"service wrapper missing allowlist tokens: {', '.join(missing)}")

    result = subprocess.run(
        [str(MANAGE_SERVICE), "enable", "ssh.service"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 0:
        raise AssertionError("service wrapper accepted an unrelated service")
    if "unsupported service" not in (result.stderr + result.stdout):
        raise AssertionError("service wrapper rejection did not explain unsupported service")


def scenario_gui_boot_source() -> None:
    text = _require_source(GUI_BOOT, "GUI boot panel")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            "class BootServicePanel",
            "Adw.PreferencesGroup",
            "Adw.ActionRow",
            "Adw.ComboRow",
            "Gtk.Switch",
            "read_boot_profile",
            "boot_instance_for_profile",
            "service_enabled",
            "service_active",
            "run_privileged",
            "acercontrol-manage-service",
        ],
    )
    if missing:
        raise AssertionError(f"GUI boot panel missing tokens: {', '.join(missing)}")
    _assert_no_tokens(text, DIRECT_ELEVATION_TOKENS, "GUI boot panel")


def scenario_window_boot_wiring() -> None:
    if not GUI_BOOT.exists():
        print("SKIP window boot wiring: GUI boot panel does not exist yet")
        return
    text = _require_source(GUI_WINDOW, "window boot wiring")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            "BootServicePanel",
            "_boot_panel",
            "SensorPanel(self)",
            "ensure_boot_service_ready",
            "wait_for_boot_service",
        ],
    )
    if missing:
        raise AssertionError(f"window boot wiring missing tokens: {', '.join(missing)}")
    if text.find("SensorPanel(self)") > text.find("BootServicePanel(self)"):
        raise AssertionError("boot panel should be below the sensor panel")


def scenario_profiles_wait_guard() -> None:
    if not GUI_BOOT.exists():
        print("SKIP profile wait guard: GUI boot panel does not exist yet")
        return
    text = _require_source(GUI_PROFILES, "profile wait guard")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            "ensure_boot_service_ready",
            'run_privileged(["acercontrol-setprofile", PROFILES[',
        ],
    )
    if missing:
        raise AssertionError(f"profile wait guard missing tokens: {', '.join(missing)}")
    if text.find("ensure_boot_service_ready") > text.find('run_privileged(["acercontrol-setprofile", PROFILES['):
        raise AssertionError("profile writes must wait for boot service readiness first")


def scenario_resume_source() -> None:
    text = _require_source(GUI_RESUME, "resume controller")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            "class ResumeReapplyController",
            "Gio.BusType.SYSTEM",
            "signal_subscribe",
            "org.freedesktop.login1",
            "PrepareForSleep",
            "/org/freedesktop/login1",
            "signal_unsubscribe",
            "reapply_last_profile_after_resume",
            "GLib.Error",
        ],
    )
    if missing:
        raise AssertionError(f"resume controller missing tokens: {', '.join(missing)}")
    _assert_no_tokens(text, DIRECT_ELEVATION_TOKENS, "resume controller")


def scenario_window_resume_wiring() -> None:
    if not GUI_RESUME.exists():
        print("SKIP window resume wiring: resume controller does not exist yet")
        return
    text = _require_source(GUI_WINDOW, "window resume wiring")
    if text is None:
        return

    missing = _contains_all(
        text,
        [
            "ResumeReapplyController",
            "_resume_controller",
            "reapply_last_profile_after_resume",
            "Profile restored after resume",
            'run_privileged(["acercontrol-setprofile", PROFILES[',
            "self._resume_controller.stop()",
        ],
    )
    if missing:
        raise AssertionError(f"window resume wiring missing tokens: {', '.join(missing)}")


def scenario_py_compile_existing() -> None:
    paths = [
        Path(__file__),
        SYSTEMD_FACADE,
        GUI_BOOT,
        GUI_WINDOW,
        GUI_PROFILES,
        GUI_RESUME,
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
        ("phase6 docs", scenario_phase6_docs_exist),
        ("unit contracts", scenario_units_contract),
        ("systemd facade", scenario_systemd_facade),
        ("GUI boot panel", scenario_gui_boot_source),
        ("window boot wiring", scenario_window_boot_wiring),
        ("profile wait guard", scenario_profiles_wait_guard),
        ("resume controller", scenario_resume_source),
        ("window resume wiring", scenario_window_resume_wiring),
    ]
    if not quick:
        scenarios.extend(
            [
                ("service wrapper allowlist", scenario_manage_service_allowlist),
                ("py compile existing", scenario_py_compile_existing),
            ]
        )
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 6 static smoke checks.")
    parser.add_argument("--quick", action="store_true", help="Skip slower/full checks.")
    args = parser.parse_args()

    scenarios = build_scenarios(args.quick)
    passed = sum(1 for name, fn in scenarios if run(name, fn))
    total = len(scenarios)
    print(f"{passed}/{total} smoke checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
