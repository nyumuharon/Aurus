# conftest.py
"""Pytest root configuration for the Aurus project.

Adds the project root to sys.path so that:
- ``from config import settings`` resolves correctly in src/ modules.
- ``import src.data.price_feed`` resolves correctly in tests.
"""

import sys
from pathlib import Path

# Project root = directory containing this file
_ROOT = Path(__file__).parent.resolve()

for _p in [str(_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
