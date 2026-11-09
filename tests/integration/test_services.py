"""Integration tests for the ClimateRouter services."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import STATE_OFF
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from voluptuous import Invalid

from custom_components.climaterouter.const import (
    DOMAIN,
    SERVICE_CANCEL_BOOST,
    SERVICE_CANCEL_MANUAL_OVERRIDE,
    SERVICE_CLEAR_ROUTE_OVERRIDE,
    SERVICE_ENTER_MANUAL_MODE,
    SERVICE_LOCK,
    SERVICE_RETURN_TO_SCHEDULE,
    SERVICE_SET_BOOST,
    SERVICE_SET_MANUAL_OVERRIDE,
    SERVICE_SET_MANUAL_TIMER,
    SERVICE_SET_ROUTE_OVERRIDE,
    SERVICE_UNLOCK,
)
from custom_components.climaterouter.models import HVAC_HEAT, ROUTE_AC, ROUTE_AUTO

RADIATOR = "climate.radiator"
AC = "climate.ac"
OUTDOOR = "sensor.outdoor"

USER = Context(user_id="user-1")


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
    coordinator = entry.runtime_data
    assert coordinator.climate_entity_id is not None
    return entry, coordinator


async def test_set_route_override_service(hass) -> None:
    """The route override service targets the proxy entity."""
    _entry, coordinator = await _setup(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ROUTE_OVERRIDE,
        {"entity_id": coordinator.climate_entity_id, "route": ROUTE_AC},
        blocking=True,
    )

    assert coordinator.route_override == ROUTE_AC


async def test_enter_manual_mode_and_return_to_schedule(hass) -> None:
    """Manual mode can be entered and ended through the services."""
    _entry, coordinator = await _setup(hass)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ENTER_MANUAL_MODE,
        {
            "entity_id": coordinator.climate_entity_id,
            "temperature": 22,
            "duration_minutes": 30,
        },
        blocking=True,
        context=USER,
    )

    manual = coordinator.data.manual_mode
    assert manual is not None
    assert manual.desired.target_temperature == 22
    assert manual.timer_minutes == 30

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MANUAL_TIMER,
        {"entity_id": coordinator.climate_entity_id, "minutes": 45},
        blocking=True,
        context=USER,
    )
    assert coordinator.data.manual_mode is not None
    assert coordinator.data.manual_mode.timer_minutes == 45

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RETURN_TO_SCHEDULE,
        {"entity_id": coordinator.climate_entity_id},
        blocking=True,
        context=USER,
    )

    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.target_temperature == 20


async def test_manual_mode_rejects_conflicting_arguments(hass) -> None:
    """Only one of temperature, preset, or mode may be supplied."""
    _entry, coordinator = await _setup(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ENTER_MANUAL_MODE,
            {
                "entity_id": coordinator.climate_entity_id,
                "temperature": 22,
                "hvac_mode": HVAC_HEAT,
            },
            blocking=True,
        )


async def test_unknown_route_override_is_rejected(hass) -> None:
    """The service schema validates the route value before dispatch."""
    _entry, coordinator = await _setup(hass)

    with pytest.raises(Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ROUTE_OVERRIDE,
            {"entity_id": coordinator.climate_entity_id, "route": "space"},
            blocking=True,
        )

    assert coordinator.route_override == ROUTE_AUTO


async def test_clear_route_override_service(hass) -> None:
    """Clearing the route override returns to automatic routing."""
    _entry, coordinator = await _setup(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ROUTE_OVERRIDE,
        {"entity_id": coordinator.climate_entity_id, "route": ROUTE_AC},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_ROUTE_OVERRIDE,
        {"entity_id": coordinator.climate_entity_id},
        blocking=True,
    )

    assert coordinator.route_override == ROUTE_AUTO


async def test_manual_override_alias_and_cancel(hass) -> None:
    """The legacy manual-override service enters and cancels manual mode."""
    _entry, coordinator = await _setup(hass)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_MANUAL_OVERRIDE,
        {"entity_id": coordinator.climate_entity_id, "temperature": 22},
        blocking=True,
        context=USER,
    )
    assert coordinator.data.manual_mode is not None
    assert coordinator.data.manual_mode.desired.target_temperature == 22

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CANCEL_MANUAL_OVERRIDE,
        {"entity_id": coordinator.climate_entity_id},
        blocking=True,
        context=USER,
    )
    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.target_temperature == 20


async def test_set_and_cancel_boost_services(hass) -> None:
    """Boost can be started and cancelled through the services."""
    _entry, coordinator = await _setup(hass, boost_enabled=True)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_BOOST,
        {"entity_id": coordinator.climate_entity_id, "duration_minutes": 5},
        blocking=True,
        context=USER,
    )
    assert coordinator.data.boost_until is not None

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CANCEL_BOOST,
        {"entity_id": coordinator.climate_entity_id},
        blocking=True,
        context=USER,
    )
    assert coordinator.data.boost_until is None


async def test_lock_and_unlock_services(hass) -> None:
    """The lock services toggle the coordinator lock state."""
    _entry, coordinator = await _setup(hass, lock_enabled=True, auto_relock_sec=0)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_LOCK,
        {"entity_id": coordinator.lock_entity_id},
        blocking=True,
    )
    assert coordinator.data.locked is True

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UNLOCK,
        {"entity_id": coordinator.lock_entity_id},
        blocking=True,
    )
    assert coordinator.data.locked is False


async def test_service_rejects_foreign_entity(hass) -> None:
    """A target that is not managed by ClimateRouter is rejected."""
    await _setup(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_ROUTE_OVERRIDE,
            {"entity_id": RADIATOR},
            blocking=True,
        )


async def test_service_requires_a_target(hass) -> None:
    """A service call without any entity target is rejected by the schema."""
    await _setup(hass)

    with pytest.raises(Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ROUTE_OVERRIDE,
            {"route": ROUTE_AC},
            blocking=True,
        )
