---
phase: 4
slug: profile-control
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-22
---

# Phase 4 — UI Design Contract

> Visual and interaction contract for Profile Control, the core value loop: click a profile button → privileged write runs → read-back confirms → the UI reflects the actual profile.

> **Stack note:** AcerControl remains a native GTK4 + libadwaita app. Do not introduce web UI, shadcn, Tailwind, CSS palettes, tray UI, live sensors, or boot-service controls in this phase.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (native libadwaita 1.5 — no shadcn / no web framework) |
| Preset | not applicable |
| Component library | libadwaita 1.5 + GTK4 from Ubuntu 24.04 apt packages |
| Icon library | GNOME named symbolic icons only; no new custom icon in Phase 4 |
| Font | Adwaita system font; no font-family overrides |

**Application shell inherited from Phase 3 and must remain unchanged:**

| Surface | Contract |
|---------|----------|
| Application | `Adw.Application(application_id="org.acercontrol.AcerControl", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)` |
| Window | `Adw.ApplicationWindow`, title `AcerControl`, default size 800 × 600 logical px |
| Top-level layout | `Adw.ToolbarView` with `Adw.HeaderBar` top bar and `Adw.ToastOverlay(Gtk.Stack)` content |
| Main view | Existing warning banners remain above the profile-control content |
| PPD force API | `MainWindow.show_ppd_banner(force=True)` is called on profile write/read-back mismatch |

---

## Phase Scope

Phase 4 ships only the profile-control surface.

| In scope | Out of scope |
|----------|--------------|
| Five profile controls: `eco`, `quiet`, `balanced`, `performance`, `turbo` | Live sensor panel |
| Current active profile visualization, including `Custom` / unknown handling | System tray / indicator |
| Privileged set-profile flow through `acercontrol-setprofile` | Boot service panel |
| Read-back verification and revert-on-mismatch UI | Temperature notifications |
| Profile-change toasts | App icon / `.desktop` packaging work |

Raw kernel values such as `low-power`, `balanced-performance`, and kernel `performance` must not appear in user-facing UI. Diagnostics remains the only carve-out from GUI-08.

---

## Layout Contract

Replace the Phase 3 placeholder `StatusPage` with a profile panel while preserving the existing Stack and warning-banner structure.

```
Adw.ApplicationWindow
└── Adw.ToolbarView
    ├── Adw.HeaderBar
    └── Adw.ToastOverlay
        └── Gtk.Stack
            ├── blocker StatusPage (unchanged from Phase 3)
            └── main
                ├── warning banners (PPD / blacklist / coretemp)
                └── Gtk.ScrolledWindow
                    └── Adw.PreferencesPage
                        └── Adw.PreferencesGroup title="Performance Profile"
                            ├── status row
                            ├── profile button flow
                            └── transient status row
```

**Responsive behavior:**

| Viewport | Required behavior |
|----------|-------------------|
| 800 × 600 verification viewport | All five profile buttons fit in one row below the `Performance Profile` group title. No horizontal scrolling. PPD banner plus profile group remain visible without clipping. |
| 640-799 px wide | Buttons may wrap to two rows via `Gtk.FlowBox`; order remains `eco`, `quiet`, `balanced`, `performance`, `turbo`. |
| 360-639 px wide | Buttons wrap to two columns where space permits, then one column below 420 px. No label truncation; vertical scrolling is allowed. |
| Any width | Never scale font size with viewport width. Never allow "performance" or "Awaiting authorisation..." to overflow its container. |

Do not hard-code a window wider than 800 px. Do not add a horizontally scrolling profile row.

---

## Spacing Scale

