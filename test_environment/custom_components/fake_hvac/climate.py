"""Fake air-conditioner climate entity for the fake HVAC test integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_TEMPERATURES,
)
from .entity import FakeHvacEntity
from .models import FakeHvacSystem

SUPPORTED_HVAC_MODES = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
SUPPORTED_PRESET_MODES = ["none", *PRESET_TEMPERATURES]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fake AC climate entity."""
    system: FakeHvacSystem = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FakeAcClimate(system, entry.entry_id)])


class FakeAcClimate(FakeHvacEntity, ClimateEntity):
    """A small thermostat-like fake AC used as an over_climate target."""

    _attr_name = "AC"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = SUPPORTED_HVAC_MODES
    _attr_preset_modes = SUPPORTED_PRESET_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_icon = "mdi:air-conditioner"

    def __init__(self, system: FakeHvacSystem, entry_id: str) -> None:
        super().__init__(system, entry_id)
        self._attr_unique_id = f"{entry_id}_ac"

    @property
    def native_current_temperature(self) -> float:
        """Return the simulated room temperature."""
        return round(self._system.room_temperature, 2)

    @property
    def native_target_temperature(self) -> float:
        """Return the AC setpoint."""
        return self._system.ac_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the simulated AC mode."""
        return self._system.ac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return the simulated AC action."""
        return self._system.ac_action

    @property
    def preset_mode(self) -> str:
        """Return the simulated AC preset."""
        return self._system.ac_preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "ac_power_on": self._system.ac_power_on,
            "thermal_power_w": round(self._system.thermal_power_w, 0),
            "room_available": self._system.room_available,
            "simulation_enabled": self._system.simulation_enabled,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the simulated AC target temperature and optional mode."""
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode is not None:
            await self._system.async_set_ac_mode(hvac_mode)

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self._system.async_set_ac_target(float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the simulated AC mode."""
        await self._system.async_set_ac_mode(hvac_mode)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the simulated AC preset."""
        await self._system.async_set_ac_preset(preset_mode)

    async def async_turn_on(self) -> None:
        """Turn the simulated AC on in heat mode."""
        await self._system.async_set_ac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the simulated AC off."""
        await self._system.async_set_ac_mode(HVACMode.OFF)
