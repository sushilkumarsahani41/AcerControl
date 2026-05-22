# Phase 05: Live Sensors + Notifications - Pattern Map

**Mapped:** 2026-05-23  
**Phase directory:** `.planning/phases/05-live-sensors-notifications`  
**Files analyzed:** Phase 5 expected files plus Phase 1-4 source-of-truth files  
**Analogs found:** 10 / 10

Phase 5 extends the existing GTK shell with live read-only telemetry and notification state machines. The implementation should reuse Phase 4's source/static smoke-runner pattern, Phase 3's `MainWindow` toast/application shell, and Phase 1's `read_sensors()` facade.

## File Classification

| Phase File | Expected Action | Role | Data Flow | Closest Analog | Match Quality |
|------------|-----------------|------|-----------|----------------|---------------|
| `tools/smoke_phase5.py` | create | smoke runner | batch source/static validation | `tools/smoke_phase4.py`, `tools/smoke_phase3.py` | exact |
| `acercontrol/gui_notifications.py` | create | notification state machines | event -> focused toast or Gio notification | `acercontrol/gui_window.py` toast helper; `acercontrol/gui.py` application ID | role-match |
| `acercontrol/gui_sensors.py` | create | GTK sensor component | `SensorReading` -> labels/bars | `acercontrol/gui_profiles.py` component style; `acercontrol/core.py` sensor API | role-match |
| `acercontrol/gui_profiles.py` | modify | profile group/controller | profile success -> centralized notification | same file | exact self-analog |
| `acercontrol/gui_window.py` | modify | shell/lifecycle coordinator | main page layout + timer + notifications | same file | exact self-analog |
| `acercontrol/core.py` | reference, no edit expected | sensor facade | sysfs -> typed snapshot | same file | exact source of truth |
| `acercontrol/sysfs.py` | reference, no edit expected | hwmon resolver | dynamic hwmon path -> raw values | same file | exact source of truth |
| `acercontrol/gui.py` | reference, no edit expected | application shell | app ID for notifications | same file | exact source of truth |
| `.planning/phases/05-live-sensors-notifications/05-UI-SPEC.md` | reference | UI contract | requirements -> concrete visual/interaction rules | same file | exact source of truth |
| `.planning/phases/05-live-sensors-notifications/05-VALIDATION.md` | reference | validation contract | phase tasks -> gates/UAT | same file | exact source of truth |

## Pattern Assignments

### `tools/smoke_phase5.py` (smoke runner)

Use `tools/smoke_phase4.py` as the closest analog:

- Project root bootstrap with `PYTHONPATH` and `ACERCONTROL_DEV`.
- `_non_comment_text(path)` helper for source assertions.
- Quick mode that skips strict implementation checks until new files exist.
- Full mode that adds MainWindow wiring and `py_compile`.

Phase 5 source gates should check these tokens once files exist:

- `GLib.timeout_add_seconds(2,`
- `GLib.source_remove`
- `read_sensors()`
- `TEMP_WARM_C = 70`
- `TEMP_HOT_C = 85`
- `CRITICAL_ENTER_C = 90`
- `CRITICAL_EXIT_C = 85`
- `FAN_MAX_RPM = 8000`
- `Gio.Notification`
- `send_notification("profile-change"`
- `send_notification("critical-temp"`
- `send_notification("critical-temp-normal"`

Forbidden source tokens in Phase 5 GUI modules:

- `threading.Thread`
- `GLib.idle_add`
- direct `"/sys/class/hwmon"` or `"hwmon"` path walking in GUI modules
- `time.sleep(`
- `notify2`
- `gi.repository.Notify`

### `acercontrol/gui_notifications.py` (notification state machines)

Use `MainWindow.show_toast()` as the in-app feedback analog:

```python
def show_toast(self, message: str, *, timeout=None) -> None:
    toast = Adw.Toast.new(message)
    if timeout is not None:
        toast.set_timeout(timeout)
    self._toast_overlay.add_toast(toast)
```

Apply by creating small, testable classes:

- `ProfileChangeNotifier(window)` with `notify(profile_name: str)`.
- `CriticalTempNotifier(window)` with `update(cpu_package_c: float | None)`.

Expected helper methods:

- `window.is_focused()` or an equivalent `MainWindow` method returning true when the active GUI window has focus.
- `window.show_toast(message, timeout=None)` for focused feedback.
- `window.get_application().send_notification(stable_id, notification)` for unfocused feedback.

Profile-change behavior:

