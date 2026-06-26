#!/usr/bin/env bash
# tools/teardown_linuwu.sh — remove the linuwu_sense DKMS install.
#
# Reverses setup_linuwu.sh: unloads the module, removes the DKMS package,
# drops the blacklist + modules-load.d files, rebuilds initramfs, and
# re-enables the stock acer_wmi driver.
#
# Usage:
#   sudo tools/teardown_linuwu.sh
#   sudo tools/teardown_linuwu.sh --dry-run

set -euo pipefail

DRY_RUN=0
DKMS_NAME="linuwu-sense"
DKMS_VER="1.0"
DKMS_SRC_DIR="/usr/src/${DKMS_NAME}-${DKMS_VER}"

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            sed -n '2,/^set/p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "unknown arg: $arg" >&2
            exit 64
            ;;
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

require_root() {
    if [[ "$DRY_RUN" -eq 1 ]]; then return 0; fi
    if [[ "$(id -u)" -eq 0 ]]; then return 0; fi
    echo "teardown_linuwu requires root; re-run with sudo." >&2
    exit 1
}

main() {
    require_root

    # 1. Reset fans to auto BEFORE removing the control sysfs
    local fan_speed=/sys/devices/platform/acer-wmi/predator_sense/fan_speed
    if [[ -w "$fan_speed" ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
            printf '[dry-run] reset fans to auto (0,0)\n'
        else
            echo "0,0" > "$fan_speed" || true
        fi
    fi

    # 2. Unload the module
    run modprobe -r linuwu_sense 2>/dev/null || true

    # 3. DKMS remove — best-effort
    if command -v dkms >/dev/null 2>&1; then
        if dkms status "${DKMS_NAME}/${DKMS_VER}" 2>/dev/null | grep -q .; then
            run dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all
        fi
    fi
    run rm -rf "$DKMS_SRC_DIR"

    # 4. Remove the boot-time autoload + blacklist
    run rm -f /etc/modprobe.d/blacklist-acer_wmi.conf
    run rm -f /etc/modules-load.d/linuwu_sense.conf

    # 5. Rebuild initramfs so the blacklist is dropped on next boot
    if command -v update-initramfs >/dev/null 2>&1; then
        run update-initramfs -u
    fi

    # 6. Restore stock acer_wmi
    run modprobe acer_wmi 2>/dev/null || true

    echo
    echo "linuwu_sense removed. Stock acer_wmi reloaded (fan control is no"
    echo "longer available — profile control still works)."
}

main
