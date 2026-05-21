# Phase 04: Profile Control (core value loop) - Pattern Map

**Mapped:** 2026-05-22
**Phase directory:** `.planning/phases/04-profile-control`
**Files analyzed:** 9 phase-relevant files (3 expected implementation edits, 6 source-of-truth/reference files)
**Analogs found:** 9 / 9

This phase is a narrow extension of the Phase 3 GUI shell. The main implementation should add a profile-control component, wire it into `MainWindow` where the Phase 3 placeholder sits, and add a Phase 4 source/static smoke runner.

## File Classification

| Phase File | Expected Action | Role | Data Flow | Closest Analog | Match Quality |
|---|---:|---|---|---|---|
| `acercontrol/gui_profiles.py` | create | component / controller | GTK event-driven + request-response read-back | `acercontrol/gui_status_pages.py` for GTK component style; `acercontrol/gui_window.py` for toast/shell handoff | role-match + data-flow partial |
| `acercontrol/gui_window.py` | modify | shell controller | probe routing + event-driven child integration | same file, especially placeholder slot and `show_ppd_banner(force)` | exact self-analog |
| `tools/smoke_phase4.py` | create | test / smoke-runner | batch source/static validation | `tools/smoke_phase3.py` | exact |
| `acercontrol/profiles.py` | reference, do not duplicate | model / mapping utility | transform raw kernel value -> UI `Profile` | same file | exact source of truth |
| `acercontrol/core.py` | reference, likely no edit | service facade | sysfs file-I/O read -> typed value | same file | exact source of truth |
| `acercontrol/privilege.py` | reference, likely no edit | privilege utility | subprocess request-response | same file | exact source of truth |
| `libexec/acercontrol-setprofile` | reference, no edit expected | privileged wrapper | argv allowlist -> sysfs file write | same file | exact trust-boundary analog |
| `acercontrol/gui_banner.py` | reference | warning component | warning state -> `Adw.Banner` | same file | exact style analog |
| `acercontrol/gui_status_pages.py` | reference, possible import cleanup only | component factory | blocker probe -> `Adw.StatusPage` | same file | exact style analog |

## Pattern Assignments

### `acercontrol/gui_profiles.py` (component/controller, GTK event-driven + read-back)

**Primary analogs:**

- `acercontrol/gui_status_pages.py` for bare GTK imports and simple component construction.
- `acercontrol/gui_window.py` for `Adw.ToastOverlay` handoff, PPD banner re-surface API, and `run_privileged()` result branching.
- `acercontrol/profiles.py`, `acercontrol/core.py`, and `acercontrol/privilege.py` for the actual profile state machine inputs.

**Imports pattern** (copy the bare GTK import style; no try/except) from `acercontrol/gui_status_pages.py:11-18`:

```python
from __future__ import annotations

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from acercontrol.features import probe
```

**Apply with Phase 4 imports:**

```python
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from acercontrol.core import list_available_profiles, read_profile
from acercontrol.privilege import run_privileged
from acercontrol.profiles import PROFILES, Profile
```

**GTK component style** from `acercontrol/gui_status_pages.py:21-31`:

```python
def _make_action_box(primary_button: Gtk.Button | None, window) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_halign(Gtk.Align.CENTER)
    if primary_button is not None:
        box.append(primary_button)
    refresh = Gtk.Button(label="Refresh")
    refresh.add_css_class("flat")
    refresh.connect("clicked", lambda *_: window._route(probe()))
    box.append(refresh)
    return box
```

**Apply:** build `ProfileControlPanel` as a native GTK widget, not as shell logic in `MainWindow`. Use `Adw.PreferencesGroup` for the "Performance Profile" section and `Gtk.FlowBox` for the five buttons. Use `Gtk.Button`, not `Gtk.ToggleButton`.

**Button construction style** from `acercontrol/gui_status_pages.py:42-46` and `:58-62`:

```python
btn = Gtk.Button(label="Load module")
btn.add_css_class("suggested-action")
btn.add_css_class("pill")
btn.connect("clicked", window._on_reload_acer_wmi_clicked)
page.set_child(_make_action_box(btn, window))
```

**Apply:** each profile button should add `.pill`; only the actual read-back active profile gets active/suggested styling. Pending requested profiles must not get active styling.

**Profile mapping source of truth** from `acercontrol/profiles.py:13-22`:

