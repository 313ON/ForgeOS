from __future__ import annotations

import re
from typing import Any

from ..domain.schemas import ExtractCandidate, ExtractProvider, ExtractResponse
from .ingestion import EMPTY_RESULT, decode_report, detect_source, parse_dxdiag, parse_systeminfo

ASSET_FIELD_CANDIDATES: list[tuple[str, str, str]] = [
    ("hostname", "Hostname", "asset"),
    ("os_name", "Operating System", "asset"),
    ("os_version", "OS Version", "asset"),
    ("manufacturer", "Manufacturer", "asset"),
    ("model", "Model", "asset"),
    ("serial_number", "Serial Number", "asset"),
    ("cpu_name", "CPU", "asset"),
    ("ram_mb", "RAM (MB)", "asset"),
    ("gpu_name", "Graphics", "asset"),
    ("bios_version", "BIOS Version", "asset"),
    ("ip_address", "IP Address", "asset"),
    ("cpu_cores", "CPU Cores", "spec"),
    ("logical_cpu_cores", "Logical Cores", "spec"),
    ("architecture", "Architecture", "spec"),
]

_HIGH_CONFIDENCE = {"hostname", "os_name", "os_version", "cpu_name", "ram_mb", "architecture"}

PROVIDERS: dict[str, tuple[str, str]] = {
    "dxdiag": ("DxDiag (Windows)", "windows"),
    "systeminfo": ("System Info (Windows)", "windows"),
    "linux": ("Linux system report", "linux"),
}


def extract_fields(text: str, filename: str = "") -> ExtractResponse | None:
    """Run the matching offline provider and return candidate asset fields.

    Returns None when the report format is not recognized.
    """
    source = detect_source(filename, text) or ("linux" if _looks_like_linux(text) else None)
    if source is None:
        return None
    if source == "linux":
        parsed = parse_linux(text)
    elif source == "dxdiag":
        parsed = parse_dxdiag(text)
    else:
        parsed = parse_systeminfo(text)
    name, source_type = PROVIDERS[source]
    candidates: list[ExtractCandidate] = []
    for key, label, target in ASSET_FIELD_CANDIDATES:
        value = parsed.get(key)
        if value in (None, "", []):
            continue
        candidates.append(
            ExtractCandidate(
                key=key,
                label=label,
                value=value,
                confidence="high" if key in _HIGH_CONFIDENCE else "medium",
                target=target,  # type: ignore[arg-type]
                source=source,
            )
        )
    provider = ExtractProvider(id=source, name=name, sourceType=source_type, retentionPolicy="ephemeral")
    return ExtractResponse(provider=provider, candidates=candidates)


def _looks_like_linux(text: str) -> bool:
    markers = (
        "static hostname:",
        "operating system:",
        "cpu op-mode(s):",
        "cpu(s):",
        "model name:",
        "architecture:",
        "pretty_name=",
    )
    normalized = text.casefold()
    return any(marker in normalized for marker in markers)


def parse_linux(text: str) -> dict[str, Any]:
    """Best-effort structured hardware data from Linux text report output."""
    result = dict(EMPTY_RESULT)
    fields: dict[str, list[str]] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        normalized_key = " ".join(key.strip().casefold().split())
        normalized_value = " ".join(value.strip().split())
        if normalized_key and normalized_value:
            fields.setdefault(normalized_key, []).append(normalized_value)

    result["hostname"] = _first(fields, "static hostname", "hostname")
    os_name = _first(fields, "operating system") or _first(fields, "pretty_name")
    result["os_name"] = _strip_quotes(os_name)
    result["os_version"] = _first(fields, "kernel", "os kernel", "kernel release")
    result["architecture"] = _first(fields, "architecture")
    result["cpu_name"] = _first(fields, "model name", "cpu model")

    cpu_count = _match_int(_first(fields, "cpu(s)"), r"(\d+)")
    sockets = _match_int(_first(fields, "socket(s)"), r"(\d+)")
    cores_per_socket = _match_int(_first(fields, "core(s) per socket"), r"(\d+)")
    threads_per_core = _match_int(_first(fields, "thread(s) per core"), r"(\d+)")
    if cores_per_socket and sockets:
        result["cpu_cores"] = cores_per_socket * sockets
        if threads_per_core:
            result["logical_cpu_cores"] = cores_per_socket * sockets * threads_per_core
    if result["logical_cpu_cores"] is None and cpu_count:
        result["logical_cpu_cores"] = cpu_count
    if result["cpu_cores"] is None and cpu_count:
        result["cpu_cores"] = cpu_count

    result["ram_mb"] = _free_memory_total_mb(text)
    return result


def _free_memory_total_mb(text: str) -> int | None:
    """Parse total memory from `free -m` output (Mem: row, second token)."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.casefold().startswith("mem:"):
            continue
        tokens = stripped.split()
        if len(tokens) >= 2:
            return _parse_linux_size(tokens[1])
    return None


def _parse_linux_size(value: str) -> int | None:
    match = re.search(r"([\d.]+)\s*([kmgt]?i?b)?", value, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "mb").casefold()
    if unit.startswith("g"):
        return round(number * 1024)
    if unit.startswith("t"):
        return round(number * 1024 * 1024)
    if unit.startswith("k"):
        return round(number / 1024)
    return round(number)


def _first(fields: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = fields.get(key)
        if values:
            return values[0]
    return None


def _match_int(value: str | None, pattern: str) -> int | None:
    if not value:
        return None
    match = re.search(pattern, value, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _strip_quotes(value: str | None) -> str | None:
    if value:
        return value.strip('"').strip()
    return None
