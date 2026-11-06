"""Test path setup.

The domain layer is imported through a lightweight package stub so pure unit
tests do not need a full Home Assistant installation to load
``custom_components/climaterouter/__init__.py``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "custom_components" / "climaterouter"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "climaterouter" not in sys.modules:
    package = types.ModuleType("climaterouter")
    package.__path__ = [str(PACKAGE_DIR)]  # type: ignore[attr-defined]
    sys.modules["climaterouter"] = package