```python
PROFILES: dict[str, str] = {
    "eco":         "low-power",
    "quiet":       "quiet",
    "balanced":    "balanced",
    "performance": "balanced-performance",
    "turbo":       "performance",
}

KERNEL_TO_UI: dict[str, str] = {v: k for k, v in PROFILES.items()}
```

**Profile enum/display pattern** from `acercontrol/profiles.py:26-53`:

```python
class Profile(Enum):
    ECO         = "low-power"
    QUIET       = "quiet"
    BALANCED    = "balanced"
    PERFORMANCE = "balanced-performance"
    TURBO       = "performance"
    CUSTOM      = "custom"

    @property
    def display(self) -> str:
        if self is Profile.CUSTOM:
            return "Custom"
        return KERNEL_TO_UI[self.value]
```

**Read API pattern** from `acercontrol/core.py:36-47`:

```python
def read_profile() -> Profile:
    """Read /sys/firmware/acpi/platform_profile and return a Profile.

    Returns Profile.CUSTOM for missing sysfs path, unreadable file, or any
    unmapped kernel value. Never raises.
    """
    return _current_profile_ui(PROFILE_PATH)


def list_available_profiles() -> list[Profile]:
    """Profiles whose kernel value appears in platform_profile_choices."""
    return _available_profiles(PROFILE_CHOICES_PATH)
```

**Apply:** initial render, generic failure recovery, and post-write verification all call `read_profile()`. Use `list_available_profiles()` only to mark unavailable buttons insensitive; do not invent another choices parser.

**Privilege invocation pattern** from `acercontrol/privilege.py:95-117` and `:187-196`:

```python
def run_privileged(
    wrapper_argv: list[str],
    *,
    timeout: int = 30,
    dry_run: bool = False,
) -> PrivilegedResult:
    if not wrapper_argv:
        raise ValueError("wrapper_argv must be non-empty")
    name = wrapper_argv[0]
    wrapper_path = resolve_wrapper(name)
```

```python
return PrivilegedResult(
    returncode=result.returncode,
    elevation=method,
    argv=tuple(full_argv),
    cancelled=(method == "pkexec" and result.returncode == 126),
    stdout=result.stdout,
    stderr=result.stderr,
)
```

**Apply:** call exactly:

```python
result = run_privileged(["acercontrol-setprofile", PROFILES[requested_profile]])
```

Do not shell out, do not call `pkexec` directly, and do not pass the user-facing label to the wrapper.

**CLI read-back analog** from `acercontrol/cli.py:232-265`:

```python
result = run_privileged(["acercontrol-setprofile", kernel_value])

if result.cancelled:
    print("Authentication cancelled.")
    return 0
if result.returncode != 0:
    sys.stderr.write(result.stderr or f"wrapper exit {result.returncode}\n")
    return 1

actual = read_profile()
if actual.value != kernel_value:
    msg = (
        f"Profile not applied — requested {args.profile} ({kernel_value}), "
        f"got {actual.display} ({actual.value}). "
        f"power-profiles-daemon may be overriding writes."
    )
```

**Apply:** the GUI variant branches the same way, but after wrapper success schedules the read-back with `GLib.timeout_add(250, ...)`. Success is only when read-back equals the requested `Profile`.

**PPD mismatch hook** from `acercontrol/gui_window.py:216-224`:

```python
def show_ppd_banner(self, force: bool = False) -> None:
    """Phase 4 contract: revert-on-mismatch handler calls this with
    force=True to override the in-session dismissed flag."""
    if force:
        self._ppd_banner_dismissed = False
    self._route(probe())
    if force and self._ppd_banner is not None:
        self._ppd_banner.set_revealed(True)
```

**Apply:** only the mismatch path calls `self._window.show_ppd_banner(force=True)`. Auth cancellation and generic wrapper failure must not force the PPD banner.

**Toast pattern** from `acercontrol/gui_window.py:228-229`:

```python
def _toast(self, message: str) -> None:
    self._toast_overlay.add_toast(Adw.Toast.new(message))
```

**Apply:** either call `window._toast(...)` for default-timeout messages or extend it in `gui_window.py` to accept `timeout: int | None`. The cancel toast must use `Adw.Toast.set_timeout(3)`.

**Core state machine to implement:**

