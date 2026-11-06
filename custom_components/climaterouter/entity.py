"""Shared entity base for ClimateRouter."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import ClimateRouterCoordinator
from .models import RouterSnapshot


class RouterEntity(CoordinatorEntity[ClimateRouterCoordinator]):
    """Base entity bound to one router config entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ClimateRouterCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer=DOMAIN,
            model="Virtual climate router",
            sw_version=VERSION,
        )

    @property
    def _snapshot(self) -> RouterSnapshot:
        return self.coordinator.data
