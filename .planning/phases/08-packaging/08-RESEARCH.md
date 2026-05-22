# Phase 8 Research: Packaging

**Phase:** 08 - Packaging  
**Researched:** 2026-05-23  
**Scope:** Debian packaging, install data, desktop/icon integration, manual fallback installer, and release verification for AcerControl v1.

## Local Sources Read

- `.planning/ROADMAP.md` - Phase 8 goal and success criteria.
- `.planning/REQUIREMENTS.md` - PKG-01 through PKG-11 plus TRAY-04 handoff.
- `.planning/research/STACK.md` - debhelper, pybuild, apt package names, icon, systemd, and desktop decisions.
- `.planning/research/ARCHITECTURE.md` - installed tree and Debian build/install/postinst sequence.
- `.planning/research/PITFALLS.md` - P7, P8, P15 packaging pitfalls and manual UAT checklist.
- `.planning/research/SUMMARY.md` - final build order and packaging architecture.
- `.planning/phases/07-tray-helper-hardware-compatibility/07-HUMAN-UAT.md` - TRAY-04 Recommends handoff.
- Current repo files: `pyproject.toml`, `data/`, `libexec/`, `tools/bundle_cli.py`, `tools/smoke_phase7.py`.

## Current Repo State

Existing:

- Python package and `pyproject.toml` with `acercontrol` and `acercontrol-gui` console scripts.
- `acercontrol/tray.py` and root `acercontrol_tray.py` shim from Phase 7.
- `data/org.acercontrol.policy` with current polkit actions.
- `data/acer-performance.service` and `data/acer-performance@.service`.
- `libexec/acercontrol-*` wrappers.
- CLI bundler and Phase 1-7 smoke runners.

Missing for packaging:

- `debian/` directory.
- `install.sh` fallback.
- `data/org.acercontrol.AcerControl.desktop`.
- `data/99-acer-wmi.conf`.
- hicolor app icons.
- Phase 8 smoke/build gates.
- `acercontrol-tray` install entry point in `pyproject.toml`.

## Packaging Strategy

Use hand-written Debian packaging:

- `debian/control`
- `debian/changelog`
- `debian/rules`
- `debian/source/format`
- `debian/copyright`
- `debian/acercontrol.install`
- `debian/acercontrol.postinst`
- `debian/acercontrol.postrm` if needed for cache refresh / purge cleanup

Build command:

```bash
dpkg-buildpackage -us -uc -b
```

Build dependencies:

- `debhelper-compat (= 13)`
- `dh-sequence-python3`
- `pybuild-plugin-pyproject`
- `python3-all`
- `python3-setuptools`

Runtime dependencies:

- `${python3:Depends}`
- `${misc:Depends}`
- `python3-gi`
- `python3-gi-cairo`
- `gir1.2-gtk-4.0`
- `gir1.2-adw-1`
- `policykit-1`
- `systemd`
- `desktop-file-utils`
- `hicolor-icon-theme`

Tray dependencies are optional:

- `Recommends: gnome-shell-extension-appindicator, gir1.2-ayatanaappindicator3-0.1`
- They must not be hard `Depends:`.

## Install Path Decisions

| Artifact | Source | Installed Path |
|---|---|---|
| Python package | `acercontrol/` | `/usr/lib/python3/dist-packages/acercontrol/` via pybuild |
| CLI | `[project.scripts] acercontrol` | `/usr/bin/acercontrol` |
| GUI | `[project.scripts] acercontrol-gui` | `/usr/bin/acercontrol-gui` |
| Tray | `[project.scripts] acercontrol-tray` | `/usr/bin/acercontrol-tray` |
| wrappers | `libexec/acercontrol-*` | `/usr/libexec/acercontrol/` |
| polkit policy | `data/org.acercontrol.policy` | `/usr/share/polkit-1/actions/` |
| systemd units | `data/acer-performance*.service` | `/usr/lib/systemd/system/` |
| desktop file | `data/org.acercontrol.AcerControl.desktop` | `/usr/share/applications/` |
| color icon | `data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg` | `/usr/share/icons/hicolor/scalable/apps/` |
| symbolic icon | `data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg` | `/usr/share/icons/hicolor/symbolic/apps/` |
| modprobe config | `data/99-acer-wmi.conf` | `/etc/modprobe.d/` |

