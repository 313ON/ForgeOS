from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.asset_tags import prefix_for_asset_type, validate_manual_tag
from app.services.ingestion import parse_systeminfo
from app.services.monitoring import (
    FAILED,
    PASS,
    WARNING,
    check_network,
    parse_ping_output,
    validate_network_host,
    validate_website_url,
)


class OperationsUpgradeTests(unittest.TestCase):
    def test_tag_prefix_mapping_and_manual_validation(self) -> None:
        self.assertEqual(prefix_for_asset_type("Laptop"), "LAP")
        self.assertEqual(prefix_for_asset_type("unknown"), "FOS")
        self.assertEqual(validate_manual_tag("lap-0012"), "LAP-0012")
        with self.assertRaises(ValueError):
            validate_manual_tag("not-a-tag")

    def test_import_parser_preserves_systeminfo_fields(self) -> None:
        parsed = parse_systeminfo(
            "Host Name: TEST-PC\nOS Name: Microsoft Windows 11\n"
            "Processor Core Count: 8\nLogical Processors: 16\nTotal Physical Memory: 16,384 MB"
        )
        self.assertEqual(parsed["hostname"], "TEST-PC")
        self.assertEqual(parsed["logical_cpu_cores"], 16)
        self.assertEqual(parsed["ram_mb"], 16384)

    def test_monitoring_validation_rejects_private_destinations(self) -> None:
        with self.assertRaises(ValueError):
            validate_website_url("http://127.0.0.1:8000")
        with self.assertRaises(ValueError):
            validate_network_host("bad host")
        self.assertEqual(validate_network_host("192.0.2.10"), "192.0.2.10")

    @patch("app.services.monitoring.subprocess.run")
    @patch("app.services.monitoring.platform.system", return_value="Windows")
    def test_network_check_maps_ping_success(self, platform_system, run) -> None:
        run.return_value.returncode = 0
        result = check_network("192.0.2.10", timeout=1)
        self.assertEqual(result.status, PASS)
        self.assertEqual(run.call_args.kwargs["shell"], False)
        self.assertEqual(run.call_args.args[0][:4], ["ping", "-n", "4", "-w"])

    @patch("app.services.monitoring.subprocess.run")
    @patch("app.services.monitoring.platform.system", return_value="Linux")
    def test_network_check_maps_ping_failure(self, platform_system, run) -> None:
        run.return_value.returncode = 1
        result = check_network("192.0.2.10", timeout=1)
        self.assertEqual(result.status, FAILED)
        self.assertEqual(run.call_args.args[0][:4], ["ping", "-c", "4", "-W"])

    def test_ping_parser_extracts_windows_metrics(self) -> None:
        metrics = parse_ping_output(
            "Reply from 192.0.2.10: bytes=32 time=10ms TTL=57\n"
            "Reply from 192.0.2.10: bytes=32 time=14ms TTL=57\n"
            "Packets: Sent = 2, Received = 2, Lost = 0 (0% loss)"
        )

        self.assertEqual(metrics.samples_ms, (10.0, 14.0))
        self.assertEqual(metrics.packets_sent, 2)
        self.assertEqual(metrics.packets_received, 2)
        self.assertEqual(metrics.packet_loss_percent, 0)
        self.assertEqual(metrics.average_latency_ms, 12)
        self.assertEqual(metrics.jitter_ms, 4)

    def test_ping_parser_extracts_unix_metrics(self) -> None:
        metrics = parse_ping_output(
            "64 bytes from 192.0.2.10: icmp_seq=1 ttl=57 time=8.25 ms\n"
            "64 bytes from 192.0.2.10: icmp_seq=2 ttl=57 time=10.75 ms\n"
            "2 packets transmitted, 2 received, 0% packet loss, time 1001ms"
        )

        self.assertEqual(metrics.samples_ms, (8.25, 10.75))
        self.assertEqual(metrics.packets_sent, 2)
        self.assertEqual(metrics.packets_received, 2)
        self.assertEqual(metrics.packet_loss_percent, 0)
        self.assertEqual(metrics.average_latency_ms, 9.5)
        self.assertEqual(metrics.jitter_ms, 2.5)

    @patch("app.services.monitoring.subprocess.run")
    @patch("app.services.monitoring.platform.system", return_value="Linux")
    def test_network_check_maps_partial_packet_loss_to_warning(
        self, platform_system, run
    ) -> None:
        run.return_value.returncode = 0
        run.return_value.stdout = (
            "64 bytes from 192.0.2.10: time=10 ms\n"
            "4 packets transmitted, 3 received, 25% packet loss"
        )

        result = check_network("192.0.2.10", timeout=1)

        self.assertEqual(result.status, WARNING)
        self.assertEqual(result.packets_sent, 4)
        self.assertEqual(result.packets_received, 3)
        self.assertEqual(result.packet_loss_percent, 25)


if __name__ == "__main__":
    unittest.main()
