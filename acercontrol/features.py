# acercontrol/features.py
"""Structured feature probe for the AcerControl runtime environment (CORE-03).

Single entry point: features.probe() -> FeatureReport. Never raises;
every sysfs check goes through sysfs._read_or_none. The FeatureReport
is consumed by the CLI (Phase 2) for `acercontrol status` and by the
GUI (Phase 3) to route to Adw.StatusPage failure screens.

Smoke entry: python3 -m acercontrol.features
"""
from __future__ import annotations
import glob
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from acercontrol import core
from acercontrol.sysfs import _read_or_none, find_hwmon


Severity = Literal["blocking", "warning", "info"]

_BLACKLIST_RE = re.compile(
    r"^\s*(blacklist\s+acer_wmi|install\s+acer_wmi\s+/bin/(?:true|false))\s*(#.*)?$"
)


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


def probe() -> FeatureReport:
    """Run the full environment probe. Never raises.

    Order matters: blocking checks first, then warnings (PPD, blacklist).
    The first blocking failure is what the GUI's Adw.StatusPage will surface.
    """
    checks: list[FeatureCheck] = []

    # 1. acer_wmi module loaded
    acer_loaded = Path("/sys/module/acer_wmi").exists()
    checks.append(FeatureCheck(
        name="acer_wmi module loaded",
        present=acer_loaded,
        detail="/sys/module/acer_wmi " + ("present" if acer_loaded else "missing"),
        fix="sudo modprobe acer_wmi predator_v4=1",
        severity="blocking",
    ))

    # 2. predator_v4 mode
    pv4 = _read_or_none(core.PREDATOR_V4_PARAM)
    checks.append(FeatureCheck(
        name="predator_v4 mode",
        present=(pv4 == "Y"),
        detail=f"predator_v4={pv4!r}",
        fix=(
            "Add 'options acer_wmi predator_v4=1' to "
            "/etc/modprobe.d/99-acer-wmi.conf, then "
            "sudo update-initramfs -u, then reboot."
        ),
        severity="blocking",
    ))

    # 3. platform_profile sysfs
    pp_present = core.PROFILE_PATH.exists()
    checks.append(FeatureCheck(
        name="platform_profile sysfs",
        present=pp_present,
        detail=str(core.PROFILE_PATH) + (" present" if pp_present else " missing"),
        fix="Requires kernel with ACPI platform_profile support (>= 6.6 recommended).",
        severity="blocking",
    ))

    # 4. acer hwmon
    acer_hwmon = find_hwmon("acer", requires=("fan1_input", "temp1_input"))
    checks.append(FeatureCheck(
        name="acer hwmon (fan+temp)",
        present=acer_hwmon is not None,
        detail=acer_hwmon or "no hwmon entry named 'acer' with fan1_input+temp1_input",
        fix="Verify acer_wmi loaded with predator_v4=1; sensor exposure may lag module load.",
        severity="warning",  # GUI renders "—" placeholders rather than refusing to load
    ))

    # 5. coretemp hwmon
    coretemp_hwmon = find_hwmon("coretemp", requires=("temp1_input",))
    checks.append(FeatureCheck(
        name="coretemp hwmon",
        present=coretemp_hwmon is not None,
        detail=coretemp_hwmon or "no hwmon entry named 'coretemp'",
        fix="sudo modprobe coretemp",
        severity="info",  # CPU package temp is nice-to-have, not blocking
    ))

    # 6. PPD active state
    ppd = _ppd_active()
    if ppd is None:
        checks.append(FeatureCheck(
            name="power-profiles-daemon state",
            present=True,  # 'unknown' is not a failure here
            detail="systemctl unavailable — PPD state unknown",
            fix="",
            severity="info",
        ))
    else:
        checks.append(FeatureCheck(
            name="power-profiles-daemon inactive",
            present=not ppd,
            detail="active — will overwrite profile writes" if ppd else "inactive",
            fix="sudo systemctl mask --now power-profiles-daemon.service",
            severity="warning",
        ))

    # 7. acer_wmi blacklist entries
    blacklist = find_blacklist_entries()
    checks.append(FeatureCheck(
        name="acer_wmi not blacklisted",
        present=not blacklist,
        detail=(
            f"{len(blacklist)} blacklist entr"
            f"{'y' if len(blacklist)==1 else 'ies'}"
            if blacklist else "no blacklist entries"
        ),
        fix=(
            "Remove or comment out matching lines in /etc/modprobe.d/*.conf "
            "and run sudo update-initramfs -u, then reboot."
        ),
        severity="blocking" if blacklist else "info",
    ))

    return FeatureReport(
        checks=tuple(checks),
        blacklist_entries=tuple(blacklist),
    )


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


if __name__ == "__main__":
    import sys
    sys.exit(_print_report(probe()))