```python
ORDER = ("eco", "quiet", "balanced", "performance", "turbo")

def _on_profile_clicked(self, _button: Gtk.Button, requested_profile: str) -> None:
    if self._pending:
        return
    if self._active_profile is not Profile.CUSTOM:
        if requested_profile == self._active_profile.display.lower():
            return

    self._begin_pending()
    result = run_privileged(["acercontrol-setprofile", PROFILES[requested_profile]])
    if result.cancelled:
        self._finish_cancelled()
    elif result.returncode != 0:
        self._finish_failed()
    else:
        GLib.timeout_add(250, self._verify_readback, requested_profile)
```

**No direct in-repo analog:** `Gtk.FlowBox`, `GLib.timeout_add(250, ...)`, exact 3-second cancel toast, and the full non-optimistic active-state reconciliation are new in Phase 4. Use the approved `04-UI-SPEC.md` for those details.

---

### `acercontrol/gui_window.py` (shell controller, child integration)

**Analog:** existing `MainWindow` shell. Modify only the main-content slot and, if needed, the toast helper timeout. Keep routing, banners, menu actions, and blocker behavior intact.

**Existing imports and shell dependencies** from `acercontrol/gui_window.py:20-38`:

```python
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from acercontrol.features import probe, FeatureReport
from acercontrol.privilege import run_privileged

from acercontrol.gui_status_pages import (
    BLOCKER_FACTORIES,
    placeholder_ok,
)
```

**Apply:** remove the `placeholder_ok` import/usage and import the new component:

```python
from acercontrol.gui_status_pages import BLOCKER_FACTORIES
from acercontrol.gui_profiles import ProfileControlPanel
```

**Main content slot to replace** from `acercontrol/gui_window.py:71-80`:

```python
self._main_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
self._main_banners = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
self._main_column.append(self._main_banners)
self._main_column.append(placeholder_ok(self))
self._content_swapper.add_named(self._main_column, "main")

# GUI-03: probe FIRST, then route.
self._route(probe())
```

**Apply:** keep `_main_banners` first, then append `ProfileControlPanel(self)` below it:

```python
self._main_column.append(self._main_banners)
self._profile_panel = ProfileControlPanel(self)
self._main_column.append(self._profile_panel)
```

**Routing must remain unchanged** from `acercontrol/gui_window.py:140-168`:

```python
if not report.ok:
    blocker = report.first_blocking_failure
    assert blocker is not None
    factory = BLOCKER_FACTORIES.get(blocker.name)
    ...
    self._content_swapper.set_visible_child_name("blocker")
    return

self._content_swapper.set_visible_child_name("main")
self._rebuild_warning_banners(report)
```

**Apply:** do not render profile controls when blockers fail. The stack route already hides `main`; preserve this behavior.

**Warning banner rebuild stays the owner of banner UI** from `acercontrol/gui_window.py:170-207`:

```python
for c in report.checks:
    if c.severity != "warning" or c.present:
        continue
    if c.name.startswith("power-profiles-daemon"):
        if self._ppd_banner_dismissed:
            continue
        banner = build_ppd_banner(self)
        self._ppd_banner = banner
        banner.connect("notify::revealed", self._on_banner_revealed_change)
        self._main_banners.append(banner)
        ppd_banner_added = True
```

**Apply:** `gui_profiles.py` should not build or manage banners. It only calls `show_ppd_banner(force=True)` on mismatch.

**Toast helper extension point** from `acercontrol/gui_window.py:228-229`:

```python
def _toast(self, message: str) -> None:
    self._toast_overlay.add_toast(Adw.Toast.new(message))
```

**Apply if needed:**

```python
def _toast(self, message: str, *, timeout: int | None = None) -> None:
    toast = Adw.Toast.new(message)
    if timeout is not None:
        toast.set_timeout(timeout)
    self._toast_overlay.add_toast(toast)
```

Keep existing Phase 3 callers working without a timeout argument.

---

### `tools/smoke_phase4.py` (test/smoke-runner, batch source/static)

**Analog:** copy the `tools/smoke_phase3.py` runner structure. Phase 4 smoke should be static/source-level because this host lacks live GTK/pkexec/systemd/sysfs.

**Bootstrap pattern** from `tools/smoke_phase3.py:27-31`:

```python
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
os.environ["ACERCONTROL_DEV"] = PROJECT_ROOT
```

**Run helper pattern** from `tools/smoke_phase3.py:53-81`:

```python
def run(label, argv, *, expect_rc=0, env_extra=None, stdin=None,
        check_stdout_contains=None, check_stderr_contains=None):
    print(f"-> {label}")
    env = {**os.environ}
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=30, env=env, input=stdin)
    except Exception as e:
        print(f"  FAIL  runner exception: {type(e).__name__}: {e}")
        return False
```

