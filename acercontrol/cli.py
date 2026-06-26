# acercontrol/cli.py
"""AcerControl CLI — status/get/set/list/temps/install (CLI-01..06; CLI-07 stdlib-only).

Stdlib only — no gi imports (CLI-07 invariant; verify_no_gtk.py guards this).
Imports from acercontrol.* for shared logic.

Six subcommands:
    acercontrol status [--json]
    acercontrol get    [--raw] [--json]
    acercontrol set    <profile> [--dry-run] [--json]
    acercontrol list   [--json]
    acercontrol temps  [--json]
    acercontrol install [--dry-run] [--json]

Exit codes (CLI layer; orthogonal to wrapper sysexits codes):
    0 OK (including PRIV-04 idempotent cancellation)
    1 runtime failure (write/elevation/mismatch)
    2 usage error (argparse default; also unknown profile via CLI validation)
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from typing import Any

from acercontrol import (
    PROFILES,
    KERNEL_TO_UI,
    Profile,
    SensorReading,
    kernel_to_profile,
    list_available_profiles,
    probe,
    read_profile,
    read_sensors,
)
from acercontrol.privilege import (
    pick_elevation,
    resolve_wrapper,
    run_privileged,
)


__all__ = ["main"]

FAN_SPEED_PATH = "/sys/devices/platform/acer-wmi/predator_sense/fan_speed"


# ── Output helpers ─────────────────────────────────────────────────

def _emit(data, text: str, *, as_json: bool) -> None:
    """Emit either JSON (one line) or human text. data may be None when as_json."""
    if as_json:
        if data is None:
            data = {"message": text}
        sys.stdout.write(json.dumps(data, separators=(",", ":"), default=str) + "\n")
    else:
        sys.stdout.write(text + ("\n" if not text.endswith("\n") else ""))


def _sensor_to_json(s: SensorReading) -> dict:
    """Map SensorReading dataclass to the locked JSON schema (Pattern 8)."""
    return {
        "cpu_package_c": s.cpu_package_c,
        "fan1_rpm":      s.fan1_rpm,
        "fan2_rpm":      s.fan2_rpm,
        "acer_temp1_c":  s.acer_temp1_c,
        "acer_temp2_c":  s.acer_temp2_c,
        "acer_temp3_c":  s.acer_temp3_c,
    }


# ── Subcommand handlers ────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    """CLI-01: feature probe + profile + list + temps."""
    report = probe()
    prof = read_profile()
    avail = list_available_profiles()
    sensors = read_sensors()
    if args.json:
        payload = {
            "probe": {
                "checks": [
                    {
                        "name": c.name,
                        "present": c.present,
                        "detail": c.detail,
                        "fix": c.fix,
                        "severity": c.severity,
                    }
                    for c in report.checks
                ],
                "ok": report.ok,
                "first_blocking_failure": (
                    None if report.first_blocking_failure is None else {
                        "name": report.first_blocking_failure.name,
                        "fix":  report.first_blocking_failure.fix,
                    }
                ),
                "blacklist_entries": [
                    {"file": f, "line": l} for f, l in report.blacklist_entries
                ],
            },
            "profile": {
                "profile":      prof.display.lower() if prof is not Profile.CUSTOM else "custom",
                "kernel_value": prof.value,
            },
            "list": {
                "profiles": [p.display.lower() for p in avail
                             if p is not Profile.CUSTOM],
                "active":   prof.display.lower() if prof is not Profile.CUSTOM else "custom",
            },
            "temps": _sensor_to_json(sensors),
        }
        sys.stdout.write(json.dumps(payload, separators=(",", ":"), default=str) + "\n")
    else:
        print(f"AcerControl status  (probe ok={report.ok})")
        print("-" * 60)
        for c in report.checks:
            mark = "OK" if c.present else c.severity[:3].upper()
            print(f"  [{mark}] {c.name}: {c.detail}")
        print()
        print(f"Current profile: {prof.display}  (kernel: {prof.value})")
        print(f"Available:       {', '.join(p.display for p in avail) or '(unknown)'}")
        print()
        print(f"CPU package: {sensors.cpu_package_c}°C   "
              f"Fan1: {sensors.fan1_rpm} RPM   Fan2: {sensors.fan2_rpm} RPM")
    # Exit code matches features.py _print_report semantics:
    #   0 clean, 1 degraded warning, 2 blocking failure
    if not report.ok:
        return 2
    if any(c.severity == "warning" and not c.present for c in report.checks):
        return 1
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """CLI-02: print profile. --raw prints kernel value."""
    prof = read_profile()
    if args.raw:
        if args.json:
            _emit({"kernel_value": prof.value}, prof.value, as_json=True)
        else:
            print(prof.value)
    else:
        name = prof.display.lower() if prof is not Profile.CUSTOM else "custom"
        if args.json:
            _emit(
                {"profile": name, "kernel_value": prof.value},
                name,
                as_json=True,
            )
        else:
            print(name)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """CLI-04: list available profiles, mark active."""
    avail = list_available_profiles()
    active = read_profile()
    active_name = active.display.lower() if active is not Profile.CUSTOM else "custom"
    names = [p.display.lower() for p in avail if p is not Profile.CUSTOM]
    if args.json:
        _emit(
            {"profiles": names, "active": active_name},
            ",".join(names),
            as_json=True,
        )
    else:
        for n in names:
            marker = " *" if n == active_name else ""
            print(f"{n}{marker}")
    return 0


def cmd_temps(args: argparse.Namespace) -> int:
    """CLI-05: print CPU package + fan1/2 + acer temps."""
    s = read_sensors()
    if args.json:
        _emit(_sensor_to_json(s), "", as_json=True)
    else:
        print(f"CPU package:  {s.cpu_package_c}°C")
        print(f"Fan 1:        {s.fan1_rpm} RPM")
        print(f"Fan 2:        {s.fan2_rpm} RPM")
        print(f"acer temp1:   {s.acer_temp1_c}°C")
        print(f"acer temp2:   {s.acer_temp2_c}°C")
        print(f"acer temp3:   {s.acer_temp3_c}°C")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    """CLI-03: validate → escalate → write through wrapper → read back."""
    # 1. CLI-side validation (fast feedback; no polkit prompt for typos)
    if args.profile not in PROFILES:
        sys.stderr.write(
            f"unknown profile: {args.profile!r}\n"
            f"available: {', '.join(PROFILES.keys())}\n"
        )
        if args.json:
            _emit({"error": "unknown_profile", "value": args.profile},
                  "", as_json=True)
        return 2

    kernel_value = PROFILES[args.profile]

    # 2. Dry-run path (CI / macOS testing)
    if args.dry_run:
        method = pick_elevation()
        wrapper_path = resolve_wrapper("acercontrol-setprofile")
        payload = {
            "dry_run":      True,
            "profile":      args.profile,
            "kernel_value": kernel_value,
            "wrapper":      str(wrapper_path) if wrapper_path else None,
            "elevation":    method,
            "argv":         [
                "acercontrol-setprofile",
                kernel_value,
            ],
        }
        if args.json:
            _emit(payload, "", as_json=True)
        else:
            print(f"[dry-run] would set profile={args.profile} (kernel={kernel_value})")
            print(f"[dry-run] elevation={method}")
            print(f"[dry-run] wrapper={wrapper_path}")
        return 0

    # 3. Real invocation
    result = run_privileged(["acercontrol-setprofile", kernel_value])

    # 4. Translate exit codes (see privilege.py mapping table)
    if result.cancelled:
        # PRIV-04: idempotent — exit 0
        if args.json:
            _emit({"cancelled": True}, "Authentication cancelled", as_json=True)
        else:
            print("Authentication cancelled.")
        return 0
    if result.returncode == 127:
        sys.stderr.write(result.stderr or "elevation unavailable\n")
        if args.json:
            _emit({"error": "elevation_unavailable",
                   "stderr": result.stderr}, "", as_json=True)
        return 1
    if result.returncode != 0:
        sys.stderr.write(result.stderr or f"wrapper exit {result.returncode}\n")
        if args.json:
            _emit({"error": "wrapper_failed",
                   "exit_code": result.returncode,
                   "stderr": result.stderr}, "", as_json=True)
        return 1

    # 5. Read-back verification (CLI-03 exits non-zero on mismatch)
    actual = read_profile()
    if actual.value != kernel_value:
        msg = (
            f"Profile not applied — requested {args.profile} ({kernel_value}), "
            f"got {actual.display} ({actual.value}). "
            f"power-profiles-daemon may be overriding writes."
        )
        sys.stderr.write(msg + "\n")
        if args.json:
            _emit({"error": "mismatch",
                   "requested": kernel_value,
                   "actual":    actual.value}, msg, as_json=True)
        return 1

    if args.json:
        _emit({"profile": args.profile, "kernel_value": kernel_value},
              f"Switched to {args.profile}", as_json=True)
    else:
        print(f"Switched to {args.profile}")
    return 0


def _read_fan_speed() -> tuple[int, int] | None:
    """Read (cpu_pct, gpu_pct) from predator_sense/fan_speed, or None on error."""
    try:
        raw = open(FAN_SPEED_PATH).read().strip()
        parts = raw.split(",")
        return int(parts[0]), int(parts[1])
    except (OSError, ValueError, IndexError):
        return None


def _fan_mode_label(cpu: int, gpu: int) -> str:
    if cpu == 0 and gpu == 0:
        return "auto"
    if cpu == 100 and gpu == 100:
        return "max"
    return f"manual ({cpu}%)"


def cmd_fan_get(args: argparse.Namespace) -> int:
    """Show current fan RPMs and speed setting."""
    s = read_sensors()
    fan1 = s.fan1_rpm
    fan2 = s.fan2_rpm
    speeds = _read_fan_speed()
    if speeds is not None:
        cpu_pct, gpu_pct = speeds
        mode = _fan_mode_label(cpu_pct, gpu_pct)
    else:
        cpu_pct = gpu_pct = None
        mode = "unknown"
    if args.json:
        _emit(
            {
                "fan1_rpm":  fan1,
                "fan2_rpm":  fan2,
                "cpu_pct":   cpu_pct,
                "gpu_pct":   gpu_pct,
                "mode":      mode,
            },
            "",
            as_json=True,
        )
    else:
        print(f"Fan 1:   {fan1} RPM" if fan1 is not None else "Fan 1:   —")
        print(f"Fan 2:   {fan2} RPM" if fan2 is not None else "Fan 2:   —")
        print(f"Mode:    {mode}")
    return 0


def cmd_fan_set(args: argparse.Namespace) -> int:
    """Set fan mode via predator_sense/fan_speed sysfs."""
    mode = args.mode

    # Pre-flight: predator_sense/fan_speed is provided by linuwu_sense,
    # not stock acer_wmi. Surface a clear error instead of letting the
    # wrapper fail with ENOENT.
    if not os.path.exists(FAN_SPEED_PATH) and not args.dry_run:
        msg = (
            "fan control unavailable: predator_sense/fan_speed sysfs is missing.\n"
            "This interface is provided by the linuwu_sense kernel module "
            "(not stock acer_wmi).\n"
            "Run 'acercontrol status' for install instructions, or see "
            "https://github.com/0x7375646F/Linuwu-Sense"
        )
        sys.stderr.write(msg + "\n")
        if args.json:
            _emit(
                {"error": "linuwu_sense_missing", "path": FAN_SPEED_PATH},
                msg, as_json=True,
            )
        return 1

    # Build wrapper argv
    if mode == "auto":
        wrapper_argv = ["acercontrol-setfan", "auto"]
    elif mode == "max":
        wrapper_argv = ["acercontrol-setfan", "max"]
    else:  # manual
        speed_str = getattr(args, "speed", "50")
        try:
            speed = int(speed_str)
        except (TypeError, ValueError):
            speed = 50
        if not (0 <= speed <= 100):
            sys.stderr.write(f"speed {speed} out of range 0-100\n")
            if args.json:
                _emit({"error": "invalid_speed", "value": speed}, "", as_json=True)
            return 2
        wrapper_argv = ["acercontrol-setfan", "manual", str(speed)]

    if args.dry_run:
        method = pick_elevation()
        wrapper_path = resolve_wrapper("acercontrol-setfan")
        payload = {
            "dry_run":    True,
            "fan_mode":   mode,
            "wrapper_argv": wrapper_argv,
            "elevation":  method,
            "wrapper":    str(wrapper_path) if wrapper_path else None,
        }
        if args.json:
            _emit(payload, "", as_json=True)
        else:
            print(f"[dry-run] fan {mode} → {' '.join(wrapper_argv)}")
            print(f"[dry-run] elevation={method}")
        return 0

    result = run_privileged(wrapper_argv)

    if result.cancelled:
        if args.json:
            _emit({"cancelled": True}, "Authentication cancelled", as_json=True)
        else:
            print("Authentication cancelled.")
        return 0
    if result.returncode == 127:
        sys.stderr.write(result.stderr or "elevation unavailable\n")
        if args.json:
            _emit({"error": "elevation_unavailable", "stderr": result.stderr}, "", as_json=True)
        return 1
    if result.returncode != 0:
        sys.stderr.write(result.stderr or f"wrapper exit {result.returncode}\n")
        if args.json:
            _emit({"error": "wrapper_failed",
                   "exit_code": result.returncode,
                   "stderr": result.stderr}, "", as_json=True)
        return 1

    # Read-back to confirm
    speeds = _read_fan_speed()
    if args.json:
        _emit(
            {"fan_mode": mode, "cpu_pct": speeds[0] if speeds else None,
             "gpu_pct": speeds[1] if speeds else None},
            f"Fan set to {mode}",
            as_json=True,
        )
    else:
        label = _fan_mode_label(*speeds) if speeds else mode
        print(f"Fan set to {label}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Remove all files installed by install.sh."""
    FAN_SPEED = "/sys/devices/platform/acer-wmi/predator_sense/fan_speed"
    files_to_remove = [
        "/usr/local/bin/acercontrol",
        "/usr/local/bin/acercontrol-gui",
        "/usr/local/bin/acercontrol-tray",
        "/usr/share/polkit-1/actions/org.acercontrol.policy",
        "/etc/systemd/system/acer-performance.service",
        "/etc/systemd/system/acer-performance@.service",
        "/usr/share/applications/org.acercontrol.AcerControl.desktop",
        "/usr/share/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg",
        "/usr/share/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg",
        "/etc/modprobe.d/99-acer-wmi.conf",
        "/usr/share/bash-completion/completions/acercontrol",
    ]
    dirs_to_remove = [
        "/usr/local/share/acercontrol",
        "/usr/libexec/acercontrol",
    ]
    steps_list = (
        [{"step": 1, "what": "reset fans to auto",
          "cmd": f"echo 0,0 > {FAN_SPEED}"}]
        + [{"step": i + 2, "what": f"stop/disable service",
            "cmd": "systemctl stop acer-performance.service && "
                   "systemctl disable acer-performance.service"}
           for i in range(1)]
        + [{"step": i + 3, "what": f"remove {p}", "cmd": f"rm -f {p}"}
           for i, p in enumerate(files_to_remove)]
        + [{"step": len(files_to_remove) + 3 + i,
            "what": f"remove {d}/", "cmd": f"rm -rf {d}"}
           for i, d in enumerate(dirs_to_remove)]
        + [{"step": len(files_to_remove) + len(dirs_to_remove) + 3,
            "what": "reload daemons + caches",
            "cmd": "systemctl daemon-reload && "
                   "update-desktop-database /usr/share/applications && "
                   "gtk-update-icon-cache -f /usr/share/icons/hicolor && "
                   "update-initramfs -u"}]
    )

    is_root = os.geteuid() == 0

    if args.dry_run or not is_root:
        if args.json:
            _emit({"dry_run": args.dry_run, "is_root": is_root,
                   "steps": steps_list}, "", as_json=True)
        else:
            if not is_root:
                print("# Run as root to execute. Steps that would be performed:\n")
            for s in steps_list:
                print(s["cmd"])
        return 0

    import shutil

    # Reset fans to auto before removing control infrastructure
    try:
        if os.path.exists(FAN_SPEED):
            with open(FAN_SPEED, "w") as f:
                f.write("0,0")
    except OSError:
        pass

    # Stop + disable service (best-effort — may not be installed)
    for cmd in [
        ["systemctl", "stop", "acer-performance.service"],
        ["systemctl", "disable", "acer-performance.service"],
    ]:
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Remove files
    for path in files_to_remove:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            sys.stderr.write(f"uninstall: could not remove {path}: {exc}\n")

    # Remove directories
    for d in dirs_to_remove:
        try:
            shutil.rmtree(d, ignore_errors=True)
        except OSError as exc:
            sys.stderr.write(f"uninstall: could not remove {d}: {exc}\n")

    # Reload caches (best-effort)
    for cmd in [
        ["systemctl", "daemon-reload"],
        ["update-desktop-database", "/usr/share/applications"],
        ["gtk-update-icon-cache", "-f", "/usr/share/icons/hicolor"],
        ["update-initramfs", "-u"],
    ]:
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    if args.json:
        _emit({"is_root": True, "completed": True}, "", as_json=True)
    else:
        print("AcerControl uninstalled.")
        print("Reboot to fully reset acer_wmi to default parameters.")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """CLI-06: print install steps (non-root) OR execute them (root).

    Root path: steps (a)/(b)/(d) abort-on-fail rc=1.
    Step (c) `systemctl enable acer-performance.service` is **best-effort** /
    continue-on-fail with a stderr warning — Phase 6 ships the unit file;
    until then enabling will fail and that's expected.
    """
    steps_text = (
        "# AcerControl install steps\n"
        "\n"
        "# 1. Configure acer_wmi to use predator_v4 mode\n"
        "echo 'options acer_wmi predator_v4=1' "
        "> /etc/modprobe.d/99-acer-wmi.conf\n"
        "\n"
        "# 2. Reload systemd unit cache\n"
        "systemctl daemon-reload\n"
        "\n"
        "# 3. Enable the boot profile service (Phase 6 ships the unit)\n"
        "systemctl enable acer-performance.service\n"
        "\n"
        "# 4. Rebuild initramfs so the option applies on next boot\n"
        "update-initramfs -u\n"
        "\n"
        "# 5. Reboot to pick up the modprobe.d change\n"
        "reboot\n"
        "\n"
        "# Polkit policy install (root):\n"
        "#   install -m 0644 data/org.acercontrol.policy \\\n"
        "#       /usr/share/polkit-1/actions/org.acercontrol.policy\n"
    )
    steps_list = [
        {"step": 1, "what": "modprobe.d snippet",
         "cmd":  "echo 'options acer_wmi predator_v4=1' > /etc/modprobe.d/99-acer-wmi.conf"},
        {"step": 2, "what": "systemctl daemon-reload",
         "cmd":  "systemctl daemon-reload"},
        {"step": 3, "what": "enable boot service (best-effort until Phase 6)",
         "cmd":  "systemctl enable acer-performance.service"},
        {"step": 4, "what": "update-initramfs",
         "cmd":  "update-initramfs -u"},
    ]

    is_root = os.geteuid() == 0
    if args.dry_run:
        if args.json:
            _emit({"dry_run": True, "is_root": is_root,
                   "steps": steps_list}, "", as_json=True)
        else:
            print(f"[dry-run] is_root={is_root}")
            print(steps_text)
        return 0

    if not is_root:
        # CONTEXT.md lock: print + exit 0
        if args.json:
            _emit({"is_root": False, "steps": steps_list,
                   "advice": "rerun as root to execute"}, "", as_json=True)
        else:
            print(steps_text)
        return 0

    # Root path — execute steps in order. Steps (a)/(b)/(d) abort-on-fail rc=1.
    # Step (c) is continue-on-fail (Phase 6 ships the unit).
    modprobe_path = "/etc/modprobe.d/99-acer-wmi.conf"
    modprobe_content = "options acer_wmi predator_v4=1\n"

    # (a) modprobe.d snippet — abort-on-fail
    try:
        os.makedirs(os.path.dirname(modprobe_path), exist_ok=True)
        with open(modprobe_path, "w", encoding="utf-8") as f:
            f.write(modprobe_content)
    except OSError as exc:
        sys.stderr.write(f"install: modprobe.d write failed: {exc}\n")
        if args.json:
            _emit({"error": "modprobe_write_failed", "stderr": str(exc)},
                  "", as_json=True)
        return 1

    # (b) systemctl daemon-reload — abort-on-fail
    try:
        r = subprocess.run(["systemctl", "daemon-reload"],
                           capture_output=True, text=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"install: systemctl daemon-reload failed: {exc}\n")
        if args.json:
            _emit({"error": "daemon_reload_failed", "stderr": str(exc)},
                  "", as_json=True)
        return 1
    if r.returncode != 0:
        sys.stderr.write(f"install: systemctl daemon-reload failed: {r.stderr}\n")
        if args.json:
            _emit({"error": "daemon_reload_failed",
                   "exit_code": r.returncode, "stderr": r.stderr},
                  "", as_json=True)
        return 1

    # (c) systemctl enable acer-performance.service — CONTINUE-ON-FAIL
    # The unit file ships in Phase 6; until then this enable will fail
    # and that's expected. Track success/failure for the final summary.
    service_enabled = False
    try:
        r = subprocess.run(
            ["systemctl", "enable", "acer-performance.service"],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode == 0:
            service_enabled = True
        else:
            sys.stderr.write(
                "install: acer-performance.service not yet installed — "
                "will enable in Phase 6\n"
            )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(
            "install: acer-performance.service not yet installed — "
            f"will enable in Phase 6 ({exc})\n"
        )

    # (d) update-initramfs -u — abort-on-fail
    try:
        r = subprocess.run(["update-initramfs", "-u"],
                           capture_output=True, text=True, timeout=300)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"install: update-initramfs failed: {exc}\n")
        if args.json:
            _emit({"error": "update_initramfs_failed", "stderr": str(exc)},
                  "", as_json=True)
        return 1
    if r.returncode != 0:
        sys.stderr.write(f"install: update-initramfs failed: {r.stderr}\n")
        if args.json:
            _emit({"error": "update_initramfs_failed",
                   "exit_code": r.returncode, "stderr": r.stderr},
                  "", as_json=True)
        return 1

    # All required steps succeeded (step c may have warned — non-fatal)
    if args.json:
        _emit({"is_root": True, "completed": True,
               "steps_executed": 4, "service_enabled": service_enabled},
              "", as_json=True)
    else:
        print("install: complete. Reboot required for "
              "`acer_wmi predator_v4=1` to take effect.")
        if not service_enabled:
            print("install: acer-performance.service was not enabled — "
                  "Phase 6 will install the unit")
    return 0


