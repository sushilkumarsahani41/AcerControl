# AcerControl

Linux performance control for Acer Predator/Nitro laptops (`acer_wmi` `predator_v4=1`).

Commands:

- `acercontrol` - zero-dependency CLI
- `acercontrol-gui` - GTK4/libadwaita desktop app
- `acercontrol-tray` - optional Ayatana AppIndicator tray helper

## Runtime Dependencies

Ubuntu 24.04 / Debian runtime packages:

```bash
sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1 systemd desktop-file-utils hicolor-icon-theme
```

Optional tray packages:

```bash
sudo apt install gnome-shell-extension-appindicator gir1.2-ayatanaappindicator3-0.1
```

## Build The Debian Package

Install packaging tools:

```bash
sudo apt install debhelper dh-sequence-python3 pybuild-plugin-pyproject python3-all python3-setuptools dpkg-dev lintian
```

Build and inspect:

```bash
dpkg-buildpackage -us -uc -b
lintian ../acercontrol_*.deb
dpkg -c ../acercontrol_*.deb | grep '\.pyc$' || echo "no .pyc files"
```

Install on a clean Ubuntu 24.04 VM:

```bash
sudo apt install ./acercontrol_*.deb
```

After install, AcerControl should appear in GNOME Activities, and the installed commands should be available on PATH.

## Manual Fallback Install

For manual/non-Debian installs from the repository root:

```bash
./install.sh
```

Preview without writing system files:

```bash
./install.sh --dry-run
```

The fallback installer builds `dist/acercontrol`, installs launchers under `/usr/local/bin`, installs privilege wrappers under `/usr/libexec/acercontrol`, installs the polkit policy, systemd units, desktop file, hicolor icons, and `/etc/modprobe.d/99-acer-wmi.conf`.

## Reboot Requirement

The modprobe file contains `options acer_wmi predator_v4=1`. Run `update-initramfs -u` and reboot before relying on boot-time profile persistence or the GUI failure checks for `predator_v4=1`.

See `.planning/PROJECT.md` for project overview, `.planning/ROADMAP.md` for build phases, and `.planning/phases/08-packaging/08-HUMAN-UAT.md` for the packaging UAT checklist.
