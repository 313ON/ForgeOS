from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

GIB = 1024**3
PROFILE_OFFICE_DESKTOP = "office_desktop"
PROFILE_LAPTOP = "laptop"
PROFILE_MINIMAL = "minimal"


@dataclass(frozen=True)
class HardwareInfo:
    hostname: str
    logical_cpu_cores: int
    ram_bytes: int
    platform: str

    @property
    def ram_gb(self) -> float:
        return round(self.ram_bytes / GIB, 1)


def _run_command(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _windows_logical_cpu_cores() -> int | None:
    output = _run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance Win32_Processor | "
            "Measure-Object NumberOfLogicalProcessors -Sum).Sum",
        ]
    )
    try:
        return int(output) if output else None
    except ValueError:
        return None


def _windows_ram_bytes() -> int | None:
    output = _run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
        ]
    )
    try:
        return int(output) if output else None
    except ValueError:
        return None


def _posix_ram_bytes() -> int | None:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return None
    return int(page_size * page_count)


def detect_hardware() -> HardwareInfo:
    hostname = socket.gethostname() or platform.node() or "unknown"
    logical_cpu_cores = os.cpu_count() or 1
    ram_bytes: int | None = None

    if platform.system() == "Windows":
        logical_cpu_cores = _windows_logical_cpu_cores() or logical_cpu_cores
        ram_bytes = _windows_ram_bytes()
    else:
        ram_bytes = _posix_ram_bytes()

    return HardwareInfo(
        hostname=hostname,
        logical_cpu_cores=max(1, logical_cpu_cores),
        ram_bytes=max(0, ram_bytes or 0),
        platform=platform.platform(),
    )


def classify_machine(hardware: HardwareInfo) -> str:
    normalized_hostname = hardware.hostname.casefold().replace("_", "-")
    office_hostname = normalized_hostname == "it-station"
    desktop_pattern = any(
        marker in normalized_hostname for marker in ("desktop", "workstation", "office")
    )

    if office_hostname or (desktop_pattern and hardware.logical_cpu_cores >= 12):
        return PROFILE_OFFICE_DESKTOP
    if hardware.logical_cpu_cores >= 4 and hardware.ram_bytes >= 8 * GIB:
        return PROFILE_LAPTOP
    return PROFILE_MINIMAL


def recommended_engine_config(hardware: HardwareInfo, profile: str) -> dict[str, Any]:
    detected_ram_gb = max(1, int(hardware.ram_bytes / GIB)) if hardware.ram_bytes else 1

    if profile == PROFILE_OFFICE_DESKTOP:
        engine = {
            "worker_count": min(6, max(2, hardware.logical_cpu_cores // 2)),
            "memory_soft_limit_mb": min(12288, max(4096, detected_ram_gb * 768)),
            "parallel_builds": True,
            "parallel_build_workers": min(10, max(2, hardware.logical_cpu_cores - 2)),
            "indexing_enabled": True,
            "indexing_worker_count": min(4, max(2, hardware.logical_cpu_cores // 3)),
            "indexing_memory_limit_mb": 2048,
        }
    elif profile == PROFILE_LAPTOP:
        engine = {
            "worker_count": min(2, max(1, hardware.logical_cpu_cores // 4)),
            "memory_soft_limit_mb": min(6144, max(3072, detected_ram_gb * 384)),
            "parallel_builds": False,
            "parallel_build_workers": 1,
            "indexing_enabled": True,
            "indexing_worker_count": 1,
            "indexing_memory_limit_mb": 1024,
        }
    else:
        engine = {
            "worker_count": 1,
            "memory_soft_limit_mb": min(2048, max(1024, detected_ram_gb * 256)),
            "parallel_builds": False,
            "parallel_build_workers": 1,
            "indexing_enabled": False,
            "indexing_worker_count": 0,
            "indexing_memory_limit_mb": 512,
        }

    return {
        "schema_version": 1,
        "profile": profile,
        "hardware": {
            **asdict(hardware),
            "ram_gb": hardware.ram_gb,
        },
        "engine": engine,
    }


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        current_value = merged.get(key)
        if isinstance(current_value, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current_value, value)
        else:
            merged[key] = value
    return merged


def load_local_override(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to load local override {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Local override {path} must contain a JSON object")
    return data


def build_system_config(local_override_path: Path | None = None) -> dict[str, Any]:
    hardware = detect_hardware()
    profile = classify_machine(hardware)
    config = recommended_engine_config(hardware, profile)
    if local_override_path is not None:
        config = _deep_merge(config, load_local_override(local_override_path))
    return config


def write_system_config(path: Path, config: Mapping[str, Any], force: bool = False) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(config, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return True
