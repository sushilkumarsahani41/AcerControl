---
phase: 3
slug: gui-shell-failure-ppd
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-16
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase 3 ships GUI plumbing fully exercisable only on PHN16-72 + Linux + GTK4. Strategy: cheap CI guards on macOS per task, regression suite per wave, hardware UAT on PHN16-72 at phase gate.

> Source: `03-RESEARCH.md` § Validation Architecture (lines 813–893). Manual UAT items mirror Phase 2's hardware-only pattern.

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

> Wave / Task IDs are placeholders pending the planner's PLAN.md output. The planner MUST replace these with the canonical IDs and add this map verbatim into PLAN.md frontmatter once generated.

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| GUI-01 | `Adw.Application(application_id="org.acercontrol.AcerControl")`; window has `Adw.ApplicationWindow` + `Adw.ToolbarView` + `Adw.HeaderBar` | unit (Linux only) | `python3 -c "from acercontrol.gui import AcerControlApp; assert AcerControlApp().get_application_id() == 'org.acercontrol.AcerControl'"` (Linux); manual on PHN16-72 for window structure | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| GUI-02 | Second launch focuses existing window | manual-only | UAT on PHN16-72: launch twice → one window | ❌ — UAT checklist | ⬜ pending |
| GUI-03 (routing) | `features.probe()` runs first; failed checks route to `Adw.StatusPage` (blocker) or `Adw.Banner` (warning) per CONTEXT decision #3 | unit + manual | unit: severity-routing test with mocked `FeatureReport`; manual: rename `/sys/firmware/acpi/platform_profile`, `modprobe -r acer_wmi`, `systemctl unmask power-profiles-daemon` to artificially fail each probe | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| GUI-04 (banner) | PPD active → persistent `Adw.Banner` with `[Disable PPD]` button + HeaderBar primary-menu "About power-profiles-daemon" entry (Landmine #1 fallback) | unit + manual | unit: assert `gui_banner.build_ppd_banner` returns `Adw.Banner` with `button-label == "Disable PPD"`; manual on PHN16-72 with PPD running | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| GUI-08 (grep gate) | UI never renders raw kernel profile values outside `gui_about.py` (Diagnostics carve-out) | grep gate (cross-platform) | `! grep -nE '"(low-power\|balanced-performance\|performance)"' acercontrol/gui.py acercontrol/gui_window.py acercontrol/gui_status_pages.py acercontrol/gui_banner.py` | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (regression) PRIV-01..05 / CLI-01..07 / CORE-01..06 | Phase 1/2 contracts unchanged | full suite | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py` | ✅ exists | ⬜ pending |
| (new wrapper) `acercontrol-disable-ppd` argv rejection | Wrapper rejects `start` / non-PPD service / no argv with EX_USAGE=64 | unit (cross-platform) | 4 invocations × `[[ $? == 64 ]]` (`start ppd.service`, `mask other.service`, no argv, both bad) | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (new wrapper) `acercontrol-reload-acer-wmi` argv rejection | Wrapper rejects extra argv with EX_USAGE=64 | unit (cross-platform) | `bash -c './libexec/acercontrol-reload-acer-wmi unexpected; [[ $? == 64 ]]'` | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (new wrapper) `acercontrol-disable-ppd` idempotency (Landmine #3) | `mask` twice → exit 0 both times | manual (Linux + root/sudo) | UAT on PHN16-72 | ❌ — UAT checklist | ⬜ pending |
| (regression) `verify_no_gtk` on bundler input list | Phase 2 bundler input list stays GTK-free | gate | `python3 tools/verify_no_gtk.py acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` | ✅ exists | ⬜ pending |
| (regression) `verify_no_gtk` on bundled output | `dist/acercontrol` stays GTK-free | gate | `python3 tools/bundle_cli.py && python3 tools/verify_no_gtk.py dist/acercontrol` | ✅ exists | ⬜ pending |
| (sanity) `verify_no_gtk` reports `gui*.py` as gtk-tainted | Sanity — proves the gate works | gate (cross-platform) | `python3 tools/verify_no_gtk.py acercontrol/gui.py; [[ $? != 0 ]]` | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (Landmine #2) `features.py` severity values match Phase 3 routing | After Phase 1 patch: `acer hwmon` → `blocking`, `coretemp` → `warning`, `acer_wmi blacklist` → `warning` | unit (cross-platform) | `python3 -c "from acercontrol.features import probe; ..."` (asserts on synthesized check map) | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (Landmine #4) `acercontrol-gui` console-script entry registered | After `pip install -e .`, the entry-point exists in `console_scripts` | gate (cross-platform) | `python3 -c "import importlib.metadata as m; eps = {ep.name for ep in m.entry_points(group='console_scripts')}; assert 'acercontrol-gui' in eps"` | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (Landmine #5) GUI module imports fail cleanly without `gi` | `import acercontrol.gui*` raises `ImportError` or `ValueError`, never another type | gate (macOS + CI) | See Landmine #5 sketch in 03-RESEARCH.md | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (Landmine #6) bundler input list excludes `gui*.py` | `tools/bundle_cli.py` `BUNDLE_ORDER` does not include any `gui_*` substring | inspection (cross-platform) | grep on `tools/bundle_cli.py` BUNDLE_ORDER section | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (regression) Polkit policy XML well-formed | After append, 5 `<action>` blocks present, parses clean | gate (cross-platform) | `python3 -c "import xml.etree.ElementTree as ET; t = ET.parse('data/org.acercontrol.policy'); assert len(t.getroot().findall('action')) == 5"` | ❌ W0 — `tools/smoke_phase3.py` | ⬜ pending |
| (UAT) Polkit dialog text on PPD disable | Dialog reads "Authentication is required to disable power-profiles-daemon" — NOT generic systemctl text | manual (Linux + GUI session) | UAT on PHN16-72 | ❌ — UAT checklist | ⬜ pending |
| (UAT) Polkit dialog text on module reload | Dialog reads "Authentication is required to reload the acer_wmi kernel module" | manual | UAT on PHN16-72 | ❌ — UAT checklist | ⬜ pending |
| (UAT) Banner has no Pango link affordance | Landmine #1 fallback applied — banner title is plain text; "About PPD" reachable via HeaderBar primary menu | manual | UAT on PHN16-72 | ❌ — UAT checklist | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

The planner MUST allocate Wave 0 to build the smoke runner before any GUI files. Without Wave 0 the per-task feedback loop has no automated guard.

- [ ] `tools/smoke_phase3.py` — full smoke runner: GUI-01..04, GUI-08, both new wrappers, regression gates, Landmines #2/#4/#5/#6, polkit XML well-formedness. ~250 LOC, single-file pattern matching `tools/smoke_phase2.py`. Supports `--quick` flag.
- [ ] Severity patch in `acercontrol/features.py` (Landmine #2 / Finding #2 from research) — 3 lines edited. After patch, re-run `python3 tools/smoke_phase1.py` to confirm Phase 1 contracts hold (Open Question 1 — 01-VERIFICATION.md may assert specific severity literals; if so, that file gets a single-line update too).

After Wave 0 lands, subsequent waves create the GUI files / wrappers / polkit policy edit / pyproject.toml line.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Single-instance focus | GUI-02 | Requires display + dbus session | Launch `acercontrol-gui` twice on PHN16-72 → only one window appears, second launch focuses the existing window |
| StatusPage routing for each blocker | GUI-03 | Requires intentionally breaking the host: `sudo modprobe -r acer_wmi`; `sudo mv /sys/firmware/acpi/platform_profile /tmp/`; etc. | UAT on PHN16-72 — break each probe in turn, confirm correct StatusPage renders, verify the "Reload module" / "Refresh" buttons work |
| PPD banner end-to-end | GUI-04 | Requires PPD running on PHN16-72 | `sudo systemctl unmask power-profiles-daemon && sudo systemctl start power-profiles-daemon`, launch GUI → banner appears → click "Disable PPD" → polkit dialog text reads "Authentication is required to disable power-profiles-daemon" → enter password → banner disappears (because PPD is now masked) |
| HeaderBar "About PPD" menu entry | GUI-04 (Landmine #1 fallback) | Requires GUI session | Click HeaderBar primary menu → "About power-profiles-daemon" entry → opens explainer dialog (same content option-(a) link would have shown) |
| Polkit dialog text on module reload | GUI-03 (reload-acer-wmi) | Requires GUI session | UAT on PHN16-72 — trigger the "Reload module" button, dialog reads "Authentication is required to reload the acer_wmi kernel module" |
| `disable-ppd` idempotency (mask-already-masked) | GUI-04 / Landmine #3 | Requires root + actual systemctl | `sudo /usr/libexec/acercontrol/acercontrol-disable-ppd mask power-profiles-daemon.service` → exit 0; run again → exit 0 (silent), no error |
| Cancel-on-Escape during wrapper invocation | PRIV-04 (carry-forward to GUI process) | Requires interactive pkexec dialog | Trigger any GUI button that elevates → press Escape → toast reads "Authentication cancelled." → exit clean, no traceback |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (planner enforces in PLAN.md)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (planner enforces)
- [ ] Wave 0 covers all MISSING references (smoke runner + features.py patch)
- [ ] No watch-mode flags
- [ ] Feedback latency < ~2s on `--quick`, <30s on full + regression
- [ ] `nyquist_compliant: true` set in frontmatter (planner sets after PLAN.md generation aligns Per-Task Verification Map)

**Approval:** pending — awaiting planner-generated PLAN.md to populate task IDs and confirm wave assignment
