"""YAML-configurable fake HVAC environment for ClimateRouter tests."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_ENABLED,
    ATTR_MINUTES,
    ATTR_NAME,
    ATTR_OUTDOOR,
    ATTR_ROOM,
    ATTR_TEMPERATURE,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADVANCE,
    SERVICE_RESET,
    SERVICE_SET_AVAILABILITY,
    SERVICE_SET_OUTDOOR_TEMPERATURE,
    SERVICE_SET_ROOM_TEMPERATURE,
    SERVICE_SET_SIMULATION,
)
from .models import FakeHvacConfig, FakeHvacSystem

_LOGGER = logging.getLogger(__name__)

SET_TEMPERATURE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TEMPERATURE): vol.All(vol.Coerce(float), vol.Range(min=-50, max=60)),
        vol.Optional(ATTR_NAME): cv.string,
    }
)

SET_SIMULATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENABLED): cv.boolean,
        vol.Optional(ATTR_NAME): cv.string,
    }
)

SET_AVAILABILITY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ROOM): cv.boolean,
        vol.Optional(ATTR_OUTDOOR): cv.boolean,
        vol.Optional(ATTR_NAME): cv.string,
    }
)

ADVANCE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(float), vol.Range(min=1, max=1440)),
        vol.Optional(ATTR_NAME): cv.string,
    }
)

RESET_SCHEMA = vol.Schema({vol.Optional(ATTR_NAME): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up services and import the optional YAML configuration."""
    _async_register_services(hass)

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=dict(config[DOMAIN]),
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one simulated HVAC system."""
    system = FakeHvacSystem(
        hass,
        entry.entry_id,
        FakeHvacConfig.from_mapping(dict(entry.data)),
    )
    await system.async_start()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = system

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a simulated HVAC system."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        system: FakeHvacSystem | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if system is not None:
            await system.async_stop()
    return unload_ok


def _get_system(hass: HomeAssistant, name: str | None) -> FakeHvacSystem:
    """Resolve a system by name, or the only one when no name is given."""
    systems: list[FakeHvacSystem] = list(hass.data.get(DOMAIN, {}).values())
    if not systems:
        raise ServiceValidationError("No fake_hvac system is configured")

    if name:
        for system in systems:
            if system.entry_id == name or system.config.name.lower() == name.lower():
                return system
        raise ServiceValidationError(f"Unknown fake_hvac system: {name}")

    if len(systems) == 1:
        return systems[0]

    raise ServiceValidationError(
        "Multiple fake_hvac systems are configured; provide the 'name' field"
    )


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the test services once."""

    def register(name: str, handler: Any, schema: vol.Schema) -> None:
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(DOMAIN, name, handler, schema=schema)

    async def handle_set_outdoor_temperature(call: ServiceCall) -> None:
        system = _get_system(hass, call.data.get(ATTR_NAME))
        await system.async_set_outdoor_temperature(call.data[ATTR_TEMPERATURE])

    async def handle_set_room_temperature(call: ServiceCall) -> None:
        system = _get_system(hass, call.data.get(ATTR_NAME))
        await system.async_set_room_temperature(call.data[ATTR_TEMPERATURE])

    async def handle_set_simulation(call: ServiceCall) -> None:
        system = _get_system(hass, call.data.get(ATTR_NAME))
        await system.async_set_simulation(call.data[ATTR_ENABLED])

    async def handle_set_availability(call: ServiceCall) -> None:
        room = call.data.get(ATTR_ROOM)
        outdoor = call.data.get(ATTR_OUTDOOR)
        if room is None and outdoor is None:
            raise ServiceValidationError("Provide at least one of 'room' or 'outdoor'")
        system = _get_system(hass, call.data.get(ATTR_NAME))
        await system.async_set_availability(room=room, outdoor=outdoor)

    async def handle_advance(call: ServiceCall) -> None:
        system = _get_system(hass, call.data.get(ATTR_NAME))
        await system.async_advance(call.data[ATTR_MINUTES])

    async def handle_reset(call: ServiceCall) -> None:
        system = _get_system(hass, call.data.get(ATTR_NAME))
        await system.async_reset()

    register(
        SERVICE_SET_OUTDOOR_TEMPERATURE,
        handle_set_outdoor_temperature,
        SET_TEMPERATURE_SCHEMA,
    )
    register(
        SERVICE_SET_ROOM_TEMPERATURE,
        handle_set_room_temperature,
        SET_TEMPERATURE_SCHEMA,
    )
    register(SERVICE_SET_SIMULATION, handle_set_simulation, SET_SIMULATION_SCHEMA)
    register(
        SERVICE_SET_AVAILABILITY,
        handle_set_availability,
        SET_AVAILABILITY_SCHEMA,
    )
    register(SERVICE_ADVANCE, handle_advance, ADVANCE_SCHEMA)
    register(SERVICE_RESET, handle_reset, RESET_SCHEMA)
