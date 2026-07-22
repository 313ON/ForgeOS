from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from forge.runtime.hardware import build_system_config, write_system_config

DEFAULT_OUTPUT = PROJECT_ROOT / "config" / "system.generated.json"
DEFAULT_OVERRIDE = PROJECT_ROOT / "config" / "system.local.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect this ForgeOS node and generate a conservative engine configuration."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--override", type=Path, default=DEFAULT_OVERRIDE)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing generated configuration.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the recommended configuration without writing a file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = build_system_config(args.override)
        hardware = config["hardware"]
        print(f"[INFO] Hostname: {hardware['hostname']}")
        print(f"[INFO] Logical CPU cores: {hardware['logical_cpu_cores']}")
        print(f"[INFO] RAM: {hardware['ram_gb']} GB")
        print(f"[INFO] Selected profile: {config['profile']}")
        if args.override.exists():
            print(f"[INFO] Applied local override: {args.override}")

        if args.print_only:
            print(json.dumps(config, indent=2, sort_keys=True))
            return 0

        written = write_system_config(args.output, config, force=args.force)
        if written:
            print(f"[ OK ] Wrote configuration: {args.output}")
        else:
            print(f"[SKIP] Configuration already exists: {args.output}")
            print("[INFO] Use --force only when regeneration is explicitly required.")
        return 0
    except (OSError, TypeError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
