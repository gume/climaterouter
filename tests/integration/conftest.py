"""Fixtures for the Home Assistant integration tests.

These tests need ``pytest-homeassistant-custom-component``. When the package is
not installed (for example in a minimal checkout), the whole directory is
skipped so the pure domain tests keep working.
"""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the custom integration from ``custom_components/``."""
    yield
