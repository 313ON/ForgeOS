from __future__ import annotations

import re
from typing import Literal

from forge.runtime.hardware import GIB, HardwareInfo, classify_machine

SourceType = Literal["dxdiag", "systeminfo"]
ParsedSystemInfo = dict[str, str | int | None]

EMPTY_RESULT: ParsedSystemInfo = {
    "hostname": None,
    "os_name": None,
    "os_version": None,
    "cpu_name": None,
    "cpu_cores": None,
    "logical_cpu_cores": None,
    "ram_mb": None,
    "gpu_name": None,
    "bios_version": None,
}


def decode_report(content: bytes) -> str:
    """Decode common Windows report encodings without external dependencies."""
    if not content:
        return ""
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return content.decode("utf-8", errors="replace")


def detect_source(filename: str, text: str) -> SourceType | None:
    """Detect whether a report is DxDiag or systeminfo output."""
    normalized_name = filename.casefold()
    normalized_text = text.casefold()
    if "dxdiag" in normalized_name or "dxdiag notes" in normalized_text:
        return "dxdiag"
    if "systeminfo" in normalized_name:
        return "systeminfo"
    if "system manufacturer:" in normalized_text or "os name:" in normalized_text:
        return "systeminfo"
    if "directx version:" in normalized_text or "card name:" in normalized_text:
        return "dxdiag"
    return None


def parse_report(source: SourceType, text: str) -> ParsedSystemInfo:
    """Parse a supported report using the matching offline parser."""
    if source == "dxdiag":
        return parse_dxdiag(text)
    return parse_systeminfo(text)


def parse_dxdiag(text: str) -> ParsedSystemInfo:
    """Parse best-effort structured hardware data from DxDiag text."""
    result = dict(EMPTY_RESULT)
    fields = _key_value_lines(text)

    result["hostname"] = _first(fields, "machine name")
    operating_system = _first(fields, "operating system")
    os_name, os_version = _split_windows_version(operating_system)
    result["os_name"] = os_name
    result["os_version"] = os_version

    processor = _first(fields, "processor")
    result["cpu_name"] = _clean_cpu_name(processor)
    result["logical_cpu_cores"] = _match_int(
        processor,
        r"\((\d+)\s+(?:cpus?|logical processors?)\)",
    )
    result["cpu_cores"] = _match_int(
        _first(fields, "processor core count", "core count"),
        r"(\d+)",
    )
    result["ram_mb"] = _parse_memory_mb(_first(fields, "memory", "available os memory"))
    result["gpu_name"] = _first(fields, "card name", "display device")
    result["bios_version"] = _first(fields, "bios")
    return result


def parse_systeminfo(text: str) -> ParsedSystemInfo:
    """Parse best-effort structured hardware data from systeminfo text."""
    result = dict(EMPTY_RESULT)
    fields = _key_value_lines(text)

    result["hostname"] = _first(fields, "host name", "hostname")
    result["os_name"] = _first(fields, "os name")
    result["os_version"] = _first(fields, "os version")
    result["bios_version"] = _first(fields, "bios version")
    result["ram_mb"] = _parse_memory_mb(
        _first(fields, "total physical memory", "physical memory")
    )
    result["cpu_cores"] = _match_int(
        _first(fields, "processor core count", "number of cores"),
        r"(\d+)",
    )
    result["logical_cpu_cores"] = _match_int(
        _first(fields, "logical processors", "number of logical processors"),
        r"(\d+)",
    )
    result["gpu_name"] = _first(
        fields,
        "display adapter",
        "video controller",
        "gpu name",
    )
    result["cpu_name"] = _systeminfo_processor_name(text, fields)
    return result


def suggest_hardware_profile(parsed: ParsedSystemInfo) -> str:
    """Classify parsed hardware through the canonical runtime classifier."""
    hostname = str(parsed.get("hostname") or "unknown")
    logical_cores = _positive_int(
        parsed.get("logical_cpu_cores") or parsed.get("cpu_cores")
    )
    ram_mb = _positive_int(parsed.get("ram_mb"), default=0)
    hardware = HardwareInfo(
        hostname=hostname,
        logical_cpu_cores=logical_cores,
        ram_bytes=ram_mb * 1024**2,
        platform=str(parsed.get("os_name") or "unknown"),
    )
    return classify_machine(hardware)


def _key_value_lines(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        normalized_key = " ".join(key.strip().casefold().split())
        normalized_value = " ".join(value.strip().split())
        if normalized_key and normalized_value:
            fields.setdefault(normalized_key, []).append(normalized_value)
    return fields


def _first(fields: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = fields.get(key)
        if values:
            return values[0]
    return None


def _split_windows_version(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    version_match = re.search(r"\(([^)]*(?:build|version)[^)]*)\)", value, re.IGNORECASE)
    if version_match:
        name = value[: version_match.start()].strip()
        return name or value, version_match.group(1).strip()
    return value, None


def _clean_cpu_name(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(
        r"\s*\(\d+\s+(?:cpus?|logical processors?)\).*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()


def _match_int(value: str | None, pattern: str) -> int | None:
    if not value:
        return None
    match = re.search(pattern, value, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _parse_memory_mb(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"([\d.,]+)\s*(kb|mb|gb)?", value, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "mb").casefold()
    if unit == "gb":
        return round(number * 1024)
    if unit == "kb":
        return round(number / 1024)
    return round(number)


def _systeminfo_processor_name(
    text: str,
    fields: dict[str, list[str]],
) -> str | None:
    direct = _first(fields, "processor name", "cpu name")
    if direct:
        return direct
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^\[\d+\]:", stripped):
            value = stripped.split(":", 1)[1].strip()
            family_match = re.search(r"(Intel64|AMD64|ARM64)\s+Family.*", value)
            return family_match.group(0) if family_match else value
    return None


def _positive_int(value: object, default: int = 1) -> int:
    try:
        return max(default, int(value))
    except (TypeError, ValueError):
        return default
