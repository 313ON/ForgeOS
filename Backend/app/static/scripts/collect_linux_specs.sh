#!/usr/bin/env bash
# ForgeOS Linux Spec Collector
# Generates plain-text hardware reports compatible with ForgeOS extraction parser.
#
# This script creates a '~/Desktop/Specs' folder (fallback to '~/Specs') and writes
# multiple plain-text reports that the ForgeOS backend parser can ingest:
#   - hostnamectl.txt      (hostnamectl output)
#   - lscpu.txt            (lscpu output)
#   - memory.txt           (free -b output)
#   - lsblk.txt            (lsblk -b output)
#   - uname.txt            (uname -a output)
#   - ip_link.txt          (ip link output)
#   - os_release.txt       (/etc/os-release)
#   - cpuinfo.txt          (/proc/cpuinfo)
#   - meminfo.txt          (/proc/meminfo)
#   - dmi.txt              (dmidecode -t system,baseboard,chassis,processor,memory -- requires root, optional)
#
# The reports are NOT sent anywhere; you upload them manually via the
# ForgeOS "Extract Asset Details" modal (Multiple Files input).
#
# NOTES:
# - Run in a terminal (no sudo required for most commands).
# - Output encoding is UTF-8.
# - Only plain-text formats already supported by the parser are generated.
# - dmidecode requires root; if not available, it's skipped with a notice.

set -euo pipefail

# Determine output directory: ~/Desktop/Specs (fallback to ~/Specs)
if [[ -d "$HOME/Desktop" ]]; then
    OUT_DIR="$HOME/Desktop/Specs"
else
    OUT_DIR="$HOME/Specs"
fi

mkdir -p "$OUT_DIR"
echo "Writing reports to: $OUT_DIR"

write_report() {
    local name="$1"
    local content="$2"
    local path="$OUT_DIR/$name"
    printf "%s\n" "$content" > "$path"
    echo "  ✓ $name"
}

# 1) hostnamectl
echo "Running hostnamectl..."
write_report "hostnamectl.txt" "$(hostnamectl 2>&1 || true)"

# 2) lscpu
echo "Running lscpu..."
write_report "lscpu.txt" "$(lscpu 2>&1 || true)"

# 3) free -b
echo "Running free -b..."
write_report "memory.txt" "$(free -b 2>&1 || true)"

# 4) lsblk -b
echo "Running lsblk -b..."
write_report "lsblk.txt" "$(lsblk -b -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL,SERIAL 2>&1 || true)"

# 5) uname -a
echo "Running uname -a..."
write_report "uname.txt" "$(uname -a 2>&1 || true)"

# 6) ip link
echo "Running ip link..."
write_report "ip_link.txt" "$(ip link show 2>&1 || true)"

# 7) /etc/os-release
echo "Reading /etc/os-release..."
write_report "os_release.txt" "$(cat /etc/os-release 2>&1 || true)"

# 8) /proc/cpuinfo
echo "Reading /proc/cpuinfo..."
write_report "cpuinfo.txt" "$(cat /proc/cpuinfo 2>&1 || true)"

# 9) /proc/meminfo
echo "Reading /proc/meminfo..."
write_report "meminfo.txt" "$(cat /proc/meminfo 2>&1 || true)"

# 10) dmidecode (optional, requires root)
if command -v dmidecode >/dev/null 2>&1; then
    echo "Running dmidecode (requires sudo)..."
    if sudo -n true 2>/dev/null; then
        write_report "dmi.txt" "$(sudo dmidecode -t system -t baseboard -t chassis -t processor -t memory 2>&1 || true)"
    else
        echo "  ⚠ dmidecode skipped (sudo not available without password)"
        write_report "dmi.txt" "dmidecode requires root privileges. Run manually: sudo dmidecode -t system -t baseboard -t chassis -t processor -t memory"
    fi
else
    echo "  ⚠ dmidecode not installed"
fi

# 11) lspci (optional, for GPU details)
if command -v lspci >/dev/null 2>&1; then
    echo "Running lspci..."
    write_report "lspci.txt" "$(lspci -v 2>&1 || true)"
fi

# 12) lsusb (optional)
if command -v lsusb >/dev/null 2>&1; then
    echo "Running lsusb..."
    write_report "lsusb.txt" "$(lsusb -v 2>&1 || true)"
fi

echo ""
echo "Done. Reports written to: $OUT_DIR"
echo "Upload ALL .txt files from this folder via ForgeOS 'Extract Asset Details' modal."