**GUI raw-kernel-value grep gate** from `tools/smoke_phase3.py:147-178`:

```python
forbidden = ['"low-power"', '"balanced-performance"', '"performance"']
files_to_check = [f for f in GUI_FILES if f.name != "gui_about.py"]
failures = []
for f in files_to_check:
    if not f.exists():
        print(f"  SKIP  {f.name} (not yet created)")
        continue
    text = f.read_text()
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for token in forbidden:
            if token in line:
                failures.append(f"{f.name}:{lineno}: {line.strip()[:120]}")
```

**Apply:** extend this gate so `gui_profiles.py` is checked and `gui_about.py` remains the only diagnostics carve-out. It is okay for `profiles.py` and wrapper files to contain kernel literals.

**Scenario builder and quick/full mode** from `tools/smoke_phase3.py:323-384`:

```python
def build_scenarios(quick: bool):
    s = []
    s.append(("inline", scenario_policy_xml_well_formed))
    ...
    if quick:
        return s
    s.append(("inline", scenario_features_severity_post_patch))
    return s
```

**Main failure accumulator** from `tools/smoke_phase3.py:387-419`:

```python
failures = []
total = 0
try:
    scenarios = build_scenarios(quick=args.quick)
    total = len(scenarios)
    for scenario in scenarios:
        if scenario[0] == "inline":
            _, fn = scenario
            label = fn.__name__
            ok = fn()
        else:
            _, label, argv, opts = scenario
            ok = run(label, argv, **opts)
        if not ok:
            failures.append(label)
except Exception as exc:
    print(f"FATAL: runner top-level exception: {type(exc).__name__}: {exc}")
    return 1
```

**Phase 4 smoke scenarios to add:**

| Scenario | Source check |
|---|---|
| exact copy strings | `Awaiting authorisation...`, `Authorization cancelled`, `Profile not applied — power-profiles-daemon may be overriding writes`, `Profile change failed. See terminal for details.`, `Switched to ` |
| profile order | `("eco", "quiet", "balanced", "performance", "turbo")` or equivalent ordered source |
| button widget | `Gtk.Button` present in `gui_profiles.py`; `Gtk.ToggleButton` absent |
| privileged argv | `run_privileged(["acercontrol-setprofile", PROFILES[` pattern or equivalent argv-list construction with wrapper name first |
| read-back timer | `GLib.timeout_add(250,` present |
| PPD mismatch hook | `show_ppd_banner(force=True)` present |
| cancel timeout | `set_timeout(3)` present for `Authorization cancelled` |
| no raw user-facing kernel labels | reuse Phase 3 GUI-08 grep gate, now including `gui_profiles.py` |

---

### `acercontrol/profiles.py` (model/utility, transform)

**Analog/source of truth:** this file itself. Do not copy profile literals into `gui_profiles.py` except the five user-facing button labels.

**Mapping and inversion** from `acercontrol/profiles.py:13-23`:

```python
PROFILES: dict[str, str] = {
    "eco":         "low-power",
    "quiet":       "quiet",
    "balanced":    "balanced",
    "performance": "balanced-performance",
    "turbo":       "performance",
}
KERNEL_TO_UI: dict[str, str] = {v: k for k, v in PROFILES.items()}
```

**Custom/unknown behavior** from `acercontrol/profiles.py:56-81`:

```python
def kernel_to_profile(raw: Optional[str]) -> Profile:
    if raw is None:
        return Profile.CUSTOM
    raw = raw.strip()
    try:
        return Profile(raw)
    except ValueError:
        return Profile.CUSTOM

def current_profile_ui(profile_path: Path) -> Profile:
    try:
        raw = profile_path.read_text().strip()
    except OSError:
        return Profile.CUSTOM
    return kernel_to_profile(raw)
```

**Apply:** `Profile.CUSTOM` is a normal render state: show `Current profile: Custom`, helper text, and no active profile button.

---

### `acercontrol/core.py` (service facade, sysfs file-I/O read)

**Analog/source of truth:** this file itself. `gui_profiles.py` imports from here, not from `sysfs.py`.

**Core imports/re-export pattern** from `acercontrol/core.py:15-23`:

```python
from acercontrol.profiles import (
    Profile,
    PROFILES,
    KERNEL_TO_UI,
    kernel_to_profile,
    current_profile_ui as _current_profile_ui,
    available_profiles as _available_profiles,
)
```

