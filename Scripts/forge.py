from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["PYTHONPATH"] = os.pathsep.join(
    filter(None, [str(PROJECT_ROOT), os.environ.get("PYTHONPATH", "")])
)

__version__ = "0.1.0"


def serve(host: str, port: int, reload: bool) -> int:
    import uvicorn

    uvicorn.run(
        "Backend.app.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge", description="ForgeOS command line interface")
    parser.add_argument("--version", action="version", version=f"forge {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="Run the ForgeOS API server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true", help="Reload on file changes")

    sub.add_parser("version", help="Print the ForgeOS version")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "serve":
        return serve(args.host, args.port, args.reload)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