# ── Parser construction ────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="acercontrol",
        description="Acer Predator/Nitro performance control",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # status
    p_status = sub.add_parser("status", help="full system status")
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    # get
    p_get = sub.add_parser("get", help="current profile (user-name)")
    p_get.add_argument("--raw",  action="store_true", help="print kernel value")
    p_get.add_argument("--json", action="store_true")
    p_get.set_defaults(func=cmd_get)

    # set
    p_set = sub.add_parser("set", help="set profile (requires privilege)")
    p_set.add_argument("profile", help=f"one of: {', '.join(PROFILES.keys())}")
    p_set.add_argument("--dry-run", action="store_true",
                       help="validate + print what would happen; no elevation")
    p_set.add_argument("--json",    action="store_true")
    p_set.set_defaults(func=cmd_set)

    # list
    p_list = sub.add_parser("list", help="available profiles")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    # temps
    p_temps = sub.add_parser("temps", help="CPU/fan/acer temperatures")
    p_temps.add_argument("--json", action="store_true")
    p_temps.set_defaults(func=cmd_temps)

    # install
    p_install = sub.add_parser(
        "install",
        help="print install steps; execute when run as root",
    )
    p_install.add_argument("--dry-run", action="store_true")
    p_install.add_argument("--json",    action="store_true")
    p_install.set_defaults(func=cmd_install)

    # uninstall
    p_uninstall = sub.add_parser(
        "uninstall",
        help="remove all installed files; execute when run as root",
    )
    p_uninstall.add_argument("--dry-run", action="store_true")
    p_uninstall.add_argument("--json",    action="store_true")
    p_uninstall.set_defaults(func=cmd_uninstall)

    # fan
    p_fan = sub.add_parser("fan", help="fan speed mode and monitoring")
    fan_sub = p_fan.add_subparsers(dest="fan_cmd", required=True)

    p_fan_get = fan_sub.add_parser("get", help="show current fan RPMs and controlling profile")
    p_fan_get.add_argument("--json", action="store_true")
    p_fan_get.set_defaults(func=cmd_fan_get)

    p_fan_set = fan_sub.add_parser("set", help="set fan mode (max/auto/manual)")
    p_fan_set.add_argument(
        "mode",
        choices=["max", "auto", "manual"],
        help="max=full speed, auto=firmware-controlled, manual=set fixed speed %%",
    )
    p_fan_set.add_argument(
        "speed",
        nargs="?",
        default="50",
        help="speed %% for manual mode (0-100, default 50)",
    )
    p_fan_set.add_argument("--dry-run", action="store_true",
                           help="show what would happen without elevation")
    p_fan_set.add_argument("--json", action="store_true")
    p_fan_set.set_defaults(func=cmd_fan_set)

    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
