from __future__ import annotations

import unittest

from app.services.extraction import extract_fields, extract_reports

DXDIGAG_SAMPLE = """
------------------
System Information
------------------
      Machine name: OPS-LAPTOP
 Operating System: Windows 11 Pro 64-bit (10.0, Build 22631)
         Processor: 13th Gen Intel(R) Core(TM) i7-1365U (12 CPUs), ~1.8GHz
            Memory: 16384MB RAM
              BIOS: 1.17.0
         Card name: Intel(R) Iris(R) Xe Graphics
        """

SYSTEMINFO_SAMPLE = (
    "Host Name: OFFICE-1\n"
    "OS Name: Microsoft Windows 11 Enterprise\n"
    "System Manufacturer: LENOVO\n"
    "System Model: 30GSCTO1WW\n"
    "System Serial Number: SN123\n"
    "IP Address: 192.0.2.10\n"
    "Total Physical Memory: 32,538 MB\n"
    "Processor Core Count: 16\n"
    "Logical Processors: 24\n"
    "Display Adapter: NVIDIA RTX A2000"
)

LINUX_SAMPLE = """static hostname: linuxbox
Operating System: Ubuntu 22.04 LTS
Architecture: x86_64
CPU op-mode(s): 32-bit, 64-bit
Model name: Intel(R) Xeon(R) Gold
CPU(s): 8
Thread(s) per core: 2
Core(s) per socket: 4
Socket(s): 1
Mem: 16384 512 16000
"""


