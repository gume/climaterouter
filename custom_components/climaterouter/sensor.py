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
from .models import RouterSnapshot

PARALLEL_UPDATES = 0


def _active_target(snapshot: RouterSnapshot) -> str:
    return snapshot.active_label


def _pending_target(snapshot: RouterSnapshot) -> str:
    return snapshot.pending_target.value if snapshot.pending_target else "none"


def _override_remaining(snapshot: RouterSnapshot) -> int | None:
    if snapshot.manual_mode is None:
        return None
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
        None,
        None,
        _active_target,
    ),
    (
        "pending_target",
        "Pending target",
        None,
        None,
        None,
        None,
        _pending_target,
    ),
    (
        "route_reason",
        "Route reason",
        None,
        None,
        None,
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
        "override_remaining",
        "Override remaining",
        None,
        None,
        None,
        "min",
        _override_remaining,
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
        self._value_fn = value_fn
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        if unit is not None:
            self._attr_native_unit_of_measurement = unit
        elif device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = coordinator.hass.config.units.temperature_unit

    @property
    def native_value(self) -> Any:
        value = self._value_fn(self._snapshot)
        if isinstance(value, datetime):
            return value
        return value