Declared values are multiples of 4 and extend the Phase 3 Adwaita defaults only where this phase adds custom containers.

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Spinner-to-label gap inside pending status row |
| sm | 8px | Button row/column spacing in the profile `Gtk.FlowBox` |
| md | 16px | Gap between status row, button flow, and transient status row |
| lg | 24px | Scrolled main-content margin around `Adw.PreferencesPage` |
| xl | 32px | Reserved for future major section gaps; not used in Phase 4 |
| 2xl | 48px | Not used in Phase 4 |
| 3xl | 64px | Not used in Phase 4 |

Exceptions:
- Profile buttons use a minimum height of 56 px and minimum width of 128 px.
- Interactive targets must be at least 44 × 44 px even in narrow layouts.
- Existing Phase 3 `Gtk.Box(spacing=12)` action boxes remain unchanged.

---

## Typography

Use Adwaita semantic text sizing. Do not add custom CSS font declarations.

| Role | Size | Weight | Line Height | Usage |
|------|------|--------|-------------|-------|
| Caption | 13px | 400 | 1.4 | Secondary helper text, unavailable tooltip text if surfaced inline |
| Body / Button | 15px | 400 | 1.5 | Profile button labels, status row body |
| Emphasis | 15px | 600 | 1.5 | Current profile value in status row |
| Heading | 20px | 600 | 1.2 | `Performance Profile` group heading if a custom heading is needed |

Allowed weights: 400 regular and 600 semibold only. Button labels stay lowercase exactly: `eco`, `quiet`, `balanced`, `performance`, `turbo`.

---

## Color

Use Adwaita system colors and state classes. No hex palette is introduced.

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | Adwaita window/background surface | Window body and scrolled page background |
| Secondary (30%) | Adwaita card/view surface | `Adw.PreferencesGroup` rows and profile panel surface |
| Accent (10%) | User's GNOME accent via Adwaita selected/suggested state | Active known profile only, keyboard focus ring, and existing `.suggested-action` remediation buttons |
| Warning | `.warning` style class | PPD banner, blacklist/coretemp warnings, mismatch-driven PPD re-surface |
| Destructive | not used | No destructive action ships in Phase 4 |

Accent reserved for:
- The currently active known profile button.
- GTK focus rings.
- Existing Phase 3 remediation buttons that already use `.suggested-action`.

Do not use accent color for the requested pending profile until read-back confirms it is actually active.

---

## Copywriting Contract

Tone remains terse, technical, and GNOME-like. Strings marked exact must not be paraphrased or punctuated differently.

| Element | Copy |
|---------|------|
| Group title | `Performance Profile` |
| Profile buttons | `eco`, `quiet`, `balanced`, `performance`, `turbo` |
| Known active status | `Current profile: <profile>` |
| Custom/unknown status | `Current profile: Custom` |
| Custom/unknown helper | `Click a profile to set a known Acer profile.` |
| Pending status, exact | `Awaiting authorisation...` |
| Success toast, exact | `Switched to <profile>` |
| Auth-cancel toast, exact | `Authorization cancelled` |
| Mismatch toast, exact | `Profile not applied — power-profiles-daemon may be overriding writes` |
| Generic failure toast | `Profile change failed. See terminal for details.` |

Toast timeouts:
- `Authorization cancelled`: exactly 3 seconds.
- Success and mismatch toasts: Adwaita default timeout.
- Generic failure toast: Adwaita default timeout.

Destructive confirmations: none. Profile changes are privileged but reversible; no confirmation dialog is shown beyond polkit.

---

## Profile Controls

Render the five controls in this exact order:

1. `eco`
2. `quiet`
3. `balanced`
4. `performance`
5. `turbo`

Use `Gtk.Button`, not `Gtk.ToggleButton`. Toggle buttons optimistically change checked state on click, which violates this phase's read-back contract.

