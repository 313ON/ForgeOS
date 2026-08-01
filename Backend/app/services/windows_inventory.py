from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    """Captured result of a bounded local inventory command."""

    command: tuple[str, ...]
    output: str | None
    error: str | None


def collect_windows_inventory(timeout: float = 20.0) -> dict[str, object]:
    """Collect safe local Windows inventory facts using fixed command arguments."""
    result: dict[str, object] = {
        "hostname": socket.gethostname(),
        "os_name": platform.system(),
        "os_version": platform.version(),
        "manufacturer": None,
        "model": None,
        "cpu": platform.processor() or None,
        "ram_mb": None,
        "disks": [],
        "network_adapters": [],
        "ip_addresses": [],
        "mac_addresses": [],
        "errors": [],
    }
    if platform.system().casefold() != "windows":
        result["errors"] = ["Windows inventory commands are available only on Windows"]
        return result
    for key, command in (
        ("systeminfo", ("systeminfo", "/fo", "csv", "/nh")),
        ("hostname", ("hostname",)),
    ):
        captured = run_fixed_command(command, timeout)
        if captured.error:
            result["errors"].append(f"{key}: {captured.error}")
    return result


def run_fixed_command(command: tuple[str, ...], timeout: float = 20.0) -> CommandResult:
    """Run an allow-listed command without shell interpretation."""
    if not command or shutil.which(command[0]) is None:
        return CommandResult(command, None, "command unavailable")
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return CommandResult(command, None, str(error))
    if completed.returncode != 0:
        return CommandResult(command, completed.stdout, completed.stderr.strip() or "command failed")
    return CommandResult(command, completed.stdout, None)


def inventory_json(path: Path | None = None) -> str:
    """Return local inventory as stable JSON, optionally writing it to a file."""
    payload = json.dumps(collect_windows_inventory(), ensure_ascii=False, indent=2)
    if path is not None:
        path.write_text(payload + "\n", encoding="utf-8")
    return payload
