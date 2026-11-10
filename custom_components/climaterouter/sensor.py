"""Sensors exposing router state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity
from .models import Conflict, RouterSnapshot, Target

PARALLEL_UPDATES = 0


TARGET_ICONS: dict[str, str] = {
    "radiator": "mdi:radiator",
    "ac": "mdi:air-conditioner",
    "both": "mdi:hvac",
    "none": "mdi:hvac-off",
}

CONFLICT_LABELS: dict[str, str] = {
    "target_unavailable": "unavailable",
    "hvac_mode_mismatch": "mode",
    "setpoint_mismatch": "setpoint",
    "preset_mismatch": "preset",
    "underlying_override": "timed preset",
    "both_targets_on": "both targets on",
    "inactive_target_on": "inactive target on",
}


def _format_value(value: Any) -> str:
    if value is None:
        return "?"
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _format_conflict(conflict: Conflict) -> str:
    """Return one short, human-readable conflict description."""
    target = conflict.target.value if conflict.target else "router"
    label = CONFLICT_LABELS.get(conflict.type, conflict.type)
    if conflict.type in ("setpoint_mismatch", "preset_mismatch", "hvac_mode_mismatch"):
        return (
            f"{target} {label} "
            f"{_format_value(conflict.expected)} -> {_format_value(conflict.actual)}"
        )
    if conflict.type == "both_targets_on":
        return label
    return f"{target} {label}"


def _truncate(value: str, limit: int = 250) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}…"


def _conflict_detail(snapshot: RouterSnapshot) -> str:
    if not snapshot.conflicts:
        return "none"
    return _truncate("; ".join(_format_conflict(conflict) for conflict in snapshot.conflicts))


def _target_mismatch_detail(snapshot: RouterSnapshot) -> str:
    reasons = snapshot.target_mismatch_reasons()
    if not reasons:
        return "none"

    radiator = snapshot.targets.get(Target.RADIATOR)
    ac = snapshot.targets.get(Target.AC)
    notes: list[str] = []
    for label, state in (("radiator", radiator), ("ac", ac)):
        if state is None:
            notes.append(f"{label} unknown")
        elif not state.available:
            notes.append(f"{label} unavailable")
        elif state.hvac_mode in (None, "off"):
            notes.append(f"{label} off")

    detail = "; ".join(reasons)
    if notes:
        detail = f"{', '.join(notes)}; {detail}"
    return _truncate(detail)


def _conflict_attributes(snapshot: RouterSnapshot) -> dict[str, Any]:
    return {
        "count": len(snapshot.conflicts),
        "conflicts": [conflict.to_dict() for conflict in snapshot.conflicts],
    }


def _target_mismatch_attributes(snapshot: RouterSnapshot) -> dict[str, Any]:
    radiator = snapshot.targets.get(Target.RADIATOR)
    ac = snapshot.targets.get(Target.AC)
    return {
        "reasons": list(snapshot.target_mismatch_reasons()),
        "radiator_target_temperature": (
            radiator.target_temperature if radiator is not None else None
        ),
        "ac_target_temperature": ac.target_temperature if ac is not None else None,
        "radiator_preset_mode": radiator.preset_mode if radiator is not None else None,
        "ac_preset_mode": ac.preset_mode if ac is not None else None,
        "radiator_hvac_mode": radiator.hvac_mode if radiator is not None else None,
        "ac_hvac_mode": ac.hvac_mode if ac is not None else None,
        "radiator_available": radiator.available if radiator is not None else None,
        "ac_available": ac.available if ac is not None else None,
    }


def _active_target(snapshot: RouterSnapshot) -> str:
    return snapshot.active_label


def _pending_target(snapshot: RouterSnapshot) -> str:
    return snapshot.pending_target.value if snapshot.pending_target else "none"


def _manual_remaining(snapshot: RouterSnapshot) -> int | None:
    if snapshot.manual_mode is None or snapshot.manual_mode.is_expired(dt_util.utcnow()):
        # An inactive or expired countdown reads as zero instead of unknown, so
        # dashboards and templates keep a numeric state.
        return 0
    return snapshot.manual_mode.remaining_minutes(dt_util.utcnow())


def _boost_remaining(snapshot: RouterSnapshot) -> int:
    if snapshot.boost_until is None:
        return 0
    seconds = (snapshot.boost_until - dt_util.utcnow()).total_seconds()
    if seconds <= 0:
        return 0
    return int((seconds + 59.9) // 60)


SENSOR_SPECS: tuple[
    tuple[
        str,
        str,
        SensorDeviceClass | None,
        SensorStateClass | None,
        EntityCategory | None,
        str | None,
        Callable[[RouterSnapshot], Any],
    ],
    ...,
] = (
    (
        "active_target",
        "Active target",
        None,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        _active_target,
    ),
    (
        "pending_target",
        "Pending target",
        None,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        _pending_target,
    ),
    (
        "route_reason",
        "Route reason",
        None,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        lambda snapshot: snapshot.route_reason,
    ),
    (
        "outdoor_temperature",
        "Outdoor temperature",
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        None,
        None,
        lambda snapshot: snapshot.outdoor_temperature,
    ),
    (
        "manual_remaining",
        "Manual remaining",
        None,
        None,
        None,
        "min",
        _manual_remaining,
    ),
    (
        "manual_until",
        "Manual until",
        SensorDeviceClass.TIMESTAMP,
        None,
        None,
        None,
        lambda snapshot: snapshot.manual_until,
    ),
    (
        "manual_timer_minutes",
        "Manual timer",
        None,
        None,
        EntityCategory.DIAGNOSTIC,
        "min",
        lambda snapshot: snapshot.manual_timer_minutes,
    ),
    (
        "boost_remaining",
        "Boost remaining",
        None,
        None,
        None,
        "min",
        _boost_remaining,
    ),
    (
        "last_handover",
        "Last handover",
        SensorDeviceClass.TIMESTAMP,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        lambda snapshot: snapshot.last_handover,
    ),
    (
        "last_command",
        "Last command",
        SensorDeviceClass.TIMESTAMP,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        lambda snapshot: snapshot.last_command,
    ),
    (
        "conflict_count",
        "Conflict count",
        None,
        SensorStateClass.MEASUREMENT,
        EntityCategory.DIAGNOSTIC,
        None,
        lambda snapshot: snapshot.conflict_count,
    ),
    (
        "conflict_detail",
        "Conflict detail",
        None,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        _conflict_detail,
    ),
    (
        "target_mismatch_detail",
        "Target mismatch detail",
        None,
        None,
        EntityCategory.DIAGNOSTIC,
        None,
        _target_mismatch_detail,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the router sensors."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities(RouterSensor(coordinator, entry, *spec) for spec in SENSOR_SPECS)


class RouterSensor(RouterEntity, SensorEntity):
    """Read-only sensor backed by the router snapshot."""

    def __init__(
        self,
        coordinator: ClimateRouterCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        state_class: SensorStateClass | None,
        entity_category: EntityCategory | None,
        unit: str | None,
        value_fn: Callable[[RouterSnapshot], Any],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._value_fn = value_fn
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._attr_icon = None
        if unit is not None:
            self._attr_native_unit_of_measurement = unit
        elif device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = coordinator.hass.config.units.temperature_unit

    @property
    def icon(self) -> str | None:
        if self._key in ("active_target", "pending_target"):
            return TARGET_ICONS.get(self._value_fn(self._snapshot), "mdi:eye")
        if self._key == "conflict_detail":
            return (
                "mdi:alert-circle-outline"
                if self._snapshot.conflicts
                else "mdi:check-circle-outline"
            )
        if self._key == "target_mismatch_detail":
            return (
                "mdi:alert-circle-outline"
                if self._snapshot.target_mismatch_reasons()
                else "mdi:check-circle-outline"
            )
        return self._attr_icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key == "conflict_detail":
            return _conflict_attributes(self._snapshot)
        if self._key == "target_mismatch_detail":
            return _target_mismatch_attributes(self._snapshot)
        return None

    @property
    def native_value(self) -> Any:
        value = self._value_fn(self._snapshot)
        if isinstance(value, datetime):
            return value
        return value
