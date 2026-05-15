# Phase 3: GUI Shell + Failure States + PPD Banner — Context

**Gathered:** 2026-05-16
**Status:** Ready for research and planning
**Source:** `/gsd-discuss-phase 3` (6 gray areas, all defaults accepted)

<domain>
## Phase Boundary

Stand up the **GTK4 + libadwaita GUI shell** wired to single-instance via the application ID `org.acercontrol.AcerControl`. On `do_activate`, `features.probe()` runs FIRST. Failed probes route to dedicated `Adw.StatusPage` screens with copy-able fix-it text and (where possible) one-click remediation buttons that invoke new privileged wrappers via `pkexec`. `power-profiles-daemon` (PPD) active surfaces as a persistent `Adw.Banner` with `[Disable PPD]` / `[Learn more]`.

**In scope (5 requirements):** GUI-01, GUI-02, GUI-03, GUI-04, GUI-08.

**Out of scope (deferred to later phases):**
- Five profile buttons (eco/quiet/balanced/performance/turbo), highlight, click-to-switch flow — Phase 4
- Read-back verification + revert-on-mismatch warning toast — Phase 4
- Live sensor refresh (`GLib.timeout_add_seconds(2, …)`), color-coded thermal bars — Phase 5
- Critical-temp notifications via `Gio.Notification` — Phase 5
- Boot service panel, `acer-performance.service` install/template — Phase 6
- System tray indicator (`gir1.2-ayatanaappindicator3-0.1` separate GTK3 process) — Phase 7
- App icon (color + symbolic SVGs, `hicolor` install, `gtk-update-icon-cache`) — Phase 8
- `.desktop` file install — Phase 8
- Hardware Predator-key binding to profile cycle — future phase per PROJECT.md addition (2026-05-15)

</domain>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before acting.**

