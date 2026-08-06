from __future__ import annotations

import re
from typing import Literal

from forge.runtime.hardware import GIB, HardwareInfo, classify_machine

SourceType = Literal[
    "dxdiag",
    "systeminfo",
    "forgeos_collector",
    "collector_ipconfig",
    "collector_memory",
    "collector_storage",
]
ParsedSystemInfo = dict[str, str | int | None]

EMPTY_RESULT: ParsedSystemInfo = {
    "hostname": None,
    "manufacturer": None,
    "model": None,
    "serial_number": None,
    "os_name": None,
    "os_version": None,
    "cpu_name": None,
    "cpu_cores": None,
    "logical_cpu_cores": None,
    "ram_mb": None,
    "gpu_name": None,
    "bios_version": None,
    "ip_address": None,
    "storage_type": None,
    "storage_capacity": None,
}


def decode_report(content: bytes) -> str:
    """Decode common Windows report encodings without external dependencies."""
    if not content:
        return ""
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16")
    if b"\x00" in content[:256]:
        for encoding in ("utf-16-le", "utf-16-be"):
            try:
                return content.decode(encoding).lstrip("\ufeff")
            except UnicodeDecodeError:
                continue
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def detect_source(filename: str, text: str) -> SourceType | None:
    """Classify supported Windows reports using content, with filename as a hint."""
    normalized_name = filename.strip().casefold()
    normalized_text = text.lstrip("\ufeff \t\r\n").casefold()
    keys = set(_key_value_lines(text))

    dxdiag_markers = (
        "directx diagnostic tool",
        "dxdiag notes",
        "directx version:",
        "card name:",
    )
    if any(marker in normalized_text for marker in dxdiag_markers):
        return "dxdiag"
    if {"machine name", "operating system", "processor"} <= keys:
        return "dxdiag"

    collector_keys = {
        "host name",
        "processor name",
        "number of cores",
        "number of logical processors",
        "gpu name",
        "ip address",
    }
    if "forgeos system report" in normalized_text or len(keys & collector_keys) >= 3:
        return "forgeos_collector"

    systeminfo_keys = {
        "host name",
        "os name",
        "os version",
        "system manufacturer",
        "system model",
        "total physical memory",
        "processor(s)",
        "bios version",
    }
    if len(keys & systeminfo_keys) >= 2:
        return "systeminfo"

    if "windows ip configuration" in normalized_text or (
        "ipv4 address" in normalized_text and "default gateway" in normalized_text
    ):
        return "collector_ipconfig"
    if _looks_like_memory_fragment(normalized_name, normalized_text, keys):
        return "collector_memory"
    if _looks_like_storage_fragment(normalized_name, normalized_text, keys):
        return "collector_storage"

    colon_lines = sum(1 for line in text.splitlines() if ":" in line)
    if (
        ("systeminfo" in normalized_name or "forgeos_system_report" in normalized_name)
        and colon_lines >= 4
        and ("windows" in normalized_text or "bios" in normalized_text)
    ):
        return "systeminfo"
    return None


def parse_report(source: SourceType, text: str) -> ParsedSystemInfo:
    """Parse a supported report using the matching offline parser."""
    if source == "dxdiag":
        return parse_dxdiag(text)
    if source == "collector_ipconfig":
        return parse_ipconfig(text)
    if source == "collector_memory":
        return parse_memory_fragment(text)
    if source == "collector_storage":
        return parse_storage(text)
    return parse_systeminfo(text)


def parse_dxdiag(text: str) -> ParsedSystemInfo:
    """Parse best-effort structured hardware data from DxDiag text."""
    result = dict(EMPTY_RESULT)
    fields = _key_value_lines(text)

    result["hostname"] = _first(fields, "machine name")
    result["manufacturer"] = _first(fields, "system manufacturer")
    result["model"] = _first(fields, "system model")
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
    result["manufacturer"] = _first(fields, "system manufacturer")
    result["model"] = _first(fields, "system model")
    result["serial_number"] = _first(fields, "system serial number")
    result["ip_address"] = _first(fields, "ip address")
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
    if result["ip_address"] is None:
        result["ip_address"] = _first_ipv4(text)
    return result


def parse_ipconfig(text: str) -> ParsedSystemInfo:
    """Extract the first usable IPv4 address from an ipconfig fragment."""
    result = dict(EMPTY_RESULT)
    result["ip_address"] = _first_ipv4(text)
    return result


def parse_memory_fragment(text: str) -> ParsedSystemInfo:
    """Extract installed memory from collector memory output."""
    result = dict(EMPTY_RESULT)
    capacities = [
        int(value)
        for value in re.findall(r"(?im)^\s*capacity\s*[:=]\s*(\d+)\s*$", text)
    ]
    if capacities:
        result["ram_mb"] = round(sum(capacities) / 1024**2)
        return result
    fields = _key_value_lines(text)
    result["ram_mb"] = _parse_memory_mb(
        _first(fields, "total physical memory", "physical memory", "mem")
    )
    return result


def parse_storage(text: str) -> ParsedSystemInfo:
    """Parse storage inventory fragments from Windows storage reports."""
    result = dict(EMPTY_RESULT)
    fields = _key_value_lines(text)
    result["storage_type"] = _first(fields, "media type", "mediaType", "mediatype", "interface type")
    size_value = _first(fields, "size", "capacity")
    result["storage_capacity"] = _parse_memory_mb(size_value)
    result["model"] = _first(fields, "model", "model name", "disk model") or result["model"]
    result["serial_number"] = _first(fields, "serial number", "serialnumber", "serial_number") or result["serial_number"]
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


def _first_ipv4(text: str) -> str | None:
    for match in re.finditer(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])", text):
        address = match.group(1)
        octets = [int(part) for part in address.split(".")]
        if any(part > 255 for part in octets):
            continue
        if address.startswith(("127.", "169.254.")) or address == "0.0.0.0":
            continue
        return address
    return None


def _looks_like_memory_fragment(
    filename: str,
    text: str,
    keys: set[str],
) -> bool:
    has_memory_fields = "capacity" in keys and bool(
        {"manufacturer", "partnumber", "part number", "speed"} & keys
    )
    return has_memory_fields or (
        "memory" in filename
        and ("capacity" in text or "mem:" in text or "total physical memory" in text)
    )


def _looks_like_storage_fragment(
    filename: str,
    text: str,
    keys: set[str],
) -> bool:
    has_storage_fields = len(
        keys & {"model", "serialnumber", "serial number", "mediatype", "media type", "size"}
    ) >= 2
    has_lsblk_header = bool(re.search(r"(?im)^\s*name\s+size\s+type\b", text))
    return has_storage_fields or (
        any(hint in filename for hint in ("storage", "disk", "lsblk"))
        and (has_lsblk_header or "size" in text)
    )
