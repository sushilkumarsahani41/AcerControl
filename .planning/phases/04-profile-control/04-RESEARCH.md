# Phase 4: Profile Control (core value loop) - Research

**Researched:** 2026-05-22  
**Domain:** GTK4/libadwaita profile-control UI, privileged `platform_profile` writes, read-back state reconciliation  
**Confidence:** HIGH for codebase contracts and UI state machine; MEDIUM for live Linux/PPD timing until PHN16-72 UAT

## User Constraints

No `04-CONTEXT.md` exists in `.planning/phases/04-profile-control`; Phase 4 constraints come from `AGENTS.md`, `ROADMAP.md`, `REQUIREMENTS.md`, the approved `04-UI-SPEC.md`, and Phase 3 carry-forward artifacts. [VERIFIED: codebase grep]

### Locked Scope

- Phase 4 closes the core value loop only: five profile buttons, active highlight, privileged set-profile call, 250 ms read-back, success/cancel/mismatch/failure UI responses. [VERIFIED: `.planning/ROADMAP.md` + `.planning/phases/04-profile-control/04-UI-SPEC.md`]
- Do not add live sensors, tray, boot-service controls, notifications beyond profile-change toasts, icons, desktop packaging, or web/shadcn UI. [VERIFIED: `.planning/phases/04-profile-control/04-UI-SPEC.md`]
- Preserve the Phase 3 shell: `Adw.Application`, `Adw.ApplicationWindow`, `Adw.ToolbarView`, `Adw.HeaderBar`, `Adw.ToastOverlay(Gtk.Stack)`, warning banners, and `MainWindow.show_ppd_banner(force=True)`. [VERIFIED: `acercontrol/gui.py`, `acercontrol/gui_window.py`, `04-UI-SPEC.md`]
- Use `Gtk.Button`, not `Gtk.ToggleButton`, for profile controls; active styling is derived only from read-back state, not click intent. [VERIFIED: `04-UI-SPEC.md`; CITED: https://docs.gtk.org/gtk4/class.Button.html]
- GUI must not render raw kernel profile values such as `low-power`, `balanced-performance`, or kernel `performance`; diagnostics remains the only carve-out. [VERIFIED: `AGENTS.md`, `REQUIREMENTS.md`, `04-UI-SPEC.md`]

### Exact User-Facing Strings

The following strings are locked and should be smoke-grepped in Phase 4. [VERIFIED: `04-UI-SPEC.md`]

- `Performance Profile`
- `Current profile: <profile>`
- `Current profile: Custom`
- `Click a profile to set a known Acer profile.`
- `Awaiting authorisation...`
- `Switched to <profile>`
- `Authorization cancelled`
- `Profile not applied — power-profiles-daemon may be overriding writes`
- `Profile change failed. See terminal for details.`

### Deferred Ideas (OUT OF SCOPE)

- Sensor panel and critical-temperature logic remain Phase 5. [VERIFIED: `.planning/ROADMAP.md`]
- Boot service panel and boot-profile persistence remain Phase 6. [VERIFIED: `.planning/ROADMAP.md`]
- Tray helper remains Phase 7. [VERIFIED: `.planning/ROADMAP.md`]
- Packaging, `.desktop`, app icon, and `.deb` install work remain Phase 8. [VERIFIED: `.planning/ROADMAP.md`]

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUI-05 | Render 5 profile buttons and keep the actual active profile visually highlighted. | Use `Profile`/`PROFILES` from `acercontrol.profiles` and `read_profile()` from `acercontrol.core`; use `Gtk.Button` controls inside a wrapping layout. [VERIFIED: `acercontrol/profiles.py`, `acercontrol/core.py`; CITED: https://docs.gtk.org/gtk4/class.Button.html, https://docs.gtk.org/gtk4/class.FlowBox.html] |
| GUI-06 | Click shows pending auth state, calls pkexec helper, reads back, then updates highlight and success toast only on match. | Use `run_privileged(["acercontrol-setprofile", PROFILES[requested]])`, then schedule a 250 ms `GLib.timeout_add` read-back callback. [VERIFIED: `acercontrol/privilege.py`, `libexec/acercontrol-setprofile`, `04-UI-SPEC.md`; CITED: https://docs.gtk.org/glib/func.timeout_add.html] |
| GUI-07 | Mismatch warns, reverts highlight to actual read-back state, and forces PPD banner visible. | Reuse `MainWindow.show_ppd_banner(force=True)` from Phase 3; mismatch is expected when PPD overwrites direct sysfs writes. [VERIFIED: `acercontrol/gui_window.py`, `04-UI-SPEC.md`, `.planning/research/PITFALLS.md`] |

</phase_requirements>

## Summary

Phase 4 should be implemented as a narrow extension to the Phase 3 main view: create a new `acercontrol/gui_profiles.py` widget/controller and replace `placeholder_ok(self)` in `MainWindow._main_column` with that profile group. The shell, blocker routing, warning banners, header menu, and toast overlay should stay in `gui_window.py`; the new profile module should own only profile-button construction, transient state rendering, read-back reconciliation, and focus/state updates. [VERIFIED: `acercontrol/gui_window.py`; VERIFIED: `04-UI-SPEC.md`]

The core safety rule is non-optimistic rendering: a click may show `Awaiting authorisation...` and disable all profile buttons, but it must not move the active highlight to the requested profile until `read_profile()` returns the requested `Profile`. This preserves GUI truthfulness across polkit cancellation, helper failure, kernel refusal, and PPD reverts. [VERIFIED: `04-UI-SPEC.md`; VERIFIED: `acercontrol/core.py`; CITED: https://polkit.pages.freedesktop.org/polkit/pkexec.1.html]

**Primary recommendation:** Add `gui_profiles.py` with an explicit `ProfileControlPanel` state machine, wire it into `MainWindow` by replacing the Phase 3 placeholder, and add `tools/smoke_phase4.py` to source-check exact strings, `Gtk.Button` usage, `run_privileged` argv shape, no raw kernel labels, button order, and no optimistic highlight assignment. [VERIFIED: codebase grep]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Profile button layout and active styling | Frontend / GTK GUI | Core library read APIs | GTK owns rendering and sensitivity; `read_profile()` owns the actual state. [VERIFIED: `acercontrol/core.py`, `04-UI-SPEC.md`] |
| User-name to kernel-value mapping | Core library | Privileged wrapper allowlist | `PROFILES` maps UI names to kernel values; wrapper re-validates kernel values. [VERIFIED: `acercontrol/profiles.py`, `libexec/acercontrol-setprofile`] |
| Privileged profile write | OS / polkit + libexec wrapper | GUI signal handler | GUI requests one allowed wrapper call; root code validates argv and writes sysfs. [VERIFIED: `acercontrol/privilege.py`, `data/org.acercontrol.policy`, `libexec/acercontrol-setprofile`] |
| Read-back verification | Frontend / GTK main loop | Core library | GUI schedules read-back and reconciles visual state; core reads `/sys/firmware/acpi/platform_profile`. [VERIFIED: `acercontrol/core.py`; CITED: https://docs.gtk.org/glib/func.timeout_add.html] |
| PPD mismatch recovery | Frontend / GTK GUI | Feature probe | Mismatch handler shows toast and calls `show_ppd_banner(force=True)`, which re-probes and rebuilds warning banners. [VERIFIED: `acercontrol/gui_window.py`] |
| macOS-safe validation | Tools / smoke runners | Manual PHN16-72 UAT | macOS lacks `gi`, `pkexec`, `systemctl`, and sysfs, so automated checks are source/static; hardware behavior remains UAT. [VERIFIED: environment probe, smoke results] |

## Standard Stack

### Core

| Library / Module | Version / Contract | Purpose | Why Standard |
|------------------|--------------------|---------|--------------|
| Python stdlib | Project requires `>=3.11`; host has Python 3.14.3. | Control logic and smoke runners. | Existing project runtime and zero-dependency CLI contract. [VERIFIED: `pyproject.toml`, environment probe] |
| PyGObject + GTK4 + libadwaita | Ubuntu apt stack locked by project; not available on this macOS host. | Native GNOME GUI. | Mandated by AGENTS/project constraints; no web, Qt, Electron, or pip-only GUI deps. [VERIFIED: `AGENTS.md`, environment probe] |
| `Gtk.Button` | GTK4 button with `clicked` signal and button accessibility role. | Five profile controls. | Does not toggle itself optimistically; UI state remains controlled by read-back. [CITED: https://docs.gtk.org/gtk4/class.Button.html; VERIFIED: `04-UI-SPEC.md`] |
| `Gtk.FlowBox` | Reflowing grid container. | Responsive 5-button layout. | Supports one-row at 800 px and wrapping at narrow widths. [CITED: https://docs.gtk.org/gtk4/class.FlowBox.html; VERIFIED: `04-UI-SPEC.md`] |
| `GLib.timeout_add` | Millisecond timer; callback repeats unless it returns remove/false. | 250 ms read-back after helper success. | `timeout_add_seconds` is too coarse for this phase's 250 ms contract. [CITED: https://docs.gtk.org/glib/func.timeout_add.html; VERIFIED: `04-UI-SPEC.md`] |
| `Adw.Toast` + `Adw.ToastOverlay` | Toast object and overlay already present in `MainWindow`. | Success, cancel, mismatch, and failure feedback. | Phase 3 shell already owns one `Adw.ToastOverlay`; `Adw.Toast.set_timeout(3)` supports exact cancel timeout. [VERIFIED: `acercontrol/gui_window.py`; CITED: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.6/class.Toast.html, https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.7/method.Toast.set_timeout.html] |
| `run_privileged()` | Existing project helper, never raises, returns `PrivilegedResult`. | Invoke `acercontrol-setprofile`. | Reuses Phase 2 privilege boundary and cancellation semantics. [VERIFIED: `acercontrol/privilege.py`] |

### Supporting

| Module / Artifact | Purpose | When to Use |
|-------------------|---------|-------------|
| `acercontrol.profiles.PROFILES` | Convert user label to kernel value. | Before calling `run_privileged`; never copy kernel strings into GUI code. [VERIFIED: `acercontrol/profiles.py`] |
| `acercontrol.core.read_profile()` | Read actual current `Profile`. | Initial render, post-failure reconciliation, and 250 ms read-back. [VERIFIED: `acercontrol/core.py`] |
| `libexec/acercontrol-setprofile` | Root wrapper allowlist and sysfs write. | Only privileged path for profile writes. [VERIFIED: `libexec/acercontrol-setprofile`] |
| `MainWindow.show_ppd_banner(force=True)` | Re-surface PPD warning after mismatch. | Mismatch path only; not auth cancel or generic failure. [VERIFIED: `acercontrol/gui_window.py`, `04-UI-SPEC.md`] |
| `tools/smoke_phase3.py` pattern | Cross-platform source/static smoke runner. | Copy structure for `tools/smoke_phase4.py`. [VERIFIED: `tools/smoke_phase3.py`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `Gtk.Button` | `Gtk.ToggleButton` | Rejected: toggle widgets carry checked state and invite optimistic UI drift. [VERIFIED: `04-UI-SPEC.md`; CITED: https://docs.gtk.org/gtk4/class.ToggleButton.html] |
| `GLib.timeout_add(250, ...)` | Immediate read after wrapper return | Rejected: UI spec requires a 250 ms read-back; immediate read may miss a fast PPD rewrite. [VERIFIED: `04-UI-SPEC.md`; ASSUMED: exact PPD timing still requires PHN16-72 UAT] |
| `GLib.timeout_add(250, ...)` | `GLib.timeout_add_seconds(1, ...)` | Rejected for this phase because second-based timer precision is intentionally coarse. [CITED: https://docs.gtk.org/glib/func.timeout_add_seconds.html] |
| `run_privileged()` | Direct `subprocess.run(["pkexec", ...])` in GUI | Rejected: duplicates Phase 2 elevation selection, wrapper resolution, timeout, and cancel handling. [VERIFIED: `acercontrol/privilege.py`, `.planning/phases/02-privilege-boundary-cli/02-01-SUMMARY.md`] |

**Installation:** No new external packages are installed in Phase 4. [VERIFIED: `04-UI-SPEC.md`, research scope]

## Package Legitimacy Audit

Phase 4 installs no npm, PyPI, crates.io, apt, or third-party UI-registry packages. Slopcheck was not run because the Package Legitimacy Gate only applies when the phase installs external packages. [VERIFIED: `04-UI-SPEC.md`; VERIFIED: codebase grep]

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| none | — | — | — | — | not applicable | No package install in Phase 4. [VERIFIED: `04-UI-SPEC.md`] |

**Packages removed due to slopcheck [SLOP] verdict:** none.  
**Packages flagged as suspicious [SUS]:** none.

## Project Constraints (from AGENTS.md)

| Directive | Phase 4 Planning Impact |
|-----------|-------------------------|
| GTK4 + libadwaita only; no Qt/Electron/web UI. | Keep Phase 4 in `acercontrol/gui*.py`; no web assets or frontend frameworks. [VERIFIED: `AGENTS.md`] |
| GUI shows user-friendly profile names and must not leak raw kernel values. | Use `Profile.display`/user labels; kernel strings only flow into wrapper argv. [VERIFIED: `AGENTS.md`, `acercontrol/profiles.py`] |
| Writing `/sys/firmware/acpi/platform_profile` requires root; never store passwords. | Use existing `run_privileged()` and wrapper; do not cache credentials in app code. [VERIFIED: `AGENTS.md`, `acercontrol/privilege.py`] |
| PPD can overwrite profile changes. | Mismatch path must warn and force the PPD banner visible again. [VERIFIED: `.planning/research/PITFALLS.md`, `04-UI-SPEC.md`] |
| Fan control is not supported; only profile-based control. | Phase 4 must not add fan sliders or RPM controls. [VERIFIED: `AGENTS.md`] |
| CLI remains single-file zero-dependency and GTK-free. | Do not import GUI modules from core/cli/bundler inputs; run `verify_no_gtk` regressions. [VERIFIED: `tools/bundle_cli.py`, `tools/verify_no_gtk.py`] |
| v1 quality is polished personal tool with manual PHN16-72 UAT and no automated test-suite requirement. | Build smoke/static checks plus explicit hardware UAT checklist. [VERIFIED: `AGENTS.md`, `.planning/ROADMAP.md`] |

## Architecture Patterns

### System Architecture Diagram

```
User click on profile button
        |
        v
ProfileControlPanel validates requested label in PROFILES
        |
        v
Set UI pending only:
  - show "Awaiting authorisation..."
  - keep previous active highlight
  - disable all profile buttons
        |
        v
run_privileged(["acercontrol-setprofile", PROFILES[requested]])
        |
        +--> cancelled=True / rc 126
        |       clear pending -> keep previous highlight -> toast "Authorization cancelled"
        |
        +--> non-zero failure
        |       clear pending -> re-read actual profile -> toast generic failure
        |
        +--> rc 0
                |
                v
        GLib.timeout_add(250, readback_callback)
                |
                v
        actual = read_profile()
                |
        +--> actual == requested Profile
        |       update highlight -> status row -> toast "Switched to <profile>"
        |
        +--> actual != requested Profile
                update highlight to actual or Custom
                toast mismatch warning
                MainWindow.show_ppd_banner(force=True)
```

### Recommended Project Structure

```
acercontrol/
├── gui_window.py       # edit: replace placeholder with ProfileControlPanel; keep shell/banners/toasts
├── gui_profiles.py     # new: profile group widget, state machine, button rendering, read-back
├── profiles.py         # unchanged: Profile enum + PROFILES mapping
├── core.py             # unchanged: read_profile()
└── privilege.py        # unchanged: run_privileged()

tools/
└── smoke_phase4.py     # new: macOS-safe static/source smoke for GUI-05..07
```

### Pattern 1: MainWindow Integration Boundary

**What:** Keep `MainWindow` as shell coordinator and place the new profile group where Phase 3 currently appends `placeholder_ok(self)`. [VERIFIED: `acercontrol/gui_window.py`]

**When to use:** Always for Phase 4; do not move header menu, warning banners, `_route()`, or PPD banner logic into `gui_profiles.py`. [VERIFIED: `04-UI-SPEC.md`]

**Example:**

```python
# Source: existing codebase pattern in acercontrol/gui_window.py
from acercontrol.gui_profiles import ProfileControlPanel

self._main_profile_panel = ProfileControlPanel(self)
self._main_column.append(self._main_profile_panel)
```

### Pattern 2: Profile State Is Read-Back State

**What:** Store `self._active_profile` from `read_profile()` and update button CSS/status rows only through `_render_profile_state(actual_profile)`. [VERIFIED: `acercontrol/core.py`, `04-UI-SPEC.md`]

**When to use:** Initial render, success, mismatch, generic failure, and focus restore. [VERIFIED: `04-UI-SPEC.md`]

**Example:**

```python
# Source: acercontrol.core.read_profile + acercontrol.profiles.Profile
actual = read_profile()
if actual is Profile.CUSTOM:
    status = "Current profile: Custom"
else:
    status = f"Current profile: {actual.display.lower()}"
```

### Pattern 3: Privileged Write + 250 ms Read-Back

**What:** Make the wrapper call synchronous, then schedule read-back via `GLib.timeout_add(250, callback)`. The callback returns `GLib.SOURCE_REMOVE` or `False` so it runs once. [VERIFIED: `acercontrol/privilege.py`, `04-UI-SPEC.md`; CITED: https://docs.gtk.org/glib/func.timeout_add.html]

**When to use:** Only after `run_privileged()` returns `returncode == 0`. Do not schedule read-back after cancellation. [VERIFIED: `04-UI-SPEC.md`]

**Example:**

```python
# Source: GLib timeout docs + existing run_privileged contract
result = run_privileged(["acercontrol-setprofile", PROFILES[requested_name]])
if result.cancelled:
    self._finish_cancelled()
elif result.returncode != 0:
    self._finish_failed()
else:
    self._readback_source_id = GLib.timeout_add(250, self._verify_readback, requested)
```

### Pattern 4: Toast Helper With Exact Cancel Timeout

**What:** Existing `MainWindow._toast()` creates default toasts; Phase 4 needs a helper that can set `timeout=3` for `Authorization cancelled`. [VERIFIED: `acercontrol/gui_window.py`, `04-UI-SPEC.md`; CITED: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.7/method.Toast.set_timeout.html]

**Example:**

```python
# Source: Adw.Toast.set_timeout docs
toast = Adw.Toast.new("Authorization cancelled")
toast.set_timeout(3)
self._toast_overlay.add_toast(toast)
```

### Anti-Patterns to Avoid

- **Optimistic active styling:** A clicked button must not receive `.suggested-action` until read-back confirms it. [VERIFIED: `04-UI-SPEC.md`]
- **Raw kernel literals in GUI labels:** `"performance"` as a kernel value means user-facing `turbo`; do not render it. [VERIFIED: `acercontrol/profiles.py`, `.planning/research/PITFALLS.md`]
- **Direct pkexec from GUI:** Do not bypass `run_privileged()`. [VERIFIED: `acercontrol/privilege.py`]
- **Long-running or repeated timeout source:** The 250 ms read-back source must remove itself after one callback. [CITED: https://docs.gtk.org/glib/func.timeout_add.html]
- **Swallowing mismatch as success:** A zero return code from the wrapper means the write command succeeded, not that the platform kept the profile. [VERIFIED: `acercontrol/cli.py`, `04-UI-SPEC.md`]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Profile mapping | Ad hoc dict in GUI or duplicated kernel strings | `acercontrol.profiles.PROFILES`, `Profile`, `read_profile()` | Prevents `performance`/`turbo` inversion and supports `Profile.CUSTOM`. [VERIFIED: `acercontrol/profiles.py`] |
| Privilege escalation | `subprocess.run(["pkexec", ...])` in GUI | `run_privileged()` | Existing helper handles wrapper resolution, sudo fallback, timeouts, and cancel flag. [VERIFIED: `acercontrol/privilege.py`] |
| Root write validation | GUI-only validation | `libexec/acercontrol-setprofile` allowlist | Wrapper must defend against direct local pkexec invocation. [VERIFIED: `libexec/acercontrol-setprofile`] |
| Toast queue | Custom in-window labels or dialogs | `Adw.Toast` / `Adw.ToastOverlay` | Existing shell already exposes overlay; docs support timeout and queue behavior. [VERIFIED: `acercontrol/gui_window.py`; CITED: https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.6/class.Toast.html] |
| Responsive button grid | Manual pixel math | `Gtk.FlowBox` | GTK provides reflowing grid behavior. [CITED: https://docs.gtk.org/gtk4/class.FlowBox.html] |
| Linux/GTK CI emulation on macOS | Fake GTK stubs | Source-level smoke + PHN16-72 UAT | Current host lacks `gi`; Phase 3 smoke already validates clean ImportError/ValueError behavior. [VERIFIED: environment probe, `tools/smoke_phase3.py`] |

**Key insight:** Phase 4 is not primarily a layout problem; it is a truthfulness problem. The UI must always show actual kernel state, not requested intent. [VERIFIED: `04-UI-SPEC.md`; VERIFIED: `.planning/research/FEATURES.md`]

## Common Pitfalls

### Pitfall 1: Toggle Button Optimism

**What goes wrong:** `Gtk.ToggleButton` changes checked state as part of activation, so the UI can briefly lie before read-back. [VERIFIED: `04-UI-SPEC.md`; CITED: https://docs.gtk.org/gtk4/class.ToggleButton.html]

**How to avoid:** Use `Gtk.Button`; manually apply active styling only in `_render_profile_state(read_profile())`. [VERIFIED: `04-UI-SPEC.md`]

**Warning signs:** Smoke finds `Gtk.ToggleButton`; code calls `set_active()` or uses `toggled`. [VERIFIED: proposed smoke design]

### Pitfall 2: Kernel Value Leakage

**What goes wrong:** User sees `performance` when the laptop is actually in Acer turbo mode, or sees `balanced-performance` instead of user `performance`. [VERIFIED: `acercontrol/profiles.py`, `.planning/research/PITFALLS.md`]

**How to avoid:** GUI labels are the five user names and `Profile.display`; kernel values only appear as the second argv item to the wrapper. [VERIFIED: `acercontrol/profiles.py`, `04-UI-SPEC.md`]

**Warning signs:** `rg '"low-power"|"balanced-performance"' acercontrol/gui*.py` finds matches outside diagnostics or the wrapper-call mapping import context. [VERIFIED: `tools/smoke_phase3.py` pattern]

### Pitfall 3: Treating Wrapper Success as UI Success

**What goes wrong:** `acercontrol-setprofile` can return 0 while PPD or firmware changes the value immediately after. [VERIFIED: `acercontrol/cli.py`, `.planning/research/PITFALLS.md`]

**How to avoid:** Always read back after 250 ms and compare `Profile`, not just raw strings. [VERIFIED: `04-UI-SPEC.md`; CITED: https://docs.gtk.org/glib/func.timeout_add.html]

**Warning signs:** Code shows `Switched to ...` before calling `read_profile()`. [VERIFIED: proposed smoke design]

### Pitfall 4: PPD Banner Stays Dismissed After It Caused a Revert

**What goes wrong:** User dismisses PPD warning, then a mismatch occurs with no visible conflict explanation. [VERIFIED: Phase 3 carry-forward summary, `04-UI-SPEC.md`]

**How to avoid:** On mismatch, call `MainWindow.show_ppd_banner(force=True)` exactly. [VERIFIED: `acercontrol/gui_window.py`]

**Warning signs:** Mismatch path only shows toast and never references `show_ppd_banner`. [VERIFIED: proposed smoke design]

### Pitfall 5: Mac Host Validation Overreach

**What goes wrong:** Planner asks for live GTK or pkexec tests on this macOS host; `gi`, `pkexec`, `systemctl`, and apt tools are missing. [VERIFIED: environment probe]

**How to avoid:** Keep automated Phase 4 checks static/source-level and leave live GTK/polkit/LED checks to PHN16-72 UAT. [VERIFIED: environment probe, `tools/smoke_phase3.py`]

**Warning signs:** Plan includes `python3 -c "import gi..."` as a required local gate on macOS. [VERIFIED: environment probe]

## Code Examples

### Profile Panel Skeleton

```python
# Source: codebase contracts in acercontrol.core/profiles/privilege + GTK docs
class ProfileControlPanel(Gtk.Box):
    ORDER = ("eco", "quiet", "balanced", "performance", "turbo")

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self._window = window
        self._buttons = {}
        self._pending = False
        self._active_profile = read_profile()
        self._build()
        self._render_profile_state(self._active_profile)

    def _on_profile_clicked(self, _button, requested_name: str) -> None:
        if self._pending:
            return
        current_name = (
            None if self._active_profile is Profile.CUSTOM
            else self._active_profile.display.lower()
        )
        if requested_name == current_name:
            return
        self._begin_pending()
        kernel_value = PROFILES[requested_name]
        result = run_privileged(["acercontrol-setprofile", kernel_value])
        if result.cancelled:
            self._finish_cancelled()
        elif result.returncode != 0:
            self._finish_failed()
        else:
            GLib.timeout_add(250, self._verify_readback, requested_name)
```

### Read-Back Reconciliation

```python
# Source: 04-UI-SPEC.md state machine
def _verify_readback(self, requested_name: str):
    actual = read_profile()
    self._active_profile = actual
    self._pending = False
    self._set_buttons_sensitive(True)
    self._render_profile_state(actual)

    requested_kernel = PROFILES[requested_name]
    if actual.value == requested_kernel:
        self._toast(f"Switched to {requested_name}")
    else:
        self._toast("Profile not applied — power-profiles-daemon may be overriding writes")
        self._window.show_ppd_banner(force=True)
    return GLib.SOURCE_REMOVE
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pkexec bash -c "echo ... > /sys"` | Dedicated libexec wrapper pinned by polkit `exec.path` | Phase 2 | Phase 4 must call `run_privileged()` and wrapper, not shell. [VERIFIED: `.planning/phases/02-privilege-boundary-cli/02-01-SUMMARY.md`; CITED: https://polkit.pages.freedesktop.org/polkit/pkexec.1.html] |
| Placeholder main content | Profile control panel replacing `placeholder_ok(self)` | Phase 4 target | Minimal shell churn; keeps Phase 3 failure surfaces stable. [VERIFIED: `acercontrol/gui_window.py`, `04-UI-SPEC.md`] |
| Immediate visual switch on click | Read-back-driven visual switch | Phase 4 target | Prevents lying during auth cancel, PPD revert, or helper failure. [VERIFIED: `04-UI-SPEC.md`] |
| Second-based GLib timers for refresh | 250 ms `GLib.timeout_add` for read-back, second timer reserved for sensor Phase 5 | Phase 4 target | Millisecond timer matches read-back contract. [CITED: https://docs.gtk.org/glib/func.timeout_add.html] |

**Deprecated/outdated:**

- `Gtk.ToggleButton` for profile state is incompatible with this phase's non-optimistic contract. [VERIFIED: `04-UI-SPEC.md`]
- Direct GUI pkexec calls duplicate and weaken the existing privilege boundary. [VERIFIED: `acercontrol/privilege.py`]
- Any GUI source-level raw-kernel profile label outside diagnostics violates GUI-08. [VERIFIED: `REQUIREMENTS.md`, `tools/smoke_phase3.py`]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The mandated 250 ms read-back delay is enough to catch the PPD overwrite path in the Phase 4 success criterion. [ASSUMED] | Architecture Patterns, Common Pitfalls | Hardware UAT may show PPD overwrites later than 250 ms; planner may need an additional delayed verification or short polling window. |
| A2 | `Gtk.FlowBox` with 128 px minimum-width buttons will fit all five controls in one row at the 800 px verification viewport once Adwaita group margins are applied. [ASSUMED] | Standard Stack, Architecture Patterns | Visual UAT may require tuning margins or `max_children_per_line`; source-level smoke cannot prove layout on macOS. |
| A3 | Existing `MainWindow._toast()` can be safely extended or wrapped for timeout-specific toasts without disturbing Phase 3 toasts. [ASSUMED] | Code Examples | If the helper remains fixed to default timeout, cancel toast will miss the exact 3-second UI contract. |

## Open Questions (RESOLVED)

1. **Does PPD overwrite within exactly 250 ms on PHN16-72?**
   - What we know: Phase 4 UI-SPEC mandates a 250 ms read-back. [VERIFIED: `04-UI-SPEC.md`]
   - RESOLVED: Plan 04-01 implements the 250 ms contract exactly using `GLib.timeout_add(250, ...)` and treats PHN16-72 PPD timing as manual UAT evidence, not a planning blocker. If hardware UAT later proves PPD overwrites occur after 250 ms, that becomes an execution deviation or follow-up gap rather than a reason to change the Phase 4 contract before implementation.

2. **Should unavailable profiles be computed from `list_available_profiles()` in Phase 4?**
   - What we know: UI-SPEC defines an unavailable-profile state and core exposes `list_available_profiles()`. [VERIFIED: `04-UI-SPEC.md`, `acercontrol/core.py`]
   - RESOLVED: Plan 04-01 includes a bounded `list_available_profiles()` path that disables known buttons missing from non-empty choices with tooltip `Unavailable on this hardware`. Broad hardware compatibility remains Phase 7; Phase 4 only prevents impossible clicks and keeps PHN16-72 happy-path behavior intact.

3. **How should source smoke detect "no optimistic highlight" robustly?**
   - What we know: Exact behavioral proof requires GTK runtime, which is unavailable on this host. [VERIFIED: environment probe]
   - RESOLVED: Plan 04-01 combines source assertions for forbidden toggle/early active-state patterns with PHN16-72 manual UAT for no flicker during polkit cancellation and PPD mismatch. The smoke runner is intentionally a source/static gate; real highlight timing remains manual UAT because GTK runtime is unavailable on this host.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | Smoke runners and package import checks | yes | 3.14.3 on this host | Target Ubuntu uses system Python per project. [VERIFIED: environment probe, `pyproject.toml`] |
| PyGObject `gi` + GTK4/Adw typelibs | Live GUI execution | no | `ModuleNotFoundError: No module named 'gi'` | Source/static smoke only on macOS; live GUI UAT on Ubuntu/PHN16-72. [VERIFIED: environment probe] |
| `pkexec` | Privileged profile write live path | no | — | Source check wrapper argv and policy XML; live auth UAT on Linux. [VERIFIED: environment probe] |
| `systemctl` | PPD state and banner live behavior | no | — | Source/static smoke; live PPD UAT on Linux. [VERIFIED: environment probe] |
| `sudo` | CLI SSH fallback and local shell availability | yes | 1.9.17p2 | Not a substitute for GUI pkexec UAT. [VERIFIED: environment probe] |
| `apt`, `apt-cache`, `dpkg-buildpackage`, `lintian` | Packaging/package version checks | no | — | Not needed in Phase 4; Phase 8 handles packaging. [VERIFIED: environment probe] |
| `ctx7` | Documentation lookup fallback | no | — | Official docs were checked via web URLs. [VERIFIED: environment probe; CITED: docs.gtk.org/libadwaita docs] |

**Missing dependencies with no fallback:**

- None for writing Phase 4 research and source-level planning. [VERIFIED: smoke results]

**Missing dependencies with fallback:**

- Live GTK, pkexec, systemd, sysfs, and PPD behavior are unavailable on this macOS host; fallback is static smoke plus PHN16-72 manual UAT. [VERIFIED: environment probe]

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Project smoke runners, no pytest detected. [VERIFIED: `rg --files`] |
| Config file | `pyproject.toml`; no pytest config. [VERIFIED: `pyproject.toml`, `rg --files`] |
| Quick run command | `python3 tools/smoke_phase4.py --quick` after Wave 0 creates it. [ASSUMED] |
| Full suite command | `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py`. [ASSUMED] |

### Current Baseline Results

| Command | Result |
|---------|--------|
| `python3 tools/smoke_phase1.py` | 6/6 passed. [VERIFIED: command output] |
| `python3 tools/smoke_phase2.py` | 28/28 passed. [VERIFIED: command output] |
| `python3 tools/smoke_phase3.py --quick` | 14/14 passed. [VERIFIED: command output] |
| `python3 tools/smoke_phase3.py` | 18/18 passed, with `acercontrol-gui` entry-point check skipped until editable install. [VERIFIED: command output] |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| GUI-05 | Five buttons in exact order; current actual profile highlighted; custom state highlights none. | source smoke + manual GTK UAT | `python3 tools/smoke_phase4.py --quick` plus PHN16-72 resize/profile UAT. [ASSUMED] | no, Wave 0 |
| GUI-06 | Click pending state, wrapper call, 250 ms read-back, success toast. | source smoke + manual GTK/polkit UAT | Static check for `run_privileged(["acercontrol-setprofile", PROFILES[requested...])`, exact strings, `GLib.timeout_add(250, ...)`; live click test on PHN16-72. [ASSUMED] | no, Wave 0 |
| GUI-07 | Mismatch warning, actual-state revert, forced PPD banner. | source smoke + manual PPD UAT | Static check for mismatch string and `show_ppd_banner(force=True)`; live PPD re-enable test on PHN16-72. [ASSUMED] | no, Wave 0 |

### Sampling Rate

- **Per task commit:** `python3 tools/smoke_phase4.py --quick` once created, plus targeted syntax check for edited files. [ASSUMED]
- **Per wave merge:** `python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py`. [ASSUMED]
- **Phase gate:** Full smoke suite green plus manual PHN16-72 UAT for GTK/polkit/LED/PPD scenarios. [VERIFIED: `.planning/ROADMAP.md`, `04-UI-SPEC.md`]

### Wave 0 Gaps

- [ ] `tools/smoke_phase4.py` - covers exact copy, button order, `Gtk.Button` not `Gtk.ToggleButton`, `run_privileged` argv shape, `GLib.timeout_add(250)`, `show_ppd_banner(force=True)`, and no raw kernel labels. [ASSUMED]
- [ ] `acercontrol/gui_profiles.py` - the module under test for profile controls. [VERIFIED: `04-UI-SPEC.md`]
- [ ] Optional smoke helper should set `ACERCONTROL_DEV` like `tools/smoke_phase3.py` so wrapper resolution stays repo-local. [VERIFIED: `tools/smoke_phase3.py`]

## Security Domain

Security enforcement is enabled because `.planning/config.json` does not set `security_enforcement: false`. [VERIFIED: `.planning/config.json`]

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | yes | polkit admin authentication via `pkexec`; cancel handled via return code 126. [CITED: https://polkit.pages.freedesktop.org/polkit/pkexec.1.html; VERIFIED: `acercontrol/privilege.py`] |
| V3 Session Management | no | No web/session token in Phase 4. [VERIFIED: codebase grep] |
| V4 Access Control | yes | Wrapper path pinned in policy; wrapper revalidates argv and requires effective uid 0. [VERIFIED: `data/org.acercontrol.policy`, `libexec/acercontrol-setprofile`] |
| V5 Input Validation | yes | Requested profile must be one of `PROFILES`; wrapper allowlists kernel values. [VERIFIED: `acercontrol/profiles.py`, `libexec/acercontrol-setprofile`] |
| V6 Cryptography | no | No cryptography in Phase 4. [VERIFIED: codebase grep] |

### Known Threat Patterns for GTK + pkexec Wrapper Flow

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Command injection through profile name | Tampering / Elevation of privilege | Pass argv list to `run_privileged`; wrapper allowlists kernel values; no shell. [VERIFIED: `acercontrol/privilege.py`, `libexec/acercontrol-setprofile`] |
| Direct wrapper invocation by local process | Elevation of privilege | Root wrapper revalidates argv and refuses non-root execution; polkit policy pins `exec.path`. [VERIFIED: `libexec/acercontrol-setprofile`, `data/org.acercontrol.policy`] |
| UI spoof or misleading profile state | Spoofing / Repudiation | Active highlight derives only from `read_profile()`; no optimistic highlight. [VERIFIED: `04-UI-SPEC.md`] |
| Raw kernel value exposure causing wrong user action | Information disclosure / Safety | GUI-08 raw-value grep gate; diagnostics-only carve-out. [VERIFIED: `REQUIREMENTS.md`, `tools/smoke_phase3.py`] |
| Auth cancel treated as failure with side effects | Denial of service / UX safety | `PrivilegedResult.cancelled` maps pkexec rc 126 to cancel path; no read-back or PPD banner force. [VERIFIED: `acercontrol/privilege.py`, `04-UI-SPEC.md`; CITED: https://polkit.pages.freedesktop.org/polkit/pkexec.1.html] |

## Sources

### Primary (HIGH confidence)

- `AGENTS.md` - project constraints, profile mapping, GUI requirements, privilege rules. [VERIFIED: codebase read]
- `.planning/ROADMAP.md` - Phase 4 goal, success criteria, dependencies. [VERIFIED: codebase read]
- `.planning/REQUIREMENTS.md` - GUI-05, GUI-06, GUI-07, GUI-08. [VERIFIED: codebase read]
- `.planning/phases/04-profile-control/04-UI-SPEC.md` - approved Phase 4 UI and interaction contract. [VERIFIED: codebase read]
- Phase 3 artifacts: `03-CONTEXT.md`, `03-RESEARCH.md`, `03-UI-SPEC.md`, `03-01/03-02 PLAN/SUMMARY` - inherited shell and PPD banner contract. [VERIFIED: codebase read]
- Current code: `acercontrol/profiles.py`, `core.py`, `privilege.py`, `gui_window.py`, `gui_banner.py`, `gui_status_pages.py`, `libexec/acercontrol-setprofile`, `tools/smoke_phase3.py`. [VERIFIED: codebase grep]
- GTK/GLib/libadwaita/polkit official docs:
  - https://docs.gtk.org/gtk4/class.Button.html
  - https://docs.gtk.org/gtk4/class.FlowBox.html
  - https://docs.gtk.org/glib/func.timeout_add.html
  - https://docs.gtk.org/glib/func.timeout_add_seconds.html
  - https://docs.gtk.org/gtk4/section-threading.html
  - https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.6/class.Toast.html
  - https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1.7/method.Toast.set_timeout.html
  - https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/class.ToastOverlay.html
  - https://polkit.pages.freedesktop.org/polkit/pkexec.1.html
  - https://www.kernel.org/doc/html/latest/userspace-api/sysfs-platform_profile.html

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md`, `FEATURES.md`, `PITFALLS.md`, `STACK.md` - project research synthesis and pitfall catalog. [VERIFIED: codebase read]

### Tertiary (LOW confidence)

- None used as authoritative; assumptions are isolated in the Assumptions Log. [VERIFIED: research process]

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH for selected APIs and existing project modules; MEDIUM for live runtime availability because this host lacks GTK/polkit/systemd. [VERIFIED: official docs, environment probe]
- Architecture: HIGH for code integration and privilege flow; Phase 3 code has stable shell contracts. [VERIFIED: codebase grep]
- Pitfalls: HIGH for non-optimistic state and raw-value leak risks; MEDIUM for exact PPD timing until hardware UAT. [VERIFIED: `04-UI-SPEC.md`, `.planning/research/PITFALLS.md`; ASSUMED: PPD timing]
- Validation: MEDIUM because source-level smoke can cover most contracts, but GTK visual/polkit behavior requires PHN16-72. [VERIFIED: environment probe]

**Research date:** 2026-05-22  
**Valid until:** 2026-06-21 for codebase planning; re-check official GTK/libadwaita docs if the project updates target distro or libadwaita baseline.
