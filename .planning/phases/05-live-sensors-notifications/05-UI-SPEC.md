---
phase: 5
slug: live-sensors-notifications
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-23
---

# Phase 5 - UI Design Contract

> Visual and interaction contract for the live thermal/fan panel and notification behavior. Phase 5 extends the Phase 4 core value loop: users can switch profile and immediately see the machine's thermal state update.

> **Stack note:** AcerControl remains a native GTK4 + libadwaita app. Do not introduce web UI, shadcn, Tailwind, Qt, Electron, third-party chart widgets, tray UI, boot-service controls, or new runtime dependencies in this phase.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (native GTK4 + libadwaita) |
| Component library | libadwaita 1.5 + GTK4 from Ubuntu 24.04 apt packages |
| Icon library | GNOME named symbolic icons only; no custom icons in Phase 5 |
| Font | Adwaita system font; no font-family overrides |
| Color source | Adwaita system colors plus minimal threshold CSS classes for sensor bars |

Inherited shell contract remains locked:

| Surface | Contract |
|---------|----------|
| Application | `Adw.Application(application_id="org.acercontrol.AcerControl")` |
| Window | `Adw.ApplicationWindow`, title `AcerControl`, default size 800 x 600 logical px |
| Top-level layout | `Adw.ToolbarView` with `Adw.HeaderBar` and `Adw.ToastOverlay(Gtk.Stack)` |
| Warning area | Existing PPD / blacklist / coretemp banners remain above the main page |
| Profile controls | The five Phase 4 buttons remain first in the main content |

---

## Phase Scope

| In scope | Out of scope |
|----------|--------------|
| Live sensor group with CPU package, Acer temps, Fan 1, Fan 2 | Boot service panel |
| 2 second main-loop refresh with `GLib.timeout_add_seconds(2, ...)` | Tray helper / indicator |
| Temperature bars with green/yellow/red threshold states | Historical graph |
| Fan RPM bars with stable scale and placeholder state | Fan RPM control or fan curves |
| Focus-aware profile-change notifications | App icon / desktop packaging |
| Hysteresis critical-temperature notifications | Systemd suspend/resume hook |

Raw sysfs paths and raw kernel profile values remain diagnostics-only. Sensor values are user-facing, but sysfs filenames such as `temp1_input` and `fan1_input` must not be visible in the normal UI.

---

## Layout Contract

Phase 5 must replace the Phase 4 "profile panel owns the page and scroller" shape with a single scrollable main page owned by `MainWindow`.

```
Adw.ApplicationWindow
└── Adw.ToolbarView
    ├── Adw.HeaderBar
    └── Adw.ToastOverlay
        └── Gtk.Stack
            ├── blocker StatusPage (unchanged)
            └── main
                ├── warning banners (unchanged)
                └── Gtk.ScrolledWindow
                    └── Adw.PreferencesPage
                        ├── ProfileControlPanel
                        │   └── Adw.PreferencesGroup title="Performance Profile"
                        └── SensorPanel
                            └── Adw.PreferencesGroup title="Sensors"
```

Required refactor:

- Keep the public `ProfileControlPanel` class name so Phase 4 source/static gates remain meaningful.
- Move the single `Gtk.ScrolledWindow` and `Adw.PreferencesPage` ownership to `MainWindow`.
- Make `ProfileControlPanel` render only the profile group/content, not a full page or nested scroller.
- Add `SensorPanel` immediately below `ProfileControlPanel` in the same `Adw.PreferencesPage`.

Responsive behavior:

| Viewport | Required behavior |
|----------|-------------------|
| 800 x 600 | Profile controls and at least the first three sensor rows are visible without horizontal scrolling. |
| 640-799 px wide | Sensor rows remain one column; value text and bars keep aligned. Profile buttons may wrap as in Phase 4. |
| 360-639 px wide | Sensor rows may stack value above bar, but labels must not clip. Vertical scrolling is allowed. |
| Any width | No horizontal scrolling; no font scaling with viewport width; no overlap between value labels and bars. |

Do not put UI cards inside cards. `Adw.PreferencesGroup` is the only section frame for the sensor surface.

---

## Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Label/value spacing inside compact rows |
| sm | 8px | Row spacing inside sensor bars |
| md | 16px | Gap between label/value text and bar when stacked |
| lg | 24px | Main page margin |
| xl | 32px | Gap between profile and sensor groups only if Adwaita default group spacing is unavailable |

Interactive targets remain at least 44 x 44 px. Sensor rows are informational and do not need button targets.

---

## Typography

Use Adwaita semantic sizing. Do not add custom font declarations.

| Role | Size | Weight | Usage |
|------|------|--------|-------|
| Caption | 13px | 400 | Secondary status such as `Live refresh: 2 s` |
| Body | 15px | 400 | Sensor labels and values |
| Value emphasis | 15px | 600 | Numeric sensor values |
| Group heading | Adwaita default | 600 | `Performance Profile`, `Sensors` |

Required sensor labels:

- `CPU Package`
- `Acer Temp 1`
- `Acer Temp 2`
- `Acer Temp 3`
- `Fan 1`
- `Fan 2`

Missing values render as exactly `-` in source/static smoke gates and as an em dash or equivalent placeholder in the live UI only if the implementation already uses that convention consistently.

