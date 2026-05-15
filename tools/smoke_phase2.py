#!/usr/bin/env python3
"""Aggregate smoke runner for Phase 2 (acercontrol/cli.py + wrappers).

Covers PRIV-01..05 + CLI-01..07. Designed to run on:
  - macOS dev box (every privileged path goes through --dry-run; reads
    degrade to None via Phase 1 contract)
  - generic Linux without acer_wmi (same as macOS, --dry-run works)
  - PHN16-72 with acer_wmi loaded + wrappers installed (full UAT)

Style copied from tools/smoke_phase1.py.

Skip rule: when run as euid 0 (e.g. someone does `sudo python3
tools/smoke_phase2.py`), the `install` non-root scenario would EXECUTE
the real steps. The runner skips it with a clear log line in that case
so CI / macOS / Linux UAT all converge on a deterministic outcome.
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Ensure imports resolve regardless of how the runner is invoked.
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run(label: str, argv: list, *,
        expect_rc=0,
        stdin: str | None = None,
        env_extra: dict | None = None,
        check_json_parses: bool = False) -> bool:
    """Run a subprocess and return True on PASS.

    expect_rc=None means "any rc OK" (used for `status` whose rc varies
    by host). check_json_parses=True parses stdout as JSON after the rc
    check. Never raises — runner-side exceptions are caught and reported
    as FAIL.
    """
    print(f"-> {label}")
    env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}
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
        if r.stdout:
            print(f"    stdout: {r.stdout.rstrip()}")
        if r.stderr:
            print(f"    stderr: {r.stderr.rstrip()}")
        return False
    if check_json_parses:
        try:
            json.loads(r.stdout)
        except json.JSONDecodeError as e:
            print(f"  FAIL  JSON parse error: {e}")
            print(f"    stdout: {r.stdout!r}")
            return False
    print(f"  PASS")
    return True


# ── Embedded python -c source builders ─────────────────────────────

def _three_actions_check_src() -> str:
    """Return python -c source: assert policy declares exactly 3 actions
    with the expected IDs AND each action's exec.path annotation points at
    /usr/libexec/acercontrol/<wrapper-name-suffix>."""
    return (
        "import xml.etree.ElementTree as ET\n"
        f"t = ET.parse({str(Path(PROJECT_ROOT) / 'data' / 'org.acercontrol.policy')!r})\n"
        "actions = t.findall('action')\n"
        "ids = sorted(a.get('id') for a in actions)\n"
        "expected = ['org.acercontrol.manage-service','org.acercontrol.set-boot-profile','org.acercontrol.setprofile']\n"
        "assert ids == expected, (ids, expected)\n"
        "for a in actions:\n"
        "    d = a.find('defaults')\n"
        "    assert d.findtext('allow_active') == 'auth_admin_keep', a.get('id')\n"
        "    assert d.findtext('allow_any') == 'auth_admin', a.get('id')\n"
        "    assert d.findtext('allow_inactive') == 'auth_admin', a.get('id')\n"
        "    wrapper = a.get('id').replace('org.acercontrol.', 'acercontrol-')\n"
        "    paths = [an.text for an in a.findall('annotate') if an.get('key') == 'org.freedesktop.policykit.exec.path']\n"
        "    assert paths == [f'/usr/libexec/acercontrol/{wrapper}'], (a.get('id'), paths)\n"
        "print('PRIV-02 defaults OK')\n"
    )


def _drift_gate_check_src() -> str:
    """Return python -c source: assert BOTH wrappers' ALLOWED_KERNEL_VALUES
    literals equal tuple(acercontrol.profiles.PROFILES.values()) — covers
    setprofile AND set-boot-profile (ISSUE-03; same hardcoded allowlist).
    """
    wrappers = (
        str(Path(PROJECT_ROOT) / "libexec" / "acercontrol-setprofile"),
        str(Path(PROJECT_ROOT) / "libexec" / "acercontrol-set-boot-profile"),
    )
    return (
        "from acercontrol.profiles import PROFILES\n"
        "import ast, pathlib\n"
        f"wrappers = {wrappers!r}\n"
        "for w in wrappers:\n"
        "    tree = ast.parse(pathlib.Path(w).read_text())\n"
        "    allowlist = [\n"
        "        n.value\n"
        "        for stmt in tree.body\n"
        "        if isinstance(stmt, ast.Assign)\n"
        "        and any(isinstance(t, ast.Name) and t.id == 'ALLOWED_KERNEL_VALUES' for t in stmt.targets)\n"
        "        for n in stmt.value.elts\n"
        "    ]\n"
        "    assert sorted(allowlist) == sorted(PROFILES.values()), (w, allowlist, list(PROFILES.values()))\n"
        "    print(f'wrapper-allowlist drift gate OK: {w}')\n"
    )


def _injected_gi_check_src() -> str:
    """Return python -c source: copy source tree to a tempdir, inject
    `import gi` into a copy of core.py, run the bundler in the sandbox,
    assert non-zero exit AND that dist/acercontrol does not exist.
    """
    return (
        "import os, shutil, subprocess, sys, tempfile, pathlib\n"
        f"repo = {PROJECT_ROOT!r}\n"
        "td = tempfile.mkdtemp(prefix='acerctl-inject-')\n"
        "try:\n"
        "    sandbox = pathlib.Path(td)\n"
        "    (sandbox / 'acercontrol').mkdir()\n"
        "    (sandbox / 'tools').mkdir()\n"
        "    (sandbox / 'dist').mkdir()\n"
        "    for f in os.listdir(os.path.join(repo, 'acercontrol')):\n"
        "        if f.endswith('.py'):\n"
        "            shutil.copy(os.path.join(repo, 'acercontrol', f), sandbox / 'acercontrol' / f)\n"
        "    for f in ('verify_no_gtk.py', 'bundle_cli.py'):\n"
        "        shutil.copy(os.path.join(repo, 'tools', f), sandbox / 'tools' / f)\n"
        "    target = sandbox / 'acercontrol' / 'core.py'\n"
        "    target.write_text(target.read_text() + chr(10) + 'import gi  # injection' + chr(10))\n"
        "    r = subprocess.run([sys.executable, str(sandbox / 'tools' / 'bundle_cli.py')], capture_output=True, text=True, cwd=sandbox)\n"
        "    assert r.returncode != 0, (r.returncode, r.stdout, r.stderr)\n"
        "    assert not (sandbox / 'dist' / 'acercontrol').exists(), 'bundle should have been removed'\n"
        "    print('CLI-07 injected-gi rejection OK')\n"
        "finally:\n"
        "    shutil.rmtree(td, ignore_errors=True)\n"
    )


def _ssh_elevation_check_src() -> str:
    """Run `acercontrol set turbo --dry-run --json` with SSH_CONNECTION set
    and assert the parsed JSON has elevation == 'sudo' (PRIV-05 lock).
    """
    return (
        "import json, os, subprocess, sys\n"
        f"repo = {PROJECT_ROOT!r}\n"
        "env = {**os.environ, 'PYTHONPATH': repo, 'SSH_CONNECTION': '1.2.3.4 22 5.6.7.8 22'}\n"
        "r = subprocess.run([sys.executable, '-m', 'acercontrol.cli', 'set', 'turbo', '--dry-run', '--json'], capture_output=True, text=True, env=env)\n"
        "assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)\n"
        "d = json.loads(r.stdout)\n"
        "assert d['elevation'] == 'sudo', d\n"
        "print('PRIV-05 SSH_CONNECTION -> sudo OK')\n"
    )


# ── SCENARIOS ─────────────────────────────────────────────────────

CLI = [sys.executable, "-m", "acercontrol.cli"]
LIBEXEC_SETPROFILE = str(Path(PROJECT_ROOT) / "libexec" / "acercontrol-setprofile")
LIBEXEC_SET_BOOT_PROFILE = str(Path(PROJECT_ROOT) / "libexec" / "acercontrol-set-boot-profile")
LIBEXEC_MANAGE_SERVICE = str(Path(PROJECT_ROOT) / "libexec" / "acercontrol-manage-service")
VERIFY_NO_GTK = str(Path(PROJECT_ROOT) / "tools" / "verify_no_gtk.py")
BUNDLE_CLI = str(Path(PROJECT_ROOT) / "tools" / "bundle_cli.py")
DIST_BUNDLE = str(Path(PROJECT_ROOT) / "dist" / "acercontrol")


def build_scenarios() -> list:
    """Return SCENARIOS list. Built lazily so PROJECT_ROOT is bound."""
    scenarios = [
        # CLI-01
        ("CLI-01 status text", CLI + ["status"], {"expect_rc": None}),
        ("CLI-01 status JSON", CLI + ["status", "--json"],
            {"expect_rc": None, "check_json_parses": True}),

        # CLI-02
        ("CLI-02 get text", CLI + ["get"], {}),
        ("CLI-02 get --raw", CLI + ["get", "--raw"], {}),
        ("CLI-02 get JSON", CLI + ["get", "--json"], {"check_json_parses": True}),

        # CLI-03 — dry-run path covers macOS/CI
        ("CLI-03 set dry-run text", CLI + ["set", "turbo", "--dry-run"], {}),
        ("CLI-03 set dry-run JSON", CLI + ["set", "turbo", "--dry-run", "--json"],
            {"check_json_parses": True}),
        ("CLI-03 set bad profile (rc=2)", CLI + ["set", "zzzz"],
            {"expect_rc": 2}),

        # CLI-04
        ("CLI-04 list text", CLI + ["list"], {}),
        ("CLI-04 list JSON", CLI + ["list", "--json"], {"check_json_parses": True}),

        # CLI-05
        ("CLI-05 temps text", CLI + ["temps"], {}),
        ("CLI-05 temps JSON", CLI + ["temps", "--json"], {"check_json_parses": True}),
    ]

    # CLI-06 — only run install scenarios when not root (would have side effects).
    if os.geteuid() != 0:
        scenarios.append(
            ("CLI-06 install non-root (rc=0)", CLI + ["install"], {"expect_rc": 0})
        )
        scenarios.append(
            ("CLI-06 install dry-run JSON",
             CLI + ["install", "--dry-run", "--json"],
             {"check_json_parses": True})
        )
    else:
        # Skip noted in main()'s log; keep total count consistent with non-root run.
        pass

    # PRIV-05 — SSH_CONNECTION → sudo (asserted via embedded python -c)
    scenarios.append(
        ("PRIV-05 SSH_CONNECTION -> sudo",
         [sys.executable, "-c", _ssh_elevation_check_src()],
         {})
    )

    # CLI-07 — verify_no_gtk on all bundle inputs
    scenarios.append(
        ("CLI-07 verify_no_gtk inputs",
         [sys.executable, VERIFY_NO_GTK,
          *[str(Path(PROJECT_ROOT) / "acercontrol" / f)
            for f in ("profiles.py", "sysfs.py", "core.py",
                      "features.py", "privilege.py", "cli.py")],
          LIBEXEC_SETPROFILE, LIBEXEC_SET_BOOT_PROFILE, LIBEXEC_MANAGE_SERVICE],
         {})
    )

    # CLI-07 — bundle and verify the output
    scenarios.append(
        ("CLI-07 bundle_cli builds dist/acercontrol",
         [sys.executable, BUNDLE_CLI], {})
    )
    scenarios.append(
        ("CLI-07 dist/acercontrol --help runs",
         [DIST_BUNDLE, "--help"], {})
    )
    scenarios.append(
        ("CLI-07 verify_no_gtk on output",
         [sys.executable, VERIFY_NO_GTK, DIST_BUNDLE], {})
    )
    scenarios.append(
        ("CLI-07 injected-gi rejection",
         [sys.executable, "-c", _injected_gi_check_src()], {})
    )

    # PRIV-02 — XML well-formed
    scenarios.append(
        ("PRIV-02 polkit policy XML well-formed",
         [sys.executable, "-c",
          "import xml.etree.ElementTree as ET; "
          f"ET.parse({str(Path(PROJECT_ROOT) / 'data' / 'org.acercontrol.policy')!r}); "
          "print('PRIV-02 XML OK')"],
         {})
    )

    # PRIV-02 — three actions + defaults + exec.path
    scenarios.append(
        ("PRIV-02 policy three actions + defaults",
         [sys.executable, "-c", _three_actions_check_src()], {})
    )

    # Wrapper-allowlist drift gate (BOTH wrappers — ISSUE-03)
    scenarios.append(
        ("Wrapper-allowlist drift gate",
         [sys.executable, "-c", _drift_gate_check_src()], {})
    )

    # Wrapper EX_USAGE rejection scenarios
    scenarios.append(
        ("Wrapper acercontrol-setprofile rejects bad value",
         [sys.executable, LIBEXEC_SETPROFILE, "garbage"], {"expect_rc": 64})
    )
    scenarios.append(
        ("Wrapper acercontrol-setprofile rejects no argv",
         [sys.executable, LIBEXEC_SETPROFILE], {"expect_rc": 64})
    )
    scenarios.append(
        ("Wrapper acercontrol-set-boot-profile rejects bad value",
         [sys.executable, LIBEXEC_SET_BOOT_PROFILE, "garbage"], {"expect_rc": 64})
    )
    scenarios.append(
        ("Wrapper acercontrol-manage-service rejects bad action",
         [sys.executable, LIBEXEC_MANAGE_SERVICE,
          "restart", "acer-performance.service"],
         {"expect_rc": 64})
    )
    scenarios.append(
        ("Wrapper acercontrol-manage-service rejects bad service",
         [sys.executable, LIBEXEC_MANAGE_SERVICE,
          "enable", "sshd.service"],
         {"expect_rc": 64})
    )

    return scenarios


def main() -> int:
    failures: list = []
    total = 0
    try:
        # Pre-flight cleanup: remove any stale dist/acercontrol so
        # `bundle_cli builds dist/acercontrol` truly tests creation.
        try:
            stale = Path(DIST_BUNDLE)
            if stale.exists():
                stale.unlink()
        except OSError:
            pass

        if os.geteuid() == 0:
            print("SKIP CLI-06 install: running as root would have side effects")

        scenarios = build_scenarios()
        total = len(scenarios)
        for label, argv, opts in scenarios:
            if not run(label, argv, **opts):
                failures.append(label)
    except Exception as exc:  # noqa: BLE001 — outer guard so runner never raises
        print(f"FATAL: runner top-level exception: {type(exc).__name__}: {exc}")
        return 1

    passed = total - len(failures)
    print(f"--- Phase 2 smoke: {passed}/{total} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