### Project-wide
- `./CLAUDE.md` — Project instructions (GTK4/Adwaita stack, polkit policy XML pattern, **decisions #1, #2, #3, #4, #5, #9**, GUI window-layout sketch, error-states table)
- `.planning/PROJECT.md` — Core value, constraints, "what NOT to use" table (especially `Gtk.StatusIcon`, deprecated `Adw.AppNotification`, raw `Notify`), Hardware integration & UX revisions section (added 2026-05-15)
- `.planning/REQUIREMENTS.md` — Authoritative GUI-01..04 + GUI-08 definitions
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria (4 explicit checks), pitfall mitigations (P2 PPD detection, P9 Adwaita window classes + `.desktop` basename match, P13 probe-first surfacing)

### Phase 1–2 carry-forward (consumed unchanged)
- `acercontrol/profiles.py` — `PROFILES`, `KERNEL_TO_UI`, `Profile` enum, `kernel_to_profile()`. **GUI-08 enforcement layer — UI labels MUST go through these.**
- `acercontrol/features.py` — `probe()` returning `FeatureReport` with `.checks`, `.ok`, `.first_blocking_failure`. **GUI-03 input — single source of truth for failure routing.**
- `acercontrol/core.py` — `read_profile()`, `read_sensors()`, `PROFILE_PATH`, `PROFILE_CHOICES_PATH` (sensors not consumed in Phase 3 but the import path is)
- `acercontrol/sysfs.py` — `find_hwmon` (used inside `features.probe()`)
- `acercontrol/privilege.py` — `pick_elevation()`, `resolve_wrapper()`, `run_privileged()`, `PrivilegedResult` (cancelled flag for pkexec exit 126). **Phase 3 reuses this for the new wrappers' invocation paths from the GUI; do NOT reimplement elevation.**
- `acercontrol/cli.py` — pattern reference for argparse + `_emit()` JSON output (GUI About → Diagnostics may reuse `--json` shape)
- `data/org.acercontrol.policy` — existing 3 polkit actions; Phase 3 EXTENDS this file (does not create a new one) with 2 new actions (#1 + #2 below)
- `libexec/acercontrol-{setprofile,set-boot-profile,manage-service}` — pattern reference for new wrappers (absolute `#!/usr/bin/python3` shebang, hardcoded allowlist tuple, sysexits codes 0/64/71/77, no `acercontrol.*` imports — pkexec scrubs PYTHONPATH)
- `.planning/phases/01-foundation/01-VERIFICATION.md` — `Profile.CUSTOM` sentinel pattern
- `.planning/phases/02-privilege-boundary-cli/02-CONTEXT.md` — wrapper input-validation policy + `_WRAPPER_DIRS` resolution order (`/usr/libexec/acercontrol/` → `/usr/local/libexec/acercontrol/` → `$ACERCONTROL_DEV/libexec/`)
- `.planning/phases/02-privilege-boundary-cli/02-VERIFICATION.md` — privilege boundary verification baseline (regression check)
- `.planning/phases/02-privilege-boundary-cli/02-REVIEW.md` — WR-01 (polkit `exec.path` only covers `/usr/libexec/acercontrol/`) and WR-03 (manage-service exit-code collapsing) — Phase 3 may surface WR-03 if the GUI distinguishes "no such unit" from "operation failed" when invoking systemd

### External specs (read for accuracy, do not paraphrase from memory)
- libadwaita 1.5 docs — `Adw.Application`, `Adw.ApplicationWindow`, `Adw.ToolbarView`, `Adw.HeaderBar`, `Adw.StatusPage`, `Adw.Banner`, `Adw.AboutDialog` (Adw.AlertDialog only on 1.4+, fine on Noble)
- GNOME HIG — application-ID-must-match-`.desktop`-basename rule (relevant for Phase 5 `Gio.Notification` but Phase 3 must register the right ID NOW)
- freedesktop polkit `.policy` DTD — extending an existing `<policyconfig>` with new `<action>` blocks
- systemd `pkexec(1)` man page — exit code 126 (auth cancelled), 127 (command not found)
- `power-profiles-daemon` man page — `systemctl mask --now` semantics (mask creates symlink to `/dev/null`; unmask requires inverse)

</canonical_refs>

<decisions>
## Implementation Decisions (this discussion)

### 1. PPD disable mechanism → **New dedicated wrapper `acercontrol-disable-ppd`**

Phase 3 ships a 4th `libexec/` wrapper at `libexec/acercontrol-disable-ppd` with a single hardcoded allowlist:

```python
ALLOWED_ACTIONS = ("mask", "unmask")
ALLOWED_SERVICES = ("power-profiles-daemon.service",)
```

Adds a 4th polkit action `org.acercontrol.disable-ppd` to `data/org.acercontrol.policy` (extend the existing file, do NOT create a new one) with:
- `<message>Authentication is required to disable power-profiles-daemon</message>`
- `<annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-disable-ppd</annotate>`
- `<allow_active>auth_admin_keep</allow_active>`, `<allow_any>auth_admin</allow_any>`, `<allow_inactive>auth_admin</allow_inactive>`

**Why:** Phase 2's `manage-service` wrapper allowlist is deliberately tight (`acer-performance.service` only). Bolting `mask`/`unmask` actions + a system-level service onto it muddies a clean security contract. A single-purpose wrapper keeps each polkit action narrow and named — auth dialog reads the human-readable message instead of generic `systemctl` text. ~70 LOC, same polkit/wrapper discipline as Phase 2.

**Test scenarios** (planner formalizes in 03-VALIDATION.md):
- `acercontrol-disable-ppd mask power-profiles-daemon.service` → exit 0 on success, EX_OSERR=71 on systemctl failure (preserve underlying rc — see WR-03 carry-forward note below)
- `acercontrol-disable-ppd start power-profiles-daemon.service` → EX_USAGE=64 (action not in allowlist)
- `acercontrol-disable-ppd mask other.service` → EX_USAGE=64 (service not in allowlist)
- `acercontrol-disable-ppd` (no argv) → EX_USAGE=64

### 2. `acer_wmi` module reload helper → **New dedicated wrapper `acercontrol-reload-acer-wmi`**

Phase 3 ships a 5th `libexec/` wrapper at `libexec/acercontrol-reload-acer-wmi` that runs:

```python
subprocess.run(["/usr/sbin/modprobe", "-r", "acer_wmi"], check=True, timeout=20)
subprocess.run(["/usr/sbin/modprobe", "acer_wmi", "predator_v4=1"], check=True, timeout=20)
```

The wrapper takes NO argv (or accepts a literal `reload` token for symmetry — planner picks). It refuses any other invocation (EX_USAGE=64). Hardcoded module name, hardcoded `predator_v4=1`. Absolute `/usr/sbin/modprobe` path (pkexec env scrub).

Adds a 5th polkit action `org.acercontrol.reload-acer-wmi` to `data/org.acercontrol.policy` with:
- `<message>Authentication is required to reload the acer_wmi kernel module</message>`
- `<annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-reload-acer-wmi</annotate>`
- `auth_admin_keep` on `<allow_active>`, bare `auth_admin` on the others

**Why:** GUI-03 promises one-click remediation. Phase 2 has no wrapper for module reload. Single-purpose wrapper keeps the polkit action narrow + named. Inline `pkexec modprobe …` would show generic text and accept arbitrary modprobe targets. Print-only mode breaks the one-click promise.

**Note for the StatusPage:** if `predator_v4` is currently `Y` (correct value), the StatusPage doesn't need this button — only when `acer_wmi` is unloaded OR `predator_v4=N` does the "Reload module" CTA render. The `platform_profile`-missing case is read-only (kernel-version requirement, not fixable from userspace) — that StatusPage offers no button.

### 3. StatusPage routing strategy → **Severity-ordered hybrid (C)**

`features.probe()`'s `FeatureReport.checks` are partitioned into two severity classes:

| Severity | Conditions | UI surface |
|----------|-----------|------------|
| **Blocker** | `acer_wmi` unloaded OR `predator_v4=N` OR `platform_profile` missing OR no `acer` hwmon found | **Full-window `Adw.StatusPage`** — main view doesn't render until resolved |
| **Warning** | PPD active OR `acer_wmi` blacklist entry detected in `/etc/modprobe.d/*.conf` OR `coretemp` hwmon missing | **Persistent `Adw.Banner`** above main view; main view renders normally |

If multiple blockers exist, render the **first** one (in declared `FeatureReport.checks` order) — fixing it triggers a re-probe via the StatusPage's "Refresh" button (Claude's-discretion item below). User walks the chain one rung at a time. Multiple warnings stack as multiple banners (Adw.Banner is single-row but cycling between them is a Phase 5 concern; for now show the most recent only).

**Why:** Blockers genuinely break the app — full StatusPage forces resolution; no half-functional UI. Warnings (PPD especially) don't break writes per se, they cause silent reverts that the GUI can detect later (Phase 4 read-back) — banner is the right surface, user keeps using the app. Severity-ordered hybrid avoids both pitfalls of flat strategies (linear single-issue mode hides scope; flat all-issues conflates broken with annoying).

### 4. PPD banner dismissibility → **Dismissible-this-session, re-surfaces on revert (B)**

The PPD banner has a close button (`Adw.Banner.use_revealer = true`, `set_revealed(false)` on click). Dismissed banner:

- Stays hidden for the rest of the current GUI session (in-memory flag; no config file)
- **Re-surfaces on next app launch** if PPD is still active (banner == truth on cold start)
- **Re-surfaces immediately** when Phase 4's revert-on-mismatch event fires (i.e., we WROTE turbo, read back balanced — that's news the user dismissed too early)

