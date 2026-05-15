# Phase 3: GUI Shell + Failure States + PPD Banner — Research

**Researched:** 2026-05-16
**Domain:** GTK4 + libadwaita 1.5 application shell — `Adw.Application` lifecycle, failure-mode `Adw.StatusPage` routing, persistent `Adw.Banner` for PPD detection, two new `pkexec` wrappers
**Confidence:** HIGH (every load-bearing API call verified against `gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest` or upstream source on `gitlab.gnome.org/GNOME/libadwaita`; the upstream stack and Phase 2 wrapper conventions are pre-locked)

## Summary

Phase 3 stands up the `Adw.Application` shell, registers `org.acercontrol.AcerControl`, runs `features.probe()` first thing on `do_activate`, and routes failed checks to either a full-window `Adw.StatusPage` (blockers) or a persistent `Adw.Banner` above main content (warnings). Two new wrappers (`acercontrol-disable-ppd`, `acercontrol-reload-acer-wmi`) are added to `libexec/`, two new `<action>` blocks are appended to the existing `data/org.acercontrol.policy`, and `acercontrol-gui` is wired through the existing `pyproject.toml` `[project.scripts]` slot.

The stack is fully locked upstream — research's job here is to **resolve the four load-bearing API questions UI-SPEC and CONTEXT explicitly flagged**, document the verified call signatures, and surface three landmines that would silently bite the executor: (1) `Adw.Banner` does not propagate `activate-link`, forcing the documented UI-SPEC fallback; (2) `features.py`'s current `severity` values disagree with CONTEXT decision #3's routing table and require a coordinated Phase 1 micro-patch; (3) `systemctl mask` errors out when the unit is already masked, so the new wrapper must idempotently swallow the "already masked" case.

**Primary recommendation:** Take the documented banner fallback (no Pango link in title; surface "About power-profiles-daemon" via the `Adw.HeaderBar` primary menu). Patch `acercontrol/features.py` severities in lockstep with the Phase 3 plan to match the locked routing table — this is preferable to maintaining a parallel severity remapper in the GUI layer. Use `Adw.AboutDialog.set_debug_info()` for the GUI-08 Diagnostics carve-out (the native upstream slot, simpler than `add_legal_section` or a custom `PreferencesPage`). Keep `subprocess.run` synchronous inside the GTK signal handler — sysfs/`pkexec` calls return in milliseconds-to-seconds and the polkit dialog itself runs out-of-process; GTK main loop blocking is acceptable and matches every Adwaita example for one-shot privileged actions.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**1. PPD disable mechanism → New dedicated wrapper `acercontrol-disable-ppd`**
- 4th `libexec/` wrapper with hardcoded allowlists `ALLOWED_ACTIONS = ("mask", "unmask")` and `ALLOWED_SERVICES = ("power-profiles-daemon.service",)`.
- 4th polkit action `org.acercontrol.disable-ppd` appended to existing `data/org.acercontrol.policy` (extend the file, do NOT create a new one) with `<message>Authentication is required to disable power-profiles-daemon</message>` and `<annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-disable-ppd</annotate>`. `auth_admin_keep` on `<allow_active>`, bare `auth_admin` elsewhere.
- WR-03 carry-forward: planner formalizes that this wrapper does NOT collapse `systemctl` exits to `EX_OSERR=71`; preserve the underlying returncode (or map systemctl-specific exits more carefully).

**2. `acer_wmi` module reload helper → New dedicated wrapper `acercontrol-reload-acer-wmi`**
- 5th `libexec/` wrapper that runs `subprocess.run(["/usr/sbin/modprobe", "-r", "acer_wmi"], check=True, timeout=20)` then `subprocess.run(["/usr/sbin/modprobe", "acer_wmi", "predator_v4=1"], check=True, timeout=20)`. Hardcoded module name and `predator_v4=1`. Absolute `/usr/sbin/modprobe` path (pkexec env scrub).
- Wrapper takes NO argv (or accepts a literal `reload` token for symmetry — planner picks). Refuses any other invocation (EX_USAGE=64).
- 5th polkit action `org.acercontrol.reload-acer-wmi` appended to `data/org.acercontrol.policy`.
- StatusPage button visibility: only when `acer_wmi` is unloaded OR `predator_v4=N`. The `platform_profile`-missing case is read-only (kernel-version requirement).

**3. StatusPage routing strategy → Severity-ordered hybrid (C)**
- Blockers: `acer_wmi` unloaded OR `predator_v4=N` OR `platform_profile` missing OR no `acer` hwmon → full-window `Adw.StatusPage`; main view does not render until resolved.
- Warnings: PPD active OR `acer_wmi` blacklist entry OR `coretemp` hwmon missing → persistent `Adw.Banner` above main view; main view renders normally.
- Multiple blockers: render the FIRST in declared `FeatureReport.checks` order; user walks the chain rung-by-rung via the StatusPage's "Refresh" button.
- Multiple warnings: stack as multiple banners (Adw.Banner is single-row; cycling is a Phase 5 concern — show the most recent only for now).

**4. PPD banner dismissibility → Dismissible-this-session, re-surfaces on revert (B)**
- In-memory `dismissed` flag held on `MainWindow` (no config file).
- Re-surfaces on next app launch if PPD still active (cold start = banner is truth).
- Re-surfaces immediately when Phase 4's revert-on-mismatch event fires.
- Phase 4 contract: `MainWindow.show_ppd_banner(force: bool = False)` — `force=True` overrides the in-session-dismissed flag.

**5. App icon → Defer to Phase 8**
- Phase 3 ships NO app icon. Window uses GTK default fallback. No `Icon=` line in any `.desktop` file (Phase 3 ships no `.desktop` either).

**6. GUI launch path → `[project.scripts]` entry `acercontrol-gui = "acercontrol.gui:main"`**
- Append (uncomment — line is already in `pyproject.toml` from Phase 2) to existing `[project.scripts]` section. After `pip install -e .`, `acercontrol-gui` is on PATH.

### Claude's Discretion

- **Window default size:** 800×600 logical pixels, user-resizable, no minimum-size constraint.
- **About dialog:** `Adw.AboutDialog` (1.5 — replaces deprecated `Adw.AboutWindow`). Standard fields plus a Diagnostics extra section showing raw `features.probe()` JSON verbatim (the GUI-08 carve-out). User can copy-paste for bug reports.
- **StatusPage "Refresh" button:** Footer button on every blocker StatusPage that re-runs `features.probe()` and re-evaluates routing. NO auth needed.
- **Banner copy:** "power-profiles-daemon is running and will overwrite profile changes" + `[Disable PPD]` + `[Learn more]`. Verbatim per ROADMAP success criterion 3.
- **"Learn more" target:** Opens an in-app modal `Adw.Window` titled "About power-profiles-daemon" with explanatory text (no external URL — project has no website).
- **Single-instance behavior:** `Adw.Application(application_id="org.acercontrol.AcerControl", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)`. Second launch triggers `do_activate` on existing instance, which calls `window.present()`.
- **File layout:** `acercontrol/gui.py` (entry), `gui_window.py` (MainWindow), `gui_status_pages.py` (StatusPage factories), `gui_banner.py` (banner + Learn-more dialog), `gui_about.py` (About + Diagnostics).
- **Bundler regression:** `tools/verify_no_gtk.py` must remain green against `acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` AND `dist/acercontrol`. New `gui*.py` files are EXEMPT (they intentionally import `gi`). Planner formalizes the exemption list.
- **Subprocess invocation for new wrappers:** GUI calls `acercontrol.privilege.run_privileged()` — same path the CLI uses; `cancelled=True` flag handled with an `Adw.Toast` "Authentication cancelled."
- **Wrapper resolution:** `_WRAPPER_NAMES` extended to include the 2 new wrappers; no code change to `privilege.py` resolution logic.
- **Smoke test scope on macOS / CI:** Polkit policy XML well-formed; both new wrappers exit 64 on bad argv; bundled `dist/acercontrol` still GTK-free; `import acercontrol.gui_*` modules raise `ImportError` cleanly when `gi` is unavailable (i.e., they fail import gracefully on dev macOS, not silently load broken stubs).

### Deferred Ideas (OUT OF SCOPE)

