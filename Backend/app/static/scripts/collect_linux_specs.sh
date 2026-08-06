#!/usr/bin/env bash
# ForgeOS Linux Spec Collector
# Creates a parser-ready report plus supporting diagnostics. Nothing is uploaded.

set -u

NO_PAUSE=0
if [[ "${1:-}" == "--no-pause" ]]; then
    NO_PAUSE=1
fi

if [[ -d "$HOME/Desktop" ]]; then
    OUT_DIR="$HOME/Desktop/ForgeOS-Specs"
else
    OUT_DIR="$HOME/ForgeOS-Specs"
fi

SUCCEEDED=0
FAILED=0
mkdir -p "$OUT_DIR"

write_report() {
    local name="$1"
    local content="$2"
    printf "%s\n" "$content" > "$OUT_DIR/$name"
    SUCCEEDED=$((SUCCEEDED + 1))
    printf "  [OK] %s\n" "$name"
}

run_report() {
    local name="$1"
    local label="$2"
    shift 2
    printf "Collecting %s...\n" "$label"
    local content
    if content="$("$@" 2>&1)" && [[ -n "$content" ]]; then
        write_report "$name" "$content"
    else
        FAILED=$((FAILED + 1))
        printf "  [FAILED] %s - command unavailable or returned no data\n" "$name" >&2
    fi
}

value_after_colon() {
    local key="$1"
    local input="$2"
    printf "%s\n" "$input" | awk -F: -v wanted="$key" '
        tolower($1) == tolower(wanted) {
            sub(/^[[:space:]]+/, "", $2)
            print $2
            exit
        }
    '
}

printf "\nForgeOS Linux Spec Collector\n"
printf "Output: %s\n\n" "$OUT_DIR"

HOSTNAMECTL_OUTPUT="$(hostnamectl 2>/dev/null || true)"
LSCPU_OUTPUT="$(lscpu 2>/dev/null || true)"
OS_NAME="$(. /etc/os-release 2>/dev/null; printf "%s" "${PRETTY_NAME:-Unknown Linux}")"
HOST_NAME="$(hostnamectl --static 2>/dev/null || hostname 2>/dev/null || printf "unknown")"
KERNEL="$(uname -r 2>/dev/null || printf "unknown")"
ARCHITECTURE="$(uname -m 2>/dev/null || printf "unknown")"
CPU_MODEL="$(value_after_colon "Model name" "$LSCPU_OUTPUT")"
CPU_COUNT="$(value_after_colon "CPU(s)" "$LSCPU_OUTPUT")"
SOCKETS="$(value_after_colon "Socket(s)" "$LSCPU_OUTPUT")"
CORES_PER_SOCKET="$(value_after_colon "Core(s) per socket" "$LSCPU_OUTPUT")"
THREADS_PER_CORE="$(value_after_colon "Thread(s) per core" "$LSCPU_OUTPUT")"
MEMORY_MB="$(awk '/^MemTotal:/ {printf "%.0f", $2 / 1024}' /proc/meminfo 2>/dev/null || true)"

PRIMARY_REPORT="$(
    cat <<EOF
Static hostname: $HOST_NAME
Operating System: $OS_NAME
Kernel: $KERNEL
Architecture: $ARCHITECTURE
Model name: ${CPU_MODEL:-Unknown}
CPU(s): ${CPU_COUNT:-0}
Socket(s): ${SOCKETS:-0}
Core(s) per socket: ${CORES_PER_SOCKET:-0}
Thread(s) per core: ${THREADS_PER_CORE:-0}
Mem: ${MEMORY_MB:-0} MB
EOF
)"
write_report "forgeos_system_report.txt" "$PRIMARY_REPORT"

[[ -n "$HOSTNAMECTL_OUTPUT" ]] && write_report "hostnamectl.txt" "$HOSTNAMECTL_OUTPUT" || FAILED=$((FAILED + 1))
[[ -n "$LSCPU_OUTPUT" ]] && write_report "lscpu.txt" "$LSCPU_OUTPUT" || FAILED=$((FAILED + 1))
run_report "memory.txt" "memory usage" free -m
run_report "storage.txt" "storage inventory" lsblk -b -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL,SERIAL
run_report "network.txt" "network interfaces" ip address show
run_report "uname.txt" "kernel details" uname -a

if command -v lspci >/dev/null 2>&1; then
    run_report "lspci.txt" "PCI devices" lspci -v
fi

if command -v dmidecode >/dev/null 2>&1; then
    if [[ "$EUID" -eq 0 ]]; then
        run_report "dmi.txt" "DMI hardware data" dmidecode -t system -t baseboard -t chassis -t processor -t memory
    else
        printf "  [INFO] dmi.txt skipped; rerun with sudo for firmware inventory.\n"
    fi
fi

printf "\nCollection complete: %s succeeded, %s failed.\n" "$SUCCEEDED" "$FAILED"
printf "Upload forgeos_system_report.txt to ForgeOS.\n"
printf "Reports folder: %s\n" "$OUT_DIR"

if [[ "$NO_PAUSE" -eq 0 && -t 0 ]]; then
    read -r -p "Press Enter to close"
fi

if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi
