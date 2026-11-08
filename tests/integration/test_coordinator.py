"""Integration tests for coordinator routing and manual mode."""

from __future__ import annotations

from typing import Any

from homeassistant.const import STATE_OFF
from homeassistant.core import Context
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.const import DOMAIN
from custom_components.climaterouter.models import HVAC_HEAT, ROUTE_AC, Target

RADIATOR = "climate.radiator"
AC = "climate.ac"
OUTDOOR = "sensor.outdoor"

USER = Context(user_id="user-1")


def _entry_data(**overrides: Any) -> dict[str, Any]:
    """Return entry data tuned for fast, deterministic routing."""
    data: dict[str, Any] = {
        "name": "Test Router",
        "radiator_entity_id": RADIATOR,
        "ac_entity_id": AC,
        "outdoor_sensor_entity_id": OUTDOOR,
        "startup_grace": 0,
        "settle_time": 0,
        "min_route_dwell": 0,
        "handover_idle_confirm": 0,
        "off_confirm_timeout": 1,
    }
    data.update(overrides)
    return data


def _set_entities(hass, *, outdoor: float = 5.0) -> None:
    hass.states.async_set(
        RADIATOR,
        STATE_OFF,
        {"hvac_modes": [HVAC_HEAT], "min_temp": 7, "max_temp": 35},
    )
    hass.states.async_set(
        AC,
        STATE_OFF,
        {"hvac_modes": [HVAC_HEAT, "cool"], "min_temp": 16, "max_temp": 30},
    )
    hass.states.async_set(OUTDOOR, str(outdoor), {"unit_of_measurement": "°C"})


async def _setup(hass, *, outdoor: float = 5.0, **data: Any):
    """Set up one entry and return it with its coordinator."""
    _set_entities(hass, outdoor=outdoor)
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


async def test_routes_to_radiator_when_cold(hass) -> None:
    """A fresh heat command below the cold threshold starts the radiator."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)

    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    assert coordinator.data.ready is True
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert coordinator.data.route_reason == "outdoor_cold"
    assert coordinator.data.desired.target_temperature == 21


async def test_switches_to_ac_when_outdoors_get_mild(hass) -> None:
    """The route follows outdoor hysteresis once the radiator is idle."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(OUTDOOR, "15.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.route_reason == "hysteresis"


async def test_route_override_wins_over_outdoor_temperature(hass) -> None:
    """An explicit route override bypasses the hysteresis decision."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    await coordinator.async_set_route_override(ROUTE_AC)
    await hass.async_block_till_done()

    assert coordinator.data.route_override == ROUTE_AC
    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.route_reason == "manual_route"


async def test_user_setpoint_starts_and_ends_manual_mode(hass) -> None:
    """A user setpoint move starts manual mode without changing the baseline."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()
    assert coordinator.data.manual_mode is None

    await coordinator.async_set_temperature(temperature=23, context=USER)
    await hass.async_block_till_done()

    manual = coordinator.data.manual_mode
    assert manual is not None
    assert manual.desired.target_temperature == 23
    assert manual.desired.hvac_mode == HVAC_HEAT
    assert coordinator.data.desired.target_temperature == 23

    await coordinator.async_return_to_schedule()
    await hass.async_block_till_done()

    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.target_temperature == 20


async def test_turn_off_ends_manual_mode(hass) -> None:
    """An explicit off is a safety command and clears manual mode."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_set_temperature(temperature=23, context=USER)
    assert coordinator.data.manual_mode is not None

    await coordinator.async_turn_off(context=USER)
    await hass.async_block_till_done()

    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.hvac_mode == "off"
    assert coordinator.data.active_targets == frozenset()
