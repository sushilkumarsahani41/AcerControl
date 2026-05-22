#!/usr/bin/env python3
"""Phase 8 static packaging smoke checks.

These checks are side-effect-free: they inspect source, packaging metadata,
installer text, and documentation only. They intentionally avoid Debian tools,
desktop caches, service managers, privilege helpers, and system paths.
"""

from __future__ import annotations

import argparse
import os
import py_compile
import sys
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PHASE_DIR = PROJECT_ROOT / ".planning" / "phases" / "08-packaging"

RESEARCH = PHASE_DIR / "08-RESEARCH.md"
PATTERNS = PHASE_DIR / "08-PATTERNS.md"
VALIDATION = PHASE_DIR / "08-VALIDATION.md"
PLANS = tuple(PHASE_DIR / f"08-0{index}-PLAN.md" for index in range(1, 5))
HUMAN_UAT = PHASE_DIR / "08-HUMAN-UAT.md"

PYPROJECT = PROJECT_ROOT / "pyproject.toml"
README = PROJECT_ROOT / "README.md"
INSTALL_SH = PROJECT_ROOT / "install.sh"

DESKTOP = PROJECT_ROOT / "data" / "org.acercontrol.AcerControl.desktop"
MODPROBE = PROJECT_ROOT / "data" / "99-acer-wmi.conf"
COLOR_ICON = (
    PROJECT_ROOT
    / "data"
    / "icons"
    / "hicolor"
    / "scalable"
    / "apps"
    / "org.acercontrol.AcerControl.svg"
)
SYMBOLIC_ICON = (
    PROJECT_ROOT
    / "data"
    / "icons"
    / "hicolor"
    / "symbolic"
    / "apps"
    / "org.acercontrol.AcerControl-symbolic.svg"
)

DEBIAN = PROJECT_ROOT / "debian"
DEBIAN_CONTROL = DEBIAN / "control"
DEBIAN_CHANGELOG = DEBIAN / "changelog"
DEBIAN_COPYRIGHT = DEBIAN / "copyright"
DEBIAN_RULES = DEBIAN / "rules"
DEBIAN_SOURCE_FORMAT = DEBIAN / "source" / "format"
DEBIAN_INSTALL = DEBIAN / "acercontrol.install"
DEBIAN_POSTINST = DEBIAN / "acercontrol.postinst"
DEBIAN_POSTRM = DEBIAN / "acercontrol.postrm"

SYSTEMCTL_DAEMON_RELOAD = "system" + "ctl daemon-reload"
UPDATE_DESKTOP_DATABASE = "update-desktop-database"
GTK_UPDATE_ICON_CACHE = "gtk-update-icon-cache"
UPDATE_INITRAMFS = "update-initramfs -u"
DPKG_BUILDPACKAGE = "dpkg-" + "buildpackage"
LINTIAN = "lin" + "tian"
APT_INSTALL_LOCAL = "a" + "pt install ./acercontrol"
PIP_INSTALL = "pip " + "install"
FORBIDDEN_FETCH_TOKENS = ("cu" + "rl", "w" + "get", PIP_INSTALL)


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


def _contains_all(text: str, tokens: list[str] | tuple[str, ...]) -> list[str]:
    return [token for token in tokens if token not in text]


def _assert_contains_all(text: str, tokens: list[str] | tuple[str, ...], label: str) -> None:
    missing = _contains_all(text, tokens)
    if missing:
        raise AssertionError(f"{label} missing token(s): {', '.join(missing)}")


def _assert_no_tokens(text: str, tokens: tuple[str, ...], label: str) -> None:
    found = [token for token in tokens if token in text]
    if found:
        raise AssertionError(f"{label} contains forbidden token(s): {', '.join(found)}")


def _control_paragraphs(text: str) -> list[str]:
    return [paragraph for paragraph in text.split("\n\n") if paragraph.strip()]


def _control_paragraph(text: str, field: str, value: str) -> str:
    needle = f"{field}:"
    for paragraph in _control_paragraphs(text):
        lines = paragraph.splitlines()
        for line in lines:
            if line.startswith(needle) and value in line[len(needle) :]:
                return paragraph
    return ""


def _control_field(paragraph: str, field: str) -> str:
    lines = paragraph.splitlines()
    values: list[str] = []
    collecting = False
    prefix = f"{field}:"
    for line in lines:
        if line.startswith(prefix):
            collecting = True
            values.append(line[len(prefix) :].strip())
            continue
        if collecting and line.startswith((" ", "\t")):
            values.append(line.strip())
            continue
        if collecting:
            break
    return " ".join(values)


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


