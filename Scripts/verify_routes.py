"""Verify ForgeOS route registration without starting a server."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "Backend"))

from app.main import app


def main() -> int:
    """Check required routes and duplicate method/path pairs."""
    routes = {(method, route.path) for route in app.routes for method in getattr(route, "methods", set())}
    required = {
        ("GET", "/api/v1/people"),
        ("POST", "/api/v1/people"),
        ("GET", "/api/v1/assets"),
        ("POST", "/api/v1/assets"),
        ("PATCH", "/api/v1/users/{user_id}"),
        ("DELETE", "/api/v1/users/{user_id}"),
        ("POST", "/api/v1/ingest"),
        ("GET", "/api/targets"),
        ("POST", "/api/targets/{target_id}/check"),
        ("GET", "/api/v1/monitoring/history"),
        ("GET", "/api/v1/monitoring/targets"),
        ("POST", "/api/v1/monitoring/targets/{target_id}/check"),
    }
    missing = required - routes
    if missing:
        print(f"Missing routes: {sorted(missing)}")
        return 1
    duplicates = [
        item for item in routes if sum(1 for route in app.routes if item[0] in getattr(route, "methods", set()) and item[1] == route.path) > 1
    ]
    if duplicates:
        print(f"Duplicate routes: {sorted(set(duplicates))}")
        return 1
    print(f"Route verification passed: {len(routes)} method/path registrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
