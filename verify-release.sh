#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
cd "$script_dir"

command -v python3 >/dev/null 2>&1 || {
  printf 'FAIL: python3 is required.\n' >&2
  exit 3
}
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)' || {
  printf 'FAIL: Python 3.8 or newer is required.\n' >&2
  exit 3
}

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -B scripts/verify_distribution.py

printf 'VERIFIED: Dravux 1.0.1 release tree passed all offline checks\n'
