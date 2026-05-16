---
phase: 3
slug: gui-shell-failure-ppd
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-16
plan_ref: 03-01-PLAN.md
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 3 ships GUI plumbing fully exercisable only on PHN16-72 + Linux + GTK4. Strategy: cheap CI guards on macOS per task, regression suite per wave, hardware UAT on PHN16-72 at phase gate.

> Source: `03-RESEARCH.md` § Validation Architecture (lines 813–893). Manual UAT items mirror Phase 2's hardware-only pattern.

> **Task IDs:** All task references below resolve to `03-01-PLAN.md` Tasks T1–T6 (single-plan phase; T1=features.py severity patch, T2=smoke_phase3.py scaffold, T3=wrappers+polkit+privilege.py+pyproject.toml, T4=gui_about/gui_status_pages/gui_banner, T5=gui_window/gui, T6=full smoke + regression verification).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Plain Python smoke runner (`tools/smoke_phase3.py`) — extends Phase 1/2 pattern. No pytest dep (preserves project's "no pip-only deps" rule) |
| **Config file** | None (single-file runner) |
| **Quick run command** | `python3 tools/smoke_phase3.py --quick` |
| **Full suite command** | `python3 tools/smoke_phase3.py` |
| **Estimated runtime** | ~2s quick / ~5s full (cross-platform — most assertions don't require GTK4) |
| **Regression** | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py` (must stay green) |

---

## Sampling Rate

- **After every task commit:** `python3 tools/smoke_phase3.py --quick` — XML well-formedness, wrapper argv rejection, ImportError pattern, GUI-08 grep gate, bundler-input GTK-free regression
- **After every plan wave:** `python3 tools/smoke_phase3.py` (full) + Phase 1/2 regression
- **Before `/gsd-verify-work 3`:** full smoke + manual UAT checklist on PHN16-72 (window structure, single-instance, broken-probe StatusPages, PPD banner + button + menu entry, polkit dialog text strings)
- **Max feedback latency:** ~2s for the quick gate; <30s for the full wave gate including regressions

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | Task | Status |
|--------|----------|-----------|-------------------|------|--------|
| GUI-01 | `Adw.Application(application_id="org.acercontrol.AcerControl")`; window has `Adw.ApplicationWindow` + `Adw.ToolbarView` + `Adw.HeaderBar` | unit (Linux only) | `python3 -c "from acercontrol.gui import AcerControlApp; assert AcerControlApp().get_application_id() == 'org.acercontrol.AcerControl'"` (Linux); manual on PHN16-72 for window structure | T5 + T6 | ⬜ pending |
| GUI-02 | Second launch focuses existing window | manual-only | UAT on PHN16-72: launch twice → one window | T5 (code) + manual | ⬜ pending |
| GUI-03 (routing) | `features.probe()` runs first; failed checks route to `Adw.StatusPage` (blocker) or `Adw.Banner` (warning) per CONTEXT decision #3 | unit + manual | unit: `scenario_features_severity_post_patch` in `tools/smoke_phase3.py`; manual on PHN16-72 (rename `/sys/firmware/acpi/platform_profile`, `modprobe -r acer_wmi`, `systemctl unmask power-profiles-daemon`) | T1 + T4 + T5 + T6 | ⬜ pending |
| GUI-04 (banner) | PPD active → persistent `Adw.Banner` with `[Disable PPD]` button + HeaderBar primary-menu "About power-profiles-daemon" entry (Landmine #1 fallback) | unit + manual | unit: grep gate on `gui_banner.py` (no use_markup; plain title); manual on PHN16-72 with PPD running | T3 + T4 + T5 + T6 | ⬜ pending |
| GUI-04 (dismissibility) | HeaderBar primary menu entry "Hide PPD warning this session" wired to `win.hide-ppd-banner` GAction (`hidden-when="action-disabled"` visibility predicate); handler sets `set_revealed(False)` + `_ppd_banner_dismissed = True`; enabled-state flips at 3 sites (creation default-False; `_rebuild_warning_banners`; `_on_banner_revealed_change`); D-04 Option A locked per checker revision 2026-05-16 | grep gate (cross-platform) + manual UAT | `scenario_dismiss_menu_entry_present` in `tools/smoke_phase3.py` (greps `acercontrol/gui_window.py` for `"Hide PPD warning this session"` + `"hide-ppd-banner"` + `hidden-when`); T5 acceptance criteria additionally count `set_enabled(` occurrences ≥ 3 | T2 + T5 + T6 | ⬜ pending |
| GUI-08 (grep gate) | UI never renders raw kernel profile values outside `gui_about.py` (Diagnostics carve-out) | grep gate (cross-platform) | `scenario_gui08_grep_gate` in `tools/smoke_phase3.py` | T2 + T4 + T5 + T6 | ⬜ pending |
| (regression) PRIV-01..05 / CLI-01..07 / CORE-01..06 | Phase 1/2 contracts unchanged | full suite | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py` | T1 + T3 + T6 | ⬜ pending |
| (new wrapper) `acercontrol-disable-ppd` argv rejection | Wrapper rejects `start` / non-PPD service / no argv with EX_USAGE=64 | unit (cross-platform) | 4 invocations × `[[ $? == 64 ]]` (`start ppd.service`, `mask other.service`, no argv, both bad) | T3 + T6 | ⬜ pending |
| (new wrapper) `acercontrol-reload-acer-wmi` argv rejection | Wrapper rejects extra argv with EX_USAGE=64 | unit (cross-platform) | `bash -c './libexec/acercontrol-reload-acer-wmi unexpected; [[ $? == 64 ]]'` | T3 + T6 | ⬜ pending |
| (new wrapper) `acercontrol-disable-ppd` idempotency (Landmine #3) | `mask` twice → exit 0 both times | manual (Linux + root/sudo) | UAT on PHN16-72 | T3 + manual | ⬜ pending |
| (regression) `verify_no_gtk` on bundler input list | Phase 2 bundler input list stays GTK-free | gate | `python3 tools/verify_no_gtk.py acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` | T6 | ⬜ pending |
| (regression) `verify_no_gtk` on bundled output | `dist/acercontrol` stays GTK-free | gate | `python3 tools/bundle_cli.py && python3 tools/verify_no_gtk.py dist/acercontrol` | T6 | ⬜ pending |
| (sanity) `verify_no_gtk` reports `gui*.py` as gtk-tainted | Sanity — proves the gate works | gate (cross-platform) | `python3 tools/verify_no_gtk.py acercontrol/gui.py; [[ $? != 0 ]]` | T2 + T6 | ⬜ pending |
| (Landmine #2) `features.py` severity values match Phase 3 routing | After Phase 1 patch: `acer hwmon` → `blocking`, `coretemp` → `warning`, `acer_wmi blacklist` → `warning` | unit (cross-platform) | `scenario_features_severity_post_patch` in `tools/smoke_phase3.py` | T1 + T6 | ⬜ pending |
| (Landmine #4) `acercontrol-gui` console-script entry registered | After `pip install -e .`, the entry-point exists in `console_scripts` | gate (cross-platform) | `scenario_entry_point_registered` in `tools/smoke_phase3.py` (SKIPs if not installed) | T3 + manual `pip install` | ⬜ pending |
| (Landmine #5) GUI module imports fail cleanly without `gi` | `import acercontrol.gui*` raises `ImportError` or `ValueError`, never another type | gate (macOS + CI) | `scenario_gui_modules_import_cleanly` in `tools/smoke_phase3.py` | T4 + T5 + T6 | ⬜ pending |
| (Landmine #6) bundler input list excludes `gui*.py` | `tools/bundle_cli.py` `BUNDLE_ORDER` does not include any `gui_*` substring | inspection (cross-platform) | `scenario_bundler_input_excludes_gui` in `tools/smoke_phase3.py` | T2 + T6 | ⬜ pending |
| (regression) Polkit policy XML well-formed | After append, 5 `<action>` blocks present, parses clean | gate (cross-platform) | `scenario_policy_xml_well_formed` in `tools/smoke_phase3.py` | T3 + T6 | ⬜ pending |
| (UAT) Polkit dialog text on PPD disable | Dialog reads "Authentication is required to disable power-profiles-daemon" — NOT generic systemctl text | manual (Linux + GUI session) | UAT on PHN16-72 | T3 + manual | ⬜ pending |
| (UAT) Polkit dialog text on module reload | Dialog reads "Authentication is required to reload the acer_wmi kernel module" | manual | UAT on PHN16-72 | T3 + manual | ⬜ pending |
| (UAT) Banner has no Pango link affordance | Landmine #1 fallback applied — banner title is plain text; "About PPD" reachable via HeaderBar primary menu | manual | UAT on PHN16-72 | T4 + T5 + manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky · Updated by execute-phase as tasks complete.*

---

## Wave 0 Requirements

The planner allocates Wave 0 (Tasks T1 + T2) to build the smoke runner and patch features.py BEFORE any GUI files / wrappers / policy edits. Without Wave 0 the per-task feedback loop has no automated guard.

- [ ] **T1**: Severity patch in `acercontrol/features.py` (Landmine #2 / Finding #2 from research) — 3 lines edited. After patch, re-run `python3 tools/smoke_phase1.py` to confirm Phase 1 contracts hold. **Open Question 1 resolved by planner during context gathering: `01-VERIFICATION.md` does NOT assert specific severity literals — no Phase 1 verification update needed.**
- [ ] **T2**: `tools/smoke_phase3.py` — full smoke runner: GUI-01..04, GUI-08, both new wrappers, regression gates, Landmines #2/#4/#5/#6, polkit XML well-formedness. ~220 LOC, single-file pattern matching `tools/smoke_phase2.py`. Supports `--quick` flag. Scaffold ships with scenarios that turn GREEN as later tasks land.

After Wave 0 lands, subsequent waves (T3 wrappers/polkit/privilege/pyproject; T4 gui leaf modules; T5 gui_window/gui entry) create the GUI files and supporting infrastructure. T6 is the verification gate (full smoke + regression).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Single-instance focus | GUI-02 | Requires display + dbus session | Launch `acercontrol-gui` twice on PHN16-72 → only one window appears, second launch focuses the existing window |
| StatusPage routing for each blocker | GUI-03 | Requires intentionally breaking the host: `sudo modprobe -r acer_wmi`; `sudo mv /sys/firmware/acpi/platform_profile /tmp/`; etc. | UAT on PHN16-72 — break each probe in turn, confirm correct StatusPage renders, verify the "Reload module" / "Refresh" buttons work |
| PPD banner end-to-end | GUI-04 | Requires PPD running on PHN16-72 | `sudo systemctl unmask power-profiles-daemon && sudo systemctl start power-profiles-daemon`, launch GUI → banner appears → click "Disable PPD" → polkit dialog text reads "Authentication is required to disable power-profiles-daemon" → enter password → banner disappears (because PPD is now masked) |
| HeaderBar "About PPD" menu entry | GUI-04 (Landmine #1 fallback) | Requires GUI session | Click HeaderBar primary menu → "About power-profiles-daemon" entry → opens explainer dialog (same content option-(a) link would have shown) |
| Dismiss PPD banner via HeaderBar menu | GUI-04 (dismissibility — D-04 Option A) | Requires GUI session + PPD running | `sudo systemctl unmask power-profiles-daemon && sudo systemctl start power-profiles-daemon`, launch GUI → banner visible → open HeaderBar primary menu → entry "Hide PPD warning this session" present → click → banner disappears for the rest of the session AND the menu entry itself disappears (because the GAction flipped to disabled and `hidden-when="action-disabled"` removes it). Close window and relaunch → banner re-appears (in-memory flag, no persistence). With Phase 4 shipped: trigger revert-on-mismatch → banner re-surfaces via `show_ppd_banner(force=True)` AND the menu entry re-appears. |
| Polkit dialog text on module reload | GUI-03 (reload-acer-wmi) | Requires GUI session | UAT on PHN16-72 — trigger the "Reload module" button, dialog reads "Authentication is required to reload the acer_wmi kernel module" |
| `disable-ppd` idempotency (mask-already-masked) | GUI-04 / Landmine #3 | Requires root + actual systemctl | `sudo /usr/libexec/acercontrol/acercontrol-disable-ppd mask power-profiles-daemon.service` → exit 0; run again → exit 0 (silent), no error |
| Cancel-on-Escape during wrapper invocation | PRIV-04 (carry-forward to GUI process) | Requires interactive pkexec dialog | Trigger any GUI button that elevates → press Escape → toast reads "Authentication cancelled." → exit clean, no traceback |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (planner enforced in 03-01-PLAN.md)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (planner enforced — every task has `<verify><automated>…</automated></verify>`)
- [x] Wave 0 covers all MISSING references (smoke runner T2 + features.py patch T1)
- [x] No watch-mode flags
- [x] Feedback latency < ~2s on `--quick`, <30s on full + regression
- [x] `nyquist_compliant: true` set in frontmatter (planner set after PLAN.md generation aligned Per-Task Verification Map)

**Approval:** APPROVED — Per-Task Verification Map populated against 03-01-PLAN.md Tasks T1-T6 by planner during context gathering (2026-05-16); revised 2026-05-16 to add the GUI-04 (dismissibility) row + matching manual UAT row after checker blocker D-04 Option A lock. `wave_0_complete: false` flips to `true` after execute-phase completes Tasks T1+T2.
