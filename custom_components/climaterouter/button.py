"""Buttons for manual router actions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
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
    """Set up the router buttons."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities(
        [
            RouterButton(
                coordinator,
                entry,
                "recalculate_route",
                "Recalculate route",
                "mdi:refresh",
                coordinator.async_recalculate,
            ),
            RouterButton(
                coordinator,
                entry,
                "cancel_override",
                "Cancel override",
                "mdi:timer-cancel-outline",
                coordinator.async_cancel_manual_override,
            ),
            RouterButton(
                coordinator,
                entry,
                "clear_conflicts",
                "Clear conflicts",
                "mdi:check-circle-outline",
                coordinator.async_clear_conflicts,
            ),
        ]
    )


class RouterButton(RouterEntity, ButtonEntity):
    """Run one coordinator action."""

    def __init__(
        self,
        coordinator: ClimateRouterCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(coordinator)
        self._action = action
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_press(self) -> None:
        await self._action()
