"""Route override select entity."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ClimateRouterCoordinator
from .entity import RouterEntity
from .models import READ_ONLY_MODES

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the route override, read-only, and manual timer selects."""
    coordinator: ClimateRouterCoordinator = entry.runtime_data
    async_add_entities(
        [
            RouterRouteOverrideSelect(coordinator, entry),
            RouterReadOnlySelect(coordinator, entry),
            RouterManualTimerSelect(coordinator, entry),
        ]
    )


class RouterRouteOverrideSelect(RouterEntity, SelectEntity):
    """Force routing to one target, independent of the outdoor sensor."""

    _attr_name = "Route override"
    _attr_icon = "mdi:source-branch"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_route_override"

    @property
    def options(self) -> list[str]:
        return self.coordinator.route_override_options

    @property
    def current_option(self) -> str:
        return self.coordinator.route_override

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_route_override(option)


class RouterReadOnlySelect(RouterEntity, SelectEntity):
    """Choose whether the router may write to the underlying thermostats."""

    _attr_name = "Read-only mode"
    _attr_icon = "mdi:eye-off-outline"

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_read_only_mode"

    @property
    def options(self) -> list[str]:
        return list(READ_ONLY_MODES)

    @property
    def current_option(self) -> str:
        return self.coordinator.read_only_mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_read_only_mode(option)


class RouterManualTimerSelect(RouterEntity, SelectEntity):
    """Choose or switch off the manual-mode countdown."""

    _attr_name = "Manual timer"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ClimateRouterCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_manual_timer"

    @property
    def options(self) -> list[str]:
        """Return timer lengths, including the configured default."""
        values = {15, 30, 60, 120, 240}
        if self.coordinator.config.default_manual_minutes > 0:
            values.add(self.coordinator.config.default_manual_minutes)
        return ["off", *(str(value) for value in sorted(values))]

    @property
    def current_option(self) -> str:
        """Return the selected timer length, or ``off`` when unused."""
        timer = self._snapshot.manual_timer_minutes
        return "off" if timer is None else str(timer)

    @property
    def icon(self) -> str:
        """Show a crossed-out timer while no countdown is running."""
        if self.current_option == "off":
            return "mdi:timer-off-outline"
        return "mdi:timer-outline"

    async def async_select_option(self, option: str) -> None:
        minutes = None if option == "off" else int(option)
        if minutes is None and not self._snapshot.manual_active:
            # ``off`` is the resting state and can be selected as a no-op when
            # manual mode is not active.
            return
        await self.coordinator.async_set_manual_timer(minutes=minutes, context=self._context)
