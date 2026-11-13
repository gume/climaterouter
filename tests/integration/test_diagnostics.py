"""Integration tests for the ClimateRouter diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_OFF
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.const import DOMAIN, VERSION
from custom_components.climaterouter.diagnostics import (
    async_get_config_entry_diagnostics,
)
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


async def test_diagnostics_serializes_snapshot_and_redacts_code(hass) -> None:
    """Diagnostics expose the routing state but never the lock code."""
    entry, coordinator = await _setup(hass, lock_code="s3cret")
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_enter_manual_mode(temperature=22, duration_minutes=30)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["version"] == VERSION
    assert diagnostics["entry"]["entry_id"] == entry.entry_id
    assert diagnostics["entry"]["data"]["lock_code"] == "**REDACTED**"
    assert diagnostics["config"]["lock_code"] == "**REDACTED**"
    assert diagnostics["snapshot"]["ready"] is True
    assert diagnostics["snapshot"]["manual_mode"] is not None
    assert diagnostics["snapshot"]["targets"]["radiator"]["entity_id"] == RADIATOR
    assert diagnostics["snapshot"]["route_target"] == "radiator"
    assert diagnostics["targets_present"] == ["ac", "radiator"]
    assert diagnostics["active_targets"] == ["radiator"]

    await coordinator.async_return_to_schedule()

    # active_targets is intentionally empty when everything is off; route_target
    # keeps the last routed target visible.
    await coordinator.async_turn_off()
    await hass.async_block_till_done()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["snapshot"]["active_targets"] == []
    assert diagnostics["snapshot"]["route_target"] == "radiator"


async def test_diagnostics_reports_unloaded_entry(hass) -> None:
    """An entry without runtime data returns a small error payload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics == {"version": VERSION, "error": "entry not loaded"}