class ExtractionProviderTests(unittest.TestCase):
    def test_dxdiag_candidates(self) -> None:
        result = extract_fields(DXDIGAG_SAMPLE, "DxDiag.txt")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.provider.id, "dxdiag")
        self.assertEqual(result.provider.sourceType, "windows")
        keys = {candidate.key for candidate in result.candidates}
        self.assertTrue({"hostname", "os_name", "cpu_name", "ram_mb", "gpu_name"} <= keys)
        self.assertTrue(all(candidate.source == "dxdiag" for candidate in result.candidates))

    def test_systeminfo_candidates(self) -> None:
        result = extract_fields(SYSTEMINFO_SAMPLE, "report.txt")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.provider.id, "systeminfo")
        keys = {candidate.key for candidate in result.candidates}
        self.assertTrue(
            {
                "hostname",
                "manufacturer",
                "model",
                "serial_number",
                "ip_address",
                "ram_mb",
                "cpu_cores",
                "logical_cpu_cores",
                "gpu_name",
            }
            <= keys
        )
        by_key = {candidate.key: candidate for candidate in result.candidates}
        self.assertEqual(by_key["cpu_cores"].value, 16)
        self.assertEqual(by_key["ram_mb"].value, 32538)

    def test_linux_candidates(self) -> None:
        result = extract_fields(LINUX_SAMPLE, "report.txt")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.provider.id, "linux")
        keys = {candidate.key for candidate in result.candidates}
        self.assertTrue(
            {"hostname", "os_name", "architecture", "cpu_cores", "logical_cpu_cores", "ram_mb"} <= keys
        )
        by_key = {candidate.key: candidate for candidate in result.candidates}
        self.assertEqual(by_key["cpu_cores"].value, 4)
        self.assertEqual(by_key["logical_cpu_cores"].value, 8)
        self.assertEqual(by_key["ram_mb"].value, 16384)

    def test_spec_target_mapping(self) -> None:
        result = extract_fields(LINUX_SAMPLE, "report.txt")
        assert result is not None
        targets = {candidate.key: candidate.target for candidate in result.candidates}
        self.assertEqual(targets["hostname"], "asset")
        self.assertEqual(targets["cpu_cores"], "spec")
        self.assertEqual(targets["logical_cpu_cores"], "spec")
        self.assertEqual(targets["architecture"], "spec")

    def test_unknown_report_returns_none(self) -> None:
        self.assertIsNone(extract_fields("hello world", "notes.txt"))

    def test_collector_primary_report(self) -> None:
        report = """
Host Name: COLLECTOR-PC
OS Name: Microsoft Windows 11 Pro
OS Version: 10.0.26100 Build 26100
System Manufacturer: Dell Inc.
System Model: Latitude 7450
System Serial Number: SERIAL-7
Processor Name: Intel(R) Core(TM) Ultra 7
Number of Cores: 16
Number of Logical Processors: 22
Total Physical Memory: 32768 MB
BIOS Version: 1.8.0
GPU Name: Intel(R) Graphics
IP Address: 192.0.2.55
"""
        result = extract_fields(report, "forgeos_system_report.txt")

        assert result is not None
        self.assertEqual(result.provider.id, "forgeos_collector")
        self.assertEqual(result.parsed_fields["hostname"], "COLLECTOR-PC")
        self.assertEqual(result.parsed_fields["logical_cpu_cores"], 22)

    def test_mixed_batch_keeps_valid_reports_and_warns_per_file(self) -> None:
        ipconfig = """
Windows IP Configuration
Ethernet adapter Ethernet:
   IPv4 Address. . . . . . . . . . . : 192.0.2.77
   Default Gateway . . . . . . . . . : 192.0.2.1
"""
        storage = """
Model        : NVMe Drive
SerialNumber : STORAGE-1
MediaType    : Fixed hard disk media
Size         : 1000204886016
"""
        result = extract_reports(
            [
                ("SYSTEMINFO.TXT", SYSTEMINFO_SAMPLE),
                ("ipconfig.txt", ipconfig),
                ("storage.log", storage),
                ("readme.txt", "not a hardware report"),
            ]
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.sources), 3)
        self.assertEqual(result.parsed_fields["hostname"], "OFFICE-1")
        self.assertEqual(result.parsed_fields["ip_address"], "192.0.2.10")
        self.assertTrue(any(issue.filename == "readme.txt" for issue in result.warnings))
        self.assertTrue(any(issue.filename == "storage.log" for issue in result.warnings))
        self.assertFalse(result.errors)

    def test_unsupported_batch_returns_structured_failure(self) -> None:
        result = extract_reports([("notes.log", "hello world")])

        self.assertFalse(result.success)
        self.assertFalse(result.sources)
        self.assertTrue(result.warnings)
        self.assertTrue(result.errors)

    def test_multiple_reports_can_be_combined(self) -> None:
        """Verify that independent report parsing produces candidates with source info."""
        dxdiag_result = extract_fields(DXDIGAG_SAMPLE, "DxDiag.txt")
        systeminfo_result = extract_fields(SYSTEMINFO_SAMPLE, "systeminfo.txt")
        linux_result = extract_fields(LINUX_SAMPLE, "linux_report.txt")

        assert dxdiag_result is not None
        assert systeminfo_result is not None
        assert linux_result is not None

        # Each provider should have its own candidates
        dxdiag_keys = {c.key for c in dxdiag_result.candidates}
        sysinfo_keys = {c.key for c in systeminfo_result.candidates}
        linux_keys = {c.key for c in linux_result.candidates}

        # All should have hostname
        self.assertIn("hostname", dxdiag_keys)
        self.assertIn("hostname", sysinfo_keys)
        self.assertIn("hostname", linux_keys)

        # Source should be correctly identified
        self.assertTrue(all(c.source == "dxdiag" for c in dxdiag_result.candidates))
        self.assertTrue(all(c.source == "systeminfo" for c in systeminfo_result.candidates))
        self.assertTrue(all(c.source == "linux" for c in linux_result.candidates))

        # Simulate frontend combining: all candidates should be mergeable
        all_candidates = (
            list(dxdiag_result.candidates)
            + list(systeminfo_result.candidates)
            + list(linux_result.candidates)
        )
        self.assertGreater(len(all_candidates), 10)  # plenty of fields total


if __name__ == "__main__":
    unittest.main()
