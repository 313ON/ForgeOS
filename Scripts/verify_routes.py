"""Verify ForgeOS route registration without starting a server."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "Backend"))

from app.main import app


def registered_routes() -> list[tuple[str, str]]:
    """Expand FastAPI routes, including lazily included routers."""
    pairs: list[tuple[str, str]] = []

    def collect(route: object) -> None:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if methods and path:
            pairs.extend((method, path) for method in methods)
            return
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            for child in original_router.routes:
                collect(child)

    for route in app.routes:
        collect(route)
    return pairs


def main() -> int:
    """Check required routes and duplicate method/path pairs."""
    registrations = registered_routes()
    routes = set(registrations)
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
    duplicates = [item for item in routes if registrations.count(item) > 1]
    if duplicates:
        print(f"Duplicate routes: {sorted(set(duplicates))}")
        return 1
    print(f"Route verification passed: {len(routes)} method/path registrations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
