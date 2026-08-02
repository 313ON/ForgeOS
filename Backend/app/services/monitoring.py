from __future__ import annotations

import ipaddress
import json
import socket
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import ssl
import platform

from ..domain.models import MonitoredTarget

PASS = "PASS"
WARNING = "WARNING"
FAILED = "FAILED"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CheckResult:
    """Normalized result from a website or network check."""

    status: str
    latency_ms: float | None
    message: str | None = None
    response_status_code: int | None = None
    ssl_metadata: dict[str, object] | None = None


def validate_website_url(value: str, allow_private: bool = False) -> str:
    """Validate an HTTP(S) URL and reject unsafe destinations by default."""
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Website URL must use http or https")
    if not allow_private and _host_is_private(parsed.hostname):
        raise ValueError("Private or local website destinations are disabled")
    return parsed.geturl()


def validate_network_host(value: str) -> str:
    """Validate an IP address or DNS hostname without shell interpretation."""
    host = value.strip()
    if not host or any(char.isspace() for char in host) or len(host) > 255:
        raise ValueError("Invalid network host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not all(label and label.replace("-", "").isalnum() for label in host.split(".")):
            raise ValueError("Invalid network host") from None
    return host


def check_target(target: MonitoredTarget) -> CheckResult:
    """Run one bounded check for a configured target."""
    if target.target_type == "website":
        return check_website(
            target.ip_or_host,
            timeout=target.timeout_sec,
            expected_status=target.expected_status_code,
            allow_private=target.allow_private_networks,
        )
    return check_network(target.ip_or_host, timeout=target.timeout_sec)


def check_website(
    url: str,
    timeout: float = 5.0,
    expected_status: int | None = None,
    allow_private: bool = False,
) -> CheckResult:
    """Check an HTTP(S) endpoint with safe TLS verification and SSRF validation."""
    try:
        validated = validate_website_url(url, allow_private)
        started = time.perf_counter()
        request = Request(validated, headers={"User-Agent": "ForgeOS-Monitor/1.0"}, method="GET")
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            latency = (time.perf_counter() - started) * 1000
            code = response.status
            expected = expected_status or 200
            result_status = PASS if code == expected else WARNING
            return CheckResult(result_status, latency, response_status_code=code)
    except Exception as error:
        return CheckResult(FAILED, None, str(error)[:500])


def check_network(host: str, timeout: float = 5.0) -> CheckResult:
    """Run a platform-compatible ping using an explicit subprocess argument list."""
    try:
        validated = validate_network_host(host)
        started = time.perf_counter()
        if platform.system().casefold() == "windows":
            command = ["ping", "-n", "1", "-w", str(max(1, int(timeout * 1000))), validated]
        else:
            command = ["ping", "-c", "1", "-W", str(max(1, int(timeout))), validated]
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout + 1, shell=False, check=False
        )
        latency = (time.perf_counter() - started) * 1000
        if completed.returncode == 0:
            return CheckResult(PASS, latency)
        return CheckResult(FAILED, latency, "ICMP ping failed")
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        return CheckResult(UNKNOWN, None, str(error)[:500])


def _host_is_private(hostname: str) -> bool:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    except OSError:
        return True
    return any(
        (address := ipaddress.ip_address(value)).is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        for value in addresses
    )


def json_metadata(value: dict[str, object] | None) -> str | None:
    """Serialize optional SSL metadata for persistence."""
    return json.dumps(value, ensure_ascii=False) if value else None


def now_utc() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)
