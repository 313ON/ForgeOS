from __future__ import annotations

import unittest

from app.services.extraction import extract_fields

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
