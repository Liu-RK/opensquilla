"""Serve a generated site directory locally for inspection.

Cross-platform via `python -m http.server` invoked as a subprocess so the
server runs in its own process and can be cleanly Ctrl-C'd.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a static site directory locally.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--bind",
        default="127.0.0.1",
        help="Address to bind (default 127.0.0.1; use 0.0.0.0 to expose on LAN)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.root.is_dir():
        print(f"error: root {args.root} not found or not a directory", file=sys.stderr)
        return 2
    print(f"serving {args.root} at http://{args.bind}:{args.port}")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "http.server",
            str(args.port),
            "--bind",
            args.bind,
        ],
        cwd=str(args.root),
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
