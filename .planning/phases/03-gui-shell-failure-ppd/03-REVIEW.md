---
phase: 03-gui-shell-failure-ppd
reviewed: 2026-05-16T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - acercontrol/gui.py
  - acercontrol/gui_window.py
  - acercontrol/gui_about.py
  - acercontrol/gui_status_pages.py
  - acercontrol/gui_banner.py
  - libexec/acercontrol-disable-ppd
  - libexec/acercontrol-reload-acer-wmi
  - tools/smoke_phase3.py
  - acercontrol/features.py
  - acercontrol/privilege.py
  - data/org.acercontrol.policy
  - pyproject.toml
  - tools/smoke_phase2.py
findings:
  blocker: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-05-16
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 3 delivers the GUI shell + probe-first routing + two new privileged
wrappers. The polkit policy is clean (5 well-formed actions, correct
exec.path annotations, consistent `auth_admin` / `auth_admin_keep`
defaults), the Landmine fallbacks are correctly threaded (plain-text
banner titles, `dialog.present(parent)`, three-site GAction visibility
predicate), and `features.py` severity literals correctly drive the
`_route` dispatch by `severity + present` rather than name string.

However, one BLOCKER breaks the primary "Load module" CTA on the
`acer_wmi_not_loaded` StatusPage — the reload wrapper unconditionally
runs `modprobe -r acer_wmi` with `check=True` before loading, which
errors when the module isn't loaded yet. Five additional WARNINGs
cover idempotency gaps, defensive-coding inconsistency, an `assert`
in a production codepath, blocking subprocess on the GTK main thread,
and a stale-banner bug in the unknown-blocker fallback.

## Blockers

### BL-01: `acercontrol-reload-acer-wmi` breaks the "Load module" StatusPage CTA

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-reload-acer-wmi:42-49`

**Issue:** The wrapper is wired to TWO StatusPages — `acer_wmi_not_loaded`
("Load module" button, where the module is NOT loaded) and
`predator_v4_disabled` ("Reload with predator_v4=1", where the module IS
loaded). The current implementation unconditionally runs
`modprobe -r acer_wmi` with `check=True` before the load step.

On the `acer_wmi_not_loaded` path:
1. `modprobe -r acer_wmi` exits non-zero (kmod returns ENOENT when the
   module is not in `/sys/module/`).
2. `subprocess.CalledProcessError` is raised because of `check=True`.
3. The `except subprocess.CalledProcessError` branch returns `EX_OSERR (71)`.
4. The follow-up `modprobe acer_wmi predator_v4=1` **never runs**.
5. GUI shows toast: "Operation failed. See terminal for details."

This is the most visible first-run failure path (StatusPage shown on a
machine that just installed acer_wmi but hasn't loaded it yet) and it is
broken end-to-end.

**Fix:** Gate the unload on prior load state. Either:

```python
import os

if os.path.exists("/sys/module/acer_wmi"):
    try:
        subprocess.run(
            [MODPROBE, "-r", MODULE],
            check=True, capture_output=True, text=True, timeout=20,
        )
    except subprocess.CalledProcessError as exc:
        # ... existing error path
        return EX_OSERR

subprocess.run(
    [MODPROBE, MODULE, PARAM],
    check=True, capture_output=True, text=True, timeout=20,
)
```

Or drop `check=True` from the unload call and treat any non-zero rc as
"already unloaded, proceed to load."

## Warnings

### WR-01: `acercontrol-disable-ppd` unmask check misses `masked-runtime` state

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-disable-ppd:68-70`

**Issue:** `systemctl is-enabled` returns `masked-runtime` (not `masked`)
for units masked via `/run/systemd/system/` (transient masks). The
current check `if action == "unmask" and current != "masked"` declares
"already unmasked" and returns `EX_OK` without doing anything, leaving
the runtime mask in place. Latent in Phase 3 (the GUI only calls
`mask`), but the wrapper exposes `unmask` in its allowlist and the
polkit policy authorizes both directions.

**Fix:**

```python
if action == "unmask" and not current.startswith("masked"):
    sys.stderr.write(f"{service} already unmasked\n")
    return EX_OK
```

### WR-02: `acercontrol-disable-ppd` uses bare `systemctl` while sibling uses absolute path

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/libexec/acercontrol-disable-ppd:57-58, 74-77`

**Issue:** Inconsistent defensive coding across the new wrappers.
`acercontrol-reload-acer-wmi` correctly hardcodes
`MODPROBE = "/usr/sbin/modprobe"` (line 19) with a comment explaining
"pkexec scrubs $PATH so we cannot rely on shell resolution."
`acercontrol-disable-ppd` invokes bare `["systemctl", ...]` — relies on
pkexec's default-PATH containing `/usr/bin`, which it does today but is
not a contract.

**Fix:** Hardcode the absolute path:

```python
SYSTEMCTL = "/usr/bin/systemctl"
# ...
subprocess.run([SYSTEMCTL, "is-enabled", service], ...)
# ...
cmd = [SYSTEMCTL, action]
```

### WR-03: `assert` in production codepath in `_route`

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/gui_window.py:150`

