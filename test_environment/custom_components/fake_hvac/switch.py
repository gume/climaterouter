"""Fake radiator switch for the fake HVAC test integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up the fake radiator and simulation switches."""
    system: FakeHvacSystem = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FakeRadiatorSwitch(system, entry.entry_id),
            FakeSimulationSwitch(system, entry.entry_id),
        ]
    )


class FakeRadiatorSwitch(FakeHvacEntity, SwitchEntity):
    """A switch that drives the simulated radiator."""

    _attr_name = "Radiator"
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:radiator"

    def __init__(self, system: FakeHvacSystem, entry_id: str) -> None:
        super().__init__(system, entry_id)
        self._attr_unique_id = f"{entry_id}_radiator"

    @property
    def is_on(self) -> bool:
        """Return whether the radiator is on."""
        return self._system.radiator_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the simulated radiator on."""
        await self._system.async_set_radiator(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the simulated radiator off."""
        await self._system.async_set_radiator(False)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "power_kw": self._system.config.radiator_power_kw,
            "room_temperature": round(self._system.room_temperature, 2),
            "simulation_enabled": self._system.simulation_enabled,
        }


class FakeSimulationSwitch(FakeHvacEntity, SwitchEntity):
    """Pause or resume the simulated thermal ticker."""

    _attr_name = "Simulation"
    _attr_icon = "mdi:play-pause"

    def __init__(self, system: FakeHvacSystem, entry_id: str) -> None:
        super().__init__(system, entry_id)
        self._attr_unique_id = f"{entry_id}_simulation"

    @property
    def is_on(self) -> bool:
        """Return whether the simulation is evolving."""
        return self._system.simulation_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume the thermal simulation."""
        await self._system.async_set_simulation(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause the thermal simulation."""
        await self._system.async_set_simulation(False)
