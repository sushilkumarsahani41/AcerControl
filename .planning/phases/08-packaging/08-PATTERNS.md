# Phase 8 Patterns: Packaging

**Phase:** 08 - Packaging  
**Generated:** 2026-05-23

## Existing Patterns to Reuse

### Smoke Runner Shape

Closest analogs:

- `tools/smoke_phase6.py`
- `tools/smoke_phase7.py`

Pattern:

- Use `PROJECT_ROOT = Path(__file__).resolve().parents[1]`.
- Keep all checks side-effect-free by default.
- Use `_read()`, `_non_comment_text()`, `_contains_all()`, `_assert_no_tokens()`, and `run()`.
- Support `--quick` for source/static checks that run before all files exist or before Linux build tools are available.
- Full mode may run additional local static checks, but must not mutate system state.

### Debian Packaging Source Gates

Implement as source/static checks in `tools/smoke_phase8.py`:

- Parse `debian/control` by paragraph/field enough to check tokens.
- Avoid invoking `dpkg-buildpackage` from smoke by default because this host may not be Linux/Noble.
- Use source checks for `debian/acercontrol.install`, `postinst`, `postrm`, `rules`, and `source/format`.

### Data Install Contract

Existing data roots:

- `data/org.acercontrol.policy`
- `data/acer-performance.service`
- `data/acer-performance@.service`

New data should follow application ID naming:

- `data/org.acercontrol.AcerControl.desktop`
- `data/99-acer-wmi.conf`
- `data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg`
- `data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg`

### Wrapper Install Contract

Existing wrappers live in `libexec/`:

- `acercontrol-setprofile`
- `acercontrol-set-boot-profile`
- `acercontrol-manage-service`
- `acercontrol-disable-ppd`
- `acercontrol-reload-acer-wmi`

Debian install rules should map them into:

- `usr/libexec/acercontrol/`

Manual install rules should map them into:

- `/usr/local/libexec/acercontrol/`

`acercontrol.privilege.resolve_wrapper()` already checks both `/usr/libexec/acercontrol` and `/usr/local/libexec/acercontrol`, so no code change is required for that split.

### Console Script Contract

`pyproject.toml` currently has:

- `acercontrol = "acercontrol.cli:main"`
- `acercontrol-gui = "acercontrol.gui:main"`

Phase 8 should add:

- `acercontrol-tray = "acercontrol.tray:main"`

The root `acercontrol_tray.py` shim can remain as a development/manual helper, but packaged installation should use the console-script name.

### App ID and Desktop Contract

The application ID is:

- `org.acercontrol.AcerControl`

The desktop file basename must match:

- `org.acercontrol.AcerControl.desktop`

The desktop file should include:

- `Name=AcerControl`
- `Exec=acercontrol-gui`
- `Icon=org.acercontrol.AcerControl`
- `Terminal=false`
- `Type=Application`
- `Categories=System;HardwareSettings;`

This is required for launcher visibility and Gio.Notification routing.

### Icon Contract

Color icon:

- source: `data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg`
- install: `usr/share/icons/hicolor/scalable/apps/`

Symbolic icon:

- source: `data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg`
- install: `usr/share/icons/hicolor/symbolic/apps/`
- should use `currentColor`
- should avoid raster images

### Modprobe Contract

Source:

- `data/99-acer-wmi.conf`

Content:

```text
options acer_wmi predator_v4=1
```

Install:

- `etc/modprobe.d/99-acer-wmi.conf`

Postinstall must explain that `update-initramfs -u` and reboot are needed for reliable initramfs-loaded module behavior.

## Forbidden Patterns

- No `stdeb`, `debmake`, Poetry, Hatch, or setuptools `package_data` for system data files.
- No tray dependencies in hard runtime `Depends:`.
- No `.pyc` entries in Debian install rules or fallback installer.
- No `curl`, `wget`, or `pip install` network setup in `install.sh`.
- No shell snippets in systemd units writing directly to `/sys/firmware/acpi/platform_profile`.
- No data install paths under legacy `/usr/share/pixmaps`.

## Verification Pattern

Per-task:

- `python3 tools/smoke_phase8.py --quick`
- targeted `python3 -m py_compile ...`
- previous phase smoke impacted by the change

Final:

```bash
python3 tools/smoke_phase8.py
python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py && python3 tools/smoke_phase7.py && python3 tools/smoke_phase8.py
```

Linux packaging UAT:

```bash
dpkg-buildpackage -us -uc -b
lintian ../acercontrol_*.deb
dpkg -c ../acercontrol_*.deb | grep '\.pyc$'
sudo apt install ./acercontrol_*.deb
```
