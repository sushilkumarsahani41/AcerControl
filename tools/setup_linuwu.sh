#!/usr/bin/env bash
# tools/setup_linuwu.sh — install the linuwu_sense kernel module via DKMS.
#
# linuwu_sense (https://github.com/0x7375646F/Linuwu-Sense) is a community
# drop-in replacement for the stock acer_wmi.ko that adds the
# predator_sense/fan_speed sysfs interface AcerControl uses for fan control.
# The stock acer_wmi module does not expose this file.
#
# Usage:
#   sudo tools/setup_linuwu.sh                  # clones from GitHub
#   sudo tools/setup_linuwu.sh --src=PATH       # uses local clone at PATH
#   sudo tools/setup_linuwu.sh --dry-run        # preview
#
# What it does:
#   1. Stages source at /usr/src/linuwu-sense-1.0/
#   2. Writes /usr/src/linuwu-sense-1.0/dkms.conf
#   3. dkms add + dkms install
#   4. Writes /etc/modprobe.d/blacklist-acer_wmi.conf
#   5. Writes /etc/modules-load.d/linuwu_sense.conf
#   6. update-initramfs -u
#   7. Unloads stock acer_wmi and loads linuwu_sense

set -euo pipefail

DRY_RUN=0
SRC=""
DKMS_NAME="linuwu-sense"
DKMS_VER="1.0"
DKMS_SRC_DIR="/usr/src/${DKMS_NAME}-${DKMS_VER}"
LINUWU_REPO="https://github.com/0x7375646F/Linuwu-Sense.git"

for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --src=*)   SRC="${arg#--src=}" ;;
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
    echo "setup_linuwu requires root; re-run with sudo." >&2
    exit 1
}

require_tool() {
    local tool="$1"
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "missing dependency: $tool" >&2
        case "$tool" in
            dkms)         echo "  sudo apt install dkms" >&2 ;;
            git)          echo "  sudo apt install git" >&2 ;;
            make)         echo "  sudo apt install build-essential" >&2 ;;
        esac
        exit 1
    fi
}

require_kernel_headers() {
    local kver
    kver="$(uname -r)"
    if [[ ! -d "/lib/modules/${kver}/build" ]]; then
        echo "kernel headers for ${kver} are missing." >&2
        echo "  sudo apt install linux-headers-${kver}" >&2
        echo "  (or:  sudo apt install linux-headers-generic-hwe-24.04)" >&2
        exit 1
    fi
}

clone_or_use_src() {
    if [[ -n "$SRC" ]]; then
        if [[ ! -f "$SRC/src/linuwu_sense.c" ]]; then
            echo "--src='$SRC' does not look like a Linuwu-Sense clone "
            echo "(missing src/linuwu_sense.c)." >&2
            exit 1
        fi
        return 0
    fi
    SRC="/tmp/Linuwu-Sense"
    if [[ -d "$SRC/.git" ]]; then
        echo "Reusing existing clone at $SRC"
        run git -C "$SRC" pull --ff-only || true
    else
        require_tool git
        run rm -rf "$SRC"
        run git clone --depth 1 "$LINUWU_REPO" "$SRC"
    fi
}

stage_source() {
    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf '[dry-run] stage source at %s\n' "$DKMS_SRC_DIR"
        return 0
    fi
    rm -rf "$DKMS_SRC_DIR"
    mkdir -p "$DKMS_SRC_DIR"
    cp -a "$SRC/src" "$SRC/Makefile" "$DKMS_SRC_DIR/"
    # Clear pre-built artifacts so DKMS does a clean build
    (cd "$DKMS_SRC_DIR/src" && rm -f \
        linuwu_sense.ko linuwu_sense.o linuwu_sense.mod \
        linuwu_sense.mod.c linuwu_sense.mod.o \
        modules.order Module.symvers .linuwu_sense.* 2>/dev/null) || true
    cat > "$DKMS_SRC_DIR/dkms.conf" <<'DKMS'
PACKAGE_NAME="linuwu-sense"
PACKAGE_VERSION="1.0"
BUILT_MODULE_NAME[0]="linuwu_sense"
BUILT_MODULE_LOCATION[0]="src"
DEST_MODULE_LOCATION[0]="/kernel/drivers/platform/x86"
AUTOINSTALL="yes"
MAKE[0]="make -C /lib/modules/${kernelver}/build M=${dkms_tree}/${PACKAGE_NAME}/${PACKAGE_VERSION}/build modules"
CLEAN="make -C /lib/modules/${kernelver}/build M=${dkms_tree}/${PACKAGE_NAME}/${PACKAGE_VERSION}/build clean"
DKMS
}

main() {
    require_root
    require_tool make
    require_tool dkms
    require_kernel_headers
    clone_or_use_src
    stage_source

    # Skip add if already added (idempotent re-runs)
    if dkms status "${DKMS_NAME}/${DKMS_VER}" 2>/dev/null | grep -q .; then
        echo "${DKMS_NAME}/${DKMS_VER} already registered with DKMS; rebuilding."
        run dkms remove -m "$DKMS_NAME" -v "$DKMS_VER" --all || true
    fi
    run dkms add -m "$DKMS_NAME" -v "$DKMS_VER"
    run dkms install -m "$DKMS_NAME" -v "$DKMS_VER" --force

    # Persist boot-time autoload + acer_wmi blacklist
    if [[ "$DRY_RUN" -eq 0 ]]; then
        cat > /etc/modprobe.d/blacklist-acer_wmi.conf <<'EOF'
# Installed by AcerControl setup_linuwu.sh.
# linuwu_sense provides predator_sense/fan_speed which stock acer_wmi does not.
# Without this blacklist, stock acer_wmi races linuwu_sense at boot and wins —
# the platform device gets registered without the predator_sense attribute group.
blacklist acer_wmi
EOF
        cat > /etc/modules-load.d/linuwu_sense.conf <<'EOF'
linuwu_sense
EOF
        rm -f /etc/modprobe.d/99-acer-wmi.conf  # legacy predator_v4=1 hint, no longer needed
    else
        printf '[dry-run] write /etc/modprobe.d/blacklist-acer_wmi.conf\n'
        printf '[dry-run] write /etc/modules-load.d/linuwu_sense.conf\n'
        printf '[dry-run] rm /etc/modprobe.d/99-acer-wmi.conf\n'
    fi

    if command -v update-initramfs >/dev/null 2>&1; then
        run update-initramfs -u
    fi

    # Hot-swap: unload stock and load linuwu_sense without rebooting
    run modprobe -r acer_wmi 2>/dev/null || true
    run modprobe linuwu_sense

    echo
    echo "linuwu_sense installed via DKMS — will auto-rebuild on kernel updates."
    if [[ "$DRY_RUN" -eq 0 ]]; then
        echo "Verify:  ls /sys/devices/platform/acer-wmi/predator_sense/"
    fi
}

main
