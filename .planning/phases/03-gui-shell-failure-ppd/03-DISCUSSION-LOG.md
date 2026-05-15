# Phase 3: GUI Shell + Failure States + PPD Banner — Discussion Log

**Date:** 2026-05-16
**Mode:** default (interactive), `--all` selected by user response
**Outcome:** all 6 gray areas accepted recommended defaults

This file is a human-readable audit trail of the discuss-phase session. Downstream agents read CONTEXT.md, not this file.

---

## Setup

- Phase 3 directory created: `.planning/phases/03-gui-shell-failure-ppd/`
- No prior CONTEXT.md, no plans yet, no SPEC.md
- Prior context loaded: PROJECT.md (incl. 2026-05-15 additions for hardware key + no-prompt setprofile), REQUIREMENTS.md (GUI-01..04, GUI-08), STATE.md, Phase 2 CONTEXT.md, Phase 2 VERIFICATION.md, Phase 2 REVIEW.md
- Prior decisions carried forward: GTK4/Adwaita stack locked, application ID `org.acercontrol.AcerControl`, `manage-service` wrapper allowlist locked to `acer-performance.service`, GUI-08 (no raw kernel values in UI labels)
- Codebase scout: 6 modules under `acercontrol/`, polkit policy + 3 wrappers under `data/` and `libexec/`, no `.planning/codebase/` maps to read

---

## Gray Areas Identified

Six gray areas surfaced. User selected `all`.

| # | Area | Why it mattered |
|---|------|-----------------|
| 1 | PPD disable mechanism | Phase 2's `manage-service` wrapper allowlist is locked to `acer-performance.service` — needs decision on how to grant systemctl mask power-profiles-daemon |
| 2 | `acer_wmi` reload helper | GUI-03 promises one-click "Load module" / "Reload with predator_v4=1" but Phase 2 has no wrapper for modprobe |
| 3 | StatusPage routing strategy | `features.probe()` can return multiple failures; how does the GUI surface them? |
| 4 | PPD banner dismissibility | UX call — can the user X-out the banner, and what brings it back? |
| 5 | App icon timing | Ship now or defer to Phase 8 packaging? |
| 6 | GUI launch path | `[project.scripts]` entry vs `python3 -m acercontrol.gui`? |

---

## Discussion

The orchestrator presented all 6 gray areas with a recommended default + rationale per area, in a single batched turn (consistent with the user's terse-decisive interaction style observed throughout the session).

User reply: **`default`** — accept all 6 recommendations.

### Decision summary

| # | Area | Decision |
|---|------|----------|
| 1 | PPD disable | New dedicated wrapper `acercontrol-disable-ppd` + 4th polkit action `org.acercontrol.disable-ppd` (extend existing `data/org.acercontrol.policy`) |
| 2 | `acer_wmi` reload | New dedicated wrapper `acercontrol-reload-acer-wmi` + 5th polkit action `org.acercontrol.reload-acer-wmi` |
| 3 | StatusPage routing | Severity-ordered hybrid: blockers → full StatusPage, warnings → persistent banner |
| 4 | PPD banner dismissibility | Dismissible-this-session, re-surfaces on cold start AND on Phase 4 revert-on-mismatch event |
| 5 | App icon | Defer to Phase 8 (packaging task — color + symbolic SVGs + cache update) |
| 6 | GUI launch path | Add `acercontrol-gui = "acercontrol.gui:main"` to `pyproject.toml` `[project.scripts]` |

---

## Claude's Discretion Items (recorded but not asked)

- Window default size: 800×600, user-resizable
- About dialog uses `Adw.AboutDialog` (1.5) with a Diagnostics section that's the SOLE place raw kernel values may appear (GUI-08 carve-out)
- StatusPage "Refresh" button re-runs `probe()` (no auth)
- Banner copy verbatim per ROADMAP success criterion 3
- "Learn more" opens an in-app `Adw.Window` with embedded text — no external URL
- GUI files split across `acercontrol/gui.py`, `gui_window.py`, `gui_status_pages.py`, `gui_banner.py`, `gui_about.py` — `verify_no_gtk` exempts these but still gates the bundled CLI
- New wrappers invoke through `acercontrol.privilege.run_privileged()` — no new elevation code
- Polkit policy file is EDITED (append actions), not replaced
- macOS / CI smoke is XML-validity + wrapper-argv-rejection + bundle-still-GTK-free + clean-import-failure-on-no-gi; live GUI testing is PHN16-72 hardware UAT only

---

## Deferred Ideas (preserved for future phases)

- Drop polkit auth entirely on `setprofile` (PROJECT.md, 2026-05-15)
- Hardware Predator key → cycle profiles (PROJECT.md, 2026-05-15)
- Per-user config file for "don't show PPD banner again" — would unlock dismissibility option C
- External docs site for "Learn more" link — no website yet
- Apply WR-03 lesson (Phase 2 review): preserve underlying systemctl exit codes in the new `disable-ppd` wrapper instead of collapsing to `EX_OSERR=71`

---

## Scope Creep Avoided

None raised in this session. The user selected `all` and accepted defaults; no questions strayed into Phase 4 (profile buttons), Phase 5 (sensors), Phase 6 (boot service), Phase 7 (tray), or Phase 8 (packaging).
