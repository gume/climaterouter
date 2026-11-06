"""Coordinator: event listeners, routing, handover, and command forwarding."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_TARGET_TEMP_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONTEXT_TTL,
    DOMAIN,
    EVENT_HANDOVER_ABORTED,
    EVENT_HANDOVER_COMPLETED,
    EVENT_HANDOVER_STARTED,
    EVENT_OVERRIDE_ENDED,
    EVENT_OVERRIDE_STARTED,
    EVENT_ROUTE_CHANGED,
    STORAGE_KEY,
    STORAGE_VERSION,
    WATCHDOG_INTERVAL,
)
from .models import (
    DEFAULT_TEMPERATURE_TOLERANCE,
    HVAC_COOL,
    HVAC_HEAT,
    HVAC_OFF,
    MODES,
    ROUTE_AC,
    ROUTE_AUTO,
    ROUTE_RADIATOR,
    DesiredState,
    HandoverState,
    OverrideState,
    RouteDecision,
    RouteInputs,
    RouterConfig,
    RouterSnapshot,
    SetpointKind,
    Target,
    UnderlyingState,
)
from .router import choose_route, normalize_manual_select

_LOGGER = logging.getLogger(__name__)


class ClimateRouterCoordinator(DataUpdateCoordinator[RouterSnapshot]):
    """Own the router state machine for one config entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        config = RouterConfig.from_mapping({**entry.data, **entry.options})
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.title}",
            update_interval=None,
        )
        self.entry = entry
        self.config = config

        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id))
        self._lock = asyncio.Lock()

        self._states: dict[Target, UnderlyingState] = {
            Target.RADIATOR: UnderlyingState(entity_id=config.radiator_entity_id),
            Target.AC: UnderlyingState(entity_id=config.ac_entity_id),
        }
        self._outdoor_temperature: float | None = None
        self._outdoor_stale = True
        self._manual_switch_state: str | None = None
        self._manual_switch_stale = False

        self._baseline = DesiredState()
        self._desired = DesiredState()
        self._override: OverrideState | None = None
        self._override_unsub: Any | None = None
        self._active_targets: frozenset[Target] = frozenset()
        self._pending_target: Target | None = None
        self._handover_state = HandoverState.OFF
        self._route_reason = "off"
        self._route_override = ROUTE_AUTO
        self._last_route: Target | None = None
        self._last_handover: datetime | None = None
        self._last_command: datetime | None = None

        self._ready = False
        self._idle_since: datetime | None = None
        self._off_sent_at: datetime | None = None
        self._dwell_until: datetime | None = None
        self._handover_started_at: datetime | None = None
        self._handover_from: Target | None = None
        self._published_route: tuple[Target | None, str] | None = None

        self._contexts: dict[str, float] = {}
        self._unsubs: list[Any] = []
        self._timers: list[Any] = []
        self._update_scheduled = False

        self.climate_entity_id: str | None = None

        self.data = self._build_snapshot()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_initialize(self) -> None:
        """Load persisted state, subscribe to inputs, and start the watchdog."""
        await self._async_load_store()
        self._refresh_inputs()
        self.data = self._build_snapshot()
        if self._override is not None:
            self._schedule_override_expiry()

        entity_ids = [
            self.config.radiator_entity_id,
            self.config.ac_entity_id,
            self.config.outdoor_sensor_entity_id,
        ]
        if self.config.manual_switch_entity_id:
            entity_ids.append(self.config.manual_switch_entity_id)

        self._unsubs.append(
            async_track_state_change_event(self.hass, entity_ids, self._handle_state_change)
        )
        self._timers.append(
            async_track_time_interval(
                self.hass,
                self._async_watchdog,
                timedelta(seconds=WATCHDOG_INTERVAL),
            )
        )

        if self.config.startup_grace > 0:
            self._timers.append(
                async_call_later(
                    self.hass,
                    self.config.startup_grace,
                    self._async_startup_grace_elapsed,
                )
            )
        else:
            await self._async_reconcile()

    async def async_shutdown(self) -> None:
        """Cancel listeners and flush persisted state."""
        for unsub in self._unsubs:
            unsub()
        for timer in self._timers:
            timer()
        self._unsubs.clear()
        self._timers.clear()
        self._cancel_override_timer()
        await self._store.async_save(self._data_to_save())

    # ------------------------------------------------------------------
    # Commands received from the proxy entity
    # ------------------------------------------------------------------
    async def async_set_temperature(
        self,
        temperature: float | None = None,
        hvac_mode: str | None = None,
        preset_mode: str | None = None,
    ) -> None:
        """Handle a set_temperature-style command."""
        if temperature is None and hvac_mode is None and preset_mode is None:
            raise HomeAssistantError("No temperature, preset, or mode supplied")

        if hvac_mode is not None:
            self._apply_mode(hvac_mode)
        if preset_mode is not None:
            self._baseline.setpoint_kind = SetpointKind.PRESET
            self._baseline.preset_mode = preset_mode
            self._baseline.target_temperature = None
        if temperature is not None:
            self._baseline.setpoint_kind = SetpointKind.TEMPERATURE
            self._baseline.target_temperature = float(temperature)
            self._baseline.preset_mode = None

        await self._async_command_received()

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Handle an explicit HVAC mode change."""
        self._apply_mode(hvac_mode)
        await self._async_command_received()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Handle a preset change."""
        self._baseline.setpoint_kind = SetpointKind.PRESET
        self._baseline.preset_mode = preset_mode
        self._baseline.target_temperature = None
        await self._async_command_received()

    async def async_turn_on(self) -> None:
        """Turn the proxy on in the last known (or heat) mode."""
        if self._baseline.hvac_mode in (None, HVAC_OFF):
            self._baseline.hvac_mode = HVAC_HEAT
        await self._async_command_received()

    async def async_turn_off(self) -> None:
        """Turn everything off immediately."""
        self._baseline.hvac_mode = HVAC_OFF
        await self._async_command_received()

    async def async_set_route_override(self, value: str) -> None:
        """Set the built-in route override select."""
        if value not in (ROUTE_AUTO, ROUTE_RADIATOR, ROUTE_AC):
            raise HomeAssistantError(f"Unsupported route override: {value}")
        self._route_override = value
        await self.async_evaluate(explicit=True)

    @property
    def route_override(self) -> str:
        """Return the built-in route override (not the effective one)."""
        return self._route_override

    @property
    def route_override_options(self) -> list[str]:
        """Return valid options for the route override select."""
        return [ROUTE_AUTO, ROUTE_RADIATOR, ROUTE_AC]

    async def async_recalculate(self) -> None:
        """Force a route evaluation."""
        await self.async_evaluate(explicit=True)

    async def async_clear_conflicts(self) -> None:
        """Acknowledge conflicts (no conflict tracking before M5)."""
        self._publish()

    def _apply_mode(self, hvac_mode: str) -> None:
        """Update the desired HVAC mode with validation."""
        if hvac_mode not in MODES:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        if hvac_mode == HVAC_OFF:
            self._pending_target = None
            self._handover_state = HandoverState.OFF
            self._idle_since = None
        self._baseline.hvac_mode = hvac_mode

    async def _async_command_received(self) -> None:
        """Record the command, persist it, and evaluate the route."""
        self._last_command = dt_util.utcnow()
        if self._baseline.hvac_mode == HVAC_OFF and self._override is not None:
            # An explicit off is a safety command and ends any override.
            self._end_override("off")
        if self._override is not None:
            # Schedule commands update the baseline; the override keeps winning.
            self._override.baseline = self._baseline.copy()
        self._sync_desired()
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate(explicit=True)

    # ------------------------------------------------------------------
    # Manual override
    # ------------------------------------------------------------------
    async def async_set_manual_override(
        self,
        *,
        temperature: float | None = None,
        preset_mode: str | None = None,
        hvac_mode: str | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        """Start or replace a bounded manual override."""
        supplied = [value is not None for value in (temperature, preset_mode, hvac_mode)]
        if sum(supplied) != 1:
            raise HomeAssistantError(
                "Exactly one of temperature, preset_mode, or hvac_mode is required"
            )

        if hvac_mode == HVAC_OFF:
            await self.async_cancel_manual_override(cause="off")
            await self.async_set_hvac_mode(HVAC_OFF)
            return
        if hvac_mode is not None and hvac_mode not in MODES:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")

        duration = (
            self.config.default_override_minutes
            if duration_minutes is None
            else int(duration_minutes)
        )
        if duration < 1 or duration > self.config.max_override_minutes:
            raise HomeAssistantError(
                f"Override duration must be between 1 and {self.config.max_override_minutes} minutes"
            )

        now = dt_util.utcnow()
        if self._override is not None:
            # Keep the original baseline, but close the previous episode first.
            self._end_override("replaced")

        baseline = self._baseline.copy()
        if baseline.is_empty:
            active = self._single_active() or self._first_on_target()
            if active is not None:
                baseline = self._adopt_desired(active)
        self._baseline = baseline

        if temperature is not None:
            kind = "temperature"
            value: Any = float(temperature)
        elif preset_mode is not None:
            kind = "preset"
            value = str(preset_mode)
        else:
            kind = "hvac_mode"
            value = str(hvac_mode)

        self._override = OverrideState(
            kind=kind,
            value=value,
            until=now + timedelta(minutes=duration),
            baseline=self._baseline.copy(),
            started_at=now,
        )
        self._last_command = now
        self._sync_desired()
        self._schedule_override_expiry()
        self._store.async_delay_save(self._data_to_save, 1)

        self.hass.bus.async_fire(
            EVENT_OVERRIDE_STARTED,
            {
                "entry_id": self.entry.entry_id,
                "kind": kind,
                "value": value,
                "duration_minutes": duration,
                "until": self._override.until.isoformat(),
            },
        )
        await self.async_evaluate(explicit=True)

    async def async_cancel_manual_override(self, cause: str = "cancelled") -> None:
        """Cancel an active manual override and restore the baseline."""
        if self._override is None:
            return
        self._end_override(cause)
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate()

    def _end_override(self, cause: str) -> None:
        """Clear the override without forwarding; callers evaluate afterwards."""
        if self._override is None:
            return
        override = self._override
        self._cancel_override_timer()
        self._override = None
        self._sync_desired()
        self.hass.bus.async_fire(
            EVENT_OVERRIDE_ENDED,
            {
                "entry_id": self.entry.entry_id,
                "kind": override.kind,
                "cause": cause,
            },
        )

    def _sync_desired(self) -> None:
        """Recompute the effective desired state from baseline and override."""
        self._desired = self._baseline.with_override(self._override)

    async def _async_override_expired(self, _now: datetime) -> None:
        self._override_unsub = None
        if self._override is None:
            return
        if not self._override.is_expired(dt_util.utcnow()):
            self._schedule_override_expiry()
            return
        self._end_override("expired")
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate()

    def _schedule_override_expiry(self) -> None:
        """Schedule the exact deadline in addition to the watchdog check."""
        self._cancel_override_timer()
        if self._override is None:
            return
        delay = (self._override.until - dt_util.utcnow()).total_seconds()
        self._override_unsub = async_call_later(
            self.hass, max(delay, 0), self._async_override_expired
        )

    def _cancel_override_timer(self) -> None:
        if self._override_unsub is not None:
            self._override_unsub()
            self._override_unsub = None

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    async def async_evaluate(self, *, explicit: bool = False) -> None:
        """Recompute the route and advance any handover."""
        async with self._lock:
            self._refresh_inputs()

            if not self._ready:
                self._publish()
                return

            if self._desired.hvac_mode == HVAC_OFF:
                await self._async_stop_all()
                self._active_targets = frozenset()
                self._pending_target = None
                self._handover_state = HandoverState.OFF
                self._route_reason = "off"
                self._publish()
                return

            if not self._active_targets:
                self._adopt_from_active()

            if self._desired.is_empty:
                # Never issue commands before the first user command. If an
                # underlying thermostat came back on after a restart, adopt it.
                self._route_reason = self._route_decision().reason
                self._publish()
                return

            if self._desired.hvac_mode not in (HVAC_HEAT, HVAC_COOL):
                # A setpoint without a mode command must not start a target or
                # trigger a route change; forward it only to an active one.
                active = self._single_active()
                if active is not None:
                    await self._async_forward_desired(active)
                self._route_reason = self._route_decision().reason
                self._publish()
                return

            decision = self._route_decision()

            if self._handover_state in (
                HandoverState.PENDING,
                HandoverState.STOPPING_OLD,
                HandoverState.STARTING_NEW,
            ):
                await self._async_advance_handover(decision)
                self._publish()
                return

            target = self._single_target(decision)
            if target is None:
                if explicit and self._desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
                    raise HomeAssistantError("No available target can handle the requested mode")
                self._route_reason = decision.reason
                self._publish()
                return

            if (
                not explicit
                and self._active_targets
                and target not in self._active_targets
                and self._dwell_until is not None
                and dt_util.utcnow() < self._dwell_until
            ):
                self._route_reason = "dwell"
                self._publish()
                return

            if self._active_targets and target in self._active_targets:
                self._route_reason = decision.reason
                self._handover_state = HandoverState.STEADY
                await self._async_forward_desired(target)
            else:
                await self._async_begin_handover(target, decision.reason, explicit=explicit)

            self._publish()

    # ------------------------------------------------------------------
    # Handover state machine
    # ------------------------------------------------------------------
    async def _async_begin_handover(
        self, new_target: Target, reason: str, *, explicit: bool
    ) -> None:
        old_target = self._single_active()
        self._pending_target = new_target
        self._route_reason = reason
        self._handover_from = old_target
        self._handover_started_at = dt_util.utcnow()

        self.hass.bus.async_fire(
            EVENT_HANDOVER_STARTED,
            {
                "entry_id": self.entry.entry_id,
                "from_target": old_target.value if old_target else None,
                "to_target": new_target.value,
                "reason": reason,
                "old_action": self._states[old_target].hvac_action if old_target else None,
            },
        )

        if old_target is None or old_target is new_target:
            await self._async_start_new(new_target)
            return

        old_state = self._states[old_target]
        if old_state.is_off:
            await self._async_stop_old(old_target, new_target)
            return

        interrupt = explicit and self._desired.hvac_mode == HVAC_COOL
        if old_state.is_active and not interrupt:
            self._handover_state = HandoverState.PENDING
            self._idle_since = None
            _LOGGER.info(
                "Route changed to %s; waiting for %s to become idle",
                new_target.value,
                old_target.value,
            )
            return

        await self._async_stop_old(old_target, new_target)

    async def _async_advance_handover(self, decision: RouteDecision) -> None:
        route_target = self._single_target(decision) or self._pending_target
        old_target = self._single_active()
        now = dt_util.utcnow()

        if self._handover_state is HandoverState.PENDING:
            if route_target is None:
                return
            if old_target is None or route_target in self._active_targets:
                # The route reverted before the handover completed.
                self._pending_target = None
                self._handover_state = HandoverState.STEADY
                if self._active_targets:
                    await self._async_forward_desired(old_target)
                self._route_reason = decision.reason
                return

            old_state = self._states[old_target]
            if old_state.is_off:
                await self._async_start_new(route_target)
                return
            if not old_state.is_active:
                if self._idle_since is None:
                    self._idle_since = now
                    self._schedule_check(self.config.handover_idle_confirm)
                    return
                elapsed = (now - self._idle_since).total_seconds()
                if elapsed < self.config.handover_idle_confirm:
                    return
                await self._async_stop_old(old_target, route_target)
                return

            self._idle_since = None
            self._pending_target = route_target
            return

        if self._handover_state is HandoverState.STOPPING_OLD:
            if old_target is None or self._states[old_target].is_off:
                if route_target is not None:
                    await self._async_start_new(route_target)
                return
            if (
                self._off_sent_at is not None
                and (now - self._off_sent_at).total_seconds() > self.config.off_confirm_timeout
            ):
                self._handover_state = HandoverState.CONFLICT
                self._pending_target = None
                self._fire_aborted("off_confirm_timeout", to_target=route_target)
            return

        if self._handover_state is HandoverState.STARTING_NEW and route_target is not None:
            await self._async_start_new(route_target)

    async def _async_stop_old(self, old_target: Target, new_target: Target) -> None:
        """Send off to the old target and wait for confirmation."""
        self._handover_state = HandoverState.STOPPING_OLD
        self._pending_target = new_target
        self._off_sent_at = dt_util.utcnow()
        self._idle_since = None

        try:
            await self._async_climate_call(old_target, "set_hvac_mode", {"hvac_mode": HVAC_OFF})
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to stop %s: %s", old_target.value, err)
            self._handover_state = HandoverState.CONFLICT
            self._pending_target = None
            self._fire_aborted(str(err), to_target=new_target)
            return
        self._states[old_target] = self._read_target(old_target)
        self._schedule_check(self.config.off_confirm_timeout + 0.5)
        if self._states[old_target].is_off:
            await self._async_start_new(new_target)

    async def _async_start_new(self, target: Target) -> None:
        """Configure the new target and mark the handover complete."""
        mode = self._desired.hvac_mode or HVAC_HEAT
        capability = self._states[target].capability
        if not capability.available or not capability.can_handle(mode):
            self._handover_state = HandoverState.CONFLICT
            self._pending_target = None
            self._fire_aborted("target_unavailable", to_target=target)
            return

        try:
            if self._states[target].hvac_mode != mode:
                await self._async_climate_call(target, "set_hvac_mode", {"hvac_mode": mode})
                self._states[target] = self._read_target(target)

            if (
                self._desired.setpoint_kind == SetpointKind.TEMPERATURE
                and self._desired.target_temperature is not None
            ):
                await self._async_climate_call(
                    target,
                    "set_temperature",
                    {"temperature": self._desired.target_temperature},
                )
            elif (
                self._desired.setpoint_kind == SetpointKind.PRESET
                and self._desired.preset_mode is not None
            ):
                await self._async_climate_call(
                    target,
                    "set_preset_mode",
                    {"preset_mode": self._desired.preset_mode},
                )
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to start %s: %s", target.value, err)
            self._handover_state = HandoverState.CONFLICT
            self._pending_target = None
            self._fire_aborted(str(err), to_target=target)
            return

        self._states[target] = self._read_target(target)
        self._active_targets = frozenset({target})
        self._pending_target = None
        self._handover_state = HandoverState.STEADY
        self._last_route = target
        self._last_handover = dt_util.utcnow()
        self._dwell_until = self._last_handover + timedelta(seconds=self.config.min_route_dwell)
        duration = 0.0
        if self._handover_started_at is not None:
            duration = (self._last_handover - self._handover_started_at).total_seconds()
        self.hass.bus.async_fire(
            EVENT_HANDOVER_COMPLETED,
            {
                "entry_id": self.entry.entry_id,
                "from_target": self._handover_from.value if self._handover_from else None,
                "to_target": target.value,
                "duration_s": duration,
            },
        )
        self._handover_from = None
        self._handover_started_at = None

    async def _async_forward_desired(self, target: Target) -> None:
        """Forward the latest desired state to the active target."""
        state = self._states[target]
        desired = self._desired

        if desired.hvac_mode not in (None, HVAC_OFF) and state.hvac_mode != desired.hvac_mode:
            await self._async_climate_call(
                target, "set_hvac_mode", {"hvac_mode": desired.hvac_mode}
            )
            state = self._read_target(target)
            self._states[target] = state

        tolerance = self.config.temperature_tolerance or DEFAULT_TEMPERATURE_TOLERANCE

        if (
            desired.setpoint_kind == SetpointKind.TEMPERATURE
            and desired.target_temperature is not None
        ):
            if (
                state.target_temperature is None
                or abs(state.target_temperature - desired.target_temperature) > tolerance
            ):
                await self._async_climate_call(
                    target,
                    "set_temperature",
                    {"temperature": desired.target_temperature},
                )
        elif (
            desired.setpoint_kind == SetpointKind.PRESET
            and desired.preset_mode is not None
            and state.preset_mode != desired.preset_mode
        ):
            await self._async_climate_call(
                target, "set_preset_mode", {"preset_mode": desired.preset_mode}
            )

    async def _async_stop_all(self) -> None:
        """Turn off every target that is not already off."""
        for target in Target:
            if not self._states[target].is_off and self._states[target].available:
                try:
                    await self._async_climate_call(target, "set_hvac_mode", {"hvac_mode": HVAC_OFF})
                except HomeAssistantError as err:
                    _LOGGER.warning("Failed to turn off %s: %s", target.value, err)
                self._states[target] = self._read_target(target)

    # ------------------------------------------------------------------
    # Startup reconciliation
    # ------------------------------------------------------------------
    async def _async_startup_grace_elapsed(self, _now: datetime) -> None:
        await self._async_reconcile()

    async def _async_reconcile(self) -> None:
        """Adopt the actual state without interrupting active heating."""
        async with self._lock:
            self._refresh_inputs()
            on_targets = [
                target
                for target in Target
                if self._states[target].hvac_mode not in (None, HVAC_OFF)
            ]

            if len(on_targets) == 1:
                self._adopt_from_active()
            elif len(on_targets) > 1:
                active = [target for target in on_targets if self._states[target].is_active]
                self._active_targets = frozenset(on_targets)
                if len(active) > 1:
                    self._handover_state = HandoverState.CONFLICT
                    self._route_reason = "startup_conflict"
                else:
                    self._last_route = active[0] if active else None
                    self._handover_state = HandoverState.STEADY
            else:
                self._active_targets = frozenset()
                self._handover_state = (
                    HandoverState.OFF
                    if self._desired.hvac_mode in (None, HVAC_OFF)
                    else HandoverState.STEADY
                )

            self._ready = True
            self._publish()

        if self._desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
            # Not explicit: targets may still be starting up. A state change or
            # the watchdog retries once they are available.
            await self.async_evaluate()
            return

        async with self._lock:
            decision = self._route_decision()
            self._route_reason = "off" if self._desired.hvac_mode == HVAC_OFF else decision.reason
            self._publish()

    def _adopt_from_active(self) -> None:
        """Adopt an underlying target that is already on, without commanding it."""
        active = self._single_active()
        if active is None:
            on_targets = [
                target
                for target in Target
                if self._states[target].hvac_mode not in (None, HVAC_OFF)
            ]
            if len(on_targets) != 1:
                return
            active = on_targets[0]
            self._active_targets = frozenset({active})

        self._last_route = active
        self._handover_state = HandoverState.STEADY
        if self._baseline.is_empty:
            self._baseline = self._adopt_desired(active)
            self._sync_desired()

    def _adopt_desired(self, target: Target) -> DesiredState:
        state = self._states[target]
        preset = state.preset_mode
        return DesiredState(
            hvac_mode=state.hvac_mode or HVAC_HEAT,
            setpoint_kind=SetpointKind.PRESET
            if preset
            else SetpointKind.TEMPERATURE
            if state.target_temperature is not None
            else SetpointKind.NONE,
            preset_mode=preset,
            target_temperature=state.target_temperature,
        )

    # ------------------------------------------------------------------
    # Inputs and snapshot
    # ------------------------------------------------------------------
    @callback
    def _handle_state_change(self, _event: Event) -> None:
        """Schedule evaluation, coalescing bursts of state changes."""
        self._refresh_inputs()
        if not self._ready:
            self._publish()
            return
        if self._update_scheduled:
            return
        self._update_scheduled = True
        self.hass.async_create_task(self._async_run_scheduled_update())

    async def _async_run_scheduled_update(self) -> None:
        try:
            await self.async_evaluate()
        finally:
            self._update_scheduled = False

    async def _async_watchdog(self, _now: datetime) -> None:
        if not self._ready:
            return
        if self._override is not None and self._override.is_expired(dt_util.utcnow()):
            await self._async_override_expired(dt_util.utcnow())
        now = time.monotonic()
        for context_id in [key for key, expiry in self._contexts.items() if expiry < now]:
            self._contexts.pop(context_id, None)
        await self.async_evaluate()

    def _schedule_check(self, delay: float) -> None:
        """Run one evaluation after a delay, so time-based transitions advance."""
        self._timers.append(async_call_later(self.hass, max(delay, 0), self._async_scheduled_check))

    async def _async_scheduled_check(self, _now: datetime) -> None:
        if self._ready:
            await self.async_evaluate()

    def _refresh_inputs(self) -> None:
        for target in Target:
            self._states[target] = self._read_target(target)
        self._read_outdoor()
        self._read_manual_switch()

    def _read_target(self, target: Target) -> UnderlyingState:
        entity_id = (
            self.config.radiator_entity_id
            if target is Target.RADIATOR
            else self.config.ac_entity_id
        )
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return UnderlyingState(entity_id=entity_id, available=False)

        attrs = state.attributes
        return UnderlyingState(
            entity_id=entity_id,
            available=True,
            hvac_mode=state.state,
            hvac_action=attrs.get(ATTR_HVAC_ACTION),
            preset_mode=attrs.get(ATTR_PRESET_MODE),
            target_temperature=_as_float(attrs.get(ATTR_TEMPERATURE)),
            current_temperature=_as_float(attrs.get(ATTR_CURRENT_TEMPERATURE)),
            min_temp=_as_float(attrs.get(ATTR_MIN_TEMP)),
            max_temp=_as_float(attrs.get(ATTR_MAX_TEMP)),
            target_temp_step=_as_float(attrs.get(ATTR_TARGET_TEMP_STEP)),
            hvac_modes=tuple(attrs.get(ATTR_HVAC_MODES) or ()),
            preset_modes=tuple(attrs.get(ATTR_PRESET_MODES) or ()),
            last_updated=state.last_updated,
            guard=_extract_guard(attrs),
            timed_preset_active=_is_timed_preset(attrs),
        )

    def _read_outdoor(self) -> None:
        entity_id = self.config.outdoor_sensor_entity_id
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._outdoor_temperature = None
            self._outdoor_stale = True
            return

        value = _as_float(state.state)
        if value is None:
            self._outdoor_temperature = None
            self._outdoor_stale = True
            return

        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        target_unit = _ha_temperature_unit(self.hass)
        if unit and unit != target_unit:
            try:
                value = TemperatureConverter.convert(value, UnitOfTemperature(unit), target_unit)
            except (ValueError, TypeError):
                _LOGGER.debug("Could not convert outdoor temperature unit %s", unit)

        self._outdoor_temperature = round(value, 2)
        if state.last_updated is None:
            self._outdoor_stale = True
            return
        age = (dt_util.utcnow() - state.last_updated).total_seconds()
        self._outdoor_stale = age > self.config.outdoor_stale_after

    def _read_manual_switch(self) -> None:
        entity_id = self.config.manual_switch_entity_id
        if not entity_id:
            self._manual_switch_state = None
            self._manual_switch_stale = False
            return

        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._manual_switch_stale = True
            return

        self._manual_switch_stale = False
        if entity_id.startswith("input_select."):
            self._manual_switch_state = normalize_manual_select(state.state)
        elif state.state == STATE_ON:
            self._manual_switch_state = STATE_ON
        else:
            self._manual_switch_state = STATE_OFF

    def _route_override_value(self) -> str:
        """Return the effective route override (built-in select wins)."""
        if self._route_override != ROUTE_AUTO:
            return self._route_override
        if self.config.manual_switch_entity_id and self.config.manual_switch_entity_id.startswith(
            "input_select."
        ):
            return self._manual_switch_state or ROUTE_AUTO
        return ROUTE_AUTO

    def _route_decision(self) -> RouteDecision:
        capabilities = {target: self._states[target].capability for target in Target}
        inputs = RouteInputs(
            hvac_mode=self._desired.hvac_mode or HVAC_HEAT,
            route_override=self._route_override_value(),
            manual_switch=self._manual_switch_state,
            manual_switch_on_target=self.config.manual_switch_on_target,
            outdoor_temperature=self._outdoor_temperature,
            outdoor_fresh=not self._outdoor_stale,
            current_target=self._current_route_target(),
            capabilities=capabilities,
            cold_threshold=self.config.cold_threshold,
            mild_threshold=self.config.mild_threshold,
            fallback_on_unavailable=self.config.fallback_on_unavailable,
            boost_active=False,
        )
        return choose_route(inputs)

    def _current_route_target(self) -> Target | None:
        return self._single_active() or self._last_route

    def _single_active(self) -> Target | None:
        if len(self._active_targets) == 1:
            return next(iter(self._active_targets))
        return None

    def _first_on_target(self) -> Target | None:
        """Return the first target whose HVAC mode is not off, if any."""
        for target in Target:
            if self._states[target].hvac_mode not in (None, HVAC_OFF):
                return target
        return None

    @staticmethod
    def _single_target(decision: RouteDecision) -> Target | None:
        if len(decision.targets) == 1:
            return next(iter(decision.targets))
        return None

    def _build_snapshot(self) -> RouterSnapshot:
        radiator = self._states[Target.RADIATOR]
        ac = self._states[Target.AC]

        hvac_modes = [HVAC_OFF, HVAC_HEAT]
        if ac.capability.can_handle(HVAC_COOL):
            hvac_modes.append(HVAC_COOL)

        presets = set(radiator.preset_modes) & set(ac.preset_modes)
        if not presets:
            presets = set(radiator.preset_modes) or set(ac.preset_modes)
        presets.add("none")

        active_state = self._states.get(self._single_active()) if self._single_active() else None
        if active_state is None:
            active_state = ac if ac.available else radiator

        return RouterSnapshot(
            ready=self._ready,
            available=radiator.available or ac.available,
            active_targets=self._active_targets,
            pending_target=self._pending_target,
            route_reason=self._route_reason,
            handover_state=self._handover_state,
            desired=self._desired,
            override=self._override,
            boost_until=None,
            conflicts=(),
            outdoor_temperature=self._outdoor_temperature,
            outdoor_stale=self._outdoor_stale,
            manual_switch_state=self._manual_switch_state,
            manual_switch_stale=self._manual_switch_stale,
            route_override=self._route_override_value(),
            last_handover=self._last_handover,
            last_command=self._last_command,
            targets=dict(self._states),
            hvac_modes=tuple(hvac_modes),
            preset_modes=tuple(sorted(presets)),
            min_temp=active_state.min_temp or 7.0,
            max_temp=active_state.max_temp or 35.0,
            target_temp_step=active_state.target_temp_step or 0.5,
        )

    def _publish(self) -> None:
        snapshot = self._build_snapshot()
        route_target = snapshot.active_target
        key = (route_target, snapshot.route_reason)
        previous_target = self._published_route[0] if self._published_route else None
        if self._ready and self._published_route is not None and route_target != previous_target:
            self._fire_route_changed(previous_target, route_target)
        self._published_route = key
        self.async_set_updated_data(snapshot)

    # ------------------------------------------------------------------
    # Service calls and events
    # ------------------------------------------------------------------
    async def _async_climate_call(self, target: Target, service: str, data: dict[str, Any]) -> None:
        state = self._states[target]
        context = Context()
        self._contexts[context.id] = time.monotonic() + CONTEXT_TTL
        _LOGGER.debug("Calling climate.%s on %s: %s", service, state.entity_id, data)
        await self.hass.services.async_call(
            "climate",
            service,
            {"entity_id": state.entity_id, **data},
            blocking=True,
            context=context,
        )

    def _fire_aborted(self, error: str, to_target: Target | None = None) -> None:
        old_target = self._single_active()
        target = to_target or self._pending_target
        self.hass.bus.async_fire(
            EVENT_HANDOVER_ABORTED,
            {
                "entry_id": self.entry.entry_id,
                "from_target": old_target.value if old_target else None,
                "to_target": target.value if target else None,
                "error": error,
            },
        )

    def _fire_route_changed(self, old: Target | None, new: Target | None) -> None:
        self.hass.bus.async_fire(
            EVENT_ROUTE_CHANGED,
            {
                "entry_id": self.entry.entry_id,
                "old_target": old.value if old else None,
                "new_target": new.value if new else None,
                "reason": self._route_reason,
                "outdoor_temperature": self._outdoor_temperature,
                "manual_switch": self._manual_switch_state,
            },
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    async def _async_load_store(self) -> None:
        data = await self._store.async_load()
        if not data:
            return
        desired = data.get("desired")
        if isinstance(desired, dict):
            self._baseline = DesiredState.from_dict(desired)
        override_data = data.get("override")
        if isinstance(override_data, dict):
            override = OverrideState.from_dict(override_data)
            if override is not None and not override.is_expired(dt_util.utcnow()):
                self._override = override
        self._sync_desired()
        last_route = data.get("last_route")
        if last_route in (Target.RADIATOR.value, Target.AC.value):
            self._last_route = Target(last_route)

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "version": STORAGE_VERSION,
            "desired": self._baseline.to_dict(),
            "override": self._override.to_dict() if self._override is not None else None,
            "last_route": self._last_route.value if self._last_route else None,
        }


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ha_temperature_unit(hass: HomeAssistant) -> UnitOfTemperature:
    try:
        return hass.config.units.temperature_unit
    except AttributeError:  # pragma: no cover - future HA API
        return UnitOfTemperature.CELSIUS


def _extract_guard(attrs: dict[str, Any]) -> str | None:
    specific = attrs.get("specific_states") or {}
    if isinstance(specific, dict):
        for key in ("hvac_mode_reason", "hvac_off_reason"):
            reason = specific.get(key)
            if reason:
                return str(reason)
    for key, label in (
        ("window_state", "window"),
        ("window_auto_state", "window"),
        ("safety_state", "safety"),
        ("overpowering_state", "power"),
    ):
        if attrs.get(key) in (STATE_ON, "on", True):
            return label
    preset = attrs.get(ATTR_PRESET_MODE)
    if preset in ("power", "safety"):
        return str(preset)
    return None


def _is_timed_preset(attrs: dict[str, Any]) -> bool:
    manager = attrs.get("timed_preset_manager") or {}
    return bool(isinstance(manager, dict) and manager.get("is_active"))
