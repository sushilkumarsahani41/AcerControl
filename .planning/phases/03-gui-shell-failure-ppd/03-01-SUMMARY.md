---
phase: 03-gui-shell-failure-ppd
plan: 01
subsystem: gui-shell
tags: [python, gtk4, libadwaita, polkit, pkexec, statuspage, banner, ppd, modprobe, stdlib-only, smoke-runner]
requires:
  - 02-privilege-boundary-cli (privilege.run_privileged, libexec analog patterns)
  - 01-foundation (acercontrol.features.probe, FeatureReport contract)
provides:
  - acercontrol.gui:AcerControlApp (single-instance Adw.Application)
  - acercontrol.gui_window:MainWindow (probe-first routing + signal handlers)
  - acercontrol.gui_window:MainWindow.show_ppd_banner(force) — Phase 4 contract
  - libexec/acercontrol-disable-ppd (pkexec mask/unmask power-profiles-daemon)
  - libexec/acercontrol-reload-acer-wmi (pkexec modprobe -r/reload acer_wmi)
  - polkit actions org.acercontrol.disable-ppd, org.acercontrol.reload-acer-wmi
  - acercontrol-gui console_scripts entry-point
affects:
  - tools/smoke_phase2.py (relaxed _three_actions_check_src equality → subset)
  - acercontrol/features.py (severity literals patched per Phase 3 routing)
