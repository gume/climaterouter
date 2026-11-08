"""Binary sensors exposing router state."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity
from .models import HVAC_OFF, RouterSnapshot, Target

PARALLEL_UPDATES = 0


def _target_active(target: Target) -> Callable[[RouterSnapshot], bool]:
    def _value(snapshot: RouterSnapshot) -> bool:
        return target in snapshot.active_targets and snapshot.desired.hvac_mode != HVAC_OFF

    return _value


def _action_is(action: str) -> Callable[[RouterSnapshot], bool]:
    def _value(snapshot: RouterSnapshot) -> bool:
        return any(
            state.hvac_action == action for state in snapshot.targets.values() if state.available
        )

    return _value


def _both_targets_differ(snapshot: RouterSnapshot) -> bool:
    radiator = snapshot.targets.get(Target.RADIATOR)
    ac = snapshot.targets.get(Target.AC)
    if radiator is None or ac is None:
        return False
    if (
        radiator.target_temperature is not None
        and ac.target_temperature is not None
        and abs(radiator.target_temperature - ac.target_temperature) > 0.2
    ):
        return True
    return bool(radiator.preset_mode and ac.preset_mode and radiator.preset_mode != ac.preset_mode)


SENSOR_SPECS: tuple[
    tuple[
        str,
        str,
        BinarySensorDeviceClass | None,
        EntityCategory | None,
        Callable[[RouterSnapshot], bool],
    ],
    ...,
] = (
    ("radiator_active", "Radiator active", None, None, _target_active(Target.RADIATOR)),
    ("ac_active", "AC active", None, None, _target_active(Target.AC)),
    (
        "heating",
        "Heating",
        BinarySensorDeviceClass.HEAT,
        None,
        _action_is("heating"),
    ),
    (
        "cooling",
        "Cooling",
        BinarySensorDeviceClass.COLD,
        None,
        _action_is("cooling"),
    ),
    (
        "handover_pending",
        "Handover pending",
        None,
        None,
        lambda snapshot: snapshot.handover_state.value == "pending",
    ),
    (
        "manual_mode",
        "Manual mode",
        None,
        None,
        lambda snapshot: snapshot.manual_mode is not None,
    ),
    (
        "boost_active",
        "Boost active",
        None,
        None,
        lambda snapshot: snapshot.boost_until is not None,
    ),
    (
        "conflict",
        "Conflict",
        BinarySensorDeviceClass.PROBLEM,
        EntityCategory.DIAGNOSTIC,
        lambda snapshot: bool(snapshot.conflicts),
    ),
    (
        "outdoor_sensor_stale",
        "Outdoor sensor stale",
        BinarySensorDeviceClass.PROBLEM,
        EntityCategory.DIAGNOSTIC,
        lambda snapshot: snapshot.outdoor_stale,
    ),
    (
        "target_mismatch",
        "Target mismatch",
        BinarySensorDeviceClass.PROBLEM,
        EntityCategory.DIAGNOSTIC,
        _both_targets_differ,
    ),
    (
        "ready",
        "Ready",
        None,
        EntityCategory.DIAGNOSTIC,
        lambda snapshot: snapshot.ready,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the router binary sensors."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities(RouterBinarySensor(coordinator, entry, *spec) for spec in SENSOR_SPECS)


class RouterBinarySensor(RouterEntity, BinarySensorEntity):
    """Read-only binary sensor backed by the router snapshot."""

    def __init__(
        self,
        coordinator: ClimateRouterCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        device_class: BinarySensorDeviceClass | None,
        entity_category: EntityCategory | None,
        value_fn: Callable[[RouterSnapshot], bool],
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._value_fn = value_fn
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_class = device_class
        self._attr_entity_category = entity_category

    @property
    def is_on(self) -> bool:
        return self._value_fn(self._snapshot)