**Issue:** `assert blocker is not None  # ok=False implies at least one`
is stripped when Python runs with `-O`. If `FeatureReport.ok` and
`first_blocking_failure` ever drift (e.g. a future severity literal is
added), the next line `factory = BLOCKER_FACTORIES.get(blocker.name)`
raises `AttributeError: 'NoneType' object has no attribute 'name'` and
crashes the window construction.

**Fix:** Replace the assertion with an explicit guard:

```python
blocker = report.first_blocking_failure
if blocker is None:
    self._content_swapper.set_visible_child_name("main")
    self._toast("Internal error: ok=False but no blocking failure found")
    return
factory = BLOCKER_FACTORIES.get(blocker.name)
```

### WR-04: Synchronous `subprocess.run` on the GTK main thread

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/gui_window.py:231-254`
(also `gui_status_pages.py:29` via Refresh button)

**Issue:** `_on_disable_ppd_clicked` and `_on_reload_acer_wmi_clicked`
invoke `run_privileged(...)`, which internally calls
`subprocess.run(..., timeout=30)`. The polkit auth dialog itself runs
during that subprocess (pkexec blocks until the user authenticates or
dismisses). For the whole window — up to 30 s plus auth-dialog interaction
— the GTK main loop is frozen: animations stall, the window stops
processing input, and the compositor may show "Application not
responding."

Phase 3's plan calls for "synchronously … surface results via Adw.Toast,"
so this is the documented design, but it is a real UX defect that should
be addressed in Phase 4+ (`Gio.Subprocess` + async callback, or
`threading.Thread` + `GLib.idle_add`).

**Fix:** Move the privileged call off the main thread, e.g.:

```python
def _on_disable_ppd_clicked(self, _src) -> None:
    def worker():
        result = run_privileged([...])
        GLib.idle_add(self._on_disable_ppd_done, result)
    threading.Thread(target=worker, daemon=True).start()

def _on_disable_ppd_done(self, result):
    # toast + re-route on main loop
    ...
    return False
```

### WR-05: Unknown-blocker fallback leaves stale warning banners

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/gui_window.py:151-156`

**Issue:** When `BLOCKER_FACTORIES.get(blocker.name)` returns `None`,
`_route` falls back to `set_visible_child_name("main")` and toasts the
unknown blocker name — but it does NOT call `_rebuild_warning_banners`
or clear `_main_banners`. If a previous probe pass appended PPD /
blacklist / coretemp banners into `_main_banners` and a subsequent
re-probe hits the unknown-blocker branch, the stale banners persist on
top of the "main" page and may contradict the current state.

**Fix:** Call `_rebuild_warning_banners(report)` (or explicitly clear
`_main_banners`) before returning from the unknown-blocker branch:

```python
if factory is None:
    self._content_swapper.set_visible_child_name("main")
    self._rebuild_warning_banners(report)
    self._toast(f"Unhandled blocker: {blocker.name}")
    return
```

## Info

### IN-01: Unused `Gio` import in three GUI modules

**Files:**
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/gui_about.py:19`
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/gui_status_pages.py:16`
- `/Users/sushilkumarsahani/Desktop/AcerControl/acercontrol/gui_banner.py:17`

**Issue:** Each imports `Gio` from `gi.repository` but only references
`Adw` / `Gtk` (and `Adw` alone in `gui_banner.py`). Dead import.

**Fix:** Drop `Gio` from each import line. `gui_window.py` does use
`Gio.Menu` / `Gio.MenuItem` / `Gio.SimpleAction` — keep it there.

### IN-02: Stale comment in `tools/smoke_phase2.py` helper name

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/tools/smoke_phase2.py:74-94`

**Issue:** The helper is named `_three_actions_check_src` and its
docstring says "three actions," but `data/org.acercontrol.policy` now
declares 5 actions. The assertion uses `set(expected).issubset(set(ids))`
so the check still passes — but the name and docstring are misleading
to a future reader.

**Fix:** Rename to `_policy_defaults_check_src` and update the docstring
to say "all expected actions present (a subset check; Phase 3 adds two
more)."

### IN-03: `pyproject.toml` `requires-python` is tighter than CLAUDE.md constraint

**File:** `/Users/sushilkumarsahani/Desktop/AcerControl/pyproject.toml:11`

**Issue:** `requires-python = ">=3.11"` but CLAUDE.md states "Python
3.10+". Not a bug (Noble ships Python 3.12 and Bookworm 3.11, both
satisfy the stricter constraint), but the project doc and the package
metadata disagree.

**Fix:** Reconcile by either relaxing `requires-python` to `>=3.10` or
updating CLAUDE.md's "Tech Stack" line to "Python 3.11+".

---

_Reviewed: 2026-05-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
