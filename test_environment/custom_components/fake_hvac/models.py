"""Shared simulated HVAC state for the fake_hvac test integration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DEFAULT_AC_POWER_KW,
    DEFAULT_AC_TARGET_TEMPERATURE,
    DEFAULT_LOSS_COEFFICIENT,
    DEFAULT_NAME,
    DEFAULT_OUTDOOR_TEMPERATURE,
    DEFAULT_RADIATOR_POWER_KW,
    DEFAULT_ROOM_TEMPERATURE,
    DEFAULT_SIMULATION_ENABLED,
    DEFAULT_THERMAL_MASS,
    DEFAULT_TIME_SCALE,
    DEFAULT_UPDATE_INTERVAL,
    MAX_TEMP,
    MIN_TEMP,
    PRESET_TEMPERATURES,
    TEMP_TOLERANCE,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FakeHvacConfig:
    """User configuration for one simulated HVAC system."""

    name: str = DEFAULT_NAME
    room_temperature: float = DEFAULT_ROOM_TEMPERATURE
    outdoor_temperature: float = DEFAULT_OUTDOOR_TEMPERATURE
    radiator_power_kw: float = DEFAULT_RADIATOR_POWER_KW
    ac_power_kw: float = DEFAULT_AC_POWER_KW
    loss_coefficient: float = DEFAULT_LOSS_COEFFICIENT
    thermal_mass: float = DEFAULT_THERMAL_MASS
    update_interval: int = DEFAULT_UPDATE_INTERVAL
    time_scale: float = DEFAULT_TIME_SCALE
    simulation_enabled: bool = DEFAULT_SIMULATION_ENABLED

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> FakeHvacConfig:
        """Build a config from a config-entry mapping."""
        return cls(
            name=str(data.get("name", DEFAULT_NAME)),
            room_temperature=float(data.get("room_temperature", DEFAULT_ROOM_TEMPERATURE)),
            outdoor_temperature=float(data.get("outdoor_temperature", DEFAULT_OUTDOOR_TEMPERATURE)),
            radiator_power_kw=float(data.get("radiator_power_kw", DEFAULT_RADIATOR_POWER_KW)),
            ac_power_kw=float(data.get("ac_power_kw", DEFAULT_AC_POWER_KW)),
            loss_coefficient=float(data.get("loss_coefficient", DEFAULT_LOSS_COEFFICIENT)),
            thermal_mass=float(data.get("thermal_mass", DEFAULT_THERMAL_MASS)),
            update_interval=int(data.get("update_interval", DEFAULT_UPDATE_INTERVAL)),
            time_scale=float(data.get("time_scale", DEFAULT_TIME_SCALE)),
            simulation_enabled=bool(data.get("simulation_enabled", DEFAULT_SIMULATION_ENABLED)),
        )


class FakeHvacSystem:
    """A tiny thermal simulation shared by all fake entities."""

    def __init__(self, hass: HomeAssistant, entry_id: str, config: FakeHvacConfig) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.config = config

        self.room_temperature = config.room_temperature
        self.outdoor_temperature = config.outdoor_temperature
        self.room_available = True
        self.outdoor_available = True

        self.radiator_on = False
        self.ac_mode = HVACMode.OFF
        self.ac_target_temperature = DEFAULT_AC_TARGET_TEMPERATURE
        self.ac_preset_mode = "none"
        self.ac_power_on = False
        self.simulation_enabled = config.simulation_enabled

        self._listeners: set[Callable[[], None]] = set()
        self._cancel_timer: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Start the simulation ticker."""
        if self.config.update_interval <= 0:
            return
        self._cancel_timer = async_track_time_interval(
            self.hass,
            self._async_tick,
            timedelta(seconds=self.config.update_interval),
        )

    async def async_stop(self) -> None:
        """Stop the simulation ticker."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    async def _async_tick(self, _now: Any) -> None:
        await self.async_update()

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Register a state listener and return its remover."""
        self._listeners.add(callback)

        def remove_listener() -> None:
            self._listeners.discard(callback)

        return remove_listener

    def _notify(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                _LOGGER.exception("Fake HVAC listener failed")

    @property
    def thermal_power_w(self) -> float:
        """Current heating/cooling power in watts (negative = cooling)."""
        power_kw = self.config.radiator_power_kw if self.radiator_on else 0.0
        if self.ac_power_on:
            if self.ac_mode == HVACMode.HEAT:
                power_kw += self.config.ac_power_kw
            elif self.ac_mode == HVACMode.COOL:
                power_kw -= self.config.ac_power_kw
        return power_kw * 1000.0

    @property
    def ac_action(self) -> HVACAction:
        """Action reported by the fake AC."""
        if self.ac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if not self.ac_power_on:
            return HVACAction.IDLE
        if self.ac_mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if self.ac_mode == HVACMode.COOL:
            return HVACAction.COOLING
        return HVACAction.IDLE

    def _evaluate_ac(self) -> None:
        """Apply a simple thermostat hysteresis to the fake AC compressor."""
        if self.ac_mode == HVACMode.OFF:
            self.ac_power_on = False
            return

        if self.ac_mode == HVACMode.HEAT:
            if self.room_temperature <= self.ac_target_temperature - TEMP_TOLERANCE:
                self.ac_power_on = True
            elif self.room_temperature >= self.ac_target_temperature + TEMP_TOLERANCE:
                self.ac_power_on = False
            return

        if self.ac_mode == HVACMode.COOL:
            if self.room_temperature >= self.ac_target_temperature + TEMP_TOLERANCE:
                self.ac_power_on = True
            elif self.room_temperature <= self.ac_target_temperature - TEMP_TOLERANCE:
                self.ac_power_on = False

    def _step(self, seconds: float) -> None:
        """Advance the thermal model by a number of simulated seconds."""
        if seconds <= 0:
            return

        self._evaluate_ac()

        heat_kw = self.thermal_power_w / 1000.0
        loss_kw = self.config.loss_coefficient * (self.room_temperature - self.outdoor_temperature)
        self.room_temperature += (heat_kw - loss_kw) * (seconds / 3600.0) / self.config.thermal_mass
        self.room_temperature = max(-20.0, min(50.0, self.room_temperature))

    async def async_update(self, dt_seconds: float | None = None) -> None:
        """Advance one simulation tick."""
        if not self.simulation_enabled:
            return

        seconds = (
            dt_seconds
            if dt_seconds is not None
            else self.config.update_interval * self.config.time_scale
        )
        self._step(seconds)
        self._notify()

    async def async_advance(self, minutes: float) -> None:
        """Fast-forward the simulation by simulated minutes."""
        remaining = max(0.0, minutes * 60.0)
        step_seconds = 60.0
        while remaining > 0:
            seconds = min(step_seconds, remaining)
            self._step(seconds)
            remaining -= seconds
        self._notify()

    async def async_set_outdoor_temperature(self, value: float) -> None:
        self.outdoor_temperature = float(value)
        self._evaluate_ac()
        self._notify()

    async def async_set_room_temperature(self, value: float) -> None:
        self.room_temperature = max(-20.0, min(50.0, float(value)))
        self._evaluate_ac()
        self._notify()

    async def async_set_simulation(self, enabled: bool) -> None:
        self.simulation_enabled = bool(enabled)
        self._notify()

    async def async_set_availability(
        self, room: bool | None = None, outdoor: bool | None = None
    ) -> None:
        if room is not None:
            self.room_available = bool(room)
        if outdoor is not None:
            self.outdoor_available = bool(outdoor)
        self._notify()

    async def async_set_radiator(self, on: bool) -> None:
        self.radiator_on = bool(on)
        self._notify()

    async def async_set_ac_mode(self, mode: HVACMode) -> None:
        self.ac_mode = mode
        if mode == HVACMode.OFF:
            self.ac_power_on = False
        else:
            self._evaluate_ac()
        self._notify()

    async def async_set_ac_target(self, temperature: float) -> None:
        self.ac_target_temperature = max(MIN_TEMP, min(MAX_TEMP, float(temperature)))
        self.ac_preset_mode = "none"
        self._evaluate_ac()
        self._notify()

    async def async_set_ac_preset(self, preset: str) -> None:
        self.ac_preset_mode = preset
        if preset in PRESET_TEMPERATURES:
            self.ac_target_temperature = PRESET_TEMPERATURES[preset]
        self._evaluate_ac()
        self._notify()

    async def async_reset(self) -> None:
        self.room_temperature = self.config.room_temperature
        self.outdoor_temperature = self.config.outdoor_temperature
        self.room_available = True
        self.outdoor_available = True
        self.radiator_on = False
        self.ac_mode = HVACMode.OFF
        self.ac_target_temperature = DEFAULT_AC_TARGET_TEMPERATURE
        self.ac_preset_mode = "none"
        self.ac_power_on = False
        self.simulation_enabled = self.config.simulation_enabled
        self._notify()
