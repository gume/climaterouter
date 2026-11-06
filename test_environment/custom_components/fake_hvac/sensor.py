"""Temperature and power sensors for the fake HVAC test integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature
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
    """Set up fake temperature and power sensors."""
    system: FakeHvacSystem = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FakeTemperatureSensor(system, entry.entry_id, "room"),
            FakeTemperatureSensor(system, entry.entry_id, "outdoor"),
            FakeThermalPowerSensor(system, entry.entry_id),
        ]
    )


class _FakeBaseSensor(FakeHvacEntity, SensorEntity):
    """Base class with shared listener/device behavior."""


class FakeTemperatureSensor(_FakeBaseSensor):
    """A simulated room or outdoor temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, system: FakeHvacSystem, entry_id: str, key: str) -> None:
        super().__init__(system, entry_id)
        self._key = key
        if key == "room":
            self._attr_name = "Room Temperature"
            self._attr_unique_id = f"{entry_id}_room_temperature"
            self._attr_icon = "mdi:home-thermometer"
        else:
            self._attr_name = "Outdoor Temperature"
            self._attr_unique_id = f"{entry_id}_outdoor_temperature"
            self._attr_icon = "mdi:thermometer"

    @property
    def available(self) -> bool:
        if self._key == "room":
            return self._system.room_available
        return self._system.outdoor_available

    @property
    def native_value(self) -> float | None:
        if self._key == "room":
            return round(self._system.room_temperature, 2)
        return round(self._system.outdoor_temperature, 2)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "simulation_enabled": self._system.simulation_enabled,
            "time_scale": self._system.config.time_scale,
        }


class FakeThermalPowerSensor(_FakeBaseSensor):
    """Current simulated heating/cooling power (negative = cooling)."""

    _attr_name = "Thermal Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:flash"

    def __init__(self, system: FakeHvacSystem, entry_id: str) -> None:
        super().__init__(system, entry_id)
        self._attr_unique_id = f"{entry_id}_thermal_power"

    @property
    def native_value(self) -> float:
        return round(self._system.thermal_power_w, 0)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "radiator_on": self._system.radiator_on,
            "ac_power_on": self._system.ac_power_on,
            "ac_mode": str(self._system.ac_mode),
        }
