# Phase 8 Validation: Packaging

**Phase:** 08 - Packaging  
**Validated:** 2026-05-23  
**Scope:** Plan quality and executable verification strategy

## Requirement Coverage Matrix

| Requirement | Phase 8 Validation Target | Planned Plan | Coverage |
|---|---|---|---|
| PKG-01 | `pyproject.toml` PEP 621 + scripts for CLI/GUI/tray. | 08-01 | COVERED |
| PKG-02 | Hand-written `debian/` with debhelper compat 13, dh-sequence-python3, pybuild pyproject, dpkg-buildpackage path. | 08-02 | COVERED |
| PKG-03 | Runtime Depends and tray Recommends in `debian/control`; tray not hard Depends. | 08-02 | COVERED |
| PKG-04 | `postinst` refreshes desktop/icon caches and systemd daemon state. | 08-02 | COVERED |
| PKG-05 | `lintian` zero-error build gate or documented Linux UAT if tool unavailable. | 08-04 | COVERED |
| PKG-06 | `.deb` does not ship `.pyc` files. | 08-04 | COVERED |
| PKG-07 | Clean Ubuntu 24.04 VM install and launcher appears. | 08-04 | COVERED AS HUMAN UAT |
| PKG-08 | `install.sh` fallback copies binaries/data, registers systemd, runs initramfs flow. | 08-03 | COVERED |
| PKG-09 | Color and symbolic hicolor SVG icons. | 08-02 | COVERED |
| PKG-10 | Desktop file basename matches app ID and launcher fields are present. | 08-02 | COVERED |
| PKG-11 | `data/99-acer-wmi.conf` and postinstall initramfs/reboot guidance. | 08-02, 08-03 | COVERED |
| TRAY-04 | AppIndicator packages are `Recommends`, not hard `Depends`. | 08-02 | COVERED |

## Automated Gates

Local source/static:

```bash
python3 -m py_compile tools/smoke_phase8.py
python3 tools/smoke_phase8.py --quick
python3 tools/smoke_phase8.py
python3 tools/smoke_phase7.py
python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py && python3 tools/smoke_phase7.py && python3 tools/smoke_phase8.py
```

Linux package build:

```bash
dpkg-buildpackage -us -uc -b
lintian ../acercontrol_*.deb
dpkg -c ../acercontrol_*.deb | grep '\.pyc$'
```

Expected source/static checks:

- Debian metadata files exist.
- `debian/control` contains required build dependencies, runtime dependencies, and tray Recommends.
- tray packages are not hard runtime Depends.
- install rules map wrappers, policy, systemd units, desktop file, icons, and modprobe config.
- `postinst` contains desktop/icon/systemd refresh hooks and initramfs/reboot guidance.
- `install.sh` contains expected manual install paths and no network dependency installation.
- `tools/smoke_phase7.py` no longer skips TRAY-04 once `debian/control` exists.

## Manual UAT Gates

Run on Ubuntu 24.04 / PHN16-72 or a clean Ubuntu 24.04 VM:

1. Install build deps.
2. Build with `dpkg-buildpackage -us -uc -b`.
3. Install the generated `.deb`.
4. Confirm:
   - `acercontrol`, `acercontrol-gui`, and `acercontrol-tray` are on PATH.
   - GNOME Activities shows AcerControl without logout/login.
   - icon is the custom SVG, not fallback.
   - polkit action file exists at `/usr/share/polkit-1/actions/org.acercontrol.policy`.
   - wrappers exist at `/usr/libexec/acercontrol/`.
   - systemd unit files exist and daemon reload happened.
   - `/etc/modprobe.d/99-acer-wmi.conf` contains `options acer_wmi predator_v4=1`.
   - no `.pyc` files are shipped in the `.deb`.
5. Run `install.sh` fallback on a disposable manual-install target or dry-run mode if implemented.

## Plan Checker Result

**VERIFICATION PASSED**

Reasoning:

- Phase 8 is split by dependency order: smoke gates first, package data/metadata second, fallback/manual docs third, final build/UAT closeout last.
- Every PKG requirement maps to at least one planned artifact and a verification gate.
- Phase 7's TRAY-04 handoff is explicitly consumed in 08-02.
- Linux-only build/install validation is isolated from macOS-safe source/static checks.
