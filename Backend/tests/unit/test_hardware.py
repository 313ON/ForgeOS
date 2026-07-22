from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from forge.runtime.hardware import (
    GIB,
    HardwareInfo,
    PROFILE_LAPTOP,
    PROFILE_MINIMAL,
    PROFILE_OFFICE_DESKTOP,
    build_system_config,
    classify_machine,
    recommended_engine_config,
    write_system_config,
)


class HardwareConfigTests(unittest.TestCase):
    @staticmethod
    def hardware(hostname: str, cores: int, ram_gb: int) -> HardwareInfo:
        return HardwareInfo(hostname, cores, ram_gb * GIB, "test")

    def test_it_station_is_office_desktop(self) -> None:
        self.assertEqual(
            classify_machine(self.hardware("IT-STATION", 12, 16)),
            PROFILE_OFFICE_DESKTOP,
        )

    def test_typical_laptop_uses_laptop_profile(self) -> None:
        self.assertEqual(
            classify_machine(self.hardware("NIMA-LAPTOP", 4, 16)),
            PROFILE_LAPTOP,
        )

    def test_low_resource_machine_uses_minimal_profile(self) -> None:
        self.assertEqual(
            classify_machine(self.hardware("UNKNOWN", 2, 4)),
            PROFILE_MINIMAL,
        )

    def test_laptop_profile_disables_parallel_builds(self) -> None:
        config = recommended_engine_config(
            self.hardware("NIMA-LAPTOP", 4, 16),
            PROFILE_LAPTOP,
        )

        self.assertEqual(config["engine"]["worker_count"], 1)
        self.assertFalse(config["engine"]["parallel_builds"])
        self.assertEqual(config["engine"]["indexing_worker_count"], 1)

    def test_local_override_is_deep_merged(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            override_path = Path(temporary_directory) / "system.local.json"
            override_path.write_text(
                json.dumps(
                    {
                        "engine": {"worker_count": 1},
                        "local": {"note": "thermal mode"},
                    }
                ),
                encoding="utf-8",
            )
            with patch(
                "forge.runtime.hardware.detect_hardware",
                return_value=self.hardware("IT-STATION", 12, 16),
            ):
                config = build_system_config(override_path)

        self.assertEqual(config["engine"]["worker_count"], 1)
        self.assertTrue(config["engine"]["parallel_builds"])
        self.assertEqual(config["local"]["note"], "thermal mode")

    def test_existing_config_is_not_overwritten_without_force(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "system.generated.json"
            output_path.write_text('{"existing": true}\n', encoding="utf-8")

            written = write_system_config(output_path, {"replacement": True})
            content = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertFalse(written)
        self.assertEqual(content, {"existing": True})


if __name__ == "__main__":
    unittest.main()
