"""Shared entity helpers for the fake HVAC test integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .models import FakeHvacSystem


class FakeHvacEntity(Entity):
    """Base entity bound to one simulated HVAC system."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, system: FakeHvacSystem, entry_id: str) -> None:
        self._system = system
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Fake",
            manufacturer="ClimateRouter test",
            model="Fake HVAC Lab",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to simulation updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._system.add_listener(self._handle_system_update))

    def _handle_system_update(self) -> None:
        self.async_write_ha_state()

    @property
    def suggested_object_id(self) -> str | None:
        """Return a stable, short entity ID base without the device prefix."""
        return self._attr_name