**Why:** Pure-persistent (A) is paternalistic — user might knowingly tolerate PPD running short-term. Dismissible-forever (C) requires a config file we don't have plumbing for. (B) respects user choice while remaining truthful when we detect actual interference.

**Re-surface API contract for Phase 4:** Phase 3's main window exposes `def show_ppd_banner(force: bool = False)` — Phase 4's mismatch handler calls this with `force=True` to override the in-session-dismissed flag.

### 5. App icon → **Defer to Phase 8 (B)**

Phase 3 ships **no app icon**. The window uses GTK's default fallback icon. No `Icon=` line in any `.desktop` file (Phase 3 doesn't ship a `.desktop` file either — that's also Phase 8).

**Why:** Icon work is its own task — color SVG + symbolic SVG (using `currentColor`), install under `/usr/share/icons/hicolor/scalable/apps/`, `gtk-update-icon-cache` postinst. Phase 3 is plumbing (StatusPages, banner, single-instance, polkit wiring). GTK fallback is fine for development. Phase 8's `dh_icons` runs the cache update automatically. Avoids scope creep.

**Phase 8 ticket:** ship `data/icons/acercontrol.svg` (color) + `data/icons/acercontrol-symbolic.svg` (16×16 viewBox, `currentColor`), install via `debian/acercontrol.install`, add `Icon=acercontrol` to `.desktop`.

### 6. GUI launch path → **`[project.scripts]` entry `acercontrol-gui = "acercontrol.gui:main"` (A)**

Append to `pyproject.toml`'s existing `[project.scripts]` section (Phase 2 added the section with `acercontrol = "acercontrol.cli:main"`):

```toml
[project.scripts]
acercontrol = "acercontrol.cli:main"
acercontrol-gui = "acercontrol.gui:main"
```

After `pip install -e .`, `acercontrol-gui` is on PATH at `~/.local/bin/acercontrol-gui` (or `/usr/local/bin/acercontrol-gui` for system install). The `.desktop` file (Phase 8) will use `Exec=acercontrol-gui` matching this name.

