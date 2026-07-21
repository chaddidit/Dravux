#!/usr/bin/env python3
"""Public entry point for the canonical Dravux report validator."""

import sys
from pathlib import Path


SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "plugins"
    / "dravux"
    / "skills"
    / "dravux"
    / "scripts"
)
sys.path.insert(0, str(SKILL_SCRIPTS))

from dravux_contract import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