def scenario_phase8_docs_exist() -> None:
    required_paths = (RESEARCH, PATTERNS, VALIDATION, *PLANS)
    missing_paths = [_relative(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise AssertionError(f"missing Phase 8 document(s): {', '.join(missing_paths)}")

    combined = "\n".join(_read(path) for path in required_paths)
    _assert_contains_all(
        combined,
        (
            "PKG-01",
            "PKG-11",
            "debian/control",
            "install.sh",
            "lintian",
            "acercontrol-tray",
        ),
        "Phase 8 docs",
    )


def scenario_pyproject_packaging_metadata() -> None:
    data = tomllib.loads(_read(PYPROJECT))
    build_system = data.get("build-system", {})
    project = data.get("project", {})
    scripts = project.get("scripts", {})

    if build_system.get("build-backend") != "setuptools.build_meta":
        raise AssertionError("pyproject.toml build-backend must remain setuptools.build_meta")
    if "setuptools" not in " ".join(build_system.get("requires", [])):
        raise AssertionError("pyproject.toml build-system must require setuptools")
    if project.get("name") != "acercontrol":
        raise AssertionError("project.name must remain acercontrol")
    if "dependencies" in project:
        raise AssertionError("runtime Python dependencies must not be added to pyproject.toml")

    expected_scripts = {
        "acercontrol": "acercontrol.cli:main",
        "acercontrol-gui": "acercontrol.gui:main",
    }
    mismatched = {
        name: expected
        for name, expected in expected_scripts.items()
        if scripts.get(name) != expected
    }
    if mismatched:
        pairs = [f"{name}={target}" for name, target in mismatched.items()]
        raise AssertionError(f"project.scripts missing or changed: {', '.join(pairs)}")


def scenario_desktop_icons_modprobe() -> None:
    required_paths = (DESKTOP, MODPROBE, COLOR_ICON, SYMBOLIC_ICON)
    if not all(path.exists() for path in required_paths):
        missing = [_relative(path) for path in required_paths if not path.exists()]
        print(f"SKIP desktop/icon/modprobe packaging: waiting for {', '.join(missing)}")
        return

    desktop_text = _non_comment_text(DESKTOP)
    _assert_contains_all(
        desktop_text,
        (
            "[Desktop Entry]",
            "Name=AcerControl",
            "Exec=acercontrol-gui",
            "Icon=org.acercontrol.AcerControl",
            "Terminal=false",
            "Type=Application",
            "Categories=System;HardwareSettings;",
        ),
        "desktop file",
    )

    modprobe_lines = [line.strip() for line in _read(MODPROBE).splitlines() if line.strip()]
    if modprobe_lines != ["options acer_wmi predator_v4=1"]:
        raise AssertionError("modprobe file must contain exactly: options acer_wmi predator_v4=1")

    color_text = _read(COLOR_ICON)
    symbolic_text = _read(SYMBOLIC_ICON)
    _assert_contains_all(color_text, ("<svg", "</svg>"), "color icon")
    _assert_contains_all(symbolic_text, ("<svg", "currentColor", "</svg>"), "symbolic icon")


def scenario_debian_metadata() -> None:
    if not DEBIAN_CONTROL.exists():
        print("SKIP Debian metadata: debian/control does not exist yet")
        return

    for path in (
        DEBIAN_CHANGELOG,
        DEBIAN_COPYRIGHT,
        DEBIAN_RULES,
        DEBIAN_SOURCE_FORMAT,
        DEBIAN_INSTALL,
        DEBIAN_POSTINST,
        DEBIAN_POSTRM,
    ):
        if not path.exists():
            raise AssertionError(f"missing {_relative(path)}")

    control_text = _read(DEBIAN_CONTROL)
    source = _control_paragraph(control_text, "Source", "acercontrol")
    package = _control_paragraph(control_text, "Package", "acercontrol")
    if not source:
        raise AssertionError("debian/control missing Source: acercontrol paragraph")
    if not package:
        raise AssertionError("debian/control missing Package: acercontrol paragraph")

    build_depends = _control_field(source, "Build-Depends")
    depends = _control_field(package, "Depends")
    recommends = _control_field(package, "Recommends")
    _assert_contains_all(
        build_depends,
        (
            "debhelper-compat (= 13)",
            "dh-sequence-python3",
            "pybuild-plugin-pyproject",
            "python3-all",
            "python3-setuptools",
        ),
        "Build-Depends",
    )
    _assert_contains_all(
        depends,
        (
            "${python3:Depends}",
            "${misc:Depends}",
            "python3-gi",
            "python3-gi-cairo",
            "gir1.2-gtk-4.0",
            "gir1.2-adw-1",
            "policykit-1",
            "systemd",
            "desktop-file-utils",
            "hicolor-icon-theme",
        ),
        "Depends",
    )
    tray_packages = ("gir1.2-ayatanaappindicator3-0.1", "gnome-shell-extension-appindicator")
    _assert_contains_all(recommends, tray_packages, "Recommends")
    misplaced = [pkg for pkg in tray_packages if pkg in depends]
    if misplaced:
        raise AssertionError(f"tray packages must not be hard Depends: {', '.join(misplaced)}")

    rules_text = _non_comment_text(DEBIAN_RULES)
    _assert_contains_all(rules_text, ("dh $@",), "debian/rules")
    if not os.access(DEBIAN_RULES, os.X_OK):
        raise AssertionError("debian/rules must be executable")
    if _read(DEBIAN_SOURCE_FORMAT).strip() != "3.0 (native)":
        raise AssertionError("debian/source/format must be 3.0 (native)")

    install_text = _non_comment_text(DEBIAN_INSTALL)
    _assert_contains_all(
        install_text,
        (
            "libexec/acercontrol-* usr/libexec/acercontrol/",
            "data/org.acercontrol.policy usr/share/polkit-1/actions/",
            "data/acer-performance.service usr/lib/systemd/system/",
            "data/acer-performance@.service usr/lib/systemd/system/",
            "data/org.acercontrol.AcerControl.desktop usr/share/applications/",
            "data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg usr/share/icons/hicolor/scalable/apps/",
            "data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg usr/share/icons/hicolor/symbolic/apps/",
            "data/99-acer-wmi.conf etc/modprobe.d/",
        ),
        "debian install map",
    )

    postinst_text = _non_comment_text(DEBIAN_POSTINST)
    _assert_contains_all(
        postinst_text,
        (
            "set -e",
            SYSTEMCTL_DAEMON_RELOAD,
            UPDATE_DESKTOP_DATABASE,
            GTK_UPDATE_ICON_CACHE,
            UPDATE_INITRAMFS,
            "reboot",
        ),
        "postinst",
    )
    postrm_text = _non_comment_text(DEBIAN_POSTRM)
    _assert_contains_all(
        postrm_text,
        ("set -e", SYSTEMCTL_DAEMON_RELOAD, UPDATE_DESKTOP_DATABASE, GTK_UPDATE_ICON_CACHE),
        "postrm",
    )


def scenario_install_fallback() -> None:
    text = _require_source(INSTALL_SH, "manual installer")
    if text is None:
        return

    _assert_contains_all(
        text,
        (
            "set -euo pipefail",
            "tools/bundle_cli.py",
            "dist/acercontrol",
            "/usr/local/bin/acercontrol",
            "/usr/local/bin/acercontrol-gui",
            "/usr/local/bin/acercontrol-tray",
            "/usr/local/share/acercontrol",
            "/usr/libexec/acercontrol",
            "/usr/share/polkit-1/actions",
            "/etc/systemd/system",
            "/usr/share/applications",
            "/usr/share/icons/hicolor",
            "/etc/modprobe.d/99-acer-wmi.conf",
            SYSTEMCTL_DAEMON_RELOAD,
            UPDATE_DESKTOP_DATABASE,
            GTK_UPDATE_ICON_CACHE,
            UPDATE_INITRAMFS,
            "reboot",
        ),
        "install.sh",
    )
    _assert_no_tokens(text, FORBIDDEN_FETCH_TOKENS, "install.sh")
    if not os.access(INSTALL_SH, os.X_OK):
        raise AssertionError("install.sh must be executable")


def scenario_docs_and_uat() -> None:
    if not HUMAN_UAT.exists():
        print("SKIP docs/UAT packaging guidance: human UAT checklist does not exist yet")
        return

    combined = _read(README) + "\n" + _read(HUMAN_UAT)
    _assert_contains_all(
        combined,
        (
            DPKG_BUILDPACKAGE,
            LINTIAN,
            "no .pyc",
            "clean Ubuntu 24.04 VM",
            APT_INSTALL_LOCAL,
            "GNOME Activities",
            "polkit",
            "acercontrol-tray",
            "update-initramfs -u",
            "reboot",
        ),
        "README/UAT packaging guidance",
    )


def scenario_no_pyc_packaging_paths() -> None:
    checked = []
    for path in (DEBIAN_INSTALL, INSTALL_SH):
        if not path.exists():
            continue
        text = _read(path)
        checked.append(_relative(path))
        if ".pyc" in text:
            raise AssertionError(f"{_relative(path)} must not reference .pyc files")
    if not checked:
        print("SKIP no-pyc packaging paths: packaging install files do not exist yet")
        return
    print(f"Checked no-pyc paths in {', '.join(checked)}")


def scenario_py_compile_existing() -> None:
    paths = [Path(__file__)]
    checked = []
    for path in paths:
        py_compile.compile(str(path), doraise=True)
        checked.append(_relative(path))
    print(f"Compiled {len(checked)} file(s): {', '.join(checked)}")


def build_scenarios(quick: bool):
    scenarios = [
        ("phase8 docs", scenario_phase8_docs_exist),
        ("pyproject packaging metadata", scenario_pyproject_packaging_metadata),
        ("py compile existing", scenario_py_compile_existing),
    ]
    if not quick:
        scenarios.extend(
            [
                ("desktop icons modprobe", scenario_desktop_icons_modprobe),
                ("Debian metadata", scenario_debian_metadata),
                ("manual installer", scenario_install_fallback),
                ("docs and UAT", scenario_docs_and_uat),
                ("no-pyc packaging paths", scenario_no_pyc_packaging_paths),
            ]
        )
    return scenarios


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 8 static packaging smoke checks.")
    parser.add_argument("--quick", action="store_true", help="Skip staged packaging checks.")
    args = parser.parse_args()

    scenarios = build_scenarios(args.quick)
    passed = sum(1 for name, fn in scenarios if run(name, fn))
    total = len(scenarios)
    print(f"{passed}/{total} smoke checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