- Drop polkit auth dialog entirely for `setprofile` (`<allow_active>yes</allow_active>` swap) — captured in PROJECT.md 2026-05-15. Belongs in Phase 2.1 or Phase 8 packaging.
- Hardware Predator/Turbo key → cycle profiles — captured in PROJECT.md 2026-05-15. Belongs between Phase 6 and Phase 7.
- Per-user config file for "don't show PPD banner again" preference — defer until any other config persistence emerges.
- External docs site for "Learn more" PPD link — defer until project has a website.
- WR-03 fix from Phase 2 review (`acercontrol-manage-service` collapses systemctl exits to EX_OSERR=71) — new `acercontrol-disable-ppd` wrapper must NOT inherit this collapsing behavior.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUI-01 | GUI uses `Adw.Application` with `application_id="org.acercontrol.AcerControl"`; main window is `Adw.ApplicationWindow` with `Adw.ToolbarView` + `Adw.HeaderBar` | Verified against [class.Application](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Application.html) and [class.ToolbarView](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.ToolbarView.html). `Adw.ToolbarView.add_top_bar(header)` + `set_content(...)` is the canonical 3-region layout. |
| GUI-02 | A second launch focuses the existing window instead of opening a duplicate | Standard GApplication idiom: subclass `Adw.Application`, override `do_activate`, fetch `self.props.active_window or new MainWindow(application=self)`, call `.present()`. The session-bus registration of `application_id` causes the second launch to forward `activate` to the primary instance. Verified against [GtkApplication docs](https://docs.gtk.org/gtk4/class.Application.html) and [Adw.Application docs](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Application.html). |
| GUI-03 | `features.probe()` runs on startup; failed probes route to dedicated `Adw.StatusPage` with one-click remediation where possible | Routing table per CONTEXT decision #3 + UI-SPEC StatusPage table. `Adw.StatusPage.set_child(Gtk.Box(orientation=VERTICAL, spacing=12))` containing primary `.suggested-action` button (when present) + `Refresh` button. **Phase 1 patch required — see Landmine #2 below.** |
| GUI-04 | Persistent `Adw.Banner` for PPD; `[Disable PPD]` + `[Learn more]` actions | `Adw.Banner.set_button_label("Disable PPD")` + `connect("button-clicked", ...)`. **`[Learn more]` cannot ride on a Pango link inside the banner — see Landmine #1.** Documented UI-SPEC fallback: drop link from title, surface "About power-profiles-daemon" via `Adw.HeaderBar` primary menu. |
| GUI-08 | UI never renders raw kernel profile values; raw values appear only in About → Diagnostics | `Adw.AboutDialog.set_debug_info(json_str)` is the native upstream slot — preferred over `add_legal_section` or a custom `Adw.PreferencesPage`. Diagnostics carve-out exempt from the grep gate documented in UI-SPEC. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Application lifecycle (single-instance, activate, present) | Frontend / GUI shell | — | `Adw.Application` is the GTK canonical owner; nothing else can register the application_id. |
| Failure-mode probe consumption (StatusPage/Banner routing) | Frontend / GUI shell | Backend / Library (probe data) | Probe is read-only data from `acercontrol.features`; routing is purely a UI rendering decision. |
| Privileged remediation invocation (Disable PPD, Reload module) | Frontend / GUI signal handler | Backend / Library (`privilege.run_privileged`) | GUI dispatches to existing privilege boundary — does NOT reimplement elevation. |
| Privileged action execution (mask PPD, modprobe acer_wmi) | OS / `pkexec` + libexec wrapper | — | Trust boundary — wrappers run as root, validate argv against allowlist. |
| About + Diagnostics presentation | Frontend / GUI | Backend (probe JSON) | `Adw.AboutDialog.set_debug_info()` is the upstream-blessed slot. |

## Standard Stack

### Core (verified against Ubuntu 24.04 Noble apt-shipped packages — pinned versions documented in Phase 1 RESEARCH §Stack)

| Library | Version (Noble) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python3-gi` (PyGObject) | 3.48.x | GTK/Adwaita/GLib bindings | Ubuntu-shipped; no pip dep [VERIFIED: CLAUDE.md decision #1, Phase 1 stack lock] |
| `gir1.2-gtk-4.0` | 4.14.x | GTK 4 typelib | `gi.require_version('Gtk', '4.0')` resolves against this [VERIFIED: same] |
| `gir1.2-adw-1` | 1.5.x | libadwaita 1 typelib | Provides `Adw.Application`, `Adw.ApplicationWindow`, `Adw.ToolbarView`, `Adw.HeaderBar`, `Adw.StatusPage`, `Adw.Banner`, `Adw.AboutDialog`, `Adw.AlertDialog`, `Adw.Toast`, `Adw.ToastOverlay` [VERIFIED: same] |
| `gir1.2-glib-2.0` | 2.80+ | GLib/Gio typelib | `Gio.ApplicationFlags.DEFAULT_FLAGS` (since GLib 2.74; `FLAGS_NONE` deprecated) [CITED: https://github.com/vmagnin/gtk-fortran/issues/267] |
| `policykit-1` | 124+ | polkit + `pkexec` | Already installed — Phase 2 polkit policy file uses it |

### Supporting (Phase 3 adds NO new pip or apt deps beyond the Phase 1/2 baseline)

None.

### Alternatives Considered (relevant to Phase 3 scope)

| Instead of | Could Use | Why we reject |
|------------|-----------|---------------|
| `subprocess.run` blocking inside the GTK signal handler | `Gio.Subprocess.communicate_async` | Polkit dialog runs out-of-process; the `pkexec` invocation itself returns in seconds at most (modprobe ≤ 2s, systemctl mask sub-second). Sync subprocess matches every Adwaita example for one-shot privileged actions. Async adds cancellation/cleanup complexity for zero perceptible UX gain. [ASSUMED — confirmed by Adwaita docs showing sync patterns] |
| `Adw.Banner` Pango link for "Learn more" | `Adw.HeaderBar` primary-menu entry "About power-profiles-daemon" | **Mandatory** — `Adw.Banner` does not expose `activate-link`. See Landmine #1. |
| `Adw.AboutDialog.add_legal_section` for Diagnostics | `Adw.AboutDialog.set_debug_info(json_str)` | `set_debug_info` is the native upstream slot [VERIFIED: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.AboutDialog.html — `adw_about_dialog_set_debug_info`]. Cleaner than overloading the legal section with technical output. |
| `Adw.Window` for the Learn-more dialog (UI-SPEC's pick) | `Adw.Dialog` (1.5+) | UI-SPEC specifies `Adw.Window`, which works. `Adw.Dialog` is the modern equivalent for modal sub-windows and shares the `present(parent)` pattern with `Adw.AboutDialog`/`Adw.AlertDialog`. Planner may upgrade; not a Phase 3 blocker. |
| `Gtk.Application` directly | `Adw.Application` | `Adw.Application` calls `adw_init()` in its default `startup` handler — using `Gtk.Application` would force a manual `Adw.init()` call. [VERIFIED: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Application.html] |
| `Gio.ApplicationFlags.FLAGS_NONE` | `Gio.ApplicationFlags.DEFAULT_FLAGS` | `FLAGS_NONE` deprecated since GLib 2.74; `DEFAULT_FLAGS` (same value, 0) is the supported spelling. Will be removed in GLib 3.0. [CITED: vmagnin/gtk-fortran#267, GLib 2.74 release notes] |

**Installation (developer setup; verifies Phase 3 stack is reachable):**

```bash
# Phase 1/2 stack already installed; Phase 3 only adds the GTK4/Adwaita typelibs to the dev box.
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1

# Verify reachable from Python
python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw; print('OK', Adw._namespace, Gtk._namespace)"
```

**Version verification:** `python3-gi` and the gir1.2-* packages on Noble are static across the LTS lifecycle. No `pip` package versions to verify for Phase 3.

## Project Constraints (from CLAUDE.md)

| Constraint | How Phase 3 honors |
|-----------|---------------------|
| GTK4 + libadwaita only — no Qt, no Electron | Confirmed; `gi.require_version('Gtk', '4.0')` and `('Adw', '1')` enforced at module top of every `gui*.py`. |
| No pip-only deps for the GUI | Confirmed; only Ubuntu-shipped `python3-gi` + typelibs used. |
| Polkit policy file extension, not replacement | New `<action>` blocks appended to existing `data/org.acercontrol.policy`; single source of truth preserved. |
| Single-file CLI must remain GTK-free | `tools/verify_no_gtk.py` unchanged behavior; new `gui*.py` files added to its IGNORE list (planner formalizes); bundler input list unchanged. |
| Compatibility — hwmon by `name` | Not Phase 3's concern (Phase 1 owns); but the StatusPage "no acer hwmon" wording must match what `find_hwmon` actually reports. |
| Distribution — `.deb` is v1 channel | Not Phase 3's concern (Phase 8); but the new wrapper install paths (`/usr/libexec/acercontrol/`) must be written to match the Phase 8 install layout. |
| Application ID `org.acercontrol.AcerControl` | Confirmed; locked in CONTEXT decision Claude-discretion + UI-SPEC. |
| Adwaita-mandated decisions table (CLAUDE.md decisions #1–#10) | All five Phase-3-relevant decisions (#1, #2, #3, #4, #9) honored. Decision #4 (`Gio.Notification` for system + `Adw.Toast` for in-app) is honored — Phase 3 uses `Adw.Toast` only (system notifications land in Phase 5 per UI-SPEC). |

## Architecture Patterns

### System Architecture Diagram

```
                             ┌─ launch: `acercontrol-gui` ──┐
                             │                                │
                             ▼                                │
                    ┌──────────────────┐                      │
                    │ Adw.Application  │  ───── if primary    │
                    │ application_id=  │   instance already   │
                    │ "org.acercontrol │   alive on session   │
                    │  .AcerControl"   │   bus, this is the   │
                    │ flags=DEFAULT    │   forwarded activate │
                    └────────┬─────────┘                      │
                             │ activate signal                │
                             ▼                                │
                    ┌──────────────────────┐                  │
                    │ App.do_activate()    │                  │
                    │   1. self.props.     │                  │
                    │      active_window?  │                  │
                    │      → present()     │ ◀────────────────┘
                    │   2. else            │  GUI-02 path
                    │      MainWindow(app) │
                    │      .present()      │
                    └────────┬─────────────┘
                             │ first-launch only
                             ▼
                    ┌──────────────────────┐
                    │ MainWindow.__init__  │
                    │   1. construct       │
                    │      ToolbarView →   │
                    │      add_top_bar(    │
                    │        HeaderBar)    │
                    │      set_content(    │
                    │        ToastOverlay) │
                    │   2. report = probe()│ ─── synchronous,
                    │   3. _route(report)  │     sub-millisecond
                    └────────┬─────────────┘
                             │
                ┌────────────┴────────────┐
                │ FeatureReport routing   │
                │ (CONTEXT decision #3)   │
                └────────────┬────────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼ blocker (severity=blocking) ▼ all-clear (FeatureReport.ok)
   ┌─────────────────────┐         ┌──────────────────────────┐
   │ render full-window  │         │ render placeholder card  │
   │ Adw.StatusPage for  │         │ "Profile controls coming │
   │ first_blocking_     │         │  in Phase 4"             │
   │ failure             │         │                          │
   │ • icon (per table)  │         │ then evaluate warnings:  │
   │ • title             │         │ for each warning probe,  │
   │ • description       │         │   stack one Adw.Banner   │
   │ • [Primary CTA]     │         │   above main content     │
   │ • [Refresh]         │         │ • PPD active → button +  │
   │                     │         │   HeaderBar menu link    │
   │ button click →      │         │   (Landmine #1 fallback) │
   │  privilege.run_     │         │ • blacklist  → read-only │
   │  privileged(...)    │         │ • coretemp   → read-only │
   │  → toast + re-probe │         └──────────────────────────┘
   └─────────────────────┘                       │
                                                 ▼
                                ┌──────────────────────────────┐
                                │ Disable PPD button click →   │
                                │  privilege.run_privileged([  │
                                │   "acercontrol-disable-ppd", │
                                │   "mask",                    │
                                │   "power-profiles-daemon.    │
                                │    service"])                │
                                │  → success: toast + re-probe │
                                │  → cancelled: toast only     │
                                │  → failure: toast only       │
                                └──────────────────────────────┘

   ┌──────────────────────────── invariants ───────────────────────────┐
   │ • All gui*.py modules import gi at module top (clean ImportError  │
   │   on macOS/CI when typelibs are absent — see CI Pattern below).   │
   │ • subprocess + privilege.run_privileged are SYNCHRONOUS inside    │
   │   the signal handler — pkexec runs out-of-process; GTK main loop  │
   │   blocking is acceptable for sub-2s actions.                      │
   │ • verify_no_gtk.py stays green on the bundler input list.         │
   │ • UI labels for profile names go through                          │
   │   acercontrol.profiles.kernel_to_profile() — NEVER raw strings.   │
   │   Phase 3 doesn't render profile names at all (Phase 4) except in │
   │   the About → Diagnostics carve-out.                              │
   └───────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (Phase 3 additions)

```
acercontrol/
├── gui.py                          # NEW — entry point: main(), Adw.Application subclass, do_activate
├── gui_window.py                   # NEW — MainWindow(Adw.ApplicationWindow): ToolbarView + HeaderBar + ToastOverlay; _route(report); show_ppd_banner(force=False)
├── gui_status_pages.py             # NEW — factory functions per blocker probe key (one per row in StatusPage Copy Table)
├── gui_banner.py                   # NEW — PPD banner construction + dismissal; Learn-more dialog
└── gui_about.py                    # NEW — Adw.AboutDialog with set_debug_info(probe JSON) and HeaderBar primary-menu wiring

libexec/
├── acercontrol-disable-ppd         # NEW — mask/unmask × power-profiles-daemon.service allowlist (CONTEXT #1)
└── acercontrol-reload-acer-wmi     # NEW — modprobe -r/+ acer_wmi predator_v4=1 (CONTEXT #2)

data/
└── org.acercontrol.policy          # EDITED — append 2 new <action> blocks (decisions #1, #2)

acercontrol/privilege.py            # EDITED — extend WRAPPER_NAMES tuple to include the 2 new wrappers (no logic change)

pyproject.toml                       # EDITED — uncomment the existing `acercontrol-gui = "acercontrol.gui:main"` line in [project.scripts]

tools/
└── smoke_phase3.py                 # NEW (planner names) — CI-safe smoke (XML well-formed, wrapper argv rejection, gi-import-fails-cleanly on macOS, bundler GTK-free regression)
```

### Pattern 1: Single-instance `Adw.Application` skeleton

**What:** Subclass `Adw.Application`, register `application_id`, handle `do_activate` to either present the existing window or construct a new one. The GApplication session-bus registration handles second-launch forwarding automatically.

**When to use:** Always for any libadwaita app; single-instance is the default, opt-out via `Gio.ApplicationFlags.NON_UNIQUE`.

**Code skeleton (Python / PyGObject):**

```python
# acercontrol/gui.py
"""AcerControl GUI entry point. Phase 3."""
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from acercontrol.gui_window import MainWindow


class AcerControlApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="org.acercontrol.AcerControl",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,  # NOT FLAGS_NONE (deprecated since GLib 2.74)
        )

    def do_activate(self) -> None:
        # GUI-02: second launch fires `activate` on the primary instance;
        # we focus the existing window instead of constructing a new one.
        win = self.props.active_window
        if win is None:
            win = MainWindow(application=self)
        win.present()


def main() -> int:
    """Entry point wired from pyproject.toml [project.scripts]."""
    return AcerControlApp().run(None)
```

**Source:** [`gtk_application_get_active_window()` example in GtkApplication docs](https://docs.gtk.org/gtk4/class.Application.html); confirms the canonical "fetch active or construct" pattern. `Adw.Application` automatically calls `adw_init()` in its default `startup` handler — no manual init needed [[class.Application](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Application.html)].

### Pattern 2: `Adw.ToolbarView` 3-region layout

**What:** Wrap `Adw.HeaderBar` as the top bar, `Adw.ToastOverlay` (containing the actual content swapper) as the content. This is the modern replacement for the old `Adw.ApplicationWindow.set_content(Gtk.Box(VERTICAL))` pattern.

**Code skeleton:**

```python
# acercontrol/gui_window.py (excerpt)
class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("AcerControl")
        self.set_default_size(800, 600)

        # 3-region layout
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        # HeaderBar primary menu (Landmine #1 fallback target)
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", primary=True)
        menu_button.set_menu_model(self._build_primary_menu())
        header.pack_end(menu_button)
        toolbar.add_top_bar(header)

        # Content area: ToastOverlay wraps a swapper (Stack or single child)
        self._toast_overlay = Adw.ToastOverlay()
        self._content_swapper = Gtk.Stack()  # blocker-page vs main-content
        self._toast_overlay.set_child(self._content_swapper)
        toolbar.set_content(self._toast_overlay)

        self.set_content(toolbar)

        # GUI-03: probe FIRST, then route
        self._route(probe())
```

**Source:** [`Adw.ToolbarView` API — `add_top_bar` + `set_content`](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.ToolbarView.html); top-bar style defaults are appropriate (subtle undershoot shadow on scroll).

### Pattern 3: Adw.Banner construction (PPD warning, single button)

**What:** `Adw.Banner` is a single-button, optionally-revealed banner. The button click emits `button-clicked`. The internal title GtkLabel is **not exposed** — Pango `<a>` links inside the title cannot be intercepted (see Landmine #1).

**Code skeleton (after Landmine #1 fallback applied):**

```python
# acercontrol/gui_banner.py (excerpt)
def build_ppd_banner(window) -> Adw.Banner:
    """Build the persistent PPD-active banner. After the activate-link
    fallback: title is plain text, button is the only interactive element,
    'Learn more' is reached via the HeaderBar primary menu."""
    banner = Adw.Banner.new(
        "power-profiles-daemon is running and will overwrite profile changes."
    )
    banner.set_button_label("Disable PPD")
    banner.set_revealed(True)
    banner.connect("button-clicked", window._on_disable_ppd_clicked)
    banner.add_css_class("warning")  # severity styling per UI-SPEC
    return banner
```

**Source:** [`Adw.Banner` properties: title, button-label, revealed, use-markup, button-style; signal: button-clicked](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Banner.html). The `use-markup` property exists but DOES NOT propagate link clicks — see Landmine #1 below.

### Pattern 4: `Adw.StatusPage` factory for a blocker page

**What:** Factory function per probe key. Constructs an `Adw.StatusPage`, sets icon/title/description, attaches a `Gtk.Box(orientation=VERTICAL, spacing=12)` as `set_child` containing the primary remediation button (when present) and the always-present `Refresh` button.

**Code skeleton:**

```python
# acercontrol/gui_status_pages.py (excerpt)
def acer_wmi_not_loaded(window) -> Adw.StatusPage:
    page = Adw.StatusPage()
    page.set_icon_name("dialog-error-symbolic")
    page.set_title("acer_wmi module not loaded")
    page.set_description(
        "The acer_wmi kernel module is required for performance control. "
        "Click below to load it with predator_v4=1."
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

    primary = Gtk.Button(label="Load module")
    primary.add_css_class("suggested-action")
    primary.add_css_class("pill")  # GNOME HIG: prominent CTA in StatusPage
    primary.connect("clicked", window._on_reload_acer_wmi_clicked)
    box.append(primary)

    refresh = Gtk.Button(label="Refresh")
    refresh.add_css_class("flat")
    refresh.connect("clicked", lambda *_: window._route(probe()))
    box.append(refresh)

    page.set_child(box)
    return page
```

**Source:** [`Adw.StatusPage` properties: icon-name, title, description (Pango markup), child, paintable](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.StatusPage.html). Description supports markup natively (no `use-markup` toggle). `set_child` accepts any `GtkWidget` including `Gtk.Box` — multi-button vertical stack is the standard Adwaita-recommended pattern for StatusPage actions.

### Pattern 5: Privileged action from a GTK signal handler

**What:** Synchronous `subprocess.run` via `privilege.run_privileged()` inside the signal handler. The GTK main loop blocks during the `pkexec` call, but the polkit auth dialog runs in its own process and the wrapper completes in milliseconds-to-seconds for both Phase 3 actions.

**Code skeleton:**

```python
# acercontrol/gui_window.py (excerpt)
def _on_disable_ppd_clicked(self, banner: Adw.Banner) -> None:
    button = self._set_button_authenticating(banner)
    try:
        result = run_privileged(
            ["acercontrol-disable-ppd", "mask", "power-profiles-daemon.service"]
        )
    finally:
        self._restore_button(banner, button)

    if result.cancelled:
        self._toast("Authentication cancelled.")
        return
    if result.returncode != 0:
        self._toast("Operation failed. See terminal for details.")
        # Optional: log result.stderr to journal via GLib.log
        return
    self._toast("power-profiles-daemon disabled.")
    # Re-probe → routing re-evaluates → banner self-removes
    self._route(probe())
```

**Source:** Phase 2's `acercontrol/privilege.py` is unchanged — same code path the CLI uses. `subprocess.run` blocking inside a GTK handler is acceptable for sub-2s actions and matches the upstream Adwaita examples for one-shot privileged operations. Async (`Gio.Subprocess.communicate_async`) adds cancellation/cleanup complexity for zero perceptible UX gain at sub-2s latencies. [ASSUMED — reviewed Adwaita examples; no upstream guidance against the sync pattern for one-shot privileged calls.]

### Pattern 6: `Adw.AboutDialog` + Diagnostics via `set_debug_info`

**What:** `Adw.AboutDialog.set_debug_info(json_str)` is the upstream-blessed slot for the GUI-08 Diagnostics carve-out. No need to overload `add_legal_section` or hand-roll a `PreferencesPage` with a `Gtk.TextView`.

**Code skeleton:**

```python
# acercontrol/gui_about.py (excerpt)
def build_about_dialog() -> Adw.AboutDialog:
    dialog = Adw.AboutDialog()
    dialog.set_application_name("AcerControl")
    dialog.set_version(__version__)
    dialog.set_developer_name("AcerControl contributors")
    dialog.set_copyright("© 2026 AcerControl contributors")
    dialog.set_license_type(Gtk.License.GPL_3_0)

    # GUI-08 carve-out: raw kernel values land here, only here.
    report = probe()
    debug_json = json.dumps(_report_to_dict(report), indent=2)
    dialog.set_debug_info(debug_json)

    return dialog


# Triggered from HeaderBar primary menu "About AcerControl"
def show_about(parent_window) -> None:
    build_about_dialog().present(parent_window)
```

**Source:** [`adw_about_dialog_set_debug_info`](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.AboutDialog.html) — explicitly intended for diagnostic information.

### Anti-Patterns to Avoid

- **`Gtk.StatusIcon`** — removed in GTK4. (CLAUDE.md decision #2; not Phase 3 but worth re-stating since UI-SPEC mentions tray-deferred-to-Phase-7.)
- **`pkexec bash -c '...'`** — the Phase 2 anti-pattern. Phase 3 calls existing `privilege.run_privileged()` which targets named wrappers.
- **Constructing `gi.repository` imports inside try/except in module code** — if `gi` is unavailable, the import should fail loudly. CI relies on this `ImportError` to skip GUI assertions on macOS. (See "Headless ImportError Pattern" below.)
- **Connecting `activate-link` to `Adw.Banner`** — the signal does not exist on the public API. See Landmine #1.
- **Reading raw `pv4` / kernel profile strings into UI text** — GUI-08 violation. Only the About → Diagnostics `set_debug_info` slot is exempt.
- **Calling `Adw.init()` manually** — `Adw.Application` does this in its default `startup`. Manual `Adw.init()` is only needed if you subclass `Gtk.Application` instead.
- **`Gio.ApplicationFlags.FLAGS_NONE`** — deprecated since GLib 2.74; use `DEFAULT_FLAGS`.
- **`Adw.AboutWindow`** — deprecated; use `Adw.AboutDialog` (1.5+).
- **`Adw.AppNotification`** — deprecated; use `Adw.Toast` + `Adw.ToastOverlay`. (CLAUDE.md decision #4.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Single-instance app behavior | Custom lockfile, `/tmp/acercontrol.pid`, D-Bus name probing | `Adw.Application(application_id=..., flags=DEFAULT_FLAGS)` + override `do_activate` | GApplication's session-bus registration handles all the edge cases (race on launch, signal forwarding, command-line activation). |
| In-app temporary feedback | Custom `Gtk.Revealer` with a label | `Adw.Toast` + `Adw.ToastOverlay` | 5-second default timeout, NORMAL/HIGH priority, action button slot — all upstream. |
| Modal "are you sure" / "About" | `Gtk.Dialog` (legacy GTK3 pattern; deprecated semantics) | `Adw.AlertDialog`, `Adw.AboutDialog` (1.5+) | Both subclass `Adw.Dialog`; share the modern `present(parent)` lifecycle and integrate with libadwaita's adaptive presentation. |
| Diagnostics text dump in About | Custom `PreferencesPage` + `TextView` + clipboard button | `Adw.AboutDialog.set_debug_info(json_str)` | Native upstream slot — handles copy-to-clipboard, scrolling, monospace formatting. |
| Persistent in-app notice ("PPD detected") | Custom `Gtk.InfoBar` (still works but un-Adwaita-flavored) | `Adw.Banner` | Adwaita-styled, has built-in revealer animation, `.warning` / `.error` style classes, and a single action button slot. |
| polkit policy file second copy | Separate `data/org.acercontrol.disable-ppd.policy` | Append `<action>` blocks to existing `data/org.acercontrol.policy` | Single source of truth; `pkaction --action-id ...` enumerates without restart. |
| Module reload | Inline `subprocess.run(["pkexec", "modprobe", ...])` from the GUI | New `acercontrol-reload-acer-wmi` wrapper invoked via `privilege.run_privileged` | Generic `pkexec` text in dialog ("authentication required to run /usr/sbin/modprobe"), plus accepts arbitrary modprobe targets. Named wrapper has named polkit action and tight allowlist. |

**Key insight:** Every Phase 3 feature has an upstream Adwaita 1.5 widget or pattern. The plan should never reach for `Gtk.*` primitives when `Adw.*` exists for the same job. The only `Gtk.*` widgets needed: `Gtk.Box` (StatusPage child container), `Gtk.Stack` (content swapper between blocker page and main), `Gtk.Button` (StatusPage primary CTA + Refresh — `Adw.*` has no plain button), `Gtk.MenuButton` (HeaderBar primary menu). Everything else is `Adw.*`.

## Runtime State Inventory

> Phase 3 is greenfield GUI work + 2 new wrappers + polkit policy edits. There is no rename/refactor/migration aspect. **This section is included for completeness; nothing to migrate.**

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 3 does not introduce a persistence layer. PPD-banner-dismissed flag is in-memory only (CONTEXT decision #4). | none |
| Live service config | None — no external service configuration changes. The Disable PPD wrapper triggers `systemctl mask`, but this is a runtime user action, not a phase migration. | none (handled by wrapper at user-action time) |
| OS-registered state | New polkit policy file actions (`org.acercontrol.disable-ppd`, `org.acercontrol.reload-acer-wmi`). Polkit hot-reloads on file overwrite — `pkaction --action-id org.acercontrol.disable-ppd` should list the new action without restart. | install policy file via Phase 8 `.install` rules; for dev mode, `sudo cp data/org.acercontrol.policy /usr/share/polkit-1/actions/` |
| Secrets/env vars | None | none |
| Build artifacts | `pyproject.toml` `[project.scripts]` change adds `acercontrol-gui` to PATH after `pip install -e .` — existing dev installs need a re-install to pick up the new console-script entry. | `pip install -e .` (one-time per dev box; planner can document in plan) |

**Nothing found in 4 of 5 categories** — Phase 3 is plumbing-and-UI work without runtime state migration concerns.

## Common Pitfalls

### Landmine #1: `Adw.Banner` does NOT propagate `activate-link` (load-bearing API risk — UI-SPEC's option (a) is empirically disconfirmed)

**What goes wrong:** UI-SPEC's locked banner design embeds a Pango `<a href="learn-more">Learn more</a>` link in the banner title and expects to intercept the click via `activate-link`. The signal does not exist on `Adw.Banner`'s public API.

**Why it happens:**
- `Adw.Banner` exposes properties `title`, `button-label`, `revealed`, `use-markup`, `button-style` and exactly ONE custom signal: `button-clicked`. [VERIFIED: [class.Banner property + signal table](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Banner.html)]
- The internal `GtkLabel` is bound from a private template (`bind_template_child(... AdwBanner, title)`) and has no public getter. [VERIFIED: [adw-banner.c source](https://gitlab.gnome.org/GNOME/libadwaita/-/raw/1.5.4/src/adw-banner.c) — `gtk_widget_class_bind_template_child (widget_class, AdwBanner, title)` with no exposed accessor]
- The internal `GtkLabel` IS handling the link click — its default `activate-link` handler calls `gtk_file_launcher_launch("learn-more")`. [VERIFIED: [GtkLabel::activate-link signal docs](https://docs.gtk.org/gtk4/signal.Label.activate-link.html) — "the default handler [...] is to call gtk_file_launcher_launch()"]
- This means clicking the link silently invokes the system's URI handler with `learn-more` as the URI — user sees a "no application available to handle this link" dialog or worse.

**How to avoid:** Take the documented UI-SPEC fallback verbatim:

> "If `Adw.Banner` does NOT expose `activate-link`, fallback is to remove the Pango link from the title and add a separate 'About PPD' entry to the `Adw.HeaderBar` primary menu."

Concrete plan:
1. Banner title becomes plain text: `"power-profiles-daemon is running and will overwrite profile changes."` (drop the `<a href="learn-more">Learn more</a>` suffix; do NOT enable `use-markup`).
2. `Adw.HeaderBar` packs a `Gtk.MenuButton(icon_name="open-menu-symbolic", primary=True)` whose menu model contains:
   - "About power-profiles-daemon" → opens the existing UI-SPEC "Learn-more" `Adw.Window` (or `Adw.Dialog` — see alternatives table)
   - "About AcerControl" → opens the `Adw.AboutDialog`
3. Banner button (`Disable PPD`) remains the only interactive element on the banner itself.

**Warning signs:** None at compile time — the misuse fails silently (clicking the link does nothing useful). Detected by Wave 0 verification (a manual click during PHN16-72 UAT).

**Alternative considered (`Adw.AlertDialog` on banner-button click):** Forces a 2-click path for both "Disable" and "Learn more" actions, breaks the verbatim ROADMAP-success-criterion phrasing of `[Disable PPD]` AND `[Learn more]` as visually distinct affordances. The HeaderBar-menu fallback is cleaner.

### Landmine #2: `features.py` severity values DON'T match CONTEXT decision #3 routing — coordinated Phase 1 patch required

**What goes wrong:** CONTEXT decision #3 specifies the routing table that the GUI uses to partition checks into blockers (full StatusPage) vs warnings (banner). The existing `features.py` file already has a `severity` field on `FeatureCheck` — but the values populated for several checks contradict the Phase 3 routing table:

| Probe key (features.py name) | features.py severity (current) | CONTEXT decision #3 wants | UI-SPEC StatusPage Copy Table position |
|------------------------------|-------------------------------|---------------------------|-----------------------------------------|
| `acer_wmi module loaded` | `blocking` | `blocking` (blocker) | ✅ blocker: `acer_wmi-not-loaded` |
| `predator_v4 mode` | `blocking` | `blocking` (blocker) | ✅ blocker: `predator_v4=N` |
| `platform_profile sysfs` | `blocking` | `blocking` (blocker) | ✅ blocker: `platform_profile-missing` |
| `acer hwmon (fan+temp)` | **`warning`** | **`blocking` (blocker)** | ❌ blocker: `no-acer-hwmon` |
| `coretemp hwmon` | **`info`** | **`warning` (banner)** | ❌ warning: `coretemp-missing` |
| `power-profiles-daemon inactive` | `warning` | `warning` (banner) | ✅ warning: `ppd-active` |
| `acer_wmi not blacklisted` | **`blocking` when found** | **`warning` (banner)** | ❌ warning: `acer_wmi-blacklisted` |

Three mismatches. If the GUI naively routes by `check.severity == "blocking"`:
- `acer hwmon` missing → renders as a warning banner instead of a full StatusPage (user sees a sensors-broken banner instead of "Acer sensors unavailable" page)
- `coretemp` missing → silent (the check is severity `info`, which neither path renders) instead of the documented `coretemp-missing` warning banner
- `acer_wmi` blacklist hit → renders as a full-window StatusPage instead of the documented warning banner

**Why it happens:** CONTEXT.md `<specifics>` flagged this explicitly — "Phase 3 may need to ADD a `severity` field to each `Check` for the routing in decision #3 — coordinate with planner whether this lives in `acercontrol/features.py` or in the GUI as a derived classifier." The field exists, but its values were chosen during Phase 1 before the Phase 3 routing table was locked.

**How to avoid (recommended path — Phase 1 micro-patch):** Plan a small, surgical edit to `acercontrol/features.py` that updates these three severities to match the Phase 3 routing. Touches:
- `acer hwmon (fan+temp)`: `severity="warning"` → `severity="blocking"`
- `coretemp hwmon`: `severity="info"` → `severity="warning"`
- `acer_wmi not blacklisted`: `severity="blocking" if blacklist else "info"` → `severity="warning" if blacklist else "info"`

**Why a Phase 1 patch over a GUI-side severity remapper:** CONTEXT.md `<canonical_refs>` declares `acercontrol/features.py` to be the "single source of truth for failure routing." A `SEVERITY_OVERRIDES` table in `gui_status_pages.py` would create two sources of truth, drift bait for any future check additions, and an inconsistency between CLI `acercontrol status` (which surfaces severities for human consumption) and GUI routing.

**Cost of the patch:**
- Phase 1's `01-VERIFICATION.md` baseline must be re-run — but the smoke test asserts probe behavior, not specific severity strings, so the re-verification is a formality.
- Phase 2's CLI behavior (`acercontrol status` rendering) does NOT depend on these severity values — `cli.py`'s `_status_format` function (per the CLI-01 contract) prints all checks regardless of severity, with severity used only for the leading glyph in human output.
- The Phase 3 plan declares this as a Wave 0 task: "PATCH `acercontrol/features.py` severity values for `acer-hwmon`, `coretemp`, `blacklist` checks to match Phase 3 routing table."

**Warning signs:** A purely `gui*.py`-only Phase 3 PR will silently misroute three of the seven probe outcomes. Detected by Wave 0 verification: a unit test that asserts `probe()` returns the expected severities, and a routing test that asserts each `(probe-key, severity)` pair lands on the correct UI surface.

### Landmine #3: `systemctl mask` ERRORS when the unit is already masked — wrapper must be idempotent

**What goes wrong:** `systemctl mask power-profiles-daemon.service` creates a symlink at `/etc/systemd/system/power-profiles-daemon.service → /dev/null`. If a matching symlink already exists from a prior `mask`, systemctl exits non-zero with `"Failed to enable unit: File /etc/systemd/system/... already exists."` (or similar). The naive wrapper would surface this as `EX_OSERR=71` and the GUI would show "Operation failed. See terminal for details." even though the user's intent (PPD masked) is satisfied.

**Why it happens:** Per the systemctl(1) manpage:
> "[mask] will create a symlink under the unit's name in /etc/systemd/system/[…] If a matching unit file already exists under these directories this operation will hence fail."
> "[mask] honors the `--runtime` option to only mask temporarily until the next reboot of the system."

So mask is persistent across reboots without `--runtime`, AND fails if the symlink already exists. The "fix" is wrapper-level idempotency.

**How to avoid (recommended wrapper logic):**

```python
# libexec/acercontrol-disable-ppd (sketch)
def main(argv):
    # ... validate argv against ALLOWED_ACTIONS / ALLOWED_SERVICES ...
    action, service = argv[1], argv[2]

    # Idempotency for `mask`: probe state first.
    if action == "mask":
        probe = subprocess.run(
            ["systemctl", "is-enabled", service],
            capture_output=True, text=True, timeout=5,
        )
        if probe.stdout.strip() == "masked":
            sys.stderr.write(f"{service} already masked\n")
            return EX_OK  # idempotent success
    # Idempotency for `unmask`: same probe, opposite intent.
    elif action == "unmask":
        probe = subprocess.run(
            ["systemctl", "is-enabled", service],
            capture_output=True, text=True, timeout=5,
        )
        if probe.stdout.strip() != "masked":
            sys.stderr.write(f"{service} already unmasked\n")
            return EX_OK

    # Now invoke the real action; preserve underlying returncode (NOT collapsed
    # to EX_OSERR — see WR-03 carry-forward note in CONTEXT.md deferred ideas).
    cmd = ["systemctl", action]
    if action == "mask":
        cmd.append("--now")  # also stop the running unit
    cmd.append(service)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode
```

Note: `mask --now` semantics confirmed — `--now` "ensure[s] that the units are also stopped" in addition to creating the mask symlink. Always pair with `--now` for the PPD use case (we want it stopped immediately, not at next reboot).

**Warning signs:** Detected by a smoke-test scenario "mask twice → exit 0 both times." Should be in 03-VALIDATION.md.

**Reversibility note:** `mask` IS reversible across reboots via `unmask`. The "Learn more" dialog copy in UI-SPEC already documents the reverse command (`sudo systemctl unmask power-profiles-daemon`). No persistent state is created beyond the symlink.

### Landmine #4: `pyproject.toml` `[project.scripts]` change requires `pip install -e .` to take effect

**What goes wrong:** Devs who already ran `pip install -e .` after Phase 2 will have `acercontrol` on PATH but NOT `acercontrol-gui`, because `[project.scripts]` is read at install time and the Phase 2 install didn't include the GUI entry. Re-installing is required. Without it, devs run the GUI as `python3 -m acercontrol.gui` — which works, but breaks the assumed `acercontrol-gui` invocation in the README and CI smoke.

**How to avoid:** Phase 3 plan includes a Wave 0 step: "Run `pip install -e . --force-reinstall` (or `pip install -e .`) to register the new console-script entry." Document this in the README's "How to run the GUI from source" section that CONTEXT.md flags as in-scope for Claude's Discretion.

**Warning signs:** `which acercontrol-gui` returns nothing; `command -v acercontrol-gui` exit 1. CI smoke can assert: `python3 -c "import importlib.metadata as m; assert 'acercontrol-gui' in {ep.name for ep in m.entry_points(group='console_scripts')}"`.

### Landmine #5: GUI module imports must FAIL CLEANLY when `gi` is unavailable on macOS / CI

**What goes wrong:** The CI smoke runner runs on macOS where `gi` (PyGObject) is not installed. If `acercontrol/gui*.py` modules wrap their `import gi` in a try/except (a common defensive instinct), they will silently load broken stubs, defeating the regression guard. Conversely, if they don't fail cleanly, the smoke's `import acercontrol.gui` may produce a confusing crash instead of a recognized `ImportError`.

**How to avoid:** Module-top imports stay raw, no try/except wrapping:

```python
# acercontrol/gui.py — module top (matches Pattern 1 above)
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402
```

On macOS without PyGObject installed: `import gi` raises `ImportError: No module named 'gi'`.

On Linux with PyGObject but missing typelibs (e.g. `gir1.2-adw-1` not installed): `gi.require_version("Adw", "1")` raises `ValueError: Namespace Adw not available` (NOT `ImportError`).

**The smoke test must accept BOTH exception types:**

```python
# tools/smoke_phase3.py (sketch)
import importlib

EXPECTED_GI_FAILURES = (ImportError, ValueError)

def test_gui_modules_fail_cleanly_without_gi():
    """On macOS/CI without PyGObject, GUI modules raise ImportError or
    ValueError at import — never silently loading broken stubs."""
    for mod in ("acercontrol.gui", "acercontrol.gui_window",
                "acercontrol.gui_status_pages", "acercontrol.gui_banner",
                "acercontrol.gui_about"):
        try:
            importlib.import_module(mod)
        except EXPECTED_GI_FAILURES:
            pass  # expected on macOS / no-typelibs
        except Exception as exc:
            raise AssertionError(
                f"{mod} raised unexpected exception type: "
                f"{type(exc).__name__}: {exc}"
            )
        else:
            # On Linux with full GTK4/Adwaita stack, import succeeds — that's fine.
            # The test passes either way; the assertion is "no spurious exception type."
            pass
```

**Warning signs:** A Phase 3 PR where Wave 0 smoke fails on macOS with `RuntimeError` or `AttributeError` instead of `ImportError`/`ValueError` — indicates a try/except snuck in at module top.

### Landmine #6: `tools/verify_no_gtk.py` exemption list must be formalized for new `gui*.py` files

**What goes wrong:** `tools/verify_no_gtk.py` runs against the bundler's input list AND (per Phase 2's CLI-07 invariant) against `dist/acercontrol`. The bundler input list is currently `acercontrol/{profiles,sysfs,core,features,privilege,cli}.py`. If the planner accidentally adds `gui*.py` to the bundler input, the bundler fails. If they accidentally extend `verify_no_gtk.py`'s scope to include `gui*.py`, every new GUI file fails the gate.

**How to avoid:** Phase 3 plan formalizes:
1. The bundler input list stays exactly as-is (Phase 2 lock — `gui*.py` are NOT added).
2. `tools/verify_no_gtk.py` itself is unchanged; it's invoked by `bundle_cli.py` against the bundler's input list and post-bundle against `dist/acercontrol`. Neither invocation touches `gui*.py`.
3. The Phase 3 smoke test reaffirms the invariant: "verify_no_gtk on the bundler input list returns 0; verify_no_gtk on the bundled output returns 0; verify_no_gtk on `acercontrol/gui*.py` returns ≥1 (sanity check that the gate works)."

**Warning signs:** `dist/acercontrol` builds clean but smoke fails because `verify_no_gtk` reports the GUI files as gtk-tainted. Solution: don't put them in the bundler input list.

### Landmine #7: `Adw.AboutDialog` requires a parent window — call `present(self)` not `present()`

**What goes wrong:** `Adw.AboutDialog` inherits from `Adw.Dialog` (1.5+); its `present()` method requires a `parent` argument: `adw_dialog_present(self, parent)`. Calling `dialog.present()` without an arg fails with a `TypeError`.

**How to avoid:** Always pass the active window: `dialog.present(self.props.active_window)` or `dialog.present(main_window)`.

**Source:** [`AdwDialog.present(parent)` since 1.5](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.AboutDialog.html).

## Code Examples

Verified patterns from the official libadwaita 1.5 documentation. All examples are skeletons; planner expands.

### Single-instance app + `do_activate`
See Pattern 1 above. Source: [GtkApplication docs](https://docs.gtk.org/gtk4/class.Application.html); [Adw.Application docs](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Application.html).

### `Adw.ToolbarView` 3-region window
See Pattern 2 above. Source: [class.ToolbarView](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.ToolbarView.html).

### `Adw.StatusPage` with vertical Box of action buttons
See Pattern 4 above. Source: [class.StatusPage](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.StatusPage.html).

### `Adw.Banner` (post-Landmine-#1 fallback)
See Pattern 3 above. Source: [class.Banner](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Banner.html).

### `Adw.Toast` with action button
```python
toast = Adw.Toast.new("power-profiles-daemon disabled.")
toast.set_timeout(5)  # default; explicit for clarity
toast.set_priority(Adw.ToastPriority.NORMAL)
self._toast_overlay.add_toast(toast)
```
Source: [class.Toast](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Toast.html).

### `Adw.AboutDialog` + `set_debug_info` for the Diagnostics carve-out
See Pattern 6 above. Source: [class.AboutDialog](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.AboutDialog.html).

### `Adw.HeaderBar` primary menu (Landmine #1 fallback target for "About PPD")

```python
def _build_primary_menu(self) -> Gio.Menu:
    menu = Gio.Menu()
    menu.append("About power-profiles-daemon", "win.about-ppd")
    menu.append("About AcerControl", "win.about")

    # Wire the actions to the window
    self.add_action(self._make_action("about-ppd", lambda *_: show_ppd_explainer(self)))
    self.add_action(self._make_action("about", lambda *_: show_about(self)))
    return menu
```

Source: [GMenu/GAction patterns are standard GLib/Gio](https://docs.gtk.org/gio/class.MenuModel.html); the `Adw.HeaderBar`'s `pack_end(Gtk.MenuButton(menu_model=..., primary=True))` is the canonical primary-menu placement.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Adw.AboutWindow` | `Adw.AboutDialog` | libadwaita 1.5 | Use `Adw.AboutDialog`; Phase 3 ships on Noble (Adwaita 1.5.x) so the new API is available. |
| `Adw.MessageDialog` | `Adw.AlertDialog` | libadwaita 1.5 | Phase 3 doesn't use either, but flag for Phase 4+ (revert-on-mismatch confirmations may want AlertDialog). |
| `Adw.AppNotification` / `.app-notification` style class | `Adw.Toast` + `Adw.ToastOverlay` | libadwaita 1.0 | Already locked in CLAUDE.md decision #4. |
| `Gtk.StatusIcon` | (none in GTK4 — defer tray to Phase 7 separate process) | GTK4 release | Already locked in CLAUDE.md decision #2. |
| `Gio.ApplicationFlags.FLAGS_NONE` | `Gio.ApplicationFlags.DEFAULT_FLAGS` | GLib 2.74 (2022-09) | Use `DEFAULT_FLAGS`; `FLAGS_NONE` will be removed in GLib 3.0. |
| `gtk_show_uri()` (default GtkLabel link handler in GTK3) | `gtk_file_launcher_launch()` (GTK4) | GTK4 release | Documented for awareness — relevant to Landmine #1 because it's what the banner's internal label invokes. |

**Deprecated/outdated (relevant to Phase 3):**
- `Adw.AboutWindow` — replaced by `Adw.AboutDialog`. Don't import it.
- `Adw.AppNotification` — replaced by `Adw.Toast`. Don't reach for it.
- `Gio.ApplicationFlags.FLAGS_NONE` — replaced by `DEFAULT_FLAGS`. Same value (0), different name.
- `Gtk.MessageDialog` (GTK4 has it; deprecated for libadwaita apps) — use `Adw.AlertDialog`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `subprocess.run` blocking inside the GTK signal handler is acceptable for sub-2s privileged actions | Pattern 5, Alternatives table | If Adwaita upstream has explicit guidance against synchronous subprocess from signal handlers (none found in the docs reviewed), switching to `Gio.Subprocess.communicate_async` is a per-handler refactor — not a re-architecture. Low blast radius. |
| A2 | The Phase 1 `01-VERIFICATION.md` baseline does not assert specific severity strings on `acer-hwmon`, `coretemp`, `blacklist` checks | Landmine #2 | If it does, the Phase 1 patch in Landmine #2 will fail re-verification and the planner needs to coordinate the verification update. Read `01-VERIFICATION.md` during planning. |
| A3 | Devs who ran `pip install -e .` after Phase 2 need to re-run after Phase 3's `pyproject.toml` edit | Landmine #4 | Per pip docs, editable installs DO pick up `pyproject.toml` `[project.scripts]` changes on next import — but the console-script entry-point shim in `~/.local/bin/` is created at install time and does not auto-regenerate. Re-install is the safe recommendation. |
| A4 | `Adw.HeaderBar` primary menu (Landmine #1 fallback) uses `Gtk.MenuButton(primary=True)` packed via `pack_end` | Pattern 2, Code Examples | The `primary=True` flag on `GtkMenuButton` is the canonical GNOME HIG pattern; verified across libadwaita example apps but not formally cited from a single docs URL. |
| A5 | The polkit policy file is hot-reloaded after overwrite (no daemon restart needed for new actions to be enumerable) | Runtime State Inventory | If polkit caches the file content for any non-trivial duration, manual `systemctl restart polkit` or `pkill -HUP polkit` may be needed. Phase 8 packaging path may need to handle this — but for dev-mode `sudo cp`, polkit's filesystem watch generally picks up changes immediately. |

**If this list is empty** would mean every claim was verified — but assumptions A1, A4, A5 are based on idiomatic Adwaita knowledge that wasn't found in a single explicit primary source citation. They are well-grounded but not formally cited; flagging them honors the research-discipline contract.

## Open Questions

1. **Does the Phase 1 `01-VERIFICATION.md` baseline assert specific severity strings for `acer-hwmon` / `coretemp` / `blacklist` checks?**
   - What we know: assumption A2 says "probably no" based on the verification-text style established in earlier phases.
   - What's unclear: whether the planner needs to coordinate a Phase 1 verification update alongside the severity patch.
   - Recommendation: planner reads `01-VERIFICATION.md` during Wave 0 plan synthesis; if asserts severity literals, plan extends to update them in lockstep.

2. **Does polkit hot-reload reliably pick up new `<action>` blocks in an existing policy file, or does some configuration require a polkit daemon restart?**
   - What we know: polkit watches `/usr/share/polkit-1/actions/` for changes; the Phase 2 install path already uses this directory.
   - What's unclear: whether amending an existing file (vs. adding a new file) triggers the watch reliably across all polkit versions on Noble.
   - Recommendation: dev-mode plan step "Verify both new action IDs are enumerated by `pkaction --action-id org.acercontrol.disable-ppd` and `pkaction --action-id org.acercontrol.reload-acer-wmi`" — if missing, fall back to `sudo systemctl restart polkit`. Document this in the README dev section.

3. **Should the `acercontrol-reload-acer-wmi` wrapper accept a literal `reload` argv token or be argv-less?**
   - What we know: CONTEXT decision #2 says "planner picks."
   - What's unclear: which is more idiomatic.
   - Recommendation: argv-less. Wrapper takes `argv == [exe_name]` only; `EX_USAGE=64` for any extra arg. Symmetric with `acercontrol-setprofile <kernel-value>` which is "exactly one positional"; making this one argv-less is fine because there's only one possible invocation. Saves one allowlist entry's worth of validation code.

4. **Phase 6 forward-compat — does the `acer-performance.service` `Conflicts=power-profiles-daemon.service` (Phase 6 BOOT-01) eliminate the need for the `acercontrol-disable-ppd` wrapper, or do they coexist?**
   - What we know: CONTEXT.md "Learn more" copy already documents that Phase 6's `Conflicts=` directive will make this automatic.
   - What's unclear: nothing — both can coexist. The user-facing "Disable PPD" button is a one-shot fix-it for users who haven't yet enabled `acer-performance.service`. Once Phase 6 ships and the boot service is enabled, the conflict directive does the masking automatically; the Phase 3 button becomes a no-op (because `is-enabled` returns `masked` already, the wrapper exits 0 idempotently per Landmine #3).
   - Recommendation: no Phase 3 plan changes needed; "Learn more" copy already covers this for the user.

5. **Should the smoke test on macOS try to import `acercontrol.gui` and assert ImportError, or just skip GUI tests entirely?**
   - What we know: Landmine #5 documents the assertion pattern.
   - What's unclear: whether the `tools/smoke_phase3.py` runner is genuinely cross-platform OR Linux-only-with-skip.
   - Recommendation: cross-platform with the assertion. The `import acercontrol.gui_*` test is the regression guard for "don't accidentally make `gui*.py` import-clean on macOS." Document via skipif markers when smoke is `pytest`-shaped, or via early `if sys.platform == "darwin": expect ImportError; else: skip` when smoke is a plain Python script.

## Environment Availability

| Dependency | Required By | Available on dev macOS | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `python3-gi` (PyGObject) | All `gui*.py` modules | ✗ (typically) | — | Smoke asserts ImportError; live GUI testing is hardware UAT on PHN16-72 (Linux) only |
| `gir1.2-gtk-4.0` | `gi.require_version("Gtk", "4.0")` | ✗ (typically) | — | Same as above |
| `gir1.2-adw-1` | `gi.require_version("Adw", "1")` | ✗ (typically) | — | Same as above |
| `pkexec` | `privilege.run_privileged()` (Linux only) | ✗ (macOS uses `osascript`/`security`) | — | Phase 2's `pick_elevation()` returns `"sudo"` if `pkexec` missing; live test on PHN16-72 |
| `systemctl` | `acercontrol-disable-ppd` wrapper | ✗ (macOS has launchd) | — | Wrapper smoke runs in argv-rejection mode only on macOS |
| `modprobe` | `acercontrol-reload-acer-wmi` wrapper | ✗ (macOS has kextload) | — | Same as above |

**Missing dependencies with no fallback:** None blocking Phase 3 development. All live-GUI work requires PHN16-72 UAT regardless.

**Missing dependencies with fallback:** All — the macOS dev box can author GUI code (modules are syntactically valid Python without the GTK runtime), the bundler verification stays green (it doesn't import the GUI modules), and the smoke test asserts the expected ImportError pattern.

## Validation Architecture

Phase 3 ships GUI plumbing that's only fully exercisable on PHN16-72 + Linux + GTK4. The Validation Architecture follows the Nyquist principle: per-task commit runs the cheap-to-run guards in CI on macOS; per-wave merge runs the wider regression suite on Linux when available; phase gate requires hardware UAT on PHN16-72.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Plain Python smoke runner (`tools/smoke_phase3.py`); follows the established Phase 1/2 pattern (`tools/smoke_phase1.py`, `tools/smoke_phase2.py`). No pytest dep — keeps the project's "no pip-only deps" constraint intact. |
| Config file | None (single-file runner) |
| Quick run command | `python3 tools/smoke_phase3.py --quick` (XML well-formed + wrapper argv rejection + ImportError assertion + bundler regression) |
| Full suite command | `python3 tools/smoke_phase3.py` (all of `--quick` plus pkaction enumeration + features.py severity assertion + dev-install entry-point check) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GUI-01 | `Adw.Application(application_id="org.acercontrol.AcerControl")` and `Adw.ApplicationWindow` + `Adw.ToolbarView` + `Adw.HeaderBar` are constructed | unit (Linux only) | `python3 -c "from acercontrol.gui import AcerControlApp; assert AcerControlApp().get_application_id() == 'org.acercontrol.AcerControl'"` (Linux); manual UAT on PHN16-72 (window structure) | ❌ Wave 0 — `tools/smoke_phase3.py` |
| GUI-02 | Second launch of `acercontrol-gui` focuses existing window instead of opening a duplicate | manual-only (requires display + dbus session) | UAT step on PHN16-72: launch twice, observe one window | ❌ — UAT checklist in `03-VALIDATION.md` |
| GUI-03 | `features.probe()` runs first on `do_activate`; failed checks route to `Adw.StatusPage` (blockers) or `Adw.Banner` (warnings) per the routing table | unit + manual | unit: severity-routing test (asserts each `(probe-key, severity)` lands on the correct surface — uses a mocked `FeatureReport`); manual: PHN16-72 with each probe artificially failed (rename `/sys/firmware/acpi/platform_profile`, `modprobe -r acer_wmi`, `systemctl unmask power-profiles-daemon`) | ❌ Wave 0 — `tools/smoke_phase3.py` for unit; `03-VALIDATION.md` for manual |
| GUI-04 | PPD active surfaces as persistent `Adw.Banner` with `[Disable PPD]` button + HeaderBar primary-menu "About power-profiles-daemon" entry (Landmine #1 fallback) | unit + manual | unit: assert `gui_banner.build_ppd_banner` returns an `Adw.Banner` with `button-label == "Disable PPD"` and no `use-markup`; manual: PHN16-72 with PPD running, click button, verify polkit dialog reads "Authentication is required to disable power-profiles-daemon" | ❌ Wave 0 — `tools/smoke_phase3.py` for unit |
| GUI-08 | UI never renders raw kernel profile values outside About → Diagnostics | grep gate | `! grep -nE '"(low-power\|balanced-performance\|performance)"' acercontrol/gui.py acercontrol/gui_window.py acercontrol/gui_status_pages.py acercontrol/gui_banner.py` (allowlist `gui_about.py`) | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (regression) PRIV-01..05, CLI-01..07, CORE-01..06 | Phase 1/2 contracts unchanged | full suite | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py` | ✅ exists |
| (new wrapper) `acercontrol-disable-ppd` argv rejection | Wrapper rejects `start` / non-PPD service / no argv with EX_USAGE=64 | unit (cross-platform) | `bash -c './libexec/acercontrol-disable-ppd start power-profiles-daemon.service; [[ $? == 64 ]]'` and 3 sibling cases | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (new wrapper) `acercontrol-reload-acer-wmi` argv rejection | Wrapper rejects any extra argv with EX_USAGE=64 | unit (cross-platform) | `bash -c './libexec/acercontrol-reload-acer-wmi unexpected; [[ $? == 64 ]]'` | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (new wrapper) `acercontrol-disable-ppd` idempotency | `mask` twice → exit 0 both times (Landmine #3) | manual (Linux + root or sudo) | UAT step on PHN16-72; document in `03-VALIDATION.md` | ❌ — UAT checklist |
| (regression) `tools/verify_no_gtk.py` on bundler input list | Bundler input list (Phase 2 lock) stays GTK-free | gate | `python3 tools/verify_no_gtk.py acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` | ✅ exists |
| (regression) `tools/verify_no_gtk.py` on bundled output | `dist/acercontrol` stays GTK-free | gate | `python3 tools/bundle_cli.py && python3 tools/verify_no_gtk.py dist/acercontrol` | ✅ exists |
| (sanity) `verify_no_gtk` reports `gui*.py` as gtk-tainted | Sanity check — proves the gate works | gate (cross-platform) | `python3 tools/verify_no_gtk.py acercontrol/gui.py; [[ $? != 0 ]]` | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (Landmine #2) features.py severity values match Phase 3 routing | After the Phase 1 patch, severity for `acer hwmon (fan+temp)` is `blocking`, `coretemp hwmon` is `warning`, `acer_wmi not blacklisted` is `warning` (when found) | unit (cross-platform — features.py is stdlib only) | `python3 -c "from acercontrol.features import probe; r = probe(); ..."` (asserts on a synthesized check map) | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (Landmine #4) `acercontrol-gui` console-script entry registered | After `pip install -e .`, the entry-point exists | gate (cross-platform) | `python3 -c "import importlib.metadata as m; eps = {ep.name for ep in m.entry_points(group='console_scripts')}; assert 'acercontrol-gui' in eps"` | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (Landmine #5) GUI module imports fail cleanly without `gi` | `import acercontrol.gui*` raises `ImportError` or `ValueError`, never another exception type | gate (macOS + CI) | See Landmine #5 sketch | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (Landmine #6) `verify_no_gtk` invocation list is correct | Bundler input list excludes `gui*.py`; verify_no_gtk runs against the right files | gate (cross-platform) | Inspection of `tools/bundle_cli.py` — assert no `gui_*` substring in the input file enumeration | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (regression) Polkit policy XML well-formed | After append, `xmllint --noout data/org.acercontrol.policy` exits 0; 5 `<action>` blocks present | gate (cross-platform; needs `libxml2-utils` or stdlib `xml.etree.ElementTree`) | `python3 -c "import xml.etree.ElementTree as ET; t = ET.parse('data/org.acercontrol.policy'); assert len(t.getroot().findall('action')) == 5"` | ❌ Wave 0 — `tools/smoke_phase3.py` |
| (UAT) Polkit dialog text on PPD disable | Reads "Authentication is required to disable power-profiles-daemon" — NOT "Authentication is needed to run /usr/sbin/systemctl" | manual (Linux + GUI session) | UAT on PHN16-72 | ❌ — UAT checklist |
| (UAT) Polkit dialog text on module reload | Reads "Authentication is required to reload the acer_wmi kernel module" | manual | UAT on PHN16-72 | ❌ — UAT checklist |
| (UAT) Banner Pango link click does NOT silently invoke an external URI handler | Banner has no Pango link in title (Landmine #1 fallback applied) | manual | UAT on PHN16-72: banner title is plain text; "About PPD" reachable via HeaderBar primary menu | ❌ — UAT checklist |

### Sampling Rate
- **Per task commit:** `python3 tools/smoke_phase3.py --quick` — runs in <2s on macOS or Linux; covers polkit XML well-formedness, wrapper argv rejection (cross-platform — `EX_USAGE=64` is determined before any sysfs access), bundler-input GTK-free regression, ImportError/ValueError pattern, and the GUI-08 grep gate. Gates the per-task commit on macOS where the GTK stack isn't installed.
- **Per wave merge:** `python3 tools/smoke_phase3.py` — adds severity-mapping assertion (post-Phase-1-patch), entry-point registration check, and (when on Linux) a no-display dry-run construction of `AcerControlApp` to verify application-id wiring.
- **Phase gate (`/gsd-verify-work`):** Full suite green + manual UAT checklist on PHN16-72 (window structure, single-instance behavior, each blocker StatusPage triggered by an artificially-broken probe, PPD banner appears + button works + Learn-more menu entry opens the explainer dialog, polkit dialog text strings).

### Wave 0 Gaps
- [ ] `tools/smoke_phase3.py` — covers GUI-01..04, GUI-08, both new wrappers, regression gates, and the 5 in-this-doc landmines (#2 severity assertion, #4 entry-point check, #5 ImportError pattern, #6 bundler-input list inspection, polkit XML well-formedness)
- [ ] Severity patch in `acercontrol/features.py` (Landmine #2) — three lines edited; coordinated with Phase 1 verification re-run
- [ ] `gui_*.py` files (5 new modules)
- [ ] `libexec/acercontrol-disable-ppd` and `libexec/acercontrol-reload-acer-wmi` (2 new wrappers)
- [ ] `data/org.acercontrol.policy` extended with 2 new `<action>` blocks
- [ ] `pyproject.toml` — uncomment the existing `acercontrol-gui = "acercontrol.gui:main"` line
- [ ] `acercontrol/privilege.py` — extend `WRAPPER_NAMES` tuple to include the 2 new wrappers (one-line edit)
- [ ] `acercontrol/__init__.py` — no change needed; gui modules are imported by entry-point shim, not from package top
- [ ] No new test framework install needed — plain Python smoke runner pattern continues from Phase 1/2

## Security Domain

> Required because `security_enforcement` defaults to enabled (no explicit `false` in `.planning/config.json`).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | polkit `pkexec` (delegated to OS); `auth_admin_keep` chains within session |
| V3 Session Management | no | No app-level sessions; OS session is the boundary |
| V4 Access Control | yes | polkit `.policy` actions tied to specific wrapper paths via `org.freedesktop.policykit.exec.path` annotation; defense-in-depth argv allowlist inside each wrapper |
| V5 Input Validation | yes | Wrappers re-validate argv against literal allowlists (`ALLOWED_ACTIONS`, `ALLOWED_SERVICES`); CLI also validates upstream for UX, but the wrapper is the trust boundary |
| V6 Cryptography | no | No cryptographic operations |

### Known Threat Patterns for libadwaita app + pkexec wrappers on Linux

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Local privilege escalation via pkexec'd shell injection | E (Elevation) | Phase 2 lock — wrappers are real-binary, NOT `pkexec bash -c`; `org.freedesktop.policykit.exec.path` pins each polkit action to a specific binary path |
| Argv injection from another local app gaining the polkit action | T (Tampering), E | Wrapper-level allowlist re-validation; another local app pkexec-ing our wrapper directly cannot escape the allowlist |
| Environment variable injection (LD_PRELOAD, PYTHONPATH) | T, E | pkexec scrubs the environment — wrappers are stdlib-only and don't import `acercontrol.*` (no PYTHONPATH dependency) |
| TOCTOU on sysfs path | T | platform_profile path is owned by `root:root` mode 0644; only the wrapper writes; no time-of-check-to-time-of-use window because we don't `stat` then `open` |
| systemctl mask command injection via service argument | T | `ALLOWED_SERVICES = ("power-profiles-daemon.service",)` literal allowlist; argv is positional, no `--` flag injection possible |
| Polkit policy file tampering | T (system level) | Policy file ships from `.deb` with `mode 0644 root:root`; modifications outside the package are detected by `dpkg --verify` |
| GTK signal handler crashes leaking stack traces | I (Information disclosure) | Wrap remediation handlers in try/except; surface "Operation failed" toast; log full trace via `GLib.log` (journal) — never to user-visible UI |

### Phase 3 specific notes

- The new `acercontrol-disable-ppd` wrapper's allowlist (`mask`/`unmask` × `power-profiles-daemon.service`) is intentionally narrower than its polkit action's `exec.path` annotation could permit. Even if a hypothetical `org.acercontrol.disable-ppd` action holder ran the wrapper directly, they couldn't mask arbitrary services.
- The new `acercontrol-reload-acer-wmi` wrapper accepts no argv (or `reload` literal — Open Question 3). Hardcoded module name + `predator_v4=1`. Cannot be coerced into loading arbitrary kernel modules.
- The polkit action messages are HUMAN-READABLE and action-specific — same lesson as PRIV-03; if generic `org.freedesktop.policykit.exec` text leaks ("Authentication is required to run /usr/sbin/modprobe"), the planner has misconfigured the action ID or `exec.path` annotation.
- Phase 3 is the FIRST phase to invoke `pkexec` from a GTK process. Confirm during PHN16-72 UAT that the polkit auth dialog appears as a focused modal (not behind the AcerControl window) — GNOME's polkit agent should handle this correctly, but a sanity check is cheap.

## Sources

### Primary (HIGH confidence — fetched this session)

- [`Adw.Banner` API reference (1-latest)](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Banner.html) — properties (title, button-label, revealed, use-markup, button-style), single signal `button-clicked`, no `activate-link`. Cross-checked against [main branch](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/main/class.Banner.html) — same conclusion. **Load-bearing for Landmine #1.**
- [`adw-banner.c` source (libadwaita 1.5.4)](https://gitlab.gnome.org/GNOME/libadwaita/-/raw/1.5.4/src/adw-banner.c) — confirms internal GtkLabel is template-private with no public accessor.
- [`Adw.ApplicationWindow` and `Adw.Application` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Application.html) — `adw_init()` in default startup, recommended over manual `Gtk.Application` + `Adw.init()`.
- [`Adw.ToolbarView` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.ToolbarView.html) — `add_top_bar`, `add_bottom_bar`, `set_content` 3-region pattern.
- [`Adw.StatusPage` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.StatusPage.html) — properties + `set_child` accepts any GtkWidget; description supports Pango markup natively.
- [`Adw.AboutDialog` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.AboutDialog.html) — confirms `set_debug_info()` slot for the Diagnostics carve-out; `present(parent)` since 1.5.
- [`Adw.AlertDialog` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.AlertDialog.html) — for Phase 4 awareness; not used in Phase 3.
- [`Adw.Toast` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.Toast.html) — properties (timeout=5s default, priority NORMAL/HIGH, button-label, action-name, use-markup), constructor `Adw.Toast.new("title")`.
- [`Adw.ToastOverlay` API](https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.ToastOverlay.html) — single child via `set_child`; toasts via `add_toast`.
- [`GtkLabel::activate-link` signal docs](https://docs.gtk.org/gtk4/signal.Label.activate-link.html) — default handler calls `gtk_file_launcher_launch()`. **Load-bearing for Landmine #1.**
- [`Gtk.Application` docs](https://docs.gtk.org/gtk4/class.Application.html) — `gtk_application_get_active_window` + `gtk_window_present` is the canonical single-instance pattern; quoted example from upstream.
- [`Gio.ApplicationFlags` enum](https://docs.gtk.org/gio/flags.ApplicationFlags.html) — `DEFAULT_FLAGS` since 2.74; `FLAGS_NONE` since 2.28; same value 0.
- [Context7 `/gnome/libadwaita`](https://context7.com/gnome/libadwaita) — toast examples, alert dialog patterns, header bar construction.

### Secondary (MEDIUM confidence — single-source)

- [vmagnin/gtk-fortran#267 — "G_APPLICATION_FLAGS_NONE is deprecated in GLib 2.74"](https://github.com/vmagnin/gtk-fortran/issues/267) — corroborates the deprecation; will be removed in GLib 3.0. Verified via WebSearch result text.
- systemctl(1) man page on `mask`/`unmask`/`mask --now` semantics — fetched from man7.org via WebFetch (one source). Cross-checked against the wording in Landmine #3.

### Tertiary (LOW confidence — not used as load-bearing)

- None. All Landmines and Patterns are backed by HIGH or MEDIUM sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every API call verified against gnome.pages.gitlab.gnome.org (libadwaita 1-latest); deprecations cross-checked with GitHub issues / man pages.
- Architecture: HIGH — Patterns 1–6 are skeleton-level, follow upstream-documented call signatures, and align with CONTEXT.md + UI-SPEC locks.
- Pitfalls: HIGH — Landmines #1 (banner activate-link), #2 (severity routing), #3 (mask idempotency) are sourced from primary docs / actual file inspection / man-page text. Landmines #4–#7 are derived from project conventions and pip/pyproject.toml semantics.
- Validation Architecture: HIGH for the structure; MEDIUM for the per-test command list (commands not yet executed because `tools/smoke_phase3.py` doesn't exist — Wave 0 builds it).
- Security Domain: HIGH for the threat patterns (carry-forward from Phase 2 threat model); MEDIUM for the Phase 3 specific notes (UAT pending).

**Research date:** 2026-05-16
**Valid until:** 2026-06-15 (libadwaita 1.5 is on Noble's frozen repo for the LTS lifecycle; the only freshness risk is upstream main-branch changes that don't affect Noble's shipped 1.5.x).
