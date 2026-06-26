#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
WITH_LINUWU=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)     DRY_RUN=1; shift ;;
        --with-linuwu) WITH_LINUWU=1; shift ;;
        --help|-h)
            cat <<'USAGE'
Usage: install.sh [--dry-run] [--with-linuwu]

  --dry-run       Print what would happen without making changes.
  --with-linuwu   Also install the linuwu_sense kernel module via DKMS.
                  Required for fan speed control (max/auto/manual).
                  Stock acer_wmi does not expose predator_sense/fan_speed.
USAGE
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 64 ;;
    esac
done

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
        # Re-launch as root, preserving the parsed flags
        local args=()
        [[ "$DRY_RUN" -eq 1 ]] && args+=(--dry-run)
        [[ "$WITH_LINUWU" -eq 1 ]] && args+=(--with-linuwu)
        exec sudo bash "$ROOT_DIR/install.sh" "${args[@]}"
    fi
    echo "AcerControl install requires root. Re-run as root." >&2
    exit 1
}

main() {
    cd "$ROOT_DIR"

    python3 tools/bundle_cli.py
    require_root

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

    if [[ "$WITH_LINUWU" -eq 1 ]]; then
        local linuwu_args=()
        [[ "$DRY_RUN" -eq 1 ]] && linuwu_args+=(--dry-run)
        # Reuse a local clone if it sits next to the repo, otherwise the
        # helper clones from GitHub itself.
        if [[ -d "$ROOT_DIR/../Linuwu-Sense/src" ]]; then
            linuwu_args+=("--src=$ROOT_DIR/../Linuwu-Sense")
        fi
        run bash "$ROOT_DIR/tools/setup_linuwu.sh" "${linuwu_args[@]}"
    else
        echo
        echo "Note: fan speed control (acercontrol fan set max|auto|manual N)"
        echo "      requires the linuwu_sense kernel module. Stock acer_wmi"
        echo "      does not expose predator_sense/fan_speed."
        echo "      Re-run with --with-linuwu, or:  sudo tools/setup_linuwu.sh"
    fi

    echo "AcerControl installed."
    echo "Please reboot before relying on the boot profile service."
    echo "Commands: acercontrol, acercontrol-gui, acercontrol-tray"
}

main "$@"
