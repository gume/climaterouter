"""Service registration for ClimateRouter."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_extract_entity_ids

from .const import (
    DOMAIN,
    SERVICE_CANCEL_BOOST,
    SERVICE_CANCEL_MANUAL_OVERRIDE,
    SERVICE_CLEAR_CONFLICTS,
    SERVICE_CLEAR_ROUTE_OVERRIDE,
    SERVICE_RECALCULATE,
    SERVICE_SET_BOOST,
    SERVICE_SET_MANUAL_OVERRIDE,
    SERVICE_SET_ROUTE_OVERRIDE,
)
from .coordinator import ClimateRouterCoordinator
from .models import HVAC_COOL, HVAC_HEAT, HVAC_OFF, ROUTE_AC, ROUTE_AUTO, ROUTE_RADIATOR

_LOGGER = logging.getLogger(__name__)

SET_ROUTE_OVERRIDE_SCHEMA = cv.make_entity_service_schema(
    {vol.Required("route"): vol.In([ROUTE_AUTO, ROUTE_RADIATOR, ROUTE_AC])}
)
EMPTY_ENTITY_SCHEMA = cv.make_entity_service_schema({})
SET_MANUAL_OVERRIDE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional("duration_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("temperature"): vol.Coerce(float),
        vol.Optional("preset_mode"): cv.string,
        vol.Optional("hvac_mode"): vol.In([HVAC_OFF, HVAC_HEAT, HVAC_COOL]),
    }
)
SET_BOOST_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional("duration_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional("targets", default="both"): vol.In(["both"]),
    }
)


async def _async_coordinators(
    hass: HomeAssistant, call: ServiceCall
) -> list[ClimateRouterCoordinator]:
    """Resolve the router coordinators targeted by a service call."""
    entity_ids = await async_extract_entity_ids(call)
    if not entity_ids:
        raise ServiceValidationError("Target at least one ClimateRouter entity")

    coordinators = [
        coordinator
        for coordinator in hass.data.get(DOMAIN, {}).values()
        if coordinator.climate_entity_id in entity_ids
    ]
    if not coordinators:
        raise ServiceValidationError("The target is not a ClimateRouter climate entity")
    return coordinators


def async_register_services(hass: HomeAssistant) -> None:
    """Register the integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_RECALCULATE):
        return

    async def handle_recalculate(call: ServiceCall) -> None:
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_recalculate()

    async def handle_set_route_override(call: ServiceCall) -> None:
        route = str(call.data["route"])
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_set_route_override(route)

    async def handle_clear_route_override(call: ServiceCall) -> None:
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_set_route_override(ROUTE_AUTO)

    async def handle_clear_conflicts(call: ServiceCall) -> None:
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_clear_conflicts()

    async def handle_set_manual_override(call: ServiceCall) -> None:
        temperature = call.data.get("temperature")
        preset_mode = call.data.get("preset_mode")
        hvac_mode = call.data.get("hvac_mode")
        if sum(value is not None for value in (temperature, preset_mode, hvac_mode)) != 1:
            raise ServiceValidationError(
                "Exactly one of temperature, preset_mode, or hvac_mode is required"
            )
        duration = call.data.get("duration_minutes")
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_set_manual_override(
                temperature=temperature,
                preset_mode=preset_mode,
                hvac_mode=hvac_mode,
                duration_minutes=duration,
            )

    async def handle_cancel_manual_override(call: ServiceCall) -> None:
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_cancel_manual_override()

    async def handle_set_boost(call: ServiceCall) -> None:
        duration = call.data.get("duration_minutes")
        targets = str(call.data.get("targets", "both"))
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_set_boost(
                duration_minutes=duration,
                targets=targets,
            )

    async def handle_cancel_boost(call: ServiceCall) -> None:
        for coordinator in await _async_coordinators(hass, call):
            await coordinator.async_cancel_boost()

    hass.services.async_register(
        DOMAIN, SERVICE_RECALCULATE, handle_recalculate, schema=EMPTY_ENTITY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ROUTE_OVERRIDE,
        handle_set_route_override,
        schema=SET_ROUTE_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_ROUTE_OVERRIDE,
        handle_clear_route_override,
        schema=EMPTY_ENTITY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_CONFLICTS,
        handle_clear_conflicts,
        schema=EMPTY_ENTITY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MANUAL_OVERRIDE,
        handle_set_manual_override,
        schema=SET_MANUAL_OVERRIDE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_MANUAL_OVERRIDE,
        handle_cancel_manual_override,
        schema=EMPTY_ENTITY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_BOOST, handle_set_boost, schema=SET_BOOST_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_BOOST,
        handle_cancel_boost,
        schema=EMPTY_ENTITY_SCHEMA,
    )