**High-level reads** from `acercontrol/core.py:36-47`:

```python
def read_profile() -> Profile:
    return _current_profile_ui(PROFILE_PATH)

def list_available_profiles() -> list[Profile]:
    return _available_profiles(PROFILE_CHOICES_PATH)
```

**Apply:** no GUI code should read `/sys/firmware/acpi/platform_profile` directly.

---

### `acercontrol/privilege.py` (privilege utility, subprocess request-response)

**Analog/source of truth:** existing wrapper resolution and result contract. No new wrapper should be added in Phase 4.

**Allowed wrapper names** from `acercontrol/privilege.py:26-32`:

```python
WRAPPER_NAMES = (
    "acercontrol-setprofile",
    "acercontrol-set-boot-profile",
    "acercontrol-manage-service",
    "acercontrol-disable-ppd",
    "acercontrol-reload-acer-wmi",
)
```

**Dev wrapper resolution** from `acercontrol/privilege.py:40-57`:

```python
def resolve_wrapper(name: str) -> Path | None:
    if name not in WRAPPER_NAMES:
        raise ValueError(f"unknown wrapper: {name!r}")
    for d in _WRAPPER_DIRS:
        p = d / name
        if p.exists() and os.access(p, os.X_OK):
            return p
    dev_root = os.environ.get("ACERCONTROL_DEV")
    if dev_root:
        p = Path(dev_root) / "libexec" / name
        if p.exists() and os.access(p, os.X_OK):
            return p
    return None
```

**Apply:** `tools/smoke_phase4.py` should set `ACERCONTROL_DEV` like Phase 3 so source checks and dry wrapper resolution remain repo-local.

---

### `libexec/acercontrol-setprofile` (privileged wrapper, argv allowlist -> sysfs write)

**Analog/source of truth:** existing wrapper. Phase 4 GUI calls it through `run_privileged`.

**Allowlist and exit codes** from `libexec/acercontrol-setprofile:31-46`:

```python
PROFILE_PATH = "/sys/firmware/acpi/platform_profile"

ALLOWED_KERNEL_VALUES = (
    "low-power",
    "quiet",
    "balanced",
    "balanced-performance",
    "performance",
)

EX_OK    = 0
EX_USAGE = 64
EX_OSERR = 71
EX_NOPERM = 77
```

**Validation and write path** from `libexec/acercontrol-setprofile:49-83`:

```python
def main(argv: list) -> int:
    if len(argv) != 2:
        ...
        return EX_USAGE

    value = argv[1]
    if value not in ALLOWED_KERNEL_VALUES:
        ...
        return EX_USAGE

    if os.geteuid() != 0:
        ...
        return EX_NOPERM

    try:
        with open(PROFILE_PATH, "w") as f:
            f.write(value)
    except OSError as exc:
        ...
        return EX_OSERR

    return EX_OK
```

**Apply:** GUI-side validation is not the security boundary. The wrapper remains the trust boundary and receives only the kernel value from `PROFILES[...]`.

---

### `acercontrol/gui_banner.py` (warning component, reference)

**Analog:** keep warning surfaces out of the profile panel.

**PPD banner pattern** from `acercontrol/gui_banner.py:20-30`:

```python
def build_ppd_banner(window) -> Adw.Banner:
    banner = Adw.Banner.new(
        "power-profiles-daemon is running and will overwrite profile changes"
    )
    banner.set_button_label("Disable PPD")
    banner.set_revealed(True)
    banner.connect("button-clicked", window._on_disable_ppd_clicked)
    banner.add_css_class("warning")
    return banner
```

**Apply:** mismatch handling in `gui_profiles.py` should not create another banner. It forces the existing banner back through `MainWindow.show_ppd_banner(force=True)`.

---

### `acercontrol/gui_status_pages.py` (blocker component factory, reference)

**Analog:** blocker pages stay Phase 3-owned. Phase 4 does not alter failure-state routing.

**Blocker dispatch table** from `acercontrol/gui_status_pages.py:104-110`:

```python
BLOCKER_FACTORIES = {
    "acer_wmi module loaded": acer_wmi_not_loaded,
    "predator_v4 mode": predator_v4_disabled,
    "platform_profile sysfs": platform_profile_missing,
    "acer hwmon (fan+temp)": no_acer_hwmon,
}
```

