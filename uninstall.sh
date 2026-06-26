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
Usage: uninstall.sh [--dry-run] [--with-linuwu]

  --dry-run       Print what would happen without removing anything.
  --with-linuwu   Also remove the linuwu_sense DKMS install (blacklist,
                  modules-load.d entry, /usr/src tree, kernel module).
                  Stock acer_wmi will load again on next reboot.
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

remove_file() {
    local path="$1"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] rm -f %s\n' "$path"
        return 0
    fi
    rm -f "$path"
}

remove_dir() {
    local path="$1"
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] rm -rf %s\n' "$path"
        return 0
    fi
    rm -rf "$path"
}

require_root() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        return 0
    fi
    if [[ "$(id -u)" -eq 0 ]]; then
        return 0
    fi
    if command -v sudo >/dev/null 2>&1; then
        local args=()
        [[ "$DRY_RUN" -eq 1 ]] && args+=(--dry-run)
        [[ "$WITH_LINUWU" -eq 1 ]] && args+=(--with-linuwu)
        exec sudo bash "$ROOT_DIR/uninstall.sh" "${args[@]}"
    fi
    echo "AcerControl uninstall requires root. Re-run as root." >&2
    exit 1
}

main() {
    require_root

    # Reset fans to auto before removing the control infrastructure
    local fan_speed_path="/sys/devices/platform/acer-wmi/predator_sense/fan_speed"
    if [[ -w "$fan_speed_path" ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
            printf '[dry-run] reset fans to auto (0,0)\n'
        else
            echo "0,0" > "$fan_speed_path" || true
        fi
    fi

    # Stop and disable systemd services
    if command -v systemctl >/dev/null 2>&1; then
        run systemctl stop 'acer-performance@*.service' 2>/dev/null || true
        run systemctl stop acer-performance.service 2>/dev/null || true
        run systemctl disable acer-performance.service 2>/dev/null || true
    fi

    # Binaries (install.sh puts these in /usr/local/bin)
    remove_file /usr/local/bin/acercontrol
    remove_file /usr/local/bin/acercontrol-gui
    remove_file /usr/local/bin/acercontrol-tray

    # Python package tree
    remove_dir /usr/local/share/acercontrol

    # Privileged wrappers
    remove_dir /usr/libexec/acercontrol

    # System data files
    remove_file /usr/share/polkit-1/actions/org.acercontrol.policy
    remove_file /etc/systemd/system/acer-performance.service
    remove_file /etc/systemd/system/acer-performance@.service
    remove_file /usr/share/applications/org.acercontrol.AcerControl.desktop
    remove_file /usr/share/icons/hicolor/scalable/apps/org.acercontrol.AcerControl.svg
    remove_file /usr/share/icons/hicolor/symbolic/apps/org.acercontrol.AcerControl-symbolic.svg
    remove_file /etc/modprobe.d/99-acer-wmi.conf
    remove_file /usr/share/bash-completion/completions/acercontrol

    # Reload caches
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
        echo "update-initramfs not found; rebuild your initramfs manually to drop predator_v4=1."
    fi

    if [[ "$WITH_LINUWU" -eq 1 ]]; then
        local linuwu_args=()
        [[ "$DRY_RUN" -eq 1 ]] && linuwu_args+=(--dry-run)
        run bash "$ROOT_DIR/tools/teardown_linuwu.sh" "${linuwu_args[@]}"
    fi

    echo "AcerControl uninstalled."
    echo "Reboot to fully reset the kernel module state."
}

main "$@"
