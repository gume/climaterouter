"""Settable temperature numbers for the fake HVAC test integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import FakeHvacEntity
from .models import FakeHvacSystem


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fake room and outdoor temperature controls."""
    system: FakeHvacSystem = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FakeTemperatureNumber(system, entry.entry_id, "room"),
            FakeTemperatureNumber(system, entry.entry_id, "outdoor"),
        ]
    )


class FakeTemperatureNumber(FakeHvacEntity, NumberEntity):
    """Set the simulated room or outdoor temperature directly."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, system: FakeHvacSystem, entry_id: str, key: str) -> None:
        super().__init__(system, entry_id)
        self._key = key
        if key == "room":
            self._attr_name = "Room Temperature Control"
            self._attr_unique_id = f"{entry_id}_room_temperature_control"
            self._attr_native_min_value = -20.0
            self._attr_native_max_value = 50.0
            self._attr_native_step = 0.1
            self._attr_icon = "mdi:home-thermometer"
        else:
            self._attr_name = "Outdoor Temperature Control"
            self._attr_unique_id = f"{entry_id}_outdoor_temperature_control"
            self._attr_native_min_value = -50.0
            self._attr_native_max_value = 60.0
            self._attr_native_step = 0.5
            self._attr_icon = "mdi:thermometer"

    @property
    def native_value(self) -> float:
        """Return the current simulated temperature."""
        if self._key == "room":
            return round(self._system.room_temperature, 2)
        return round(self._system.outdoor_temperature, 2)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new simulated temperature."""
        if self._key == "room":
            await self._system.async_set_room_temperature(value)
        else:
            await self._system.async_set_outdoor_temperature(value)
