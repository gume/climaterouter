"""Integration tests for the entity platforms."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.const import STATE_OFF
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.const import DOMAIN, VERSION
from custom_components.climaterouter.models import HVAC_HEAT, ROUTE_AC

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


async def test_climate_entity_is_optimistic_then_mirrors(hass, monkeypatch) -> None:
    """The proxy shows the command first, then the underlying target value."""
    from custom_components.climaterouter import climate as climate_module

    _entry, coordinator = await _setup(hass, settle_time=30)
    await coordinator.async_set_temperature(temperature=23, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    state = hass.states.get(coordinator.climate_entity_id)
    assert state is not None
    assert state.state == HVAC_HEAT
    assert state.attributes["temperature"] == 23

    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 21,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    await hass.async_block_till_done()
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    state = hass.states.get(coordinator.climate_entity_id)
    assert state.attributes["temperature"] == 23

    now = climate_module.dt_util.utcnow()
    monkeypatch.setattr(climate_module.dt_util, "utcnow", lambda: now + timedelta(seconds=31))
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    state = hass.states.get(coordinator.climate_entity_id)
    assert state.attributes["temperature"] == 21
    assert state.attributes["current_temperature"] is None


async def test_climate_entity_is_unavailable_without_targets(hass) -> None:
    """The proxy reports unavailable when both underlying targets are gone."""
    _entry, coordinator = await _setup(hass)
    hass.states.async_set(RADIATOR, "unavailable")
    hass.states.async_set(AC, "unavailable")

    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    state = hass.states.get(coordinator.climate_entity_id)
    assert state is not None
    assert state.state == "unavailable"


async def test_select_button_and_switch_entities(hass) -> None:
    """The auxiliary entities drive the coordinator through HA services."""
    entry, coordinator = await _setup(hass)
    registry = er.async_get(hass)

    select_id = registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_route_override")
    assert select_id is not None
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": select_id, "option": ROUTE_AC},
        blocking=True,
    )
    assert coordinator.route_override == ROUTE_AC

    button_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_recalculate_route"
    )
    assert button_id is not None
    await hass.services.async_call("button", "press", {"entity_id": button_id}, blocking=True)
    await hass.async_block_till_done()

    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    switch_id = registry.async_get_entity_id("switch", DOMAIN, f"{entry.entry_id}_manual_mode")
    assert switch_id is not None
    await hass.services.async_call("switch", "turn_on", {"entity_id": switch_id}, blocking=True)
    assert coordinator.data.manual_mode is not None

    await hass.services.async_call("switch", "turn_off", {"entity_id": switch_id}, blocking=True)
    assert coordinator.data.manual_mode is None


async def test_lock_entity_only_when_enabled(hass) -> None:
    """The UI lock platform is only set up when the feature is enabled."""
    entry, coordinator = await _setup(hass, lock_enabled=True)

    assert coordinator.lock_entity_id is not None
    lock = hass.states.get(coordinator.lock_entity_id)
    assert lock is not None
    assert lock.state == "unlocked"

    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert "lock" in {item.domain for item in entries}
