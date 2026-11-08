"""Fixtures for the Home Assistant integration tests.

These tests need ``pytest-homeassistant-custom-component``. When the package is
not installed (for example in a minimal checkout), the whole directory is
skipped so the pure domain tests keep working.
"""

from __future__ import annotations

import inspect

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load the custom integration from ``custom_components/``."""
    yield


@pytest.fixture(autouse=True)
def _compat_extract_entity_ids(monkeypatch):
    """Bridge the service-call signature across Home Assistant versions.

    Recent Home Assistant versions resolve targeted entities from the service
    call alone; older test harnesses still require the ``hass`` argument.
    """
    from homeassistant.helpers import service as ha_service

    from custom_components.climaterouter import services as services_module

    original = ha_service.async_extract_entity_ids
    wants_hass = len(inspect.signature(original).parameters) > 1

    async def _extract(call):
        if wants_hass:
            return await original(call.hass, call)
        return await original(call)

    monkeypatch.setattr(services_module, "async_extract_entity_ids", _extract)
