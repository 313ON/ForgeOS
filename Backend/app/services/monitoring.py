from __future__ import annotations

import ipaddress
import json
import re
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
    packets_sent: int | None = None
    packets_received: int | None = None
    packet_loss_percent: float | None = None
    min_latency_ms: float | None = None
    max_latency_ms: float | None = None
    jitter_ms: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    probe_source: str = "local"


@dataclass(frozen=True)
class PingMetrics:
    """Parsed ICMP observations from a bounded platform ping command."""

    samples_ms: tuple[float, ...]
    packets_sent: int | None
    packets_received: int | None
    packet_loss_percent: float | None

    @property
    def min_latency_ms(self) -> float | None:
        return min(self.samples_ms) if self.samples_ms else None

    @property
    def average_latency_ms(self) -> float | None:
        return sum(self.samples_ms) / len(self.samples_ms) if self.samples_ms else None

    @property
    def max_latency_ms(self) -> float | None:
        return max(self.samples_ms) if self.samples_ms else None

    @property
    def jitter_ms(self) -> float | None:
        if len(self.samples_ms) < 2:
            return None
        differences = [
            abs(current - previous)
            for previous, current in zip(self.samples_ms, self.samples_ms[1:], strict=False)
        ]
        return sum(differences) / len(differences)


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
        started_at = now_utc()
        started = time.perf_counter()
        request = Request(validated, headers={"User-Agent": "ForgeOS-Monitor/1.0"}, method="GET")
        with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            latency = (time.perf_counter() - started) * 1000
            completed_at = now_utc()
            code = response.status
            expected = expected_status or 200
            result_status = PASS if code == expected else WARNING
            return CheckResult(
                result_status,
                latency,
                response_status_code=code,
                packets_sent=1,
                packets_received=1,
                packet_loss_percent=0,
                min_latency_ms=latency,
                max_latency_ms=latency,
                jitter_ms=0,
                started_at=started_at,
                completed_at=completed_at,
            )
    except Exception as error:
        return CheckResult(
            FAILED,
            None,
            str(error)[:500],
            packets_sent=1,
            packets_received=0,
            packet_loss_percent=100,
            started_at=locals().get("started_at"),
            completed_at=now_utc(),
        )


def check_network(host: str, timeout: float = 5.0, packet_count: int = 4) -> CheckResult:
    """Run and parse a bounded multi-packet ICMP probe."""
    packet_count = min(5, max(3, packet_count))
    started_at = now_utc()
    try:
        validated = validate_network_host(host)
        if platform.system().casefold() == "windows":
            command = [
                "ping",
                "-n",
                str(packet_count),
                "-w",
                str(max(1, int(timeout * 1000))),
                validated,
            ]
        else:
            command = [
                "ping",
                "-c",
                str(packet_count),
                "-W",
                str(max(1, int(timeout))),
                validated,
            ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=(timeout * packet_count) + 2,
            shell=False,
            check=False,
        )
        output = completed.stdout if isinstance(completed.stdout, str) else ""
        metrics = parse_ping_output(output)
        completed_at = now_utc()
        if metrics.packets_received == 0 or (
            metrics.packets_received is None and completed.returncode != 0
        ):
            result_status = FAILED
            message = "ICMP ping failed"
        elif metrics.packets_sent is None or metrics.packets_received is None:
            result_status = PASS
            message = "Host responded, but packet statistics were unavailable"
        elif metrics.packets_received < metrics.packets_sent:
            result_status = WARNING
            message = "ICMP packet loss detected"
        else:
            result_status = PASS
            message = None
        return CheckResult(
            result_status,
            metrics.average_latency_ms,
            message,
            packets_sent=metrics.packets_sent,
            packets_received=metrics.packets_received,
            packet_loss_percent=metrics.packet_loss_percent,
            min_latency_ms=metrics.min_latency_ms,
            max_latency_ms=metrics.max_latency_ms,
            jitter_ms=metrics.jitter_ms,
            started_at=started_at,
            completed_at=completed_at,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        return CheckResult(
            UNKNOWN,
            None,
            str(error)[:500],
            packets_sent=packet_count,
            packets_received=0,
            packet_loss_percent=100,
            started_at=started_at,
            completed_at=now_utc(),
        )


def parse_ping_output(output: str) -> PingMetrics:
    """Parse RTT samples and packet counts from Windows or Unix ping output."""
    samples: list[float] = []
    for match in re.finditer(r"(?:time|زمان)\s*[=<]\s*(\d+(?:[.,]\d+)?)\s*ms", output, re.IGNORECASE):
        value = float(match.group(1).replace(",", "."))
        samples.append(0.5 if "<" in match.group(0) and value <= 1 else value)

    packets_sent = packets_received = None
    packet_loss_percent = None
    windows_counts = re.search(
        r"Sent\s*=\s*(\d+).*?Received\s*=\s*(\d+).*?Lost\s*=\s*(\d+)\s*\((\d+(?:[.,]\d+)?)%",
        output,
        re.IGNORECASE | re.DOTALL,
    )
    unix_counts = re.search(
        r"(\d+)\s+packets transmitted,\s*(\d+)\s+(?:packets )?received.*?(\d+(?:[.,]\d+)?)%\s*packet loss",
        output,
        re.IGNORECASE | re.DOTALL,
    )
    counts = windows_counts or unix_counts
    if counts:
        packets_sent = int(counts.group(1))
        packets_received = int(counts.group(2))
        packet_loss_percent = float(counts.group(4 if windows_counts else 3).replace(",", "."))

    return PingMetrics(
        samples_ms=tuple(samples),
        packets_sent=packets_sent,
        packets_received=packets_received,
        packet_loss_percent=packet_loss_percent,
    )


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
