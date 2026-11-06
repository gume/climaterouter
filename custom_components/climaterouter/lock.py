"""Native lock entity for ClimateRouter."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
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
    """Set up the native lock when it is enabled."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    if not coordinator.lock_enabled:
        return
    async_add_entities([RouterLock(coordinator, entry)])


class RouterLock(RouterEntity, LockEntity):
    """Lock that rejects user and automation commands on the proxy."""

    _attr_name = "Lock"

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_lock"
        self._attr_code_format = r"^\d{4,8}$" if coordinator.config.lock_code else None

    @property
    def is_locked(self) -> bool:
        return self._snapshot.locked

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.lock_entity_id = self.entity_id

    async def async_will_remove_from_hass(self) -> None:
        if self.coordinator.lock_entity_id == self.entity_id:
            self.coordinator.lock_entity_id = None
        await super().async_will_remove_from_hass()

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.async_lock()

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.async_unlock(code=kwargs.get("code"))
