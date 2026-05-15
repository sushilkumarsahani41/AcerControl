# Phase 03: GUI Shell + Failure States + PPD Banner — Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 12 (7 new, 5 modified)
**Analogs found:** 11 / 12 with concrete repo analogs (1 partial / shape-only)

PATTERNS.md's value-add over RESEARCH.md is the cross-reference to *existing repo code* — not a restatement of the target skeletons. Verbatim target skeletons for the 5 GUI files live in RESEARCH.md §Patterns 1–6; PATTERNS.md cites those by line number and pairs every new/modified file with its closest in-repo analog and the concrete lines to copy from.

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `acercontrol/gui.py` (new) | entry-point | GApplication activate signal → MainWindow construction → `sys.exit(app.run())` | `acercontrol/cli.py:480-487` (`main()` dispatch + `sys.exit`) | role-match |
| `acercontrol/gui_window.py` (new) | component / controller | features.probe() → severity-partition → route to Adw.StatusPage or banner stack; `run_privileged()` on button click → Toast feedback | `acercontrol/cli.py:233-256` (`cmd_set`: `run_privileged` + `result.cancelled` + `returncode != 0` branches) | role-match (strong data-flow match) |
| `acercontrol/gui_status_pages.py` (new) | component / factory | probe-key → `Adw.StatusPage` with icon + title + description + action `Gtk.Button` child | no direct analog — factory pattern is new | shape-only (RESEARCH §Pattern 4 verbatim) |
| `acercontrol/gui_banner.py` (new) | component | PPD warning state → `Adw.Banner` construction + dismissed flag + Learn-more `Adw.Window`; `run_privileged()` on Disable-PPD click | `acercontrol/cli.py:233-256` (`run_privileged` + cancelled/failed branches) | role-match (data-flow match) |
| `acercontrol/gui_about.py` (new) | component | `features.probe()` → JSON serialization → `Adw.AboutDialog.set_debug_info()` | `acercontrol/cli.py:82-117` (`cmd_status` JSON probe→dict transform) | role-match |
| `libexec/acercontrol-disable-ppd` (new, +x) | privileged wrapper | argv → (action × service) allowlist → `subprocess.run(["systemctl", action, "--now", service])` → preserve returncode (NOT WR-03 collapse) | `libexec/acercontrol-manage-service:22-62` (allowlist tuples + argv validation + systemctl subprocess) | exact (data-flow) |
| `libexec/acercontrol-reload-acer-wmi` (new, +x) | privileged wrapper | argv → zero-extra-args check → `subprocess.run(["/usr/sbin/modprobe", "-r", "acer_wmi"])` → `subprocess.run(["/usr/sbin/modprobe", "acer_wmi", "predator_v4=1"])` | `libexec/acercontrol-setprofile:49-66` (argv shape + EX_USAGE) + `libexec/acercontrol-manage-service:53-59` (subprocess pattern) | role-match |
| `data/org.acercontrol.policy` (edit — append 2 actions) | config (XML) | static declaration → polkitd hot-reloads | `data/org.acercontrol.policy:34-44` (manage-service `<action>` block — closest shape to the new actions) | append-only delta |
| `acercontrol/privilege.py` (edit — extend `WRAPPER_NAMES`) | helper module | N/A — tuple literal extension only | `acercontrol/privilege.py:26-30` (the `WRAPPER_NAMES` tuple) | exact |
| `pyproject.toml` (edit — uncomment GUI entry) | build config | TOML metadata | existing `[project.scripts]` section (comment on Phase 2's `# acercontrol-gui = "acercontrol.gui:main"` line) | uncomment-only delta |
| `acercontrol/features.py` (edit — 3 severity values — Landmine #2) | library module | N/A — surgical 3-line patch | `acercontrol/features.py:148,158,194` (current severity literals being replaced) | exact |
| `tools/smoke_phase3.py` (new) | smoke-runner | scenario list → subprocess each → failure accumulator → exit 0/1 | `tools/smoke_phase2.py:32-69` (run() helper) + `tools/smoke_phase2.py:311-340` (main() accumulator) | exact |

---

## Pattern Assignments

### `acercontrol/gui.py` (entry-point, GApplication lifecycle)

**Analog A:** `acercontrol/cli.py:480-487` — `main()` function as the `[project.scripts]` entry point. The GUI `main()` is structurally identical: construct the app object, invoke its run, return/exit the result.

```python
# acercontrol/cli.py:480-487
def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

**Apply:** `gui.py::main()` replaces `_build_parser()` + `args.func(args)` with `AcerControlApp().run(None)`. The `if __name__ == "__main__": sys.exit(main())` guard is copied verbatim.

**GTK-free violation guard (Landmine #5):** Module top of `gui.py` MUST have bare `import gi; gi.require_version(...)` — no try/except. If `gi` is absent on macOS the raw `ImportError` is the regression guard.

**Adwaita skeleton:** RESEARCH.md §Pattern 1 lines 270-302. The `AcerControlApp(Adw.Application)` subclass with `do_activate` fetching `self.props.active_window or MainWindow(application=self)` then `.present()` is verbatim from that section. Do NOT requote here; planner reads RESEARCH directly.

**Key invariants to copy from RESEARCH §Pattern 1:**
- `application_id="org.acercontrol.AcerControl"` (exact string — Phase 5 `Gio.Notification` requires this to match the `.desktop` basename)
- `flags=Gio.ApplicationFlags.DEFAULT_FLAGS` (NOT `FLAGS_NONE` — deprecated since GLib 2.74)

---

### `acercontrol/gui_window.py` (component/controller, probe → route → GTK signal handler)

**Primary analog — privileged action invocation:** `acercontrol/cli.py:233-256` — `cmd_set` lines for `run_privileged()` + `result.cancelled` + `result.returncode != 0` branches. The GUI signal handlers (`_on_disable_ppd_clicked`, `_on_reload_acer_wmi_clicked`) mirror this idiom exactly but surface `Adw.Toast` instead of `print()`.

```python
# acercontrol/cli.py:233-256
result = run_privileged(["acercontrol-setprofile", kernel_value])

if result.cancelled:
    if args.json:
        _emit({"cancelled": True}, "Authentication cancelled", as_json=True)
    else:
        print("Authentication cancelled.")
    return 0
if result.returncode == 127:
    sys.stderr.write(result.stderr or "elevation unavailable\n")
    ...
    return 1
if result.returncode != 0:
    sys.stderr.write(result.stderr or f"wrapper exit {result.returncode}\n")
    ...
    return 1
```

**Apply:** GUI handler replaces `print()` / `sys.stderr.write()` with `self._toast("Authentication cancelled.")` / `self._toast("Operation failed. See terminal for details.")` via `self._toast_overlay.add_toast(Adw.Toast.new(...))`. Re-probe via `self._route(probe())` on success (line 258 `read_profile()` read-back is analogous; Phase 3 re-probes instead).

**Secondary analog — probe consumption shape:** `acercontrol/features.py:99-200` — `probe()` returns `FeatureReport` with `.ok`, `.first_blocking_failure`, and the `.checks` tuple. The `_route(report)` method in `MainWindow` partitions by `c.severity == "blocking"`.

```python
# acercontrol/features.py:47-56 — the routing predicates
@property
def ok(self) -> bool:
    """True iff every 'blocking' check is present."""
    return all(c.present for c in self.checks if c.severity == "blocking")

@property
def first_blocking_failure(self) -> FeatureCheck | None:
    for c in self.checks:
        if c.severity == "blocking" and not c.present:
            return c
    return None
```

**Apply:** `_route(report)` uses `report.ok` and `report.first_blocking_failure` exactly as declared. No re-implementation of the severity logic in the GUI layer.

**Landmine #1 (Banner Pango-link — mandatory fallback):** The `Adw.Banner` in this window MUST NOT attempt Pango `<a href>` in its title. The "About power-profiles-daemon" affordance lives in `Adw.HeaderBar` primary menu instead. RESEARCH.md §Landmine #1 lines 507-531 documents this verbatim. Pattern assignment:

```python
# acercontrol/gui_window.py (sketch — primary menu wiring)
def _build_primary_menu(self) -> Gio.Menu:
    menu = Gio.Menu()
    menu.append("About power-profiles-daemon", "win.about-ppd")
    menu.append("About AcerControl", "win.about")
    self.add_action(self._make_action("about-ppd", lambda *_: show_ppd_explainer(self)))
    self.add_action(self._make_action("about", lambda *_: show_about(self)))
    return menu
```

Source: RESEARCH.md §Code Examples lines 726-740.

**Adwaita ToolbarView skeleton:** RESEARCH.md §Pattern 2 lines 312-339. `Adw.ToolbarView.add_top_bar(header)` + `set_content(toast_overlay)` + `Adw.ApplicationWindow.set_content(toolbar)`. Planner reads RESEARCH directly.

**`show_ppd_banner(force: bool = False)` API contract (Phase 4 carry-forward):**
- `force=True` overrides the in-session dismissed flag and calls `banner.set_revealed(True)`.
- Cold start: dismissed flag is in-memory only (`self._ppd_banner_dismissed = False`); a fresh launch always re-evaluates PPD state from `probe()`.

---

### `acercontrol/gui_status_pages.py` (component, factory-per-blocker)

**No direct in-repo analog.** The factory pattern (one function per probe key returning `Adw.StatusPage`) does not exist anywhere in the repo today.

**Adwaita skeleton:** RESEARCH.md §Pattern 4 lines 371-399. Copy the `acer_wmi_not_loaded()` factory function shape verbatim for all four blocker pages:
- `Adw.StatusPage()` → `set_icon_name()` → `set_title()` → `set_description()`
- `Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)` as the child container
- Primary `Gtk.Button` with `.suggested-action` + `.pill` style classes (where a remediation exists)
- `Refresh` `Gtk.Button` with `.flat` style class (on every blocker StatusPage)

**StatusPage copy matrix (per UI-SPEC table lines 157-176):**

| Factory function | Probe key | Icon | Has primary CTA | Polkit wrapper invoked |
|---|---|---|---|---|
| `acer_wmi_not_loaded(window)` | `acer_wmi module loaded` → `False` | `dialog-error-symbolic` | Yes — "Load module" | `acercontrol-reload-acer-wmi` |
| `predator_v4_disabled(window)` | `predator_v4 mode` → `False` | `dialog-warning-symbolic` | Yes — "Reload with predator_v4=1" | `acercontrol-reload-acer-wmi` |
| `platform_profile_missing(window)` | `platform_profile sysfs` → `False` | `dialog-error-symbolic` | No (read-only) | none |
| `no_acer_hwmon(window)` | `acer hwmon (fan+temp)` → `False` | `dialog-error-symbolic` | No (Refresh only) | none |

**Routing by name convention (from features.py check names):** The probe key string (`c.name`) from `FeatureReport.checks` is the dispatch key. The `_route` method in `gui_window.py` maps each check name to its factory function.

---

### `acercontrol/gui_banner.py` (component, PPD warning + Learn-more dialog)

**Analog — privileged action invocation:** same as `gui_window.py` — `acercontrol/cli.py:233-256`. The `_on_disable_ppd_clicked` handler is a direct translation of `cmd_set`'s `run_privileged` + cancelled/failed branching.

**Adwaita banner skeleton:** RESEARCH.md §Pattern 3 lines 349-365.

```python
# acercontrol/gui_banner.py key excerpt (from RESEARCH §Pattern 3)
banner = Adw.Banner.new(
    "power-profiles-daemon is running and will overwrite profile changes."
)
banner.set_button_label("Disable PPD")
banner.set_revealed(True)
banner.connect("button-clicked", window._on_disable_ppd_clicked)
banner.add_css_class("warning")
```

**Landmine #1 (mandatory — applied in this file):** Banner title MUST be plain text — NO Pango `<a href="learn-more">` markup. Setting `banner.use_markup = True` and embedding a link does not intercept clicks; the internal `GtkLabel` silently invokes `gtk_file_launcher_launch("learn-more")`. Source: RESEARCH.md §Landmine #1 lines 507-531, verified against libadwaita 1.5.4 source `adw-banner.c`.

**Dismissal in-memory flag pattern:**
```python
# gui_banner.py — in-session dismissed flag (CONTEXT decision #4)
# No config file. MainWindow holds: self._ppd_banner_dismissed = False
# Banner close-button callback:
def _on_banner_closed(self, *_):
    self._ppd_banner.set_revealed(False)
    self._ppd_banner_dismissed = True
```

**Learn-more dialog:** `Adw.Window` (modal, `transient_for=main_window`), 480×360 px. Built in this file per UI-SPEC lines 210-219. Body is a `Gtk.Label` with `wrap=True` and Pango markup permitted, or `Adw.PreferencesPage` with one `Adw.PreferencesGroup` (planner picks). NO external URL — embedded copy only.

---

### `acercontrol/gui_about.py` (component, About dialog + Diagnostics carve-out)

**Analog — probe JSON serialization:** `acercontrol/cli.py:82-117` — `cmd_status` builds a `probe→dict` structure and passes it to `json.dumps`. The About dialog's `set_debug_info()` call uses the same serialization idiom.

```python
# acercontrol/cli.py:82-117 — probe→dict shape (the diagnostic JSON source)
report = probe()
payload = {
    "probe": {
        "checks": [
            {
                "name": c.name,
                "present": c.present,
                "detail": c.detail,
                "fix": c.fix,
                "severity": c.severity,
            }
            for c in report.checks
        ],
        "ok": report.ok,
        "first_blocking_failure": (
            None if report.first_blocking_failure is None else {
                "name": report.first_blocking_failure.name,
                "fix":  report.first_blocking_failure.fix,
            }
        ),
        ...
    },
    ...
}
```

**Apply:** `gui_about.py` calls `probe()`, serializes the same dict shape with `json.dumps(..., indent=2)`, passes the string to `dialog.set_debug_info(json_str)`.

**Adwaita skeleton:** RESEARCH.md §Pattern 6 lines 440-461.

```python
# Key calls (from RESEARCH §Pattern 6)
dialog = Adw.AboutDialog()
dialog.set_application_name("AcerControl")
dialog.set_version(__version__)          # from acercontrol.__version__
dialog.set_developer_name("AcerControl contributors")
dialog.set_copyright("© 2026 AcerControl contributors")
dialog.set_license_type(Gtk.License.GPL_3_0)
dialog.set_debug_info(debug_json)        # GUI-08 carve-out: sole exempt zone
```

**Landmine #7 (parent required):** `dialog.present(parent_window)` — NOT `dialog.present()`. `Adw.Dialog.present()` requires a `parent` arg since libadwaita 1.5. Source: RESEARCH.md §Landmine #7 lines 691-696.

**HeaderBar primary menu wiring:** `gui_about.py` exports a `show_about(parent_window)` function; `gui_window.py` calls it from the primary-menu `win.about` action (see `_build_primary_menu` above).

**GUI-08 enforcement:** `gui_about.py` is the ONLY file where raw kernel profile value strings (`"low-power"`, `"balanced-performance"`, `"performance"` etc.) may appear in user-visible surfaces. The grep gate in `smoke_phase3.py` allowlists this file and asserts absence in the other four `gui*.py` files.

---

### `libexec/acercontrol-disable-ppd` (privileged wrapper, systemctl mask/unmask)

**Primary analog:** `libexec/acercontrol-manage-service` — **exact data-flow match.** The new wrapper shares the same (action × service) allowlist structure, argv validation, `subprocess.run(["systemctl", ...])` pattern, and EX_* exit codes.

**Allowlist literals** (from `acercontrol-manage-service:22-23`):

```python
# libexec/acercontrol-manage-service:22-23 — copy the pattern, change the values
ALLOWED_ACTIONS  = ("enable", "disable", "start", "stop")
ALLOWED_SERVICES = ("acer-performance.service",)
```

**Apply (new values for `acercontrol-disable-ppd`):**
```python
ALLOWED_ACTIONS  = ("mask", "unmask")
ALLOWED_SERVICES = ("power-profiles-daemon.service",)
```

**Argv validation** (from `acercontrol-manage-service:31-47`):

```python
# libexec/acercontrol-manage-service:31-47
def main(argv: list) -> int:
    if len(argv) != 3:
        sys.stderr.write(
            f"usage: {os.path.basename(argv[0] or 'acercontrol-manage-service')} "
            f"<action> <service>\n"
            f"  action  in {ALLOWED_ACTIONS}\n"
            f"  service in {ALLOWED_SERVICES}\n"
        )
        return EX_USAGE

    action, service = argv[1], argv[2]
    if action not in ALLOWED_ACTIONS:
        sys.stderr.write(f"refusing: action {action!r} not allowed\n")
        return EX_USAGE
    if service not in ALLOWED_SERVICES:
        sys.stderr.write(f"refusing: service {service!r} not allowed\n")
        return EX_USAGE
    if os.geteuid() != 0:
        sys.stderr.write("refusing: must run as root\n")
        return EX_NOPERM
```

**WR-03 carry-forward (CRITICAL DELTA from the analog):** `acercontrol-manage-service:62` collapses non-zero returncode to `EX_OSERR`:

```python
# acercontrol-manage-service:62 — this collapse is the WR-03 bug; do NOT copy
return result.returncode if result.returncode == 0 else EX_OSERR
```

The new `acercontrol-disable-ppd` MUST preserve the underlying returncode:

```python
# acercontrol-disable-ppd — correct pattern (no collapse)
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
return result.returncode
```

**Landmine #3 (idempotency — unique to this wrapper, no in-repo analog):** `systemctl mask` fails with a non-zero exit if the unit is already masked (symlink exists). The wrapper MUST probe state first:

```python
# libexec/acercontrol-disable-ppd — idempotency check (no analog in repo)
if action == "mask":
    probe = subprocess.run(
        ["systemctl", "is-enabled", service],
        capture_output=True, text=True, timeout=5,
    )
    if probe.stdout.strip() == "masked":
        sys.stderr.write(f"{service} already masked\n")
        return EX_OK  # idempotent — intent satisfied

elif action == "unmask":
    probe = subprocess.run(
        ["systemctl", "is-enabled", service],
        capture_output=True, text=True, timeout=5,
    )
    if probe.stdout.strip() != "masked":
        sys.stderr.write(f"{service} already unmasked\n")
        return EX_OK
```

Source: RESEARCH.md §Landmine #3 lines 567-618.

**systemctl subprocess** (copy from `acercontrol-manage-service:53-61`):

```python
# libexec/acercontrol-manage-service:53-61 — the subprocess shape to copy
try:
    result = subprocess.run(["systemctl", action, service],
        capture_output=True, text=True, timeout=20,
    )
except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
    sys.stderr.write(f"systemctl failed: {exc}\n")
    return EX_OSERR
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
```

**Apply delta:** `mask` invocation uses `["systemctl", "mask", "--now", service]` to stop the running unit immediately (not just create the symlink for next boot). Source: RESEARCH.md §Landmine #3 line 612.

**EX_* constants:** copy verbatim from any existing wrapper (e.g. `acercontrol-setprofile:43-46`):

```python
# libexec/acercontrol-setprofile:43-46
EX_OK    = 0
EX_USAGE = 64
EX_OSERR = 71
EX_NOPERM = 77
```

**Shebang and module bottom:** `#!/usr/bin/python3` (absolute — pkexec scrubs PATH) + `if __name__ == "__main__": sys.exit(main(sys.argv))`.

---

### `libexec/acercontrol-reload-acer-wmi` (privileged wrapper, modprobe)

**Analog A — argv validation shape:** `libexec/acercontrol-setprofile:49-66` — rigid `len(argv) != expected` check returning EX_USAGE. This wrapper takes NO extra argv (only the executable name in `sys.argv`), so the check is `len(argv) != 1`.

```python
# libexec/acercontrol-setprofile:49-66 — argv validation shape
def main(argv: list) -> int:
    if len(argv) != 2:            # <-- new wrapper uses != 1 (no positional args)
        sys.stderr.write(
            f"usage: {os.path.basename(argv[0] or 'acercontrol-setprofile')} "
            f"<kernel-value>\n"
        )
        return EX_USAGE
    ...
    if os.geteuid() != 0:
        sys.stderr.write(
            f"refusing: must run as root (effective uid {os.geteuid()})\n"
        )
        return EX_NOPERM
```

**Analog B — subprocess pattern:** `libexec/acercontrol-manage-service:53-59` — `subprocess.run` with `capture_output=True`, `text=True`, `timeout=20`, and `(FileNotFoundError, subprocess.TimeoutExpired)` handling.

**Two-step modprobe (no in-repo analog — flag for planner):** The unload → reload sequence is new. Use CONTEXT.md decision #2 verbatim:

```python
# libexec/acercontrol-reload-acer-wmi — no in-repo analog; from CONTEXT decision #2
subprocess.run(["/usr/sbin/modprobe", "-r", "acer_wmi"], check=True, timeout=20)
subprocess.run(["/usr/sbin/modprobe", "acer_wmi", "predator_v4=1"], check=True, timeout=20)
```

Note: absolute `/usr/sbin/modprobe` path — pkexec scrubs `$PATH`. `check=True` propagates subprocess failure as `CalledProcessError`; wrap both calls in `try: ... except subprocess.CalledProcessError as exc: sys.stderr.write(...); return EX_OSERR`.

**EX_* constants, shebang, module bottom:** identical to `acercontrol-disable-ppd` above.

---

### `data/org.acercontrol.policy` (edit — append 2 new `<action>` blocks)

**Analog:** `data/org.acercontrol.policy:34-44` — the `org.acercontrol.manage-service` action block is the closest shape (message is verb-on-system-service, same three `<defaults>` children, same `<annotate>` pattern).

```xml
<!-- data/org.acercontrol.policy:34-44 — shape to copy for the 2 new actions -->
  <action id="org.acercontrol.manage-service">
    <description>Manage the AcerControl boot service</description>
    <message>Authentication is required to manage the AcerControl boot service</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/libexec/acercontrol/acercontrol-manage-service</annotate>
  </action>
```

**New Action 4 — `org.acercontrol.disable-ppd`:**
- `<message>Authentication is required to disable power-profiles-daemon</message>`
- `<annotate>` exec.path: `/usr/libexec/acercontrol/acercontrol-disable-ppd`
- Same `<defaults>` block (auth_admin / auth_admin / auth_admin_keep)

**New Action 5 — `org.acercontrol.reload-acer-wmi`:**
- `<message>Authentication is required to reload the acer_wmi kernel module</message>`
- `<annotate>` exec.path: `/usr/libexec/acercontrol/acercontrol-reload-acer-wmi`
- Same `<defaults>` block

**Insert point:** before the closing `</policyconfig>` on line 46. The file must have exactly 5 `<action>` blocks after the edit (Phase 3 smoke asserts `len(t.findall('action')) == 5`).

---

### `acercontrol/privilege.py` (edit — extend `WRAPPER_NAMES` tuple)

**Analog:** `acercontrol/privilege.py:26-30` — the existing `WRAPPER_NAMES` tuple (note: real symbol has NO leading underscore, unlike what some docs say).

```python
# acercontrol/privilege.py:26-30 — current tuple; extend by 2 entries
WRAPPER_NAMES = (
    "acercontrol-setprofile",
    "acercontrol-set-boot-profile",
    "acercontrol-manage-service",
)
```

**Apply:** append the 2 new wrapper names:

```python
WRAPPER_NAMES = (
    "acercontrol-setprofile",
    "acercontrol-set-boot-profile",
    "acercontrol-manage-service",
    "acercontrol-disable-ppd",       # Phase 3 — PPD mask/unmask
    "acercontrol-reload-acer-wmi",   # Phase 3 — acer_wmi module reload
)
```

No other change to `privilege.py`. Resolution logic in `resolve_wrapper()` is unchanged; it already walks `_WRAPPER_DIRS` and `$ACERCONTROL_DEV/libexec/` for any name in `WRAPPER_NAMES`.

---

### `pyproject.toml` (edit — uncomment GUI entry)

**Analog:** Phase 2 already added the `[project.scripts]` section and left the GUI line as a comment (per Phase 2 PATTERNS.md lines 268-276):

```toml
# current state in pyproject.toml (Phase 2 left this commented)
[project.scripts]
acercontrol = "acercontrol.cli:main"
# acercontrol-gui = "acercontrol.gui:main"   # Phase 3 adds this
```

**Apply (uncomment — NOT append):**

```toml
[project.scripts]
acercontrol = "acercontrol.cli:main"
acercontrol-gui = "acercontrol.gui:main"
```

After this edit, `pip install -e .` (or `pip install -e . --force-reinstall` for existing installs) registers the `acercontrol-gui` console-script entry point at `~/.local/bin/acercontrol-gui`.

**Landmine #4:** Devs who already ran `pip install -e .` after Phase 2 must re-install to register the new entry. The smoke asserts entry-point registration via `importlib.metadata`. Source: RESEARCH.md §Landmine #4 lines 622-628.

---

### `acercontrol/features.py` (edit — 3 severity values — Landmine #2 fix)

**Analog:** the exact 3 lines being changed in `acercontrol/features.py`.

**Surgical 3-line diff:**

```python
# BEFORE — line 148 (acer hwmon severity):
        severity="warning",  # GUI renders "—" placeholders rather than refusing to load

# AFTER:
        severity="blocking",  # no acer hwmon → full StatusPage, not a banner

# BEFORE — line 158 (coretemp severity):
        severity="info",  # CPU package temp is nice-to-have, not blocking

# AFTER:
        severity="warning",  # coretemp missing surfaces as a banner

# BEFORE — line 194 (blacklist severity):
        severity="blocking" if blacklist else "info",

# AFTER:
        severity="warning" if blacklist else "info",  # blacklist → banner, not full StatusPage
```

**Why this patch exists:** CONTEXT decision #3's routing table specifies acer hwmon missing as a blocker and blacklist detected as a warning; the current features.py has these reversed. If not patched, the GUI misroutes three of seven probe outcomes silently. Source: RESEARCH.md §Landmine #2 lines 532-566.

**Coordination:** `acercontrol/features.py` is stdlib-only — the patch can be verified cross-platform by `tools/smoke_phase3.py` without GTK.

---

### `tools/smoke_phase3.py` (smoke-runner)

**Analog:** `tools/smoke_phase2.py` — **the entire file is the analog.** Structure, `run()` helper shape, `main()` outer guard, and failure accumulator are all copied.

**`run()` helper** (copy from `tools/smoke_phase2.py:32-69`):

```python
# tools/smoke_phase2.py:32-69 — the canonical run() shape with expect_rc + check_json_parses
def run(label: str, argv: list, *,
        expect_rc=0,
        stdin: str | None = None,
        env_extra: dict | None = None,
        check_json_parses: bool = False) -> bool:
    print(f"-> {label}")
    env = {**os.environ, "PYTHONPATH": PROJECT_ROOT}
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(argv, capture_output=True, text=True,
                           timeout=30, env=env, input=stdin)
    except Exception as e:  # noqa: BLE001 — runner must never raise
        print(f"  FAIL  runner exception: {type(e).__name__}: {e}")
        return False
    if expect_rc is not None and r.returncode != expect_rc:
        print(f"  FAIL  rc={r.returncode} (expected {expect_rc})")
        ...
        return False
    ...
    print(f"  PASS")
    return True
```

**`main()` failure accumulator** (copy from `tools/smoke_phase2.py:311-340`):

```python
# tools/smoke_phase2.py:311-340
def main() -> int:
    failures: list = []
    total = 0
    try:
        scenarios = build_scenarios()
        total = len(scenarios)
        for label, argv, opts in scenarios:
            if not run(label, argv, **opts):
                failures.append(label)
    except Exception as exc:  # noqa: BLE001 — outer guard
        print(f"FATAL: runner top-level exception: {type(exc).__name__}: {exc}")
        return 1

    passed = total - len(failures)
    print(f"--- Phase 3 smoke: {passed}/{total} passed ---")
    if failures:
        print(f"    failed: {', '.join(failures)}")
    return 1 if failures else 0
```

**`PROJECT_ROOT` + `PYTHONPATH` bootstrap** (copy from `tools/smoke_phase2.py:24-29`):

```python
# tools/smoke_phase2.py:24-29
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

**Policy XML check function:** `smoke_phase2.py:74-94` (`_three_actions_check_src`) becomes `_five_actions_check_src()` — same `ET.parse` + `findall('action')` shape, with `expected` list extended to 5 action IDs and the 2 new `exec.path` annotations asserted.

**New scenarios unique to Phase 3 (no Phase 2 analog — use RESEARCH.md §Validation Architecture lines 825-860):**
- Polkit policy XML has 5 actions (not 3)
- `acercontrol-disable-ppd start power-profiles-daemon.service` → exit 64
- `acercontrol-disable-ppd mask other.service` → exit 64
- `acercontrol-disable-ppd` (no argv) → exit 64
- `acercontrol-reload-acer-wmi unexpected_arg` → exit 64
- `import acercontrol.gui` raises `ImportError` or `ValueError` on macOS (Landmine #5 assertion — see RESEARCH.md §Landmine #5 lines 632-677)
- `tools/verify_no_gtk.py acercontrol/gui.py` exits ≥ 1 (sanity: gate works on GUI files)
- `features.py` severity assertions: `acer hwmon` == `"blocking"`, `coretemp hwmon` == `"warning"`, `acer_wmi not blacklisted` == `"warning"` when found (Landmine #2 verification)
- `acercontrol-gui` entry-point registered in `importlib.metadata` (Landmine #4)

**`--quick` flag:** Phase 3 smoke supports `--quick` (XML well-formed + wrapper argv rejection + ImportError assertion + bundler GTK-free regression). Full suite adds severity assertions + entry-point registration. Source: RESEARCH.md §Sampling Rate lines 849-852.

---

## Shared Patterns

### Shared 1 — Sysexits-style exit codes (64 / 71 / 77) in wrappers

**Source:** All three existing `libexec/*` wrappers (e.g. `acercontrol-setprofile:43-46`).

```python
# acercontrol-setprofile:43-46
EX_OK    = 0
EX_USAGE = 64
EX_OSERR = 71
EX_NOPERM = 77
```

**Apply to:** `libexec/acercontrol-disable-ppd` and `libexec/acercontrol-reload-acer-wmi`. Same literal constants at module top. Same EX_USAGE for allowlist rejection / bad argv; EX_OSERR for subprocess/OS failure; EX_NOPERM for non-root invocation.

### Shared 2 — `subprocess.run` + `timeout` + `(FileNotFoundError, TimeoutExpired)` triple

**Source:** `acercontrol/features.py:87-96` (`_ppd_active`) and `acercontrol-manage-service:53-59`.

**Apply to:** both new wrappers. `timeout=20` for systemctl/modprobe operations (same as `acercontrol-manage-service`). `capture_output=True, text=True`.

### Shared 3 — Absolute shebang + stdlib-only + no `acercontrol.*` imports in wrappers

**Source:** `libexec/acercontrol-setprofile:1,27-29` — `#!/usr/bin/python3` + `import os, sys` only.

```python
#!/usr/bin/python3
# ...docstring...
import os
import subprocess
import sys
```

**Apply to:** both new wrappers. pkexec scrubs PYTHONPATH; `from acercontrol.*` would fail until Phase 8 installs to `/usr/lib/python3/dist-packages/`.

### Shared 4 — GTK-free-by-construction: bare `import gi` at module top with NO try/except (Landmine #5)

**Source:** No in-repo analog (first GUI phase). This is the cross-cutting invariant for ALL 5 new `gui*.py` files.

```python
# acercontrol/gui.py (and all gui*.py) — module top
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402
```

**No try/except** wrapping these imports. On macOS without PyGObject, `import gi` raises `ImportError` loudly — the regression guard for the smoke test. Wrapping with try/except would silently load broken stubs and defeat the CI gate. Source: RESEARCH.md §Landmine #5 lines 632-677.

**Apply to:** `acercontrol/gui.py`, `gui_window.py`, `gui_status_pages.py`, `gui_banner.py`, `gui_about.py` — every GUI module.

### Shared 5 — `PROJECT_ROOT` + `PYTHONPATH` bootstrap for tools/

**Source:** `tools/smoke_phase2.py:24-29` (same shape as `smoke_phase1.py:24-29`).

```python
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
os.environ.setdefault("PYTHONPATH", PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
```

**Apply to:** `tools/smoke_phase3.py`.

### Shared 6 — `run_privileged()` + `PrivilegedResult.cancelled` pattern from GUI signal handlers

**Source:** `acercontrol/cli.py:233-256` (`cmd_set` — the canonical `run_privileged` invocation + result branch structure).

**Apply to:** `acercontrol/gui_window.py` (`_on_reload_acer_wmi_clicked`) and `acercontrol/gui_banner.py` (`_on_disable_ppd_clicked`). Replace `print()` / `sys.stderr.write()` with `self._toast_overlay.add_toast(Adw.Toast.new(...))`. Replace `return 0/1` with GTK-idiomatic handler exit (no return needed; callback returns `None`).

---

## No Analog Found

| New File / Sub-pattern | Why No Analog | Direction |
|---|---|---|
| `acercontrol/gui_status_pages.py` (factory-per-blocker function shape) | No factory pattern exists in the repo today; no GTK/Adwaita code exists at all | Use RESEARCH.md §Pattern 4 lines 371-399 verbatim as the factory template |
| `Adw.ToolbarView` 3-region layout in `gui_window.py` | First GUI code in the repo | Use RESEARCH.md §Pattern 2 lines 312-339 verbatim |
| `Adw.Application` subclass in `gui.py` | First GUI code in the repo | Use RESEARCH.md §Pattern 1 lines 270-302 verbatim |
| `Adw.AboutDialog.set_debug_info()` call in `gui_about.py` | First GUI code in the repo | Use RESEARCH.md §Pattern 6 lines 440-461 verbatim |
| `Adw.Banner` construction in `gui_banner.py` | First GUI code in the repo | Use RESEARCH.md §Pattern 3 lines 349-365 verbatim |
| Two-step modprobe in `acercontrol-reload-acer-wmi` | No modprobe invocation anywhere in repo today | Use CONTEXT.md decision #2 verbatim (RESEARCH.md also documents) |
| Idempotency `is-enabled` pre-check in `acercontrol-disable-ppd` | No is-enabled probe in existing wrappers | Use RESEARCH.md §Landmine #3 lines 578-613 verbatim |

---

## Metadata

**Analog search scope:** `acercontrol/*.py` (7 files fully read), `libexec/*` (3 wrapper files fully read), `data/org.acercontrol.policy` (fully read), `tools/smoke_phase2.py` (fully read), `tools/smoke_phase1.py` (lines 24-29, 92-122, 125-179 from Phase 2 PATTERNS.md).

**Files scanned:** 12 source files (full read), plus RESEARCH.md §Patterns 1–6 (lines 262-464), §Landmines 1–7 (lines 507-697), §Validation Architecture (lines 813-859) targeted reads.

**Pattern extraction date:** 2026-05-16

**Verified analogs cited:**
- `acercontrol/cli.py:82-117` (probe→dict JSON serialization)
- `acercontrol/cli.py:233-256` (`run_privileged` + `result.cancelled` + `returncode != 0`)
- `acercontrol/cli.py:480-487` (`main()` entry-point shape)
- `acercontrol/features.py:47-56` (`FeatureReport.ok` + `first_blocking_failure` routing predicates)
- `acercontrol/features.py:82-96` (`subprocess.run` + timeout + defensive exceptions)
- `acercontrol/features.py:148` (acer hwmon severity — Landmine #2 patch target)
- `acercontrol/features.py:158` (coretemp severity — Landmine #2 patch target)
- `acercontrol/features.py:194` (blacklist severity — Landmine #2 patch target)
- `acercontrol/privilege.py:26-30` (`WRAPPER_NAMES` tuple — real symbol, no underscore prefix)
- `libexec/acercontrol-setprofile:43-46` (EX_* constants)
- `libexec/acercontrol-setprofile:49-66` (argv validation shape)
- `libexec/acercontrol-manage-service:22-23` (allowlist tuple structure)
- `libexec/acercontrol-manage-service:31-47` (argv validation + allowlist check)
- `libexec/acercontrol-manage-service:53-62` (subprocess systemctl pattern + WR-03 collapse to avoid)
- `data/org.acercontrol.policy:34-44` (`<action>` block template for new actions)
- `tools/smoke_phase2.py:24-29` (`PROJECT_ROOT` + `PYTHONPATH` bootstrap)
- `tools/smoke_phase2.py:32-69` (`run()` helper with `expect_rc` + `check_json_parses`)
- `tools/smoke_phase2.py:74-94` (`_three_actions_check_src` → becomes `_five_actions_check_src`)
- `tools/smoke_phase2.py:311-340` (`main()` failure accumulator + outer guard)

**Carry-forward to PLAN.md:**
1. **WR-03 delta** in `acercontrol-disable-ppd`: do NOT copy `manage-service:62`'s returncode collapse to EX_OSERR. Preserve `result.returncode` directly.
2. **Landmine #1** in `gui_banner.py` + `gui_window.py`: banner title is plain text; "About PPD" goes in HeaderBar primary menu, not in the banner title string.
3. **Landmine #2** in `features.py`: 3-line severity patch is Wave 0 — must land before any GUI routing test.
4. **Landmine #3** in `acercontrol-disable-ppd`: idempotency `is-enabled` pre-check before `mask` / `unmask` — smoke asserts "mask twice → exit 0 both times."
5. **WRAPPER_NAMES** (no leading underscore) — the real symbol in `privilege.py`.
6. **GUI module exemption from `verify_no_gtk.py`**: bundler input list (`profiles,sysfs,core,features,privilege,cli.py`) stays unchanged; new `gui*.py` are NOT added to bundler inputs. Verify_no_gtk invocation in `smoke_phase3.py` asserts gui files return ≥1 (sanity) while bundler inputs return 0.
