from __future__ import annotations

import re
from typing import Any

from ..domain.schemas import (
    ExtractCandidate,
    ExtractIssue,
    ExtractProvider,
    ExtractResponse,
    ExtractSource,
)
from .ingestion import EMPTY_RESULT, detect_source, parse_report

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
    "forgeos_collector": ("ForgeOS Collector (Windows)", "windows"),
    "collector_ipconfig": ("ForgeOS Network Fragment", "windows"),
    "collector_memory": ("ForgeOS Memory Fragment", "windows"),
    "collector_storage": ("ForgeOS Storage Fragment", "windows"),
    "linux": ("Linux system report", "linux"),
}


def extract_fields(text: str, filename: str = "") -> ExtractResponse | None:
    """Run the matching offline provider and return candidate asset fields.

    Returns None when the report format is not recognized.
    """
    source = detect_source(filename, text) or ("linux" if _looks_like_linux(text) else None)
    if source is None:
        return None
    parsed = parse_linux(text) if source == "linux" else parse_report(source, text)
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
    return ExtractResponse(
        success=True,
        parsed_fields={
            key: value for key, value in parsed.items() if value not in (None, "", [])
        },
        sources=[
            ExtractSource(
                filename=filename or "report.txt",
                format=source,
                provider=provider,
                parsed_fields={
                    key: value for key, value in parsed.items() if value not in (None, "", [])
                },
            )
        ],
        unmapped=_unmapped_fields(text, parsed, filename),
        provider=provider,
        candidates=candidates,
    )


def extract_reports(reports: list[tuple[str, str]]) -> ExtractResponse:
    """Classify reports independently and merge recognized fields deterministically."""
    candidates: list[ExtractCandidate] = []
    sources: list[ExtractSource] = []
    warnings: list[ExtractIssue] = []
    errors: list[ExtractIssue] = []
    unmapped: dict[str, list[str]] = {}
    parsed_fields: dict[str, Any] = {}
    first_provider: ExtractProvider | None = None

    for filename, text in reports:
        result = extract_fields(text, filename)
        if result is None:
            warnings.append(
                ExtractIssue(filename=filename, message="Unsupported or unrecognized report fragment")
            )
            continue
        if first_provider is None:
            first_provider = result.provider
        sources.extend(result.sources)
        if result.unmapped:
            unmapped.update(result.unmapped)
        for key, value in result.parsed_fields.items():
            parsed_fields.setdefault(key, value)
        for candidate in result.candidates:
            candidates.append(candidate.model_copy(update={"source_file": filename}))
        if not result.candidates:
            warnings.append(
                ExtractIssue(
                    filename=filename,
                    message="Report recognized; no directly mapped asset fields were found",
                )
            )

    if not sources:
        errors.append(
            ExtractIssue(
                filename="batch",
                message="Unable to identify any supported report format",
            )
        )
    return ExtractResponse(
        success=bool(sources),
        parsed_fields=parsed_fields,
        sources=sources,
        warnings=warnings,
        unmapped=unmapped,
        errors=errors,
        provider=first_provider,
        candidates=candidates,
    )


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


def _unmapped_fields(
    text: str,
    parsed: dict[str, Any],
    filename: str,
) -> dict[str, list[str]]:
    mapped_values = {str(value).casefold() for value in parsed.values() if value not in (None, "")}
    keys: list[str] = []
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        normalized_key = " ".join(key.strip().split())
        normalized_value = " ".join(value.strip().split()).casefold()
        if normalized_key and normalized_value and normalized_value not in mapped_values:
            keys.append(normalized_key)
    unique_keys = list(dict.fromkeys(keys))[:50]
    return {filename or "report.txt": unique_keys} if unique_keys else {}


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
