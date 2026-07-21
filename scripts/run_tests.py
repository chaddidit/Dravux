#!/usr/bin/env python3
"""Run Dravux's complete offline standard-library test suite."""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
