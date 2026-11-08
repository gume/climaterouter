"""Integration tests for the entity platforms."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_OFF
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.const import DOMAIN, VERSION
from custom_components.climaterouter.models import HVAC_HEAT

RADIATOR = "climate.radiator"
AC = "climate.ac"
OUTDOOR = "sensor.outdoor"


def _entry_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "Test Router",
        "radiator_entity_id": RADIATOR,
        "ac_entity_id": AC,
        "outdoor_sensor_entity_id": OUTDOOR,
        "startup_grace": 0,
        "settle_time": 0,
        "min_route_dwell": 0,
    }
    data.update(overrides)
    return data


def _set_entities(hass) -> None:
    hass.states.async_set(RADIATOR, STATE_OFF, {"hvac_modes": [HVAC_HEAT]})
    hass.states.async_set(AC, STATE_OFF, {"hvac_modes": [HVAC_HEAT, "cool"]})
    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})


async def _setup(hass, **data: Any):
    _set_entities(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(**data),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


async def test_platforms_create_entities(hass) -> None:
    """Every always-on platform contributes entities for the entry."""
    entry, coordinator = await _setup(hass)

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    domains = {item.domain for item in entries}

    assert domains == {
        "binary_sensor",
        "button",
        "climate",
        "select",
        "sensor",
        "switch",
    }
    assert coordinator.climate_entity_id is not None
    climate = hass.states.get(coordinator.climate_entity_id)
    assert climate is not None
    assert climate.state == STATE_OFF

    device = registry.async_get(coordinator.climate_entity_id)
    assert device is not None
    assert device.unique_id == f"{entry.entry_id}_climate"


async def test_climate_entity_tracks_device_info(hass) -> None:
    """The proxy entity is registered as a device with the integration version."""
    entry, coordinator = await _setup(hass)

    from homeassistant.helpers import device_registry as dr

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert device is not None
    assert device.name == "Test Router"
    assert device.sw_version == VERSION
    assert coordinator.climate_entity_id in {
        entity.entity_id for entity in er.async_entries_for_device(er.async_get(hass), device.id)
    }


async def test_lock_entity_only_when_enabled(hass) -> None:
    """The UI lock platform is only set up when the feature is enabled."""
    entry, coordinator = await _setup(hass, lock_enabled=True)

    assert coordinator.lock_entity_id is not None
    lock = hass.states.get(coordinator.lock_entity_id)
    assert lock is not None
    assert lock.state == "unlocked"

    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert "lock" in {item.domain for item in entries}
