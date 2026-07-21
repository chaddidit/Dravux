#!/usr/bin/env python3
"""Reset the synthetic live demo to the known broken or repaired source."""

import argparse
import shutil
from pathlib import Path


DEMO_ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset the local Dravux GitHub demo.")
    parser.add_argument("--state", choices=("broken", "repaired"), required=True)
    parser.add_argument("--destination", type=Path, default=DEMO_ROOT / "live" / "index.html")
    args = parser.parse_args()
    source = DEMO_ROOT / args.state / "index.html"
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, args.destination)
    print(f"Reset {args.destination} to {args.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