- focused -> toast `Switched to <profile>`
- unfocused -> `Gio.Notification.new("Profile changed")`, body `AcerControl is now using <profile>.`, stable ID `profile-change`

Critical behavior:

- normal -> critical at `>= CRITICAL_ENTER_C`
- critical -> normal at `< CRITICAL_EXIT_C`
- focused -> toasts only
- unfocused -> `send_notification("critical-temp", ...)` and `send_notification("critical-temp-normal", ...)`

### `acercontrol/gui_sensors.py` (sensor component)

Use `gui_profiles.py` for bare GTK import style and component ownership:

```python
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402
```

Use `core.SensorReading` / `read_sensors()` as the source-of-truth API:

```python
@dataclass(frozen=True)
class SensorReading:
    cpu_package_c: Optional[float]
    fan1_rpm: Optional[int]
    fan2_rpm: Optional[int]
    acer_temp1_c: Optional[float]
    acer_temp2_c: Optional[float]
    acer_temp3_c: Optional[float]
```

Recommended component structure:

- `class SensorPanel(Adw.PreferencesGroup)` or `Gtk.Box` containing one `Adw.PreferencesGroup`.
- `class SensorRow(Gtk.Box)` or private helper holding label, value label, and bar.
- `SensorPanel.update(reading: SensorReading)` updates all rows in place.

Constants:

```python
TEMP_WARM_C = 70
TEMP_HOT_C = 85
CRITICAL_ENTER_C = 90
CRITICAL_EXIT_C = 85
FAN_MAX_RPM = 8000
```

Sensor rows:

- `CPU Package`: temperature row, source `reading.cpu_package_c`
- `Acer Temp 1`: temperature row, source `reading.acer_temp1_c`
- `Acer Temp 2`: temperature row, source `reading.acer_temp2_c`
- `Acer Temp 3`: temperature row, source `reading.acer_temp3_c`
- `Fan 1`: fan row, source `reading.fan1_rpm`
- `Fan 2`: fan row, source `reading.fan2_rpm`

### `acercontrol/gui_profiles.py` (centralized profile-change notification)

Current Phase 4 success path:

```python
self._toast(f"Switched to {requested_profile}")
```

Phase 5 should route this through the window:

- Add `MainWindow.notify_profile_change(profile_name)`.
- Replace the direct success toast call with `self._window.notify_profile_change(requested_profile)`.
- Keep cancellation, generic failure, and mismatch toasts unchanged.
- Ensure the window updates its last-seen profile before the next 2 second tick can duplicate-notify.

Do not change Phase 4's exact cancel or mismatch strings.

### `acercontrol/gui_window.py` (main page + lifecycle)

Current Phase 4 main page:

```python
self._main_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
self._main_banners = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
self._main_column.append(self._main_banners)
self._profile_panel = ProfileControlPanel(self)
self._main_column.append(self._profile_panel)
```

Phase 5 target shape:

- `_main_column` still owns `_main_banners`.
- Create one `_main_scroll = Gtk.ScrolledWindow()`.
- Create one `_main_page = Adw.PreferencesPage()`.
- Create `self._profile_panel = ProfileControlPanel(self)`.
- Create `self._sensor_panel = SensorPanel(self)`.
- Append both panels to `_main_page`.
- Set `_main_scroll.set_child(_main_page)` and append the scroller below banners.

Timer lifecycle:

- Store `_sensor_source_id: int | None`.
- Start the timer once when main view is active and blockers pass.
- Stop the timer when blocker routing replaces the main view or when the window closes.
- Refresh callback:
  1. `reading = read_sensors()`
  2. `self._sensor_panel.update(reading)`
  3. `self._critical_notifier.update(reading.cpu_package_c)`
  4. read profile and detect external profile change without initial notification
  5. return `GLib.SOURCE_CONTINUE`

Close cleanup:

- Connect `close-request` or `destroy` to a method that removes the source ID.
- The smoke runner should grep for `GLib.source_remove`.

## No Direct Analogs

These are new in Phase 5 and should be specified directly in the plan:

- Focus-aware `Gio.Notification` routing.
- Critical-temperature hysteresis state machine.
- Sensor bar threshold CSS classes.
- External CLI profile-change detection through the 2 second main-loop tick.

## Regression Constraints

- `python3 tools/smoke_phase4.py` must continue passing after the `ProfileControlPanel` layout refactor.
- CLI bundler inputs must remain GTK-free; do not import GUI modules from core/cli.
- GUI-08 raw kernel profile value source gate remains in force.
- No new external packages or dependencies.
