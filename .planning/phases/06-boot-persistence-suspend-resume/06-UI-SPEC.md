---
phase: 6
slug: boot-persistence-suspend-resume
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-23
---

# Phase 6 - UI Design Contract

Phase 6 extends the Phase 5 main page with a boot persistence panel and a resume reapply safety net. The core loop stays first: profile buttons, then live sensors, then boot persistence controls.

## Stack Note

AcerControl remains a native GTK4 + libadwaita application. Do not introduce web UI, Qt, Electron, tray UI, packaging UI, new runtime dependencies, or a long-lived privileged daemon in this phase.

## Layout Contract

Main page ordering is locked:

```text
Adw.ApplicationWindow
└── Adw.ToolbarView
    ├── Adw.HeaderBar
    └── Adw.ToastOverlay
        └── Gtk.Stack
            ├── blocker StatusPage
            └── main
                ├── warning banners
                └── Gtk.ScrolledWindow
                    └── Adw.PreferencesPage
                        ├── ProfileControlPanel
                        ├── SensorPanel
                        └── BootServicePanel
```

`BootServicePanel` must be one `Adw.PreferencesGroup` appended after `SensorPanel`. It must not wrap itself in a nested scroller or page.

## Boot Service Panel

Group title: `Boot Service`

Rows:

| Row | Widget contract | Copy |
|-----|-----------------|------|
| Service status | `Adw.ActionRow` with status label or subtitle | `acer-performance.service` |
| Enable at boot | switch-style control | `Enable at boot` |
| Boot profile | combo/dropdown using user-facing profile names | `Boot profile` |
| Apply now | optional button or row suffix action | `Apply now` |

Required profile choices, in order:

- `eco`
- `quiet`
- `balanced`
- `performance`
- `turbo`

The GUI must never show raw kernel values (`low-power`, `balanced-performance`, `performance`) in the boot panel. Raw values may only appear in argv construction or diagnostics.

## Copy Contract

| Situation | Copy |
|-----------|------|
| Group title | `Boot Service` |
| Helper/description | `Apply a profile during startup and after resume.` |
| Service row title | `acer-performance.service` |
| Enabled state | `enabled` |
| Disabled state | `disabled` |
| Missing unit state | `not installed` |
| Failed state | `failed` |
| Unknown state | `unknown` |
| Enable row | `Enable at boot` |
| Boot profile row | `Boot profile` |
| Apply action | `Apply now` |
| Success toast | `Boot profile updated` |
| Enable success toast | `Boot service enabled` |
| Disable success toast | `Boot service disabled` |
| Failure toast | `Boot service update failed. See terminal for details.` |
| Cancellation toast | `Authorization cancelled` |
| Resume reapply toast | `Profile restored after resume` |

## Interaction Contract

### Startup race guard

- When blockers pass, `MainWindow` must perform a bounded boot-service wait before the first profile write is allowed.
- The wait helper must use systemd through the stdlib subprocess facade, not GTK code.
- The bound must be short, target 5 seconds.
- The profile panel should still render; if the wait fails or times out, the UI remains usable and profile writes can proceed after surfacing a quiet status/toast.

### Enable/disable

- Toggling `Enable at boot` calls the existing privileged service wrapper, not `pkexec` or `systemctl` directly from GUI code.
- Enable should operate on the stable public unit `acer-performance.service`.
- Disable should operate on the same stable public unit.
- Cancellation must leave the visual switch at the actual service state.

### Boot profile change

- Selecting a boot profile writes `/etc/default/acercontrol` through `acercontrol-set-boot-profile`.
- The stored value is the kernel profile value, but the UI shows only user-facing names.
- After the config write succeeds, the GUI may start the corresponding templated unit instance `acer-performance@<kernel-value>.service` through `acercontrol-manage-service` to apply immediately.
- On success, refresh service status and show `Boot profile updated`.

### Resume reapply

- Subscribe to system `org.freedesktop.login1.Manager.PrepareForSleep`.
- Ignore `start=true` before-sleep signals.
- On `start=false` after resume, read the current profile. If it differs from the last user-selected non-custom profile, reapply that profile through the existing privileged profile wrapper.
- If the system bus or login1 subscription is unavailable, degrade silently and keep the rest of the GUI functional.

## Error States

| Condition | UI response |
|-----------|-------------|
| Unit missing | Show `not installed`; controls remain visible but privileged actions produce the standard failure toast. |
| `systemctl` unavailable | Show `unknown`; do not crash. |
| Polkit cancelled | Show `Authorization cancelled`; refresh actual state. |
| Config write failed | Show `Boot service update failed. See terminal for details.` |
| Service action failed | Show `Boot service update failed. See terminal for details.` |
| Resume reapply failed | Keep current profile highlight from read-back; show no repeated notifications. |

## Out Of Scope

- Packaging install paths.
- Tray helper.
- Direct fan control.
- Persistent root daemon.
- Automatic profile rules by AC/battery state.
- Editing polkit prompt policy to remove password prompts.

## Manual UAT

- Enable boot service, set boot profile to `turbo`, cold boot twice, and verify `acercontrol get` returns `turbo` before opening the GUI.
- Open GUI immediately after login and click a profile within 2 seconds; verify the boot unit does not clobber that choice 10 seconds later.
- Suspend/resume; within 5 seconds of unlock, verify the last selected profile is restored if firmware changed it.
- Re-enable power-profiles-daemon temporarily and verify unit conflicts/PPD warnings remain understandable.