tech-stack:
  added:
    - GTK4 (gi.require_version("Gtk", "4.0"))
    - libadwaita 1.x (gi.require_version("Adw", "1"))
    - GLib/Gio (Gio.SimpleAction, Gio.Menu, Gio.MenuItem, GLib.Variant)
  patterns:
    - Bare `import gi` at module top (Landmine #5 — no try/except wrapping)
    - Adw.ToolbarView.add_top_bar(Adw.HeaderBar) + set_content(Adw.ToastOverlay(Gtk.Stack))
    - HeaderBar primary menu via Gtk.MenuButton(icon_name="open-menu-symbolic", primary=True)
    - GAction visibility predicate via Gio.MenuItem.set_attribute_value("hidden-when", "action-disabled")
    - Synchronous run_privileged() in GTK signal handler (sub-50ms wrapper rc)
    - Adw.Toast for transient user feedback in place of print()
key-files:
  created:
    - acercontrol/gui.py (49 LOC) — Adw.Application entry-point
    - acercontrol/gui_window.py (254 LOC) — MainWindow + routing
    - acercontrol/gui_about.py (75 LOC) — About + Diagnostics carve-out
    - acercontrol/gui_status_pages.py (110 LOC) — 4 blocker factories + dispatch table
    - acercontrol/gui_banner.py (102 LOC) — PPD/blacklist/coretemp banners + explainer
    - libexec/acercontrol-disable-ppd (92 LOC) — PPD mask/unmask wrapper
    - libexec/acercontrol-reload-acer-wmi (66 LOC) — acer_wmi reload wrapper
    - tools/smoke_phase3.py (370 LOC) — full smoke runner
  modified:
    - acercontrol/features.py — 3 severity literals patched (Landmine #2)
    - acercontrol/privilege.py — WRAPPER_NAMES extended 3 → 5
    - data/org.acercontrol.policy — 3 → 5 polkit actions
    - pyproject.toml — [project.scripts] uncommented acercontrol-gui
    - tools/smoke_phase2.py — Rule 1 fix: relaxed equality on action-count check
    - .planning/phases/03-gui-shell-failure-ppd/03-VALIDATION.md — wave_0_complete + per-row status
decisions:
  - D-04 Option A (HeaderBar primary menu dismiss entry with hidden-when visibility predicate) locked
  - WR-03 DELTA: acercontrol-disable-ppd preserves systemctl returncode (does NOT collapse non-zero to EX_OSERR — fix-forward delta from manage-service)
  - Landmine #1 fallback LOCKED: banner title plain text; "About PPD" lives in HeaderBar primary menu (Adw.Banner activate-link disconfirmed)
  - Severity routing in features.py is the single source of truth (no GUI-side SEVERITY_OVERRIDES)
metrics:
  duration_minutes: 14
  completed_date: 2026-05-16
  total_files_changed: 13
  total_files_created: 8
  total_files_modified: 5
  total_loc_added: ~1118
  smoke_runner_lines: 370
---

# Phase 3 Plan 01: GTK4 + libadwaita GUI Shell Summary

GTK4 + libadwaita GUI shell stood up: single-instance Adw.Application (org.acercontrol.AcerControl) with probe-first lifecycle on do_activate, severity-routed failure surfacing (Adw.StatusPage for blockers; Adw.Banner for warnings), persistent PPD warning banner whose [Disable PPD] button invokes a dedicated pkexec wrapper, plus a dedicated acer_wmi reload wrapper for the "Load module" / "Reload with predator_v4=1" StatusPage CTAs.

## What Shipped

### New files (8)

| Path | LOC | Purpose |
|------|-----|---------|
| `acercontrol/gui.py` | 49 | AcerControlApp(Adw.Application) — application_id="org.acercontrol.AcerControl"; do_activate focuses existing window via self.props.active_window.present() (GUI-02). main() entry-point for pyproject.toml [project.scripts]. |
| `acercontrol/gui_window.py` | 254 | MainWindow(Adw.ApplicationWindow) — Adw.ToolbarView(HeaderBar + ToastOverlay(Stack)); probe-first routing in __init__; _route dispatches BLOCKER_FACTORIES or _rebuild_warning_banners; HeaderBar primary menu hosts "About PPD" + "About AcerControl" + "Hide PPD warning this session" (D-04 Option A); signal handlers mirror cli.py:233-256 with Adw.Toast in place of print(); show_ppd_banner(force=False) Phase 4 API. |
| `acercontrol/gui_about.py` | 75 | build_about_dialog() returns Adw.AboutDialog; Adw.AboutDialog.set_debug_info(json.dumps(_report_to_dict(probe()))) is the GUI-08 exempt zone for raw kernel values. show_about(parent) calls dialog.present(parent) per Landmine #7. |
| `acercontrol/gui_status_pages.py` | 110 | 4 factories (verbatim UI-SPEC copy): acer_wmi_not_loaded, predator_v4_disabled, platform_profile_missing, no_acer_hwmon. Each returns Adw.StatusPage with optional .suggested-action .pill primary button + always-present .flat Refresh button. BLOCKER_FACTORIES dispatch table. placeholder_ok() empty-state. |
| `acercontrol/gui_banner.py` | 102 | build_ppd_banner (plain title — Landmine #1 fallback; single "Disable PPD" button); build_blacklist_banner + build_coretemp_banner (read-only); show_ppd_explainer modal Adw.Window (480×360) with embedded copy (no external URL). |
| `libexec/acercontrol-disable-ppd` | 92 | Hardcoded allowlist (mask|unmask × power-profiles-daemon.service); pre-probes systemctl is-enabled for idempotency (Landmine #3); preserves underlying systemctl rc (WR-03 DELTA); mask invocation uses --now; stdlib-only. |
| `libexec/acercontrol-reload-acer-wmi` | 66 | Argv-less wrapper (`len(argv) != 1` → EX_USAGE); runs absolute /usr/sbin/modprobe -r acer_wmi then /usr/sbin/modprobe acer_wmi predator_v4=1; stdlib-only. |
| `tools/smoke_phase3.py` | 370 | Full smoke runner — XML well-formedness, 5-action assertion + exec.path annotation, wrapper argv rejection (6 scenarios), GUI module ImportError/ValueError gate, GUI-08 grep gate, D-04 menu entry grep gate, bundler GTK-free + sanity scenarios, features.py severity gate, console_scripts entry-point gate. Supports --quick mode. |

### Modified files (5)

| Path | Change |
|------|--------|
| `acercontrol/features.py` | 3-line severity patch (Landmine #2): acer hwmon warning→blocking, coretemp info→warning, blacklist-detected blocking→warning. Phase 1 smoke unchanged. |
| `acercontrol/privilege.py` | WRAPPER_NAMES extended from 3 → 5 entries (`acercontrol-disable-ppd`, `acercontrol-reload-acer-wmi`). resolve_wrapper / pick_elevation / run_privileged unchanged. |
| `data/org.acercontrol.policy` | Two new `<action>` blocks appended before `</policyconfig>`: org.acercontrol.disable-ppd + org.acercontrol.reload-acer-wmi. Each pins org.freedesktop.policykit.exec.path to its wrapper at /usr/libexec/acercontrol/. Defaults: auth_admin / auth_admin / auth_admin_keep. Literal `<message>` strings for spoof-resistant polkit dialog text. Total: 5 actions. |
| `pyproject.toml` | `[project.scripts]` line uncommented: `acercontrol-gui = "acercontrol.gui:main"`. After `pip install -e . --force-reinstall`, the entry appears in `importlib.metadata.entry_points(group='console_scripts')`. |
| `tools/smoke_phase2.py` | [Rule 1 - Bug] `_three_actions_check_src` had hardcoded equality check on the original 3 action IDs; relaxed to `set(expected).issubset(set(ids))` so Phase 3+ extensions (5 actions now) don't break Phase 2 regression. Per-action defaults + exec.path validation in for-loop body unchanged and now correctly validates all 5 actions. |

## Commits (7)

| Hash | Type | Message |
|------|------|---------|
| `387bb10` | fix | align features.py severity values with Phase 3 routing table |
| `6961abb` | chore | scaffold tools/smoke_phase3.py — GUI/wrapper/policy smoke runner |
| `21028bc` | feat | add disable-ppd + reload-acer-wmi wrappers, polkit actions, GUI entry-point |
| `016cf96` | feat | add GUI leaf modules — gui_about/gui_status_pages/gui_banner |
| `11a43be` | feat | add Adw.Application shell + MainWindow with probe-first routing |
| `0e435a4` | docs | flip wave_0_complete + mark automated rows green in 03-VALIDATION.md |
| (pending) | docs | (this SUMMARY.md commit) |

## Smoke Runner Scenarios

### Quick mode (`python3 tools/smoke_phase3.py --quick`) — 13 scenarios, ~1.5s

| Scenario | Coverage |
|----------|----------|
| scenario_policy_xml_well_formed | Polkit policy parses, exactly 5 `<action>` blocks, both new actions' exec.path annotations match expected wrapper paths |
| disable-ppd: bad action (start) | EX_USAGE=64 |
| disable-ppd: bad service (other.service) | EX_USAGE=64 |
| disable-ppd: no argv | EX_USAGE=64 |
| disable-ppd: both bad | EX_USAGE=64 |
| reload-acer-wmi: unexpected argv | EX_USAGE=64 |
| reload-acer-wmi: two extra args | EX_USAGE=64 |
| scenario_gui_modules_import_cleanly | Landmine #5 — all 5 gui*.py modules raise ImportError/ValueError on macOS (no other exception type) |
| scenario_gui08_grep_gate | Raw kernel literals ("low-power", "balanced-performance", "performance") absent from gui/gui_window/gui_status_pages/gui_banner (gui_about.py exempt) |
| scenario_bundler_input_excludes_gui | Landmine #6 — tools/bundle_cli.py BUNDLE_ORDER contains no gui_* substring |
| scenario_dismiss_menu_entry_present | D-04 — gui_window.py contains "Hide PPD warning this session" + "hide-ppd-banner" + hidden-when |
| verify_no_gtk on bundler input list | Phase 2 bundle inputs stay GTK-free |
| verify_no_gtk SANITY on gui.py | Gate works on tainted GUI files (rc != 0) |

### Full mode (`python3 tools/smoke_phase3.py`) — 17 scenarios, ~2.5s

Adds (post-Task 1):
| Scenario | Coverage |
|----------|----------|
| scenario_features_severity_post_patch | Landmine #2 / T1 — runtime probe() returns expected severity for acer hwmon / coretemp / blacklist |
| scenario_entry_point_registered | Landmine #4 — acercontrol-gui in console_scripts (SKIPs if no `pip install -e .` done yet) |
| bundler produces GTK-free dist/acercontrol | Bundler runs cleanly with all GUI files in tree |
| verify_no_gtk on dist/acercontrol | dist/acercontrol stays GTK-free post-build |

## Landmines Surfaced + Mitigated

| # | Landmine | Mitigation |
|---|----------|------------|
| #1 | Adw.Banner does not propagate Pango `<a href>` link activation (research disconfirmed activate-link signal) | LOCKED fallback: banner title is plain text (no `set_use_markup(True)`); "About power-profiles-daemon" affordance lives in HeaderBar primary menu wired to `win.about-ppd` GAction. Grep gate ensures no `set_use_markup` / `<a href` in gui_banner.py. |
| #2 | features.py severities pre-Phase-3 misrouted 3/7 probe outcomes (acer hwmon warning where blocker expected; coretemp info where warning expected; blacklist blocking where warning expected) | T1 surgical 3-line patch. Phase 1 smoke unchanged. features.py remains canonical source of truth (no GUI-side override table). |
| #3 | `systemctl mask` errors when unit is already masked, surfacing spurious "Operation failed" toast | acercontrol-disable-ppd pre-probes with `systemctl is-enabled`; returns EX_OK=0 if state already matches intent (mask|unmask). Manual UAT on PHN16-72 will confirm "mask twice → 0 twice". |
| #4 | pyproject.toml [project.scripts] additions don't register in `console_scripts` entry-points until `pip install -e . --force-reinstall` | smoke runner's scenario_entry_point_registered SKIPs (not FAILs) if entry missing — keeps gate green on macOS / pre-dev-install. README/UAT notes the `pip install -e . --force-reinstall` step. |
| #5 | Wrapping `import gi` in try/except hides real ImportError/ValueError on Linux without typelibs (silent macOS-stub fallback) | All 5 gui*.py modules have BARE `import gi; gi.require_version(...)` at module top. AST gate + smoke scenario_gui_modules_import_cleanly assert no other exception class is raised. |
| #6 | tools/bundle_cli.py BUNDLE_ORDER must NEVER include gui_* — would taint the stdlib-only CLI bundle | scenario_bundler_input_excludes_gui inspects bundler source for `gui_*` substring outside comments; plus regression `verify_no_gtk` on bundler input list and on dist/acercontrol. |
| #7 | Adw.AboutDialog.present() (no parent) breaks on libadwaita 1.5+ (Adw.Dialog requires parent) | gui_about.show_about(parent_window) calls dialog.present(parent_window) — never dialog.present(). |

## WR-03 Carry-Forward Delta from Phase 2

The Phase 2 `acercontrol-manage-service` wrapper collapses any non-zero systemctl return code to EX_OSERR=71 (see line 62: `return result.returncode if result.returncode == 0 else EX_OSERR`). The new Phase 3 `acercontrol-disable-ppd` wrapper deliberately does NOT do this — it returns `result.returncode` directly so the GUI can distinguish "unit not found" (rc=4) from "operation failed" (rc=1) in future phases. The manage-service collapse is a known-bug-to-fix in a future phase (deferred per Phase 3 CONTEXT scope; out of this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Phase 2 smoke had hardcoded equality on action count**
- **Found during:** T3 verification (Phase 2 regression check)
- **Issue:** `tools/smoke_phase2.py:_three_actions_check_src` asserted `ids == expected` where `expected` listed exactly the original 3 action IDs. T3's polkit policy extension to 5 actions broke this equality check.
- **Fix:** Changed to `set(expected).issubset(set(ids))` — preserves Phase 2's intent ("the 3 actions Phase 2 ships are correctly configured") while allowing later phases to extend. The for-loop body that validates each action's defaults + exec.path is unchanged and now correctly checks all 5 actions because they share the same defaults block and `org.acercontrol.X` → `acercontrol-X` naming convention.
- **Files modified:** `tools/smoke_phase2.py` (1-line change at line 84)
- **Commit:** `21028bc` (rolled into T3 commit)
- **Why Rule 1, not Rule 4:** Phase 2's test had an implicit assumption (exactly 3 actions forever) that T3's plan-authorized policy extension directly contradicted. No architectural decision — just a stale assertion.

### Auth gates encountered

None. All Phase 3 work is source-level and cross-platform; no privileged operations were invoked during execution.

## Phase 4 Carry-Forward

`MainWindow.show_ppd_banner(force: bool = False)` is the API Phase 4's revert-on-mismatch handler will call. When `force=True`:
1. `_ppd_banner_dismissed` is reset to False
2. `_route(probe())` re-runs and re-renders banners via `_rebuild_warning_banners`
3. The `win.hide-ppd-banner` GAction is re-enabled (Site #2 of the 3-site enabled-state flip), so the HeaderBar menu entry re-appears
4. If the banner widget was already present (e.g. user dismissed via close button), `set_revealed(True)` is called explicitly

Phase 4 should call `show_ppd_banner(force=True)` whenever it detects a profile write was reverted by PPD between request and read-back.

## Phase 5 Carry-Forward

`application_id="org.acercontrol.AcerControl"` is the literal that Phase 8's `.desktop` file MUST match (basename: `org.acercontrol.AcerControl.desktop` at `/usr/share/applications/`). Phase 5's Gio.Notification calls will silently fail if the .desktop file is missing or the basename doesn't match. The application_id is therefore frozen as of this plan.

## Phase 6 Carry-Forward

When Phase 6 ships `acer-performance.service` with `Conflicts=power-profiles-daemon.service`, the PPD banner's `[Disable PPD]` button becomes a one-shot fix-it that returns rc=0 idempotently (because PPD will already be masked once the boot service is enabled). No code change needed in gui_window.py or gui_banner.py — the existing idempotency in `acercontrol-disable-ppd` handles the already-masked case cleanly.

## Phase 8 Carry-Forward

The .deb (Phase 8) must install:
- `data/org.acercontrol.policy` → `/usr/share/polkit-1/actions/org.acercontrol.policy` (mode 0644 root:root)
- `libexec/acercontrol-disable-ppd` → `/usr/libexec/acercontrol/acercontrol-disable-ppd` (mode 0755 root:root)
- `libexec/acercontrol-reload-acer-wmi` → `/usr/libexec/acercontrol/acercontrol-reload-acer-wmi` (mode 0755 root:root)
- `org.acercontrol.AcerControl.desktop` (Phase 8 ships this; basename must match application_id from gui.py)
- App icon (color SVG + symbolic SVG) at hicolor paths — DEFERRED per CONTEXT D-05

The polkit `exec.path` annotations are LITERAL strings in the policy file pointing at `/usr/libexec/acercontrol/...` — if Phase 8 installs to a different location, the polkit action will fail to match the wrapper and pkexec will reject the invocation.

## Hardware UAT Checklist (PHN16-72)

Pending PHN16-72 hardware access. These items remain ⬜ pending in 03-VALIDATION.md:

1. **GUI-02 single-instance focus**: Launch `acercontrol-gui` twice → only one window appears, second launch focuses the existing window.
2. **GUI-03 + Landmine #3 module-reload + idempotency**: `sudo modprobe -r acer_wmi`, launch GUI → "acer_wmi module not loaded" StatusPage with "Load module" button → click → polkit dialog reads "Authentication is required to reload the acer_wmi kernel module" → enter password → module reloads → StatusPage replaced by main view. Then: `sudo /usr/libexec/acercontrol/acercontrol-disable-ppd mask power-profiles-daemon.service` → exit 0; run again → exit 0 (silent).
3. **GUI-04 PPD banner end-to-end + polkit dialog text**: `sudo systemctl unmask power-profiles-daemon && sudo systemctl start power-profiles-daemon`, relaunch GUI → PPD banner appears → click "Disable PPD" → polkit dialog reads "Authentication is required to disable power-profiles-daemon" → banner disappears after PPD masked.
4. **Landmine #1 fallback**: HeaderBar primary menu → "About power-profiles-daemon" → explainer dialog opens with the verbatim copy from UI-SPEC Learn-more Dialog.
5. **GUI-08 carve-out + Landmine #7**: HeaderBar primary menu → "About AcerControl" → About dialog opens; expand Diagnostics → raw `features.probe()` JSON visible.
6. **D-04 dismissibility**: With PPD active and banner visible, open HeaderBar primary menu → "Hide PPD warning this session" entry present → click → banner disappears, menu entry itself disappears. Close window and relaunch → banner re-appears (in-memory flag, no persistence).
7. **PRIV-04 cancel-on-Escape**: Trigger any GUI button that elevates → press Escape on polkit dialog → toast reads "Authentication cancelled." → no traceback, no re-probe.

After hardware UAT, run `/gsd-verify-work 3` to advance phase status.

## Self-Check: PASSED

All claimed artifacts exist:

- `[x]` acercontrol/features.py (modified, T1 commit `387bb10`)
- `[x]` acercontrol/privilege.py (modified, T3 commit `21028bc`)
- `[x]` acercontrol/gui.py (created, T5 commit `11a43be`)
- `[x]` acercontrol/gui_window.py (created, T5 commit `11a43be`)
- `[x]` acercontrol/gui_status_pages.py (created, T4 commit `016cf96`)
- `[x]` acercontrol/gui_banner.py (created, T4 commit `016cf96`)
- `[x]` acercontrol/gui_about.py (created, T4 commit `016cf96`)
- `[x]` libexec/acercontrol-disable-ppd (created, mode 0755, T3 commit `21028bc`)
- `[x]` libexec/acercontrol-reload-acer-wmi (created, mode 0755, T3 commit `21028bc`)
- `[x]` data/org.acercontrol.policy (extended, T3 commit `21028bc`)
- `[x]` pyproject.toml (modified, T3 commit `21028bc`)
- `[x]` tools/smoke_phase3.py (created, mode 0755, T2 commit `6961abb`)
- `[x]` tools/smoke_phase2.py (modified — Rule 1 fix, T3 commit `21028bc`)
- `[x]` .planning/phases/03-gui-shell-failure-ppd/03-VALIDATION.md (frontmatter flip + row status updates, T6 commit `0e435a4`)

All 7 plan commits present in `git log --oneline` (plus this SUMMARY commit appended below).

Smoke gates green at completion: smoke_phase3.py (full) 17/17 · smoke_phase1.py 6/6 · smoke_phase2.py 28/28 · bundler builds GTK-free dist/acercontrol · verify_no_gtk SANITY on gui.py reports tainted (rc != 0).
