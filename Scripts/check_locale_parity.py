from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def flattened_keys(value: Any, prefix: str = "") -> set[str]:
    """Return dotted keys for a nested locale mapping."""
    if not isinstance(value, dict):
        return {prefix}
    keys: set[str] = set()
    for key, child in value.items():
        child_prefix = f"{prefix}.{key}" if prefix else key
        keys.update(flattened_keys(child, child_prefix))
    return keys


def check_locale_pair(english_path: Path, persian_path: Path) -> bool:
    """Validate that two locale JSON files have exactly the same key set."""
    english = json.loads(english_path.read_text(encoding="utf-8"))
    persian = json.loads(persian_path.read_text(encoding="utf-8"))
    english_keys = flattened_keys(english)
    persian_keys = flattened_keys(persian)
    missing = sorted(english_keys - persian_keys)
    extra = sorted(persian_keys - english_keys)
    if missing or extra:
        print(f"Locale mismatch: {english_path} vs {persian_path}")
        if missing:
            print(f"  missing in Persian: {', '.join(missing)}")
        if extra:
            print(f"  extra in Persian: {', '.join(extra)}")
        return False
    return True


def main() -> int:
    """Check repository locale pairs and return a CI-friendly exit code."""
    root = Path(__file__).resolve().parents[1]
    pairs = (
        (root / "Backend/locales/en.json", root / "Backend/locales/fa.json"),
        (
            root / "Backend/app/static/i18n/en.json",
            root / "Backend/app/static/i18n/fa.json",
        ),
    )
    return 0 if all(check_locale_pair(*pair) for pair in pairs) else 1


if __name__ == "__main__":
    sys.exit(main())