| Button state | Visual contract | Interaction |
|--------------|-----------------|-------------|
| Inactive | `.pill`; normal Adwaita button styling | Click starts the privileged set flow |
| Active known profile | `.pill` + selected/accent styling; use `.suggested-action` only for the actual read-back profile | Click is a no-op; no polkit prompt and no toast |
| Pending requested profile | No active/accent styling unless it was already active before the click | All profile buttons become insensitive while the helper/read-back flow is running |
| Unavailable profile | Insensitive; same label; tooltip `Unavailable on this hardware` | No click handler |
| Custom/unknown current profile | No profile button is active; status row shows `Current profile: Custom` and helper copy | All available buttons remain clickable |

The active highlight is derived only from `acercontrol.core.read_profile()` / `Profile.display`, never from the requested button.

---

## Interaction Flow

### Initial render

1. Phase 3 blocker routing still runs first. If any blocking `FeatureReport` check fails, render the existing blocker `Adw.StatusPage`; do not render profile controls.
2. If blockers pass, render the main view and warning banners.
3. Read current profile via `read_profile()`.
4. If the profile is one of the five known `Profile` members, highlight the matching button and show `Current profile: <profile>`.
5. If `Profile.CUSTOM`, highlight no button and show `Current profile: Custom` plus the helper copy.

### Click a different profile

1. User activates an inactive profile button.
2. UI immediately shows visible status text `Awaiting authorisation...`.
3. Existing active highlight remains unchanged.
4. All profile buttons become insensitive to prevent duplicate writes.
5. Invoke `run_privileged(["acercontrol-setprofile", PROFILES[requested_profile]])`.
6. If the privileged call returns 0, schedule a read-back verification 250 ms later using the GTK main loop.
7. Re-enable controls only after the terminal state below is handled.

### Success

Condition: read-back returns the requested profile.

Required UI response:
- Clear `Awaiting authorisation...`.
- Move the active highlight to the requested button.
- Update status row to `Current profile: <profile>`.
- Show toast exactly `Switched to <profile>`.

### Authorization cancelled

Condition: `PrivilegedResult.cancelled is True` or pkexec return code 126.

Required UI response:
- Clear `Awaiting authorisation...`.
- Re-enable controls.
- Keep the previous active highlight unchanged; no flicker to requested profile.
- Show toast exactly `Authorization cancelled` with timeout 3 seconds.
- Do not call `show_ppd_banner(force=True)`.

### Mismatch / PPD override

Condition: helper returns 0, but the 250 ms read-back profile does not equal the requested profile.

Required UI response:
- Clear `Awaiting authorisation...`.
- Re-enable controls.
- Revert highlight to the actual read-back profile.
- If read-back is `Profile.CUSTOM`, highlight no profile button and show the Custom status/helper copy.
- Show warning toast exactly `Profile not applied — power-profiles-daemon may be overriding writes`.
- Call `MainWindow.show_ppd_banner(force=True)` so the PPD banner reappears even if the user dismissed it earlier in the session.

### Non-cancel failure

Condition: wrapper/elevation returns non-zero and not cancelled.

Required UI response:
- Clear `Awaiting authorisation...`.
- Re-enable controls.
- Re-read the current profile and render the actual state.
- Show toast `Profile change failed. See terminal for details.`
- Do not optimistically move highlight to the requested button.

---

## Accessibility and Focus

| Surface | Contract |
|---------|----------|
| Initial focus | Known profile: focus the active profile button. Custom/unknown: focus `balanced`. |
| Tab order | HeaderBar menu → first warning banner button/close control → profile buttons in fixed order → any footer/status action. |
| Keyboard activation | Space/Enter on a focused profile button starts the same flow as mouse click. |
| Focus after success | Move focus to the newly active profile button. |
| Focus after cancellation | Return focus to the previously active button; if the previous state was Custom, return focus to the requested button. |
| Focus after mismatch | Move focus to the actual read-back profile button; if Custom, move focus to `balanced`. |
| Accessible names | Buttons expose `Set profile to <profile>`; active button additionally exposes state text `Current profile`. |
| Busy state | While pending, the profile group exposes busy state through the visible `Awaiting authorisation...` status row; no custom modal is shown. |

