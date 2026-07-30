from __future__ import annotations

import unittest

from app.services.ingestion import (
    detect_source,
    parse_dxdiag,
    parse_systeminfo,
    suggest_hardware_profile,
)


class IngestionParserTests(unittest.TestCase):
    def test_empty_file_returns_empty_shape(self) -> None:
        parsed = parse_dxdiag("")

        self.assertEqual(
            set(parsed),
            {
                "hostname",
                "os_name",
                "os_version",
                "cpu_name",
                "cpu_cores",
                "logical_cpu_cores",
                "ram_mb",
                "gpu_name",
                "bios_version",
            },
        )
        self.assertTrue(all(value is None for value in parsed.values()))

    def test_malformed_file_is_tolerated(self) -> None:
        parsed = parse_systeminfo("not a report\n::::\nMemory: unknown MB\n[broken")

        self.assertIsNone(parsed["hostname"])
        self.assertIsNone(parsed["ram_mb"])
        self.assertEqual(suggest_hardware_profile(parsed), "minimal")

    def test_minimal_valid_dxdiag_sample(self) -> None:
        sample = """
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

        parsed = parse_dxdiag(sample)

        self.assertEqual(parsed["hostname"], "OPS-LAPTOP")
        self.assertEqual(parsed["os_name"], "Windows 11 Pro 64-bit")
        self.assertEqual(parsed["os_version"], "10.0, Build 22631")
        self.assertEqual(parsed["cpu_name"], "13th Gen Intel(R) Core(TM) i7-1365U")
        self.assertEqual(parsed["logical_cpu_cores"], 12)
        self.assertEqual(parsed["ram_mb"], 16384)
        self.assertEqual(parsed["gpu_name"], "Intel(R) Iris(R) Xe Graphics")
        self.assertEqual(parsed["bios_version"], "1.17.0")
        self.assertEqual(suggest_hardware_profile(parsed), "laptop")

    def test_real_world_systeminfo_lines(self) -> None:
        sample = """
Host Name:                 OFFICE-WORKSTATION-7
OS Name:                   Microsoft Windows 11 Enterprise
OS Version:                10.0.26100 N/A Build 26100
System Manufacturer:       LENOVO
System Model:              30GSCTO1WW
BIOS Version:              LENOVO S0MKT42A, 5/14/2025
Processor(s):              1 Processor(s) Installed.
                           [01]: Intel64 Family 6 Model 191 Stepping 2 GenuineIntel ~2400 Mhz
Processor Core Count:      16
Logical Processors:        24
Total Physical Memory:     32,538 MB
Display Adapter:           NVIDIA RTX A2000
        """

        parsed = parse_systeminfo(sample)

        self.assertEqual(parsed["hostname"], "OFFICE-WORKSTATION-7")
        self.assertEqual(parsed["os_name"], "Microsoft Windows 11 Enterprise")
        self.assertEqual(parsed["os_version"], "10.0.26100 N/A Build 26100")
        self.assertIn("Intel64 Family 6", parsed["cpu_name"])
        self.assertEqual(parsed["cpu_cores"], 16)
        self.assertEqual(parsed["logical_cpu_cores"], 24)
        self.assertEqual(parsed["ram_mb"], 32538)
        self.assertEqual(parsed["gpu_name"], "NVIDIA RTX A2000")
        self.assertEqual(
            suggest_hardware_profile(parsed),
            "office_desktop",
        )

    def test_source_detection_uses_filename_and_content(self) -> None:
        self.assertEqual(detect_source("DxDiag.txt", ""), "dxdiag")
        self.assertEqual(
            detect_source("report.txt", "OS Name: Microsoft Windows"),
            "systeminfo",
        )
        self.assertIsNone(detect_source("notes.txt", "hello world"))


if __name__ == "__main__":
    unittest.main()