## Postinstall / Postremove Hooks

`debian/acercontrol.postinst` should handle `configure`:

- `update-desktop-database -q || true`
- `gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true`
- `systemctl daemon-reload || true`
- print a clear `update-initramfs -u` + reboot note for `predator_v4=1`
- preserve `#DEBHELPER#`

`debian/acercontrol.postrm` can refresh caches and daemon state on `remove|purge`:

- `systemctl daemon-reload || true`
- `update-desktop-database -q || true`
- `gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true`
- preserve `#DEBHELPER#`

`dh_installsystemd` should own service maintscript behavior where possible.

## Manual Install Fallback

`install.sh` should be a root-aware, explicit fallback:

- Build or refresh `dist/acercontrol` using `tools/bundle_cli.py`.
- Copy `dist/acercontrol` to `/usr/local/bin/acercontrol`.
- Copy GUI/tray launchers to `/usr/local/bin/acercontrol-gui` and `/usr/local/bin/acercontrol-tray` as thin Python entry scripts.
- Copy wrappers to `/usr/local/libexec/acercontrol/`.
- Copy policy to `/usr/share/polkit-1/actions/`.
- Copy systemd units to `/etc/systemd/system/`.
- Copy desktop file to `/usr/share/applications/`.
- Copy icons to `/usr/share/icons/hicolor/...`.
- Copy `data/99-acer-wmi.conf` to `/etc/modprobe.d/`.
- Run `systemctl daemon-reload`, desktop/icon cache updates, and `update-initramfs -u` when available.
- Print reboot guidance.

## Required Smoke Coverage

Create `tools/smoke_phase8.py` with source/static checks safe on macOS:

- Phase 8 docs exist.
- `pyproject.toml` has `acercontrol`, `acercontrol-gui`, and `acercontrol-tray`.
- data files exist with required desktop/icon/modprobe tokens.
- `debian/control` has required build/runtime dependencies and tray `Recommends`.
- tray packages are absent from `Depends:`.
- `debian/acercontrol.install` maps all required data/wrapper files to correct install paths.
- `postinst` contains cache/daemon reload hooks and initramfs/reboot guidance.
- `debian/rules` is executable and invokes `dh`.
- `install.sh` contains expected copy paths and no `curl|wget|pip install` network flow.
- existing Phase 7 packaging contract passes once `debian/control` exists.
- no `.pyc` files are referenced by packaging/install rules.

Linux-only full build checks should be documented and run when available:

- `dpkg-buildpackage -us -uc -b`
- `lintian ../acercontrol_*.deb`
- `dpkg -c ../acercontrol_*.deb | grep '\.pyc$'` should be empty
- `sudo apt install ./acercontrol_*.deb` on clean Ubuntu 24.04 VM

## Plan Split

Phase 8 should be four plans:

1. `08-01` - Packaging smoke runner and integration metadata.
2. `08-02` - Desktop data, icons, modprobe snippet, install rules, Debian metadata.
3. `08-03` - Manual `install.sh` fallback and documentation/UAT checklist.
4. `08-04` - Debian build/lintian/VM verification closeout and roadmap/state completion.

## Open Questions for Execution

- Exact Noble package micro versions must be checked on the Linux target with `apt-cache policy`; do not pin versions in `debian/control` from this macOS host.
- The package name for polkit may differ on some derivatives, but project requirements explicitly call for `policykit-1`.
- `lintian` may warn about missing manpages for `/usr/bin/*`; warnings can be reviewed, but errors must be fixed.
- If `dpkg-buildpackage` is unavailable on the execution host, the executor should still complete source/static packaging and record Linux build UAT as pending.
