# Phase 8 Human UAT: Packaging

Run these checks on a Linux target, preferably a clean Ubuntu 24.04 VM. Local macOS smoke checks are source/static only and do not replace package build or install validation.

## Package Build Status

Status: Linux-pending as of 2026-05-23 on the current macOS execution host.

The following gates were not run locally because `dpkg-buildpackage`, `lintian`, and `dpkg` are unavailable on this host:

```bash
dpkg-buildpackage -us -uc -b
lintian ../acercontrol_*.deb
dpkg -c ../acercontrol_*.deb | grep '\.pyc$'
```

Do not mark PKG-05, PKG-06, or PKG-07 as Linux-passed until these commands and the clean VM install checks below succeed on Ubuntu 24.04 or a compatible Debian build target.

## Source/Static Checks

From the repository root:

```bash
python3 tools/smoke_phase8.py
python3 tools/smoke_phase1.py && python3 tools/smoke_phase2.py && python3 tools/smoke_phase3.py && python3 tools/smoke_phase4.py && python3 tools/smoke_phase5.py && python3 tools/smoke_phase6.py && python3 tools/smoke_phase7.py && python3 tools/smoke_phase8.py
```

## Debian Build

Install build tools:

```bash
sudo apt install debhelper dh-sequence-python3 pybuild-plugin-pyproject python3-all python3-setuptools dpkg-dev lintian
```

Build:

```bash
dpkg-buildpackage -us -uc -b
```

Lint:

```bash
lintian ../acercontrol_*.deb
```

No packaged bytecode:

```bash
dpkg -c ../acercontrol_*.deb | grep '\.pyc$' && echo "unexpected .pyc files" || echo "no .pyc files"
```

## Clean VM Install

On a clean Ubuntu 24.04 VM:

```bash
sudo apt install ./acercontrol_*.deb
```

Verify:

- `command -v acercontrol`
- `command -v acercontrol-gui`
- `command -v acercontrol-tray`
- GNOME Activities shows an AcerControl launcher with the custom icon.
- `/usr/share/applications/org.acercontrol.AcerControl.desktop` exists.
- `/usr/share/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg` exists.
- `/usr/share/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg` exists.
- `/usr/share/polkit-1/actions/org.acercontrol.policy` exists and contains the polkit wrapper annotations.
- `/usr/libexec/acercontrol/acercontrol-setprofile` exists.
- `/usr/libexec/acercontrol/acercontrol-set-boot-profile` exists.
- `/usr/libexec/acercontrol/acercontrol-manage-service` exists.
- `/usr/lib/systemd/system/acer-performance.service` exists.
- `/usr/lib/systemd/system/acer-performance@.service` exists.
- `/etc/modprobe.d/99-acer-wmi.conf` contains `options acer_wmi predator_v4=1`.

Run:

```bash
systemctl daemon-reload
update-desktop-database /usr/share/applications
gtk-update-icon-cache -f /usr/share/icons/hicolor
update-initramfs -u
```

Then reboot before judging `predator_v4=1` boot behavior.

## Manual Fallback Install

On a disposable manual-install target:

```bash
./install.sh --dry-run
./install.sh
```

Verify the fallback path installed:

- `/usr/local/bin/acercontrol`
- `/usr/local/bin/acercontrol-gui`
- `/usr/local/bin/acercontrol-tray`
- `/usr/local/share/acercontrol/acercontrol`
- `/usr/libexec/acercontrol`
- `/usr/share/polkit-1/actions/org.acercontrol.policy`
- `/etc/systemd/system/acer-performance.service`
- `/etc/systemd/system/acer-performance@.service`
- `/usr/share/applications/org.acercontrol.AcerControl.desktop`
- `/usr/share/icons/hicolor`
- `/etc/modprobe.d/99-acer-wmi.conf`

Run `acercontrol status` after reboot on target hardware.

## Hardware Notes

On PHN16-72, confirm:

- `acercontrol get` reports a user-facing profile.
- `acercontrol set turbo` triggers polkit and read-back succeeds.
- `acercontrol-gui` opens from GNOME Activities.
- `acercontrol-tray` exits cleanly if the AppIndicator watcher is unavailable, or shows the tray menu if available.
- Boot persistence is checked only after `update-initramfs -u` and reboot.
