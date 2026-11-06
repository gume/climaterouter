"""Route override select entity."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the route override select."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities([RouterRouteOverrideSelect(coordinator, entry)])


class RouterRouteOverrideSelect(RouterEntity, SelectEntity):
    """Force routing to one target, independent of the outdoor sensor."""

    _attr_name = "Route override"
    _attr_icon = "mdi:source-branch"

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_route_override"

    @property
    def options(self) -> list[str]:
        return self.coordinator.route_override_options

    @property
    def current_option(self) -> str:
        return self.coordinator.route_override

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_route_override(option)