**Why:** Symmetry with Phase 2's CLI entry. Devs who `pip install -e .` get the binary on PATH for testing. Phase 8's `.deb` reuses the same script entry — no rework. One-line change to `pyproject.toml`.

</decisions>

<claude_discretion>
## Claude's Discretion (downstream may decide; not asked)

### Window default size
800×600 logical pixels, user-resizable, no minimum-size constraint beyond what Adwaita widgets require. Sensible default for a tool window; not enough product info to optimize further.

### About → Diagnostics page
`Adw.AboutDialog` (libadwaita 1.5 — replaces deprecated `Adw.AboutWindow`). Standard fields: name, version (from `acercontrol.__version__`), license (TBD by user; Phase 8 packaging will need it), website placeholder (none yet — leave blank). Add a "Diagnostics" extra section that shows raw kernel values per **GUI-08 carve-out** — this is the ONE place raw values like `"performance"` may appear in the UI. Render `features.probe()` JSON output verbatim in a `Gtk.TextView` with `monospace` style class; user can copy-paste for bug reports.

### StatusPage "Refresh" button
Every blocker StatusPage gets a footer button "Refresh" that re-runs `features.probe()` and re-evaluates routing. NO auth needed — pure read-only re-check after the user fixed the underlying issue (or pressed the privileged "Reload module" / "Disable PPD" button which already triggered a refresh).

### Banner copy
"power-profiles-daemon is running and will overwrite profile changes" + `[Disable PPD]` + `[Learn more]`. Verbatim per ROADMAP success criterion 3.

### "Learn more" target
Opens an in-app `Adw.Window` (modal, parented to main window) titled "About power-profiles-daemon" with explanatory text:
- What PPD is
- Why it conflicts (it ALSO writes `/sys/firmware/acpi/platform_profile`)
- That `mask --now` is reversible (`sudo systemctl unmask power-profiles-daemon` to restore)
- That Phase 6's `acer-performance.service` will declare `Conflicts=power-profiles-daemon.service` so this becomes automatic in v1+

NO external URL — project has no website. Embedded text means no broken links.

### Single-instance behavior
`Adw.Application(application_id="org.acercontrol.AcerControl", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)`. Second launch triggers `do_activate` on the existing instance, which calls `window.present()` to focus. Standard GApplication idiom, no extra code.

### File layout for the GUI
- `acercontrol/gui.py` — entry point with `main()` function, `Adw.Application` subclass, app activation handler
- `acercontrol/gui_window.py` — main `Adw.ApplicationWindow` subclass (toolbar + headerbar + scrollable content area)
- `acercontrol/gui_status_pages.py` — `Adw.StatusPage` factory functions per blocker class (one per `FeatureReport` check name)
- `acercontrol/gui_banner.py` — PPD banner construction + dismissal logic
- `acercontrol/gui_about.py` — About dialog + Diagnostics extension

The bundler (`tools/bundle_cli.py`) MUST NOT bundle these — they import `gi`. The GTK-free contract enforced by `tools/verify_no_gtk.py` is now stricter: `verify_no_gtk` must remain green against `acercontrol/{profiles,sysfs,core,features,privilege,cli}.py` AND the bundled `dist/acercontrol`. New GUI files (`gui*.py`) are EXEMPT from `verify_no_gtk` because they intentionally import `gi`. Planner formalizes the exemption list.

### Subprocess invocation for the new wrappers
The GUI calls `acercontrol.privilege.run_privileged()` for the new `disable-ppd` and `reload-acer-wmi` wrappers — same path the CLI uses for `setprofile`. Returns a `PrivilegedResult` with the `cancelled` flag for Escape-on-dialog handling. GUI shows an `Adw.Toast` "Authentication cancelled." instead of an error.

### `_WRAPPER_DIRS` resolution
The new wrappers go through `acercontrol.privilege.resolve_wrapper()` — already searches `/usr/libexec/acercontrol/` → `/usr/local/libexec/acercontrol/` → `$ACERCONTROL_DEV/libexec/`. No code change to `privilege.py`; just add `acercontrol-disable-ppd` and `acercontrol-reload-acer-wmi` to `_WRAPPER_NAMES`.

### Polkit policy file extension, not replacement
Phase 3 EDITS the existing `data/org.acercontrol.policy` to append 2 new `<action>` blocks. Single source of truth; no second `.policy` file. Install path stays `/usr/share/polkit-1/actions/org.acercontrol.policy`.

### Apt dependencies (development; Phase 8 codifies for `.deb`)
Add to README "How to run the GUI from source": `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`. (CLAUDE.md already enumerates these.) No `pip` deps for the GUI itself.

