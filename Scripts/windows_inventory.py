"""Collect a structured local Windows inventory for ForgeOS enrollment."""

from __future__ import annotations

import argparse
from pathlib import Path

from Backend.app.services.windows_inventory import inventory_json


def main() -> int:
    """Run the inventory collector and print or save JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    print(inventory_json(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
