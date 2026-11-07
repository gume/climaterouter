"""Manual-mode switch for ClimateRouter."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the manual-mode switch."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities([RouterManualModeSwitch(coordinator, entry)])


class RouterManualModeSwitch(RouterEntity, SwitchEntity):
    """Turn proxy-owned manual mode on or return to the schedule."""

    _attr_name = "Manual mode"
    _attr_icon = "mdi:hand-back-right"

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_manual_mode"

    @property
    def is_on(self) -> bool:
        """Return whether manual mode is active."""
        return self._snapshot.manual_active

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Expose the current manual deadline and selected timer."""
        snapshot = self._snapshot
        return {
            "until": snapshot.manual_until.isoformat() if snapshot.manual_until else None,
            "timer_minutes": snapshot.manual_timer_minutes,
            "remaining_minutes": (
                snapshot.manual_mode.remaining_minutes(dt_util.utcnow())
                if snapshot.manual_mode is not None
                else None
            ),
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enter manual mode using the current desired state."""
        await self.coordinator.async_enter_manual_mode(context=self._context)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Return to the schedule."""
        await self.coordinator.async_return_to_schedule(cause="switch")
