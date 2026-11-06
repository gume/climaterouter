"""Proxy climate entity."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity
from .models import (
    HVAC_COOL,
    HVAC_HEAT,
    HVAC_OFF,
    SetpointKind,
    Target,
)
from .vt_display import build_vt_display_attributes

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the proxy climate entity."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities([RouterClimate(coordinator, entry)])


class RouterClimate(RouterEntity, ClimateEntity):
    """Single climate entity that routes to one of the underlying thermostats."""

    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_climate"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.climate_entity_id = self.entity_id

    @property
    def available(self) -> bool:
        return self._snapshot.available

    @property
    def native_temperature_unit(self) -> str:
        return self.hass.config.units.temperature_unit

    @property
    def hvac_modes(self) -> list[HVACMode]:
        return [HVACMode(mode) for mode in self._snapshot.hvac_modes]

    @property
    def preset_modes(self) -> list[str]:
        return list(self._snapshot.preset_modes)

    @property
    def min_temp(self) -> float:
        return self._snapshot.min_temp

    @property
    def max_temp(self) -> float:
        return self._snapshot.max_temp

    @property
    def target_temperature_step(self) -> float:
        return self._snapshot.target_temp_step

    @property
    def _optimistic(self) -> bool:
        last = self._snapshot.last_command
        if last is None:
            return False
        settle = timedelta(seconds=self.coordinator.config.settle_time)
        return dt_util.utcnow() - last < settle

    @property
    def _active_state(self):
        snapshot = self._snapshot
        target = snapshot.active_target
        if target is not None:
            return snapshot.targets.get(target)
        if len(snapshot.active_targets) > 1:
            return snapshot.targets.get(Target.AC)
        return None

    @property
    def native_current_temperature(self) -> float | None:
        snapshot = self._snapshot
        values = [
            snapshot.targets[target].current_temperature
            for target in snapshot.active_targets
            if target in snapshot.targets
            and snapshot.targets[target].current_temperature is not None
        ]
        if values:
            return round(sum(values) / len(values), 2)
        return self._active_state.current_temperature if self._active_state else None

    @property
    def native_target_temperature(self) -> float | None:
        desired = self._snapshot.desired
        if self._optimistic and desired.setpoint_kind == SetpointKind.TEMPERATURE:
            return desired.target_temperature
        state = self._active_state
        return state.target_temperature if state else None

    @property
    def hvac_mode(self) -> HVACMode:
        snapshot = self._snapshot
        desired = snapshot.desired
        if desired.hvac_mode == HVAC_OFF:
            return HVACMode.OFF
        if self._optimistic and desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
            return HVACMode(desired.hvac_mode)
        state = self._active_state
        if state is None or state.hvac_mode in (None, HVAC_OFF):
            return HVACMode.OFF
        return HVACMode(state.hvac_mode)

    @property
    def hvac_action(self) -> HVACAction | None:
        snapshot = self._snapshot
        if snapshot.desired.hvac_mode == HVAC_OFF:
            return HVACAction.OFF
        actions = [
            snapshot.targets[target].hvac_action
            for target in snapshot.active_targets
            if target in snapshot.targets
        ]
        if "heating" in actions:
            return HVACAction.HEATING
        if "cooling" in actions:
            return HVACAction.COOLING
        if actions:
            return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def preset_mode(self) -> str | None:
        desired = self._snapshot.desired
        if self._optimistic and desired.setpoint_kind == SetpointKind.PRESET:
            return desired.preset_mode
        state = self._active_state
        return state.preset_mode if state and state.preset_mode else "none"

    @property
    def _vt_display_attributes(self) -> dict[str, Any]:
        """Return read-only VTherm display attributes for the active target."""
        snapshot = self._snapshot
        attributes: list[Mapping[str, Any]] = []
        for target in Target:
            if target not in snapshot.active_targets:
                continue
            state = snapshot.targets.get(target)
            if state is None:
                continue
            entity_state = self.hass.states.get(state.entity_id)
            if entity_state is not None:
                attributes.append(entity_state.attributes)
        return build_vt_display_attributes(attributes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self._snapshot
        state = self._active_state
        attributes = {
            "active_target": snapshot.active_label,
            "pending_target": (
                snapshot.pending_target.value if snapshot.pending_target else "none"
            ),
            "route_reason": snapshot.route_reason,
            "outdoor_temperature": snapshot.outdoor_temperature,
            "outdoor_sensor_stale": snapshot.outdoor_stale,
            "manual_switch_state": snapshot.manual_switch_state,
            "manual_switch_stale": snapshot.manual_switch_stale,
            "route_override": snapshot.route_override,
            "desired_hvac_mode": snapshot.desired.hvac_mode,
            "desired_preset_mode": snapshot.desired.preset_mode,
            "desired_temperature": snapshot.desired.target_temperature,
            "active_target_hvac_mode": state.hvac_mode if state else None,
            "active_target_preset_mode": state.preset_mode if state else None,
            "active_target_temperature": state.target_temperature if state else None,
            "override": snapshot.override.to_dict() if snapshot.override else None,
            "boost_active": snapshot.boost_until is not None,
            "boost_until": snapshot.boost_until.isoformat() if snapshot.boost_until else None,
            "boost_targets": sorted(target.value for target in snapshot.boost_targets),
            "conflict_count": snapshot.conflict_count,
            "conflicts": [conflict.to_dict() for conflict in snapshot.conflicts],
            "handover_state": snapshot.handover_state.value,
            "last_handover": snapshot.last_handover.isoformat() if snapshot.last_handover else None,
            "ready": snapshot.ready,
            "targets": {
                target.value: {
                    "entity_id": target_state.entity_id,
                    "available": target_state.available,
                    "hvac_mode": target_state.hvac_mode,
                    "hvac_action": target_state.hvac_action,
                    "preset_mode": target_state.preset_mode,
                    "target_temperature": target_state.target_temperature,
                    "current_temperature": target_state.current_temperature,
                    "guard": target_state.guard,
                }
                for target, target_state in snapshot.targets.items()
            },
        }
        # Cards such as Equinox recognise VTherm extras only when the climate
        # entity exposes VTherm's attribute names. Keep the proxy authoritative
        # and add only a read-only view of the active target.
        attributes.update(self._vt_display_attributes)
        return attributes

    async def async_set_temperature(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_temperature(
            temperature=kwargs.get(ATTR_TEMPERATURE),
            hvac_mode=kwargs.get(ATTR_HVAC_MODE),
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_set_hvac_mode(hvac_mode.value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.async_set_preset_mode(preset_mode)

    async def async_turn_on(self) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self) -> None:
        await self.coordinator.async_turn_off()
