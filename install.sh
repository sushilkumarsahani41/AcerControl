#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    shift
fi

run() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] %q' "$1"
        shift || true
        for arg in "$@"; do
            printf ' %q' "$arg"
        done
        printf '\n'
        return 0
    fi
    "$@"
}

write_file() {
    local path="$1"
    local mode="$2"
    local content="$3"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] install generated file %s mode %s\n' "$path" "$mode"
        return 0
    fi

    install -d -m 0755 "$(dirname "$path")"
    printf '%s\n' "$content" > "$path"
    chmod "$mode" "$path"
}

install_file() {
    local mode="$1"
    local source="$2"
    local target="$3"

    run install -D -m "$mode" "$source" "$target"
}

copy_tree() {
    local source="$1"
    local target="$2"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] copy tree %s -> %s\n' "$source" "$target"
        return 0
    fi

    rm -rf "$target"
    install -d -m 0755 "$(dirname "$target")"
    cp -a "$source" "$target"
    find "$target" -type d -exec chmod 0755 {} +
    find "$target" -type f -exec chmod 0644 {} +
}

require_root() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        return 0
    fi
    if [[ "$(id -u)" -eq 0 ]]; then
        return 0
    fi
    if command -v sudo >/dev/null 2>&1; then
        exec sudo bash "$ROOT_DIR/install.sh" "$@"
    fi
    echo "AcerControl install requires root. Re-run as root." >&2
    exit 1
}

main() {
    cd "$ROOT_DIR"

    python3 tools/bundle_cli.py
    require_root "$@"

    install_file 0755 dist/acercontrol /usr/local/bin/acercontrol
    copy_tree acercontrol /usr/local/share/acercontrol/acercontrol

    write_file /usr/local/bin/acercontrol-gui 0755 '#!/bin/sh
export PYTHONPATH=/usr/local/share/acercontrol${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m acercontrol.gui "$@"'

    write_file /usr/local/bin/acercontrol-tray 0755 '#!/bin/sh
export PYTHONPATH=/usr/local/share/acercontrol${PYTHONPATH:+:$PYTHONPATH}
exec python3 -m acercontrol.tray "$@"'

    run install -d -m 0755 /usr/libexec/acercontrol
    for wrapper in libexec/acercontrol-*; do
        install_file 0755 "$wrapper" "/usr/libexec/acercontrol/$(basename "$wrapper")"
    done

    install_file 0644 data/org.acercontrol.policy /usr/share/polkit-1/actions/org.acercontrol.policy
    install_file 0644 data/acer-performance.service /etc/systemd/system/acer-performance.service
    install_file 0644 data/acer-performance@.service /etc/systemd/system/acer-performance@.service
    install_file 0644 data/org.acercontrol.AcerControl.desktop /usr/share/applications/org.acercontrol.AcerControl.desktop
    install_file 0644 data/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg \
        /usr/share/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg
    install_file 0644 data/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg \
        /usr/share/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg
    install_file 0644 data/99-acer-wmi.conf /etc/modprobe.d/99-acer-wmi.conf
    install_file 0644 data/acercontrol.bash-completion \
        /usr/share/bash-completion/completions/acercontrol

    if command -v systemctl >/dev/null 2>&1; then
        run systemctl daemon-reload
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        run update-desktop-database /usr/share/applications
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        run gtk-update-icon-cache -f /usr/share/icons/hicolor
    fi
    if command -v update-initramfs >/dev/null 2>&1; then
        run update-initramfs -u
    else
        echo "update-initramfs not found; refresh your initramfs with your distribution tool."
    fi

    echo "AcerControl installed."
    echo "Please reboot before relying on predator_v4=1 or the boot profile service."
    echo "Commands: acercontrol, acercontrol-gui, acercontrol-tray"
}

main "$@"
