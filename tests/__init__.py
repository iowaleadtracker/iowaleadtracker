"""Tests for the dispersion model and the Iowa scenario site.

Importing the package makes the model and the scenario scripts importable, for pytest
and for ``python -m tests.test_regression`` alike.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "iowa-aap-2026-11-20"
for _path in (ROOT, SCENARIO):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
