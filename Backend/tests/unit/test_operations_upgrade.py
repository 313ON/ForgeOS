from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.asset_tags import prefix_for_asset_type, validate_manual_tag
from app.services.ingestion import parse_systeminfo
from app.services.monitoring import (
    FAILED,
    PASS,
    check_network,
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
    def test_network_check_maps_ping_success(self, run) -> None:
        run.return_value.returncode = 0
        result = check_network("192.0.2.10", timeout=1)
        self.assertEqual(result.status, PASS)
        self.assertEqual(run.call_args.kwargs["shell"], False)

    @patch("app.services.monitoring.subprocess.run")
    def test_network_check_maps_ping_failure(self, run) -> None:
        run.return_value.returncode = 1
        result = check_network("192.0.2.10", timeout=1)
        self.assertEqual(result.status, FAILED)


if __name__ == "__main__":
    unittest.main()