All visible text must remain readable at 360 px width. Button labels must not ellipsize; wrapping the button grid is preferred over truncation.

---

## File Layout

| File | Phase 4 responsibility |
|------|------------------------|
| `acercontrol/gui_window.py` | Replace placeholder main content with the profile-control panel; keep `ToolbarView`, `HeaderBar`, `ToastOverlay`, `Stack`, warning banners, and `show_ppd_banner(force)` intact |
| `acercontrol/gui_profiles.py` | New preferred module for the profile group widget, button state rendering, and set-profile interaction flow |
| `acercontrol/core.py` | Existing `read_profile()`, `PROFILES`, and `Profile` APIs are the source of truth |
| `acercontrol/privilege.py` | Existing `run_privileged()` executes `acercontrol-setprofile`; no GUI-side elevation reimplementation |
| `libexec/acercontrol-setprofile` | Existing privileged trust boundary; receives kernel profile values only |
| `tools/smoke_phase4.py` | New smoke/UAT helper preferred for exact-copy, no-raw-values, and non-optimistic-highlight source checks |

Do not put profile mapping literals in GUI code except the five user-facing labels. Kernel values come from `PROFILES[profile_name]`.

---

## Verification / UAT Checklist

Automated or source-level checks:

- [ ] GUI source contains all exact strings: `Awaiting authorisation...`, `Authorization cancelled`, `Profile not applied — power-profiles-daemon may be overriding writes`, and `Switched to `.
- [ ] GUI profile code uses `Gtk.Button`, not `Gtk.ToggleButton`, for the five profile controls.
- [ ] GUI profile code calls `run_privileged(["acercontrol-setprofile", PROFILES[requested_profile]])`.
- [ ] Source grep confirms raw kernel values (`"low-power"`, `"balanced-performance"`, kernel `"performance"`) do not appear in user-facing GUI labels outside `gui_about.py` diagnostics.
- [ ] Button order is exactly `eco`, `quiet`, `balanced`, `performance`, `turbo`.
- [ ] There is no optimistic active-state assignment before read-back verification.

Human UAT on PHN16-72:

- [ ] Click each of the five profile buttons in turn; after each click, `acercontrol get` in a separate terminal returns the matching user-facing name.
- [ ] Clicking `turbo` makes the chassis LED blink; clicking `performance` leaves it solid.
- [ ] Press Escape on the polkit dialog; previous highlight remains stable, toast shows exactly `Authorization cancelled` for 3 seconds, and `journalctl --user` has no traceback.
- [ ] Re-enable PPD, click a profile PPD overwrites, and confirm the mismatch toast appears exactly, highlight reverts to actual read-back profile, and PPD banner reappears after dismissal.
- [ ] Force `/sys/firmware/acpi/platform_profile` to a custom/unknown value; GUI shows `Current profile: Custom`, no button is active, and clicking any known profile enters the normal set flow.
- [ ] Resize to 800 × 600 and 360 px wide; no text clips, no horizontal scroll appears, and button order remains stable.

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| not applicable (native GNOME app, no shadcn/web component registry) | — | not applicable |

The shadcn gate does not apply: this project is Python GTK4/libadwaita, not React/Next/Vite. No third-party UI registry or web component block is introduced.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS — exact transient/toast strings and Custom copy declared
- [ ] Dimension 2 Visuals: PASS — five-button profile panel, active/custom/pending states, responsive wrapping declared
- [ ] Dimension 3 Color: PASS — Adwaita semantic roles only; accent reserved for actual active state
- [ ] Dimension 4 Typography: PASS — 3 concrete semantic sizes, 2 weights, line heights declared
- [ ] Dimension 5 Spacing: PASS — multiples-of-4 scale and button target exceptions declared
- [ ] Dimension 6 Registry Safety: PASS — N/A for native libadwaita

**Approval:** pending (awaiting gsd-ui-checker)