### Smoke test scope on macOS / CI
`tools/smoke_phase3.py` (planner names) cannot run the actual Adw.Application loop on macOS (no GTK4 there). Phase 3's CI smoke is limited to:
- Polkit policy XML well-formed (extended file still parses, has 5 actions)
- Both new wrappers exit 64 on bad argv (no GTK dependency)
- Bundled `dist/acercontrol` still GTK-free (regression — verify_no_gtk on bundle output)
- `import acercontrol.gui_*` modules raise `ImportError` cleanly when `gi` is unavailable (i.e., they fail import gracefully on dev macOS, not silently load broken stubs)

Live GUI testing is hardware UAT on PHN16-72 only.

</claude_discretion>

<deferred>
## Deferred Ideas (captured here to not lose; not in Phase 3)

- **Drop polkit auth dialog entirely for `setprofile`** (`<allow_active>yes</allow_active>` swap) — captured in PROJECT.md → Hardware integration & UX revisions on 2026-05-15. Belongs in a small Phase 2.1 or rolls into Phase 8 packaging.
- **Hardware Predator/Turbo key → cycle profiles** — captured in PROJECT.md (same date). Needs `evtest` on PHN16-72 to discover the keycode. Belongs in a future phase between Phase 6 and Phase 7.
- **Per-user config file** for "don't show PPD banner again" preference — would unlock dismissibility option (C) for Phase 3 but adds config-storage scope. Defer until any other config persistence emerges (e.g., remembering window size/position, remembering last-used profile).
- **External docs site** for "Learn more" PPD link — defer until project has a website.
- **WR-03 fix from Phase 2 review** — `acercontrol-manage-service` collapses systemctl exits to `EX_OSERR=71`. The new `acercontrol-disable-ppd` wrapper should NOT inherit this — preserve the underlying systemctl returncode (or map systemctl's specific exit codes through to sysexits more carefully). Planner should document this as the lesson applied.

</deferred>

<specifics>
## Specific References & Examples

- **Phase 2's wrapper file pattern** is the gold standard for the 2 new wrappers — match the structure of `libexec/acercontrol-setprofile` exactly:
  - Module-level `ALLOWED_*` literal tuples
  - `def main(argv): ...` with explicit argv validation before any subprocess call
  - `sys.exit(main(sys.argv[1:]))` at module bottom
  - Sysexits: `EX_OK=0`, `EX_USAGE=64`, `EX_OSERR=71`, `EX_NOPERM=77`
- **Phase 2's polkit policy file** (`data/org.acercontrol.policy`) shows the exact `<action>` block structure — copy + adapt for the 2 new actions.
- **Phase 1's `FeatureReport`** structure (in `acercontrol/features.py`) — the GUI reads `report.checks` (ordered list), `report.ok` (any blocker false), `report.first_blocking_failure` (the check to route to). Phase 3 may need to ADD a `severity` field to each `Check` for the routing in decision #3 — coordinate with planner whether this lives in `acercontrol/features.py` or in the GUI as a derived classifier.
- **Adwaita 1.5 widgets to use** (and only these — older versions deprecated):
  - `Adw.ApplicationWindow` (NOT `Adw.Window`)
  - `Adw.ToolbarView` + `Adw.HeaderBar` (replaces old `Gtk.HeaderBar` placement)
  - `Adw.StatusPage` (with `set_icon_name`, `set_title`, `set_description`, `set_child` for the action button)
  - `Adw.Banner` (1.3+, available on Noble — use `set_button_label` and `connect("button-clicked", …)`; for two buttons stack a `Gtk.Box` with `Adw.Banner.set_child` is NOT supported — Adw.Banner has at most ONE button — so for the PPD banner: `[Disable PPD]` is the banner button, `[Learn more]` is a clickable label/link in the banner title text via Pango markup `<a href="…">`. Or use `Adw.AlertDialog` for a two-action prompt. Planner picks the cleanest 1.5-API.)
  - `Adw.AboutDialog` (1.5 — replaces deprecated `Adw.AboutWindow`)
  - `Adw.Toast` + `Adw.ToastOverlay` (for cancelled-auth feedback)
- **Single-instance Python idiom:**
  ```python
  class App(Adw.Application):
      def __init__(self):
          super().__init__(application_id="org.acercontrol.AcerControl",
                           flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
      def do_activate(self):
          win = self.props.active_window or MainWindow(application=self)
          win.present()
  ```

</specifics>

---

*Phase: 03-gui-shell-failure-ppd*
*Context gathered: 2026-05-16 via /gsd-discuss-phase 3*
