"""Buttons for manual router actions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity
from .models import HandoverState

PARALLEL_UPDATES = 0


def _handover_in_progress(coordinator: ClimateRouterCoordinator) -> bool:
    """Return whether there is a handover that can be forced."""
    return coordinator.data.handover_state in (
        HandoverState.PENDING,
        HandoverState.STOPPING_OLD,
        HandoverState.STARTING_NEW,
    )


def _manual_active(coordinator: ClimateRouterCoordinator) -> bool:
    """Return whether manual mode can be ended."""
    return coordinator.data.manual_active


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
                "return_to_schedule",
                "Return to schedule",
                "mdi:calendar-clock",
                coordinator.async_return_to_schedule,
                _manual_active,
            ),
            RouterButton(
                coordinator,
                entry,
                "clear_conflicts",
                "Clear conflicts",
                "mdi:check-circle-outline",
                coordinator.async_clear_conflicts,
            ),
            RouterButton(
                coordinator,
                entry,
                "force_handover",
                "Force handover",
                "mdi:swap-horizontal-bold",
                coordinator.async_force_handover,
                _handover_in_progress,
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
        available: Callable[[ClimateRouterCoordinator], bool] | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._action = action
        self._available_fn = available
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def available(self) -> bool:
        """Return whether the action can currently be run."""
        if not super().available:
            return False
        if self._available_fn is None:
            return True
        return self._available_fn(self.coordinator)

    async def async_press(self) -> None:
        await self._action()
