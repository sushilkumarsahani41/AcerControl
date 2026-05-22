# Phase 06: Boot Persistence + Suspend/Resume - Pattern Map

**Mapped:** 2026-05-23  
**Phase directory:** `.planning/phases/06-boot-persistence-suspend-resume`  
**Files analyzed:** Phase 6 expected files plus Phase 2-5 source-of-truth files  

Phase 6 adds a systemd substrate, a GUI boot-service panel, and a login1 resume reapply controller. The work should reuse Phase 2 wrapper discipline, Phase 4 profile write/read-back behavior, and Phase 5's shared main page/component pattern.

## File Classification

| Phase File | Expected Action | Role | Closest Analog | Match Quality |
|------------|-----------------|------|----------------|---------------|
| `tools/smoke_phase6.py` | create | source/static phase runner | `tools/smoke_phase5.py`, `tools/smoke_phase3.py` | exact |
| `data/acer-performance.service` | create | stable boot unit | `libexec/acercontrol-setprofile`, Phase 2 install notes | role-match |
| `data/acer-performance@.service` | create | templated immediate-apply unit | `data/acer-performance.service` | role-match |
| `acercontrol/systemd.py` | create | stdlib service/config facade | `acercontrol/features.py`, `acercontrol/privilege.py` | role-match |
| `libexec/acercontrol-manage-service` | modify | privileged systemctl allowlist | same file; `libexec/acercontrol-disable-ppd` | exact |
| `acercontrol/gui_boot.py` | create | boot-service UI group | `acercontrol/gui_sensors.py`, `acercontrol/gui_profiles.py` | role-match |
| `acercontrol/gui_window.py` | modify | main-page integration and startup wait | same file | exact |
| `acercontrol/gui_profiles.py` | modify | first-write wait guard | same file | exact |
| `acercontrol/gui_resume.py` | create | login1 subscription controller | `acercontrol/gui_notifications.py` | role-match |
| `acercontrol/privilege.py` | reference, maybe no edit | wrapper resolution | same file | exact |

## Pattern Assignments

### Smoke runner

Use `tools/smoke_phase5.py`:

- Project root bootstrap.
- `_non_comment_text()` source assertions.
- Quick mode that skips implementation-file-specific scenarios until the files exist.
- Full mode adds source wiring and `py_compile`.
- No `gi` import in the runner.
- No privilege prompts, no real `systemctl`, no sysfs writes.

Phase 6 smoke checks should include:

- `data/acer-performance.service` contains `Type=oneshot`, `RemainAfterExit=yes`, `EnvironmentFile=-/etc/default/acercontrol`, `ConditionKernelModuleLoaded=acer_wmi`, `ConditionPathExists=/sys/firmware/acpi/platform_profile`, `After=systemd-modules-load.service`, `Conflicts=power-profiles-daemon.service`, `Before=graphical.target`, and `acercontrol-setprofile`.
- `data/acer-performance@.service` contains the same critical unit directives and uses `%i`.
- `libexec/acercontrol-manage-service` allows only stable service plus allowed templated instances.
- GUI files do not contain direct `pkexec`, `sudo`, or mutating `systemctl` subprocess calls.
- `gui_window.py` appends `BootServicePanel` after `SensorPanel`.
- `gui_resume.py` subscribes to `PrepareForSleep` and handles the `false` after-resume signal.

### Unit files

Pattern from existing wrappers: no shell snippets for sysfs writes. Call the existing real binary:

```text
ExecStart=/usr/libexec/acercontrol/acercontrol-setprofile ${BOOT_PROFILE}
ExecStart=/usr/libexec/acercontrol/acercontrol-setprofile %i
```

Stable unit:

- `Environment=BOOT_PROFILE=balanced`
- `EnvironmentFile=-/etc/default/acercontrol`
- `[Install] WantedBy=graphical.target`

Template:

- `%i` is an internal kernel-value instance.
- No `[Install]` is required unless execution chooses to support enabled instances explicitly; stable service is the public enabled target.

### `acercontrol/systemd.py`

Use `features.py` subprocess style:

```python
subprocess.run([...], capture_output=True, text=True, timeout=N)
```

Use defensive returns instead of raising:

- Missing `systemctl` -> `"unknown"` or `False`.
- Timeout -> `"unknown"`/not ready.
- Missing config -> default `Profile.BALANCED`.

Keep this module stdlib-only and GTK-free.

### Service wrapper allowlist

Use the existing `libexec/acercontrol-disable-ppd` style:

- Tuple allowlists.
- Reject bad action before touching systemctl.
- Reject bad service before touching systemctl.
- Preserve existing bad-service smoke behavior.

Allowed services should be derived as literals from the known kernel values:

```python
ALLOWED_SERVICES = (
    "acer-performance.service",
    "acer-performance@low-power.service",
    "acer-performance@quiet.service",
    "acer-performance@balanced.service",
    "acer-performance@balanced-performance.service",
    "acer-performance@performance.service",
)
```

### Boot panel

Use `SensorPanel` and `ProfileControlPanel` component shape:

- `class BootServicePanel(Adw.PreferencesGroup)`.
- Owned by `MainWindow`, appended to the shared `Adw.PreferencesPage`.
- Keeps its own labels/switch/dropdown state.
- Calls `run_privileged()` for mutations.
- Calls `acercontrol.systemd` for read-only state.

Do not make a nested page/scroller. Do not add cards inside cards.

### Startup wait guard

Add a single method on `MainWindow`:

```python
def ensure_boot_service_ready(self) -> bool:
    ...
```

Call it:

- once after blockers pass, before live refresh starts;
- from `ProfileControlPanel._on_profile_clicked()` before invoking `acercontrol-setprofile`.

This makes the first-write guarantee resilient if a profile click happens before normal route startup work finished.

### Resume controller

Use `Gio` directly:

```python
Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
connection.signal_subscribe(
    "org.freedesktop.login1",
    "org.freedesktop.login1.Manager",
    "PrepareForSleep",
    "/org/freedesktop/login1",
    None,
    Gio.DBusSignalFlags.NONE,
    callback,
)
```

On signal:

- `start=True`: ignore.
- `start=False`: call back into `MainWindow.reapply_last_profile_after_resume()`.

Cleanup:

- unsubscribe on window close.
- tolerate no system bus/login1 on macOS or non-systemd hosts.

## Regression Constraints

- Phase 1-5 smoke suites must continue passing.
- CLI bundle remains GTK-free; do not import `gui_*` from CLI/core/systemd.
- Wrapper allowlists remain strict.
- Normal GUI source still avoids raw kernel values in user-facing strings.
- Phase 5 sensor timer cleanup remains intact.
