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
    SERVICE_CLEAR_CONFLICTS,
    SERVICE_CLEAR_ROUTE_OVERRIDE,
    SERVICE_RECALCULATE,
    SERVICE_SET_ROUTE_OVERRIDE,
)
from .coordinator import ClimateRouterCoordinator
from .models import ROUTE_AC, ROUTE_AUTO, ROUTE_RADIATOR

_LOGGER = logging.getLogger(__name__)

SET_ROUTE_OVERRIDE_SCHEMA = cv.make_entity_service_schema(
    {vol.Required("route"): vol.In([ROUTE_AUTO, ROUTE_RADIATOR, ROUTE_AC])}
)
EMPTY_ENTITY_SCHEMA = cv.make_entity_service_schema({})


async def _async_coordinators(
    hass: HomeAssistant, call: ServiceCall
) -> list[ClimateRouterCoordinator]:
    """Resolve the router coordinators targeted by a service call."""
    entity_ids = await async_extract_entity_ids(hass, call)
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