---

## Color And Bars

Temperature thresholds are locked:

| Range | State | Visual contract |
|-------|-------|-----------------|
| `< 70 C` | normal | green/success sensor bar |
| `70-84 C` | warm | yellow/warning sensor bar |
| `>= 85 C` | hot | red/error sensor bar |
| missing | unavailable | neutral empty bar and placeholder value |

Critical notification thresholds are separate:

| Transition | Threshold |
|------------|-----------|
| enter critical | `>= 90 C` |
| leave critical | `< 85 C` |

Fan bars:

- Use RPM value text: `<rpm> RPM`.
- Use a fixed scale constant `FAN_MAX_RPM = 8000` unless hardware UAT proves a better PHN16-72 ceiling.
- Clamp fractions to `[0.0, 1.0]`; never resize rows based on RPM text length.
- Fan bars use neutral/accent styling, not red/yellow thermal semantics.

Preferred widget: `Gtk.ProgressBar` or `Gtk.LevelBar`. If custom CSS is required, keep it local to GUI modules and use three explicit classes: `sensor-ok`, `sensor-warm`, `sensor-hot`.

---

## Copywriting Contract

Tone remains terse and operational.

| Element | Copy |
|---------|------|
| Sensor group title | `Sensors` |
| Refresh helper | `Live refresh: 2 s` |
| CPU row label | `CPU Package` |
| Fan labels | `Fan 1`, `Fan 2` |
| Acer temp labels | `Acer Temp 1`, `Acer Temp 2`, `Acer Temp 3` |
| Missing sensor value | `-` or the existing project placeholder if standardized during implementation |
| Critical enter system notification title | `CPU temperature critical` |
| Critical enter body | `CPU package temperature is above 90 C.` |
| Critical leave system notification title | `CPU temperature back to normal` |
| Critical leave body | `CPU package temperature is below 85 C.` |
| External profile-change notification title | `Profile changed` |
| External profile-change body | `AcerControl is now using <profile>.` |

Profile-change success copy from Phase 4 stays exact for focused in-app feedback: `Switched to <profile>`.

---

## Interaction Flow

### Live refresh

1. Main view is shown only after Phase 3 blocker routing passes.
2. `SensorPanel` renders all rows immediately with placeholder values.
3. A main-loop timer starts with `GLib.timeout_add_seconds(2, refresh_callback)`.
4. Each tick calls `acercontrol.core.read_sensors()` synchronously on the main loop.
5. Each row updates value text and bar fraction from the snapshot.
6. Callback returns `GLib.SOURCE_CONTINUE`.
7. On window close/destroy, the source ID is removed with `GLib.source_remove(source_id)`.

No background thread is allowed in Phase 5.

### Sensor read failure

Required UI response:

- Only the failed row renders the missing placeholder.
- Other rows continue updating.
- Timer continues running.
- No traceback reaches the GTK main loop.
- The core resolver retry behavior from `read_sensors()` remains the only hwmon re-resolution path.

### Focus-aware profile-change notification

When profile changes while the window is focused:

- Show an `Adw.Toast`.
- Do not send `Gio.Notification`.

When profile changes while the window is unfocused:

- Send `Gio.Notification`.
- Use stable notification ID `profile-change`.
- Do not stack multiple notifications for repeated profile changes.

Phase 4's profile-button success path must route through the same notification helper so copy and focus behavior are centralized.

### Critical temperature hysteresis

State machine:

- Initial state: not critical.
- If CPU package temp is missing: keep prior critical state and send nothing.
- If not critical and temp `>= 90 C`: enter critical.
- If critical and temp `< 85 C`: leave critical.
- While critical and temp remains `>= 85 C`: send nothing.
- While normal and temp remains `< 90 C`: send nothing.

Focused window:

- Use `Adw.Toast` only.
- Send zero `Gio.Notification` instances.

Unfocused window:

- Use stable notification IDs `critical-temp` and `critical-temp-normal`.
- Send exactly one enter notification per crossing and one normal notification per leave crossing.

---

## Accessibility

- Sensor labels must be text labels, not icon-only rows.
- Bars must have accessible value text that matches visible text where GTK APIs allow it.
- Missing sensors must be represented by placeholder text, not only by color.
- Color must not be the only signal: value text remains visible for normal/warm/hot states.
- Keyboard tab order remains: profile controls first, then any focusable controls from future phases. Sensor rows should not add unnecessary focus stops.

---

## Quality Gates

Automated source/static gates should verify:

- `GLib.timeout_add_seconds(2,` exists for sensor refresh.
- No `threading.Thread`, no `GLib.idle_add`, and no worker-thread sensor pattern appears in Phase 5 GUI modules.
- `read_sensors()` is the only sensor read API used by GUI sensor code.
- Temperature thresholds `70`, `85`, and `90` appear as named constants.
- Critical hysteresis uses enter `>= 90` and leave `< 85`.
- `Gio.Notification` and `send_notification("profile-change"` are present.
- `send_notification("critical-temp"` and `send_notification("critical-temp-normal"` are present.
- Timer cleanup uses `GLib.source_remove`.
- Phase 1-4 smoke suites continue passing.

Manual PHN16-72 UAT remains required for real GTK, polkit, Gio.Notification, sysfs, and stress-temperature behavior.