**Apply:** `MainWindow._route()` remains the only owner of blocker routing. `gui_profiles.py` assumes it is only visible after blockers pass.

## Shared Patterns

### GTK Import Discipline

**Source:** `acercontrol/gui_window.py:20-23`, `acercontrol/gui_status_pages.py:13-16`, `acercontrol/gui_banner.py:14-17`

**Apply to:** `acercontrol/gui_profiles.py`

Use bare `import gi` and `gi.require_version(...)` at module top. Do not catch `ImportError` or create macOS stubs.

### Non-Optimistic Profile Truth

**Source:** `acercontrol/core.py:36-42`, `acercontrol/profiles.py:48-53`, `acercontrol/cli.py:257-265`

**Apply to:** `acercontrol/gui_profiles.py`

The active highlight comes only from `read_profile()` / `Profile.display`, not from the clicked button. A wrapper return code of `0` is not GUI success until read-back matches.

### Exact User-Facing Strings

**Source:** approved `04-UI-SPEC.md`

**Apply to:** `acercontrol/gui_profiles.py` and `tools/smoke_phase4.py`

Use exact strings:

```text
Performance Profile
Current profile: <profile>
Current profile: Custom
Click a profile to set a known Acer profile.
Awaiting authorisation...
Switched to <profile>
Authorization cancelled
Profile not applied — power-profiles-daemon may be overriding writes
Profile change failed. See terminal for details.
```

### Privilege Boundary

**Source:** `acercontrol/privilege.py:95-196`, `libexec/acercontrol-setprofile:49-83`

**Apply to:** `acercontrol/gui_profiles.py`

Pass an argv list through `run_privileged()`. Do not run shell commands. Do not invoke `pkexec` directly. Do not send user-facing names to the wrapper.

### PPD Re-Surface Contract

**Source:** `acercontrol/gui_window.py:216-224`

**Apply to:** mismatch branch in `acercontrol/gui_profiles.py`

Call `show_ppd_banner(force=True)` only when read-back does not match the requested profile after a successful wrapper return.

### Smoke Runner Shape

**Source:** `tools/smoke_phase3.py:27-31`, `:53-81`, `:323-419`

**Apply to:** `tools/smoke_phase4.py`

Keep `--quick`, inline scenarios, subprocess scenarios, the outer failure accumulator, and cross-platform source checks. Do not require live GTK, pkexec, systemd, or sysfs on this macOS host.

## No Analog Found

| File / Sub-pattern | Role | Data Flow | Reason | Direction |
|---|---|---|---|---|
| `ProfileControlPanel` full state machine | component/controller | event-driven + delayed read-back | No existing widget performs pending auth, privileged write, 250 ms read-back, and active-state reconciliation | Use `04-UI-SPEC.md` interaction flow exactly |
| `Gtk.FlowBox` profile grid | component layout | responsive layout | Existing GUI components use simple boxes and status pages only | Use GTK4 `Gtk.FlowBox`; smoke only source-checks, visual UAT verifies widths |
| `GLib.timeout_add(250, ...)` read-back | event timer | one-shot delayed callback | Phase 3 uses no GLib timer | Callback must return `GLib.SOURCE_REMOVE` or `False` |
| `Adw.Toast.set_timeout(3)` cancel toast | feedback | transient UI | Existing `_toast()` has default timeout only | Extend `_toast()` or create toast locally for cancellation |

## Metadata

**Analog search scope:** `acercontrol/*.py`, `libexec/acercontrol-setprofile`, `tools/smoke_phase3.py`, Phase 3 summaries and pattern map, Phase 4 UI/research/validation contracts.

**Files scanned:** 9 source files with line numbers plus 5 phase artifacts.

**Project instructions:** `AGENTS.md` read. No project-local `.codex/skills/` or `.agents/skills/` directory found.

**Pattern extraction date:** 2026-05-22

**Planner carry-forward:**

1. Create `gui_profiles.py` as the only new GUI component for profile controls.
2. Modify `gui_window.py` by replacing `placeholder_ok(self)` with `ProfileControlPanel(self)` and optionally extending `_toast()` for timeout.
3. Create `tools/smoke_phase4.py` by copying the Phase 3 smoke runner shape.
4. Keep `profiles.py`, `core.py`, `privilege.py`, `libexec/acercontrol-setprofile`, `gui_banner.py`, and `gui_status_pages.py` as source-of-truth/reference unless implementation discovers a narrow compatibility need.
