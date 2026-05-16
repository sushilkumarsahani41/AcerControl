---
phase: 03-gui-shell-failure-ppd
verified: 2026-05-16T23:10:00Z
status: gaps_found
score: 22/23 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Clicking [Load module] on the acer_wmi_not_loaded StatusPage successfully reloads the module via run_privileged([\"acercontrol-reload-acer-wmi\"])"
    status: failed
    reason: "libexec/acercontrol-reload-acer-wmi unconditionally runs `modprobe -r acer_wmi` with check=True before the load step. On the acer_wmi-not-loaded path (the exact scenario SC#2 exercises), kmod returns ENOENT, subprocess.CalledProcessError is raised, the except branch returns EX_OSERR=71, and the follow-up `modprobe acer_wmi predator_v4=1` never runs. The GUI shows the toast 'Operation failed. See terminal for details.' instead of the intended remediation. This is the primary first-run failure surface and the most user-visible remediation in Phase 3 — it is broken end-to-end. (Confirmed by code review BL-01.)"
    artifacts:
      - path: "libexec/acercontrol-reload-acer-wmi"
        issue: "Lines 42-49: unconditional `modprobe -r acer_wmi` with check=True before the load step. No guard on `/sys/module/acer_wmi` existence."
    missing:
      - "Gate `modprobe -r acer_wmi` on `os.path.exists('/sys/module/acer_wmi')` before the unload step, OR drop check=True from the unload call and treat any non-zero rc as 'already unloaded, proceed to load'."
      - "Optional: add a smoke scenario that asserts the unloaded-module path is handled (mock /sys/module/ absence) so this regression is caught next time."
human_verification:
  - test: "Single-instance window focus (SC#1 runtime)"
    expected: "Launching `acercontrol-gui` while a window is already open focuses the existing window instead of opening a duplicate."
    why_human: "Requires Linux + X11/Wayland display + dbus session. Code shape verified (application_id literal correct; do_activate uses self.props.active_window.present()), but actual focus behaviour cannot be exercised on macOS orchestrator."
  - test: "StatusPage routing on acer_wmi unloaded (SC#2 runtime — module-loaded variant only)"
    expected: "With `sudo modprobe -r acer_wmi`, GUI shows 'acer_wmi module not loaded' StatusPage with 'Load module' button. Predator_v4=N variant renders 'Reload with predator_v4=1' button. platform_profile missing renders read-only kernel-version explanation."
    why_human: "Requires breaking the host (sudo modprobe -r / sudo mv on real PHN16-72). NOTE: the 'Load module' branch is BLOCKED by gap BL-01 — even with all hardware in place, the CTA will fail until the wrapper is fixed."
  - test: "PPD banner end-to-end + polkit dialog text (SC#3)"
    expected: "With `sudo systemctl unmask power-profiles-daemon && sudo systemctl start power-profiles-daemon`, GUI shows persistent banner 'power-profiles-daemon is running and will overwrite profile changes' with 'Disable PPD' button. Clicking opens polkit dialog reading exactly 'Authentication is required to disable power-profiles-daemon'. After auth, banner disappears."
    why_human: "Polkit dialog rendering, exact message string from <message> element, and systemctl-state-driven banner removal require Linux + GUI session + PPD installed."
  - test: "Mask idempotency (Landmine #3)"
    expected: "`sudo /usr/libexec/acercontrol/acercontrol-disable-ppd mask power-profiles-daemon.service` returns exit 0 on first run AND on second run (already-masked case returns silent EX_OK)."
    why_human: "Requires real systemctl + root on Linux. Code shape verified (is-enabled pre-probe + early EX_OK on matching state)."
  - test: "Polkit dialog text on module reload (GUI-03)"
    expected: "Clicking 'Load module' / 'Reload with predator_v4=1' triggers polkit dialog reading exactly 'Authentication is required to reload the acer_wmi kernel module'."
    why_human: "Polkit dialog rendering requires Linux + GUI session. Policy XML message literal verified, but actual rendering must be checked on PHN16-72. NOTE: blocked by BL-01 on the unloaded-module branch."
  - test: "Landmine #1 fallback rendering (GUI-04 HeaderBar primary menu)"
    expected: "HeaderBar primary menu (open-menu-symbolic) → 'About power-profiles-daemon' opens explainer Adw.Window with the verbatim copy. Banner title remains plain text (no Pango <a href> active link rendered)."
    why_human: "Visual / interaction test requires GTK4 + libadwaita 1.5 rendering."
  - test: "D-04 dismissibility flow"
    expected: "With PPD active and banner visible, primary menu shows 'Hide PPD warning this session'. Clicking → banner disappears AND the menu entry itself disappears (hidden-when='action-disabled'). Close + relaunch → banner re-appears."
    why_human: "Requires PPD running on real Linux + interactive GUI session. GAction enabled-state flips at 3 sites — visual confirmation needed."
  - test: "PRIV-04 cancel-on-Escape"
    expected: "Pressing Escape on the polkit auth dialog triggered from a GUI button produces toast 'Authentication cancelled.' and no traceback. No re-probe."
    why_human: "Interactive polkit dialog dismissal."
  - test: "Landmine #4 — console-script entry-point after dev install"
    expected: "After `pip install -e . --force-reinstall`, `acercontrol-gui` appears in `importlib.metadata.entry_points(group='console_scripts')` and `which acercontrol-gui` returns a path."
    why_human: "Smoke runner SKIPs the entry-point check (not FAILs) when dev install hasn't been performed. The pyproject.toml [project.scripts] declaration is verified; runtime registration requires a one-time install step on the developer machine."
---

# Phase 3: GUI Shell + Failure States + PPD Banner Verification Report

**Phase Goal:** Stand up the `Adw.Application` shell wired to single-instance, register the application ID, and make `features.probe()` the first thing that runs on `do_activate`. Each failed probe routes to a dedicated `Adw.StatusPage` with copy-able fix-it text and (where possible) one-click remediation. PPD active surfaces as a persistent `Adw.Banner` with `[Disable PPD]` / `[Learn more]`. No profile buttons, no sensors yet.

**Verified:** 2026-05-16T23:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### ROADMAP Success Criteria

| # | Success Criterion | Status | Evidence |
|---|------------------|--------|----------|
| 1 | Second launch focuses existing window via `Adw.Application(application_id="org.acercontrol.AcerControl")` | PASSED (code) / needs human (runtime) | `acercontrol/gui.py:27` declares the literal application_id. `gui.py:34-40` `do_activate` uses `self.props.active_window or MainWindow(...)` then `.present()`. Actual focus behaviour can only be exercised on Linux. |
| 2 | acer_wmi unloaded → StatusPage "acer_wmi module not loaded" + "Load module" button invoking pkexec reload helper; predator_v4=N → "Reload with predator_v4=1"; platform_profile missing → read-only explanation | FAILED | StatusPage factories and routing are correct (`gui_status_pages.py:34-90`; `gui_window.py:140-164`); button wiring to `run_privileged(["acercontrol-reload-acer-wmi"])` is in place (`gui_window.py:246`). **However, the reload wrapper itself is broken on the acer_wmi-not-loaded path** — see BL-01. CTA fails end-to-end on the most visible first-run failure surface. |
| 3 | PPD active → persistent `Adw.Banner` "power-profiles-daemon is running and will overwrite profile changes" with [Disable PPD] (pkexec systemctl mask --now) + [Learn more] | PASSED (code) / needs human (runtime) | Banner literal matches verbatim (`gui_banner.py:23-25`). [Disable PPD] wired to `run_privileged(["acercontrol-disable-ppd", "mask", "power-profiles-daemon.service"])` (`gui_window.py:231-243`). Wrapper invokes `systemctl mask --now <svc>` (line 74-77). [Learn more] = HeaderBar primary menu entry "About power-profiles-daemon" (Landmine #1 fallback — `Adw.Banner` does not propagate Pango `<a href>` activation). Runtime banner appearance + polkit dialog text require Linux. |
| 4 | Grepping GUI source for raw kernel values returns no matches outside `profiles.py` mapping and About → Diagnostics | VERIFIED | Manual grep `grep -nE '"low-power"|"balanced-performance"|"performance"' acercontrol/gui{,_window,_status_pages,_banner}.py` returns no matches. Smoke runner `scenario_gui08_grep_gate` confirms (PASS). `gui_about.py` is the documented carve-out (sole exempt zone). |

### Observable Truths (from PLAN frontmatter)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Single-instance via Adw.Application + DEFAULT_FLAGS + active_window.present() | PASSED (code) | `gui.py:23-40` matches exactly. application_id="org.acercontrol.AcerControl"; flags=Gio.ApplicationFlags.DEFAULT_FLAGS. Runtime behaviour → human. |
| 2 | MainWindow = Adw.ApplicationWindow + ToolbarView(HeaderBar) + ToastOverlay(Stack); title "AcerControl"; 800×600 | VERIFIED | `gui_window.py:41-69`: ApplicationWindow subclass; ToolbarView + add_top_bar(HeaderBar); ToastOverlay child = Stack; title and size set. |
| 3 | features.probe() runs FIRST on do_activate before user-visible content | VERIFIED | `gui_window.py:80` — `self._route(probe())` is the last call in `__init__`, after layout construction. Single synchronous call before window present. |
| 4 | Blocker failure → full-window Adw.StatusPage with UI-SPEC copy | VERIFIED | `gui_status_pages.py:34-90` — 4 factories with verbatim titles ("acer_wmi module not loaded", "Predator mode disabled", "platform_profile interface unavailable", "Acer sensors unavailable"); CTAs ("Load module", "Reload with predator_v4=1", read-only Refresh on remaining two). Dispatch via BLOCKER_FACTORIES (lines 105-110). |
| 5 | All-clear + PPD active → persistent Adw.Banner plain-text title; single "Disable PPD" button; "About PPD" via HeaderBar primary menu | VERIFIED | `gui_banner.py:20-30` — title is plain text (no set_use_markup); single button label "Disable PPD"; `.warning` CSS class. HeaderBar primary menu in `gui_window.py:84-130` includes "About power-profiles-daemon" → `show_ppd_explainer`. |
| 6 | [Disable PPD] click → run_privileged(["acercontrol-disable-ppd", "mask", "power-profiles-daemon.service"]); polkit dialog reads literal message | PASSED (code) | `gui_window.py:231-243` invokes exactly this argv. Policy XML message string in `data/org.acercontrol.policy:49`. Dialog rendering → human. |
| 7 | [Load module] / [Reload with predator_v4=1] click → run_privileged(["acercontrol-reload-acer-wmi"]); polkit dialog reads literal message | PARTIAL | Argv invocation correct (`gui_window.py:246`); policy XML message correct (`org.acercontrol.policy:61`). **Wrapper itself broken on Load-module path — see BL-01 gap.** |
| 8 | Both new wrappers in libexec/ with /usr/bin/python3 shebang, stdlib-only, hardcoded allowlists, sysexits codes, no acercontrol.* imports | VERIFIED | `libexec/acercontrol-disable-ppd`: shebang line 1, imports os/subprocess/sys only, ALLOWED_ACTIONS/ALLOWED_SERVICES literal tuples, EX_OK/EX_USAGE/EX_OSERR/EX_NOPERM defined. Same for `acercontrol-reload-acer-wmi`. Both 0755 perms. |
| 9 | disable-ppd is idempotent on already-masked; preserves underlying systemctl rc (no WR-03 collapse) | VERIFIED (code) | `acercontrol-disable-ppd:56-70` pre-probes via systemctl is-enabled and returns EX_OK on matching state. Line 88 `return result.returncode` (no collapse to EX_OSERR). Runtime mask-twice idempotency → human UAT. |
| 10 | reload-acer-wmi takes zero argv; runs /usr/sbin/modprobe -r then -modprobe-load with predator_v4=1 | PARTIAL | argv-less contract enforced (lines 31-36); absolute path /usr/sbin/modprobe used (line 19). **But unconditional unload-with-check=True breaks SC#2 — see BL-01.** |
| 11 | Polkit policy XML well-formed; 5 actions; new exec.path annotations literal; auth_admin_keep / auth_admin / auth_admin | VERIFIED | `org.acercontrol.policy:5-70` parses; 5 `<action>` blocks present; `org.acercontrol.disable-ppd` (lines 47-56) and `org.acercontrol.reload-acer-wmi` (lines 59-68) have exec.path pointing at /usr/libexec/acercontrol/<basename>; defaults match. Smoke `scenario_policy_xml_well_formed` PASS. |
| 12 | privilege.WRAPPER_NAMES extended 3→5 in order; resolve_wrapper raises ValueError on unknown | VERIFIED | `privilege.py:26-32` — tuple now contains 5 names in declared order. `resolve_wrapper:45-46` raises ValueError on unknown. Phase 2 regression smoke (28/28) confirms existing 3 names still resolve. |
| 13 | features.py severities match Phase 3 routing (acer hwmon blocking; coretemp warning; blacklist warning when found) | VERIFIED | `features.py:148` `severity="blocking"` on acer hwmon; line 158 `severity="warning"` on coretemp; line 194 `severity="warning" if blacklist else "info"`. Phase 1 smoke 6/6 still green. Smoke `scenario_features_severity_post_patch` PASS. |
| 14 | pyproject.toml [project.scripts] declares acercontrol-gui = "acercontrol.gui:main" | VERIFIED | `pyproject.toml:34`. Entry-point runtime registration check is SKIP (gated on `pip install -e .`). |
| 15 | All 5 GUI modules have BARE `import gi; gi.require_version(...)` at module top (no try/except wrapping) | VERIFIED | gui.py:15-17, gui_window.py:20-22, gui_status_pages.py:13-15, gui_banner.py:14-16, gui_about.py:16-18 — all bare imports. Smoke `scenario_gui_modules_import_cleanly` PASS (ImportError/ValueError only). |
| 16 | GUI-08 grep gate: forbidden literals absent from gui*.py except gui_about.py | VERIFIED | Manual grep returns no matches. Smoke `scenario_gui08_grep_gate` PASS. |
| 17 | Bundler invariant unchanged: BUNDLE_ORDER has no gui_ substring; verify_no_gtk gates green | VERIFIED | Smoke runner: `scenario_bundler_input_excludes_gui` PASS; `verify_no_gtk` on bundler input list PASS; SANITY check on gui.py reports tainted (rc=1) PASS; bundler-built dist/acercontrol GTK-free PASS. |
| 18 | smoke_phase3.py --quick exits 0 on macOS and Linux | VERIFIED | Quick mode 13 scenarios. (Full mode run: 17/17 PASS — confirmed in this session.) |
| 19 | smoke_phase3.py full additionally asserts severities, entry-point (SKIP if absent), exec.path annotations | VERIFIED | Full run: 17/17 PASS (entry-point SKIPped as expected on macOS without dev install). |
| 20 | Regression: smoke_phase1.py and smoke_phase2.py both exit 0 unchanged | VERIFIED | Both regressions executed this session: phase 1 = 6/6 PASS, phase 2 = 28/28 PASS. |
| 21 | PPD banner dismissible via HeaderBar menu entry "Hide PPD warning this session" wired to win.hide-ppd-banner GAction; hidden-when="action-disabled" | VERIFIED (code) | `gui_window.py:103-109` constructs Gio.MenuItem with hidden-when attribute; `gui_window.py:125-128` registers GAction (initially disabled); `gui_window.py:204-206` flips enabled-state in `_rebuild_warning_banners`; `gui_window.py:208-214` flips it on banner dismissal. Smoke `scenario_dismiss_menu_entry_present` PASS. Visual rendering → human. |
| 22 | show_ppd_banner(force=True) re-surfaces banner regardless of dismiss flag; re-enables hide-ppd-banner GAction | VERIFIED | `gui_window.py:216-224` — force=True resets `_ppd_banner_dismissed`, re-runs `_route(probe())` (which calls `_rebuild_warning_banners` → re-enables GAction at Site #2), and explicitly calls `set_revealed(True)` on the banner. |
| 23 | (ROADMAP SC#4) Raw kernel values do not leak into user-facing labels | VERIFIED | (See Success Criterion #4 above.) |

**Score:** 22/23 truths verified (1 FAILED — BL-01 / SC#2 remediation CTA).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `acercontrol/gui.py` | Adw.Application subclass with application_id literal | VERIFIED | 49 LOC; literal present (line 27); main() entry-point. |
| `acercontrol/gui_window.py` | MainWindow with ToolbarView + probe-first routing + signal handlers + dismiss action | VERIFIED | 254 LOC; all required tokens present; 3-site GAction enabled-state flip implemented. |
| `acercontrol/gui_about.py` | About dialog with set_debug_info as GUI-08 carve-out | VERIFIED | 75 LOC; `set_debug_info(json.dumps(_report_to_dict(probe())))` (line 65-66); present(parent) used (Landmine #7). |
| `acercontrol/gui_status_pages.py` | 4 blocker factories + BLOCKER_FACTORIES dispatch | VERIFIED | 110 LOC; all 4 factory functions + placeholder_ok + dispatch table. Verbatim UI-SPEC copy. |
| `acercontrol/gui_banner.py` | build_ppd_banner (plain title) + blacklist + coretemp banners + show_ppd_explainer | VERIFIED | 102 LOC; PPD title literal matches SC#3 verbatim; no use_markup; explainer dialog 480×360 modal. |
| `libexec/acercontrol-disable-ppd` | Allowlist mask/unmask × power-profiles-daemon.service; idempotent; preserves rc | VERIFIED (with minor WR-01/WR-02 warnings — see review) | 92 LOC, 0755. Idempotency probe present. rc preserved. |
| `libexec/acercontrol-reload-acer-wmi` | Argv-less; absolute modprobe path; modprobe -r then modprobe with predator_v4=1 | STUB (functional defect) | 66 LOC, 0755. Argv-less contract and absolute path correct, but BL-01 — the unconditional `modprobe -r` with check=True breaks the unloaded-module path. The artifact exists and is wired, but the runtime contract for the "Load module" CTA is broken. |
| `data/org.acercontrol.policy` | 5 actions; 2 new with exec.path annotations + literal messages | VERIFIED | XML parses; 5 actions; new actions' exec.path strings match expected wrapper paths. |
| `pyproject.toml` | acercontrol-gui = "acercontrol.gui:main" in [project.scripts] | VERIFIED | Line 34. |
| `tools/smoke_phase3.py` | Aggregate runner: XML, wrapper argv, GUI import pattern, GUI-08 grep, bundler regression, severity, entry-point | VERIFIED | 370 LOC; --quick mode supported; 17 scenarios (full); cross-platform. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `gui.py` | `gui_window.py` | `from acercontrol.gui_window import MainWindow` | WIRED | gui.py:20. |
| `gui_window.py` | `gui_status_pages.py` + `gui_banner.py` + `gui_about.py` | imports of BLOCKER_FACTORIES, placeholder_ok, build_ppd_banner, build_blacklist_banner, build_coretemp_banner, show_ppd_explainer, show_about | WIRED | gui_window.py:28-38. |
| `gui_window.py` | `features.py` + `privilege.py` | `from acercontrol.features import probe, FeatureReport`; `from acercontrol.privilege import run_privileged` | WIRED | gui_window.py:25-26. |
| `gui_window.py` | `libexec/acercontrol-disable-ppd` | `run_privileged(["acercontrol-disable-ppd", "mask", "power-profiles-daemon.service"])` | WIRED | gui_window.py:233. |
| `gui_window.py` | `libexec/acercontrol-reload-acer-wmi` | `run_privileged(["acercontrol-reload-acer-wmi"])` | WIRED (but downstream broken) | gui_window.py:246 calls the wrapper correctly; wrapper itself fails on unloaded-module path (BL-01). |
| `data/org.acercontrol.policy` | `/usr/libexec/acercontrol/acercontrol-disable-ppd` + `.../acercontrol-reload-acer-wmi` | `<annotate key="org.freedesktop.policykit.exec.path">…</annotate>` | WIRED | Lines 55 + 67. Smoke validates literal exec.path strings. |
| `privilege.py` | New wrappers on disk | `WRAPPER_NAMES` extended; resolve_wrapper walks `_WRAPPER_DIRS` and `$ACERCONTROL_DEV/libexec/` | WIRED | privilege.py:26-32. |
| `gui_about.py` | `features.probe` (GUI-08 carve-out) | `Adw.AboutDialog.set_debug_info(json.dumps(_report_to_dict(probe())))` | WIRED | gui_about.py:54-67. |
| `pyproject.toml [project.scripts]` | `acercontrol.gui:main` | entry_point | WIRED | Line 34. Registration runtime check is SKIP without `pip install -e .`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `MainWindow._route` | `report` | `features.probe()` returning FeatureReport with 7 checks | YES — probe() is Phase 1 verified, returns real FeatureReport (smoke phase 1 6/6) | FLOWING |
| `gui_about.set_debug_info` | `debug_json` | `json.dumps(_report_to_dict(probe()), indent=2)` | YES — real probe data serialized to JSON | FLOWING |
| `_on_disable_ppd_clicked` → toast | `result` | `run_privileged([...])` returning PrivilegedResult | YES (will return real subprocess result on Linux; on macOS returns rc=127 wrapper-not-installed, but that is correct behaviour) | FLOWING |
| `_on_reload_acer_wmi_clicked` → toast | `result` | `run_privileged([...])` | FLOWING TO HOLLOW: wrapper exists and is invoked; on unloaded-module path the wrapper returns EX_OSERR and the toast shows "Operation failed" instead of the intended remediation. The data flow is intact; the wrapper logic is wrong. → see BL-01 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 3 full smoke | `python3 tools/smoke_phase3.py` | 17/17 passed | PASS |
| Phase 1 regression | `python3 tools/smoke_phase1.py` | 6/6 passed | PASS |
| Phase 2 regression | `python3 tools/smoke_phase2.py` | 28/28 passed | PASS |
| Manual GUI-08 grep gate | `grep -nE '"low-power"\|"balanced-performance"\|"performance"' gui{,_window,_status_pages,_banner}.py` | no matches | PASS |
| Application ID literal | `grep -nE 'application_id="org.acercontrol.AcerControl"' gui.py` | gui.py:27 match | PASS |
| Module-import chain (key links) | `grep` for imports across gui*.py | all present | PASS |
| Wrapper file perms | `stat -f '%Mp%Lp' libexec/acercontrol-disable-ppd libexec/acercontrol-reload-acer-wmi` | 0755 / 0755 | PASS |

**Note:** Smoke gates assert argv rejection and structural shape; they do NOT exercise the runtime path of the reload wrapper against a real (or simulated) unloaded-module state. Green smoke is consistent with BL-01 being present.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| GUI-01 | 03-01-PLAN.md | Adw.Application with application_id, ApplicationWindow + ToolbarView + HeaderBar | SATISFIED (code) | gui.py:27 application_id literal; gui_window.py:41-69 widget hierarchy. Runtime structure → human UAT. |
| GUI-02 | 03-01-PLAN.md | Second launch focuses existing window | SATISFIED (code) / needs human (runtime) | gui.py:34-40 do_activate logic correct. Runtime focus → human UAT. |
| GUI-03 | 03-01-PLAN.md | features.probe() runs on startup; failed probes → Adw.StatusPage with fix-it text and one-click remediation buttons (reload module, mask PPD) | PARTIAL | StatusPage rendering + routing PASSED. PPD-mask remediation PASSED (code). **acer_wmi reload remediation BLOCKED by BL-01.** |
| GUI-04 | 03-01-PLAN.md | PPD active → persistent Adw.Banner with [Disable PPD] + [Learn more]; pkexec systemctl mask --now power-profiles-daemon | SATISFIED (code) / needs human (runtime) | Banner literal + button + wrapper invocation all verified in code. Polkit dialog text + banner removal → human UAT. |
| GUI-08 | 03-01-PLAN.md | No raw kernel profile values in user-facing UI; only in About → Diagnostics | SATISFIED | Manual grep + smoke gate both clean. gui_about.py is documented carve-out. |

No orphaned requirements: REQUIREMENTS.md maps GUI-01, GUI-02, GUI-03, GUI-04, GUI-08 to Phase 3 — all 5 are claimed by 03-01-PLAN.md frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `libexec/acercontrol-reload-acer-wmi` | 42-49 | Unconditional `modprobe -r acer_wmi` with `check=True` before load step | BLOCKER | Breaks SC#2 "Load module" CTA on the most visible first-run failure path. See BL-01 in 03-REVIEW.md. |
| `acercontrol/gui_window.py` | 150 | `assert blocker is not None` in production codepath (stripped under -O) | Warning | Risk of AttributeError on future severity-literal drift. See WR-03 in 03-REVIEW.md. |
| `acercontrol/gui_window.py` | 231-254 | Synchronous `subprocess.run` (via run_privileged) on GTK main thread | Warning | Up to 30 s + auth-dialog interaction blocks main loop. Documented as Phase 3 design; address in Phase 4+. See WR-04 in 03-REVIEW.md. |
| `acercontrol/gui_window.py` | 151-156 | Unknown-blocker fallback doesn't clear stale warning banners | Warning | Stale banners can persist if probe drifts to unknown blocker name. See WR-05 in 03-REVIEW.md. |
| `libexec/acercontrol-disable-ppd` | 68-70 | unmask check misses `masked-runtime` state | Warning | Latent (mask path used in Phase 3; unmask path exposed via allowlist). See WR-01. |
| `libexec/acercontrol-disable-ppd` | 57-58, 74-77 | Bare `systemctl` (sibling wrapper hardcodes `/usr/sbin/modprobe`) | Warning | Defensive-coding inconsistency. Currently safe (pkexec default PATH contains /usr/bin) but not a contract. See WR-02. |
| `gui_about.py`, `gui_status_pages.py`, `gui_banner.py` | imports | Unused `Gio` import in 3 modules | Info | Dead import. See IN-01. |
| `pyproject.toml` | 11 | `requires-python = ">=3.11"` but CLAUDE.md says "3.10+" | Info | Doc/metadata drift. See IN-03. |

### Human Verification Required

See `human_verification:` frontmatter section above. 9 items requiring PHN16-72 UAT, GTK4 rendering, polkit dialog rendering, or one-time dev install. **Note: items 2 and 5 are partially blocked by BL-01 — even on real hardware, the Load-module CTA will fail until the wrapper is fixed.**

### Gaps Summary

**One BLOCKER gap:** The `acercontrol-reload-acer-wmi` wrapper's unconditional `modprobe -r acer_wmi` with `check=True` breaks the primary "Load module" CTA on `acer_wmi_not_loaded` StatusPage — the exact path that SC#2 of the phase goal exercises on a freshly-installed PHN16-72 that hasn't loaded the module yet. The artifact exists, is wired, and is invoked correctly by the GUI; the failure is inside the wrapper's logic. This was flagged as BL-01 in code review (03-REVIEW.md) and the fix is straightforward (gate `modprobe -r` on `/sys/module/acer_wmi` existence, or drop `check=True` from the unload call).

Smoke gates (17/17 full + 6/6 phase1 regression + 28/28 phase2 regression) are all green — but they validate argv shape and policy structure, not the runtime behaviour on the unloaded-module path. Treating "smoke green" as proof of SC#2 closure would mask this bug; this verification surfaces it explicitly.

All other must-haves (22/23) are verified by code shape, smoke gates, and structural grep. Eight runtime/visual behaviours are routed to human UAT as designed (single-instance focus, polkit dialog text rendering, banner visual behaviour, idempotency on real systemctl, dismissibility flow, cancel-on-Escape).

---

_Verified: 2026-05-16T23:10:00Z_
_Verifier: Claude (gsd-verifier)_
