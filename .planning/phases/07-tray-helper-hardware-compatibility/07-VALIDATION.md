# Phase 7 Validation: Tray Helper + Hardware Compatibility

**Phase:** 07 — Tray Helper + Hardware Compatibility  
**Validated:** 2026-05-23  
**Scope:** Plan quality and executable verification strategy

## Requirement Coverage Matrix

| Requirement | Phase 7 Validation Target | Planned Plan | Coverage |
|-------------|---------------------------|--------------|----------|
| TRAY-01 | Separate `acercontrol-tray` helper process uses GTK3 + Ayatana, displays current profile, and runs long-lived. | 07-02 | COVERED |
| TRAY-02 | Tray helper detects `org.kde.StatusNotifierWatcher`; exits 0 when absent; About diagnostics mention tray status. | 07-01 | COVERED |
| TRAY-03 | Tray menu has five quick-switch profile items and `Show AcerControl`. | 07-02 | COVERED |
| TRAY-04 | Tray packages are packaging `Recommends`, not hard `Depends`. | 07-03 | COVERED AS CONTRACT; Phase 8 will satisfy once `debian/control` exists. |
| HW-01 | PHN16-72 full happy-path UAT remains required and documented. | 07-03 | COVERED |
| HW-02 | Partial-compatible hardware behavior is fixture-gated and UAT-documented. | 07-03 | COVERED |

## Automated Gates

Run after Phase 7 execution:

```bash
python3 -m py_compile tools/smoke_phase7.py acercontrol/tray_status.py acercontrol/tray.py acercontrol/gui_about.py
python3 tools/smoke_phase7.py --quick
python3 tools/smoke_phase7.py
python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py && python3 tools/smoke_phase7.py
```

Expected source/static checks:

- Tray helper is the only source using GTK3/Ayatana.
- Main GTK4 GUI never imports tray helper code.
- Tray helper uses wrapper-only profile writes.
- StatusNotifierWatcher detection is present and non-fatal.
- CLI bundler remains GTK-free.
- Partial sensor/profile fixtures pass.
- Packaging Recommends handoff is enforced when `debian/control` exists.

## Manual UAT Gates

Run on Ubuntu 24.04 / PHN16-72:

1. Install tray dependencies:

   ```bash
   sudo apt install gir1.2-ayatanaappindicator3-0.1 gnome-shell-extension-appindicator
   ```

2. With AppIndicator extension enabled:
   - Run `acercontrol-tray`.
   - Confirm tray icon/menu appears.
   - Confirm menu shows `eco`, `quiet`, `balanced`, `performance`, `turbo`, `Show AcerControl`, and `Quit`.
   - Switch each profile from tray; `acercontrol get` returns the requested user-facing name.
   - Select `Show AcerControl`; existing GUI focuses or launches.

3. With AppIndicator extension disabled or unavailable:
   - Run `acercontrol-tray`.
   - It exits 0 within 5 seconds.
   - No traceback appears.
   - About diagnostics mention tray unavailability.

4. Hardware compatibility:
   - PHN16-72 full happy path: profile buttons, live sensors, boot persistence, suspend/resume, and tray quick-switch.
   - Compatible partial sensor hardware or fixture-equivalent: missing fan/temp values render placeholders, unsupported profiles are insensitive, no traceback.

## Plan Checker Result

**VERIFICATION PASSED**

Reasoning:

- Phase 7 has a concrete three-plan decomposition with explicit dependencies.
- Every TRAY/HW requirement has a planned artifact and verification method.
- The risky GTK3/GTK4 boundary is handled with a separate process and source gates.
- TRAY-04's packaging dependency is acknowledged as a Phase 8 implementation handoff while still protected by a Phase 7 contract gate.
