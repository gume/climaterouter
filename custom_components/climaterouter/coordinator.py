"""Coordinator: event listeners, routing, handover, and command forwarding."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate.const import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
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
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import (
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
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
    CONFLICT_CLEAR_AFTER,
    CONFLICT_REASSERT_GRACE,
    CONTEXT_TTL,
    DOMAIN,
    EVENT_BOOST_ENDED,
    EVENT_BOOST_STARTED,
    EVENT_CONFLICT_CLEARED,
    EVENT_CONFLICT_DETECTED,
    EVENT_HANDOVER_ABORTED,
    EVENT_HANDOVER_COMPLETED,
    EVENT_HANDOVER_STARTED,
    EVENT_MANUAL_MODE_ENDED,
    EVENT_MANUAL_MODE_STARTED,
    EVENT_MANUAL_TIMER_CHANGED,
    EVENT_ROUTE_CHANGED,
    STORAGE_KEY,
    STORAGE_VERSION,
    WATCHDOG_INTERVAL,
)
from .models import (
    DEFAULT_BOOST_MINUTES,
    DEFAULT_MAX_BOOST_MINUTES,
    DEFAULT_TEMPERATURE_TOLERANCE,
    HVAC_COOL,
    HVAC_HEAT,
    HVAC_OFF,
    MODES,
    PRESET_OFF,
    READ_ONLY_HARD,
    READ_ONLY_MODES,
    READ_ONLY_OFF,
    ROUTE_AUTO,
    BoostState,
    Conflict,
    DesiredState,
    HandoverState,
    ManualMode,
    OffPresetHold,
    RouteDecision,
    RouteInputs,
    RouterConfig,
    RouterSnapshot,
    SetpointKind,
    Target,
    UnderlyingState,
    lock_blocks_context,
)
from .router import choose_route, target_conflict

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

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id)
        )
        self._lock = asyncio.Lock()

        self._states: dict[Target, UnderlyingState] = {
            Target.RADIATOR: UnderlyingState(entity_id=config.radiator_entity_id),
            Target.AC: UnderlyingState(entity_id=config.ac_entity_id),
        }
        self._outdoor_temperature: float | None = None
        self._outdoor_stale = True

        self._baseline = DesiredState()
        self._desired = DesiredState()
        self._last_live: DesiredState | None = None
        self._manual: ManualMode | None = None
        self._manual_unsub: Any | None = None
        self._off_preset: OffPresetHold | None = None
        self._off_preset_pending = False
        self._boost: BoostState | None = None
        self._boost_unsub: Any | None = None
        self._active_targets: frozenset[Target] = frozenset()
        self._pending_target: Target | None = None
        self._handover_state = HandoverState.OFF
        self._route_reason = "off"
        self._route_override = ROUTE_AUTO
        self._last_route: Target | None = None
        self._last_handover: datetime | None = None
        self._last_command: datetime | None = None

        self._locked = False
        self._auto_relock_unsub: Any | None = None
        self._auto_relock_at: datetime | None = None
        self._pause_switch_active: bool | None = None
        self._read_only_mode_value = config.read_only_mode

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

        self._conflicts: dict[str, Conflict] = {}
        self._conflict_history: list[Conflict] = []
        self._conflict_count = 0
        self._conflict_cleared_since: dict[str, datetime] = {}
        self._conflict_reasserted: set[str] = set()
        self._suppress_conflicts_until: datetime | None = None
        self._last_state_source: dict[Target, str] = {}
        self._idle_bypass_applied = False

        self.climate_entity_id: str | None = None
        self.lock_entity_id: str | None = None

        self.data = self._build_snapshot()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_initialize(self) -> None:
        """Load persisted state, subscribe to inputs, and start the watchdog."""
        await self._async_load_store()
        self._refresh_inputs()
        if self._manual is not None:
            self._schedule_manual_expiry()
            # A restored manual session must continue to keep Velair out.
            await self._async_velair_pause()
            await self._async_set_pause_switch(True)
        if self._boost is not None:
            self._schedule_boost_expiry()
        if self._auto_relock_at is not None:
            remaining = (self._auto_relock_at - dt_util.utcnow()).total_seconds()
            if remaining <= 0:
                self._locked = True
                self._auto_relock_at = None
                self._store.async_delay_save(self._data_to_save, 1)
            else:
                self._schedule_auto_relock(remaining)
        self.data = self._build_snapshot()

        entity_ids = [
            entity_id
            for entity_id in (
                self.config.radiator_entity_id,
                self.config.ac_entity_id,
                self.config.outdoor_sensor_entity_id,
            )
            if entity_id
        ]

        if entity_ids:
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
        self._cancel_manual_timer()
        self._cancel_boost_timer()
        self._cancel_auto_relock()
        if self._manual is not None:
            await self._async_velair_resume()
        if self._pause_switch_active:
            await self._async_set_pause_switch(False)
        await self._store.async_save(self._data_to_save())

    # ------------------------------------------------------------------
    # Commands received from the proxy entity
    # ------------------------------------------------------------------
    @staticmethod
    def _is_user_context(context: Context | None) -> bool:
        """Return whether a command came from a user (UI/service), not a schedule."""
        return context is not None and context.user_id is not None

    def _read_only_mode(self) -> str:
        """Return the read-only level that applies to the current mode.

        Manual mode always allows the user to write, while schedule and
        automation commands are deferred. The runtime selector therefore only
        applies outside manual mode.
        """
        if self._manual is not None:
            return READ_ONLY_OFF
        return self._read_only_mode_value

    @property
    def read_only_mode(self) -> str:
        """Return the runtime read-only level for schedule control."""
        return self._read_only_mode_value

    async def async_set_read_only_mode(self, value: str) -> None:
        """Set the runtime read-only level used outside manual mode."""
        if value not in READ_ONLY_MODES:
            raise HomeAssistantError(f"Unsupported read-only mode: {value}")
        if value == self._read_only_mode_value:
            return
        self._read_only_mode_value = value
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate(explicit=True)

    def _configured_targets(self) -> frozenset[Target]:
        """Return the underlying targets that are configured."""
        return self.config.configured_targets

    def _single_configured_target(self) -> Target | None:
        """Return the only configured target, if any."""
        return self.config.single_target

    def _read_only_mirror(self) -> None:
        """Adopt the actual underlying state without issuing any command."""
        configured = self._configured_targets()
        on_targets = [
            target
            for target in configured
            if self._states[target].hvac_mode not in (None, HVAC_OFF)
        ]
        self._pending_target = None
        self._off_sent_at = None
        self._idle_since = None
        if len(on_targets) == 1:
            target = on_targets[0]
            self._active_targets = frozenset({target})
            self._last_route = target
            self._handover_state = HandoverState.STEADY
        elif len(on_targets) > 1:
            self._active_targets = frozenset(on_targets)
            self._handover_state = HandoverState.STEADY
        else:
            self._active_targets = frozenset()
            self._handover_state = HandoverState.OFF
        self._route_reason = "read_only"

    def _evaluate_read_only(self) -> None:
        """Recompute the visible route while writes are suppressed.

        Hard mode is a frozen mirror of the underlying thermostats. Soft mode
        keeps a command visible even though it was not written; without a
        command both levels simply mirror the real state.
        """
        if self._read_only_mode() == READ_ONLY_HARD or self._desired.is_empty:
            self._read_only_mirror()
            return

        self._pending_target = None
        self._off_sent_at = None
        self._idle_since = None

        if self._desired.hvac_mode == HVAC_OFF:
            self._active_targets = frozenset()
            self._handover_state = HandoverState.OFF
            self._route_reason = "off"
            return

        if self._desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
            decision = self._route_decision()
            self._active_targets = decision.targets
            self._handover_state = HandoverState.STEADY if decision.targets else HandoverState.OFF
            self._route_reason = decision.reason
            single = self._single_target(decision)
            if single is not None:
                self._last_route = single
            return

        # A setpoint without a mode cannot pick a route.
        self._read_only_mirror()

    def _apply_setpoint(
        self,
        desired: DesiredState,
        *,
        temperature: float | None,
        preset_mode: str | None,
    ) -> None:
        """Apply a temperature or preset to one desired-state object."""
        if preset_mode is not None:
            desired.setpoint_kind = SetpointKind.PRESET
            desired.preset_mode = preset_mode
            desired.target_temperature = None
        if temperature is not None:
            desired.setpoint_kind = SetpointKind.TEMPERATURE
            desired.target_temperature = float(temperature)
            desired.preset_mode = None

    def _clear_off_preset(self) -> None:
        """Drop a decoupled off-preset hold after a new live command."""
        if self._off_preset is None and not self._off_preset_pending:
            return
        self._off_preset = None
        self._off_preset_pending = False
        self._sync_desired()

    def _off_preset_live_state(self) -> DesiredState:
        """Return the live state to keep while the underlying targets are stopped.

        The decoupled off preset must never copy an ``off`` state into the
        proxy: the proxy is supposed to stay live. When the targets are already
        off, the last live state (or the last known setpoint) is reused instead,
        and the off preset is simply shown as the proxy's preset.
        """
        if self._manual is not None and self._manual.desired.hvac_mode in (
            HVAC_HEAT,
            HVAC_COOL,
        ):
            return self._manual.desired.copy()

        active = self._single_active() or self._first_on_target()
        if active is not None and self._states[active].hvac_mode not in (None, HVAC_OFF):
            return self._adopt_desired(active)

        # The targets are already off. Do not copy that off state: reuse the
        # last live state so the proxy keeps heating/cooling while the off
        # preset is active.
        if self._last_live is not None:
            return self._last_live.copy()
        if not self._desired.is_empty and self._desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
            return self._desired.copy()

        source = active
        if source is None:
            source = next(
                (target for target in self._configured_targets() if self._states[target].available),
                None,
            )
        live = self._adopt_desired(source) if source is not None else DesiredState()
        if live.hvac_mode in (None, HVAC_OFF):
            # Nothing live was ever recorded. Keep the last known setpoint but
            # present the proxy as heating so the off preset stays decoupled.
            live.hvac_mode = HVAC_HEAT
        return live

    def _activate_off_preset_hold(self, desired: DesiredState | None = None) -> None:
        """Keep the proxy live while the underlying targets are off."""
        live = desired.copy() if desired is not None else self._off_preset_live_state()
        target = self._single_active() or self._first_on_target() or self._last_route
        action = self._states[target].hvac_action if target is not None else None
        self._off_preset = OffPresetHold(
            desired=live.copy(),
            target=target,
            hvac_action=action,
        )
        self._off_preset_pending = False
        self._baseline = live.copy()
        self._sync_desired()

    async def _async_apply_off_preset(self, context: Context | None) -> None:
        """Apply the synthetic off preset, coupled or with a live proxy."""
        if not (self.config.off_preset_enabled and self.config.off_preset_keeps_live_state):
            # Coupled behaviour: the proxy follows the underlying climate off.
            if self._defers_schedule_command(context):
                self._baseline.hvac_mode = HVAC_OFF
            else:
                self._clear_off_preset()
                self._end_manual("off")
                self._apply_mode(HVAC_OFF)
            await self._async_command_received()
            return

        if self._defers_schedule_command(context):
            # A scheduler off during manual mode is remembered for the return
            # to schedule instead of stopping the manual session.
            self._off_preset_pending = True
            self._baseline.hvac_mode = HVAC_OFF
            await self._async_command_received()
            return

        live = self._off_preset_live_state()
        self._activate_off_preset_hold(live)
        self._end_manual("off")
        self._baseline = live.copy()
        self._sync_desired()
        await self._async_command_received()

    async def async_set_temperature(
        self,
        temperature: float | None = None,
        hvac_mode: str | None = None,
        preset_mode: str | None = None,
        context: Context | None = None,
    ) -> None:
        """Handle a set_temperature-style command."""
        self._ensure_unlocked(context)
        if temperature is None and hvac_mode is None and preset_mode is None:
            raise HomeAssistantError("No temperature, preset, or mode supplied")
        if preset_mode == PRESET_OFF:
            await self.async_set_preset_mode(PRESET_OFF, context=context)
            return
        self._clear_off_preset()

        from_user = self._is_user_context(context)
        has_setpoint = temperature is not None or preset_mode is not None

        defer = self._defers_schedule_command(context)

        if hvac_mode == HVAC_OFF:
            if defer:
                # A scheduler off must not stop manual mode. Remember it as the
                # latest schedule state so the timer expiry returns to it.
                self._baseline.hvac_mode = HVAC_OFF
            else:
                # An explicit off is a safety command and always ends manual mode.
                self._end_manual("off")
                self._apply_mode(HVAC_OFF)
            await self._async_command_received()
            return

        if self._manual is not None and from_user:
            # A user move during manual mode updates the manual value only. It
            # must not touch the schedule baseline and must not reset the timer.
            if hvac_mode is not None:
                if hvac_mode not in MODES:
                    raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
                self._manual.desired.hvac_mode = hvac_mode
            self._apply_setpoint(
                self._manual.desired,
                temperature=temperature,
                preset_mode=preset_mode,
            )
        elif defer:
            # A schedule/automation move while manual mode is active is kept as
            # the return target but is not applied now. This protects the manual
            # setting and makes the next timer expiry follow the latest schedule.
            if hvac_mode is not None:
                if hvac_mode not in MODES:
                    raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
                self._baseline.hvac_mode = hvac_mode
            self._apply_setpoint(
                self._baseline,
                temperature=temperature,
                preset_mode=preset_mode,
            )
        elif from_user and (has_setpoint or hvac_mode is not None):
            # Any user change starts manual mode. Seed the baseline from an
            # already running target first, so the first move after a restart
            # is not lost when no schedule command is known yet.
            self._ensure_manual_baseline()
            desired = self._baseline.copy()
            if hvac_mode is not None:
                if hvac_mode not in MODES:
                    raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
                desired.hvac_mode = hvac_mode
            self._apply_setpoint(
                desired,
                temperature=temperature,
                preset_mode=preset_mode,
            )
            if desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
                self._start_manual(dt_util.utcnow(), desired=desired)
            else:
                # A setpoint for a proxy that is off stays a schedule value; it
                # must not turn the climate on.
                self._apply_setpoint(
                    self._baseline,
                    temperature=temperature,
                    preset_mode=preset_mode,
                )
                if hvac_mode is not None:
                    self._apply_mode(hvac_mode)
        else:
            # Schedule/automation command, or a mode-only user command: update
            # the baseline while an existing manual mode keeps winning.
            if hvac_mode is not None:
                self._apply_mode(hvac_mode)
            self._apply_setpoint(
                self._baseline,
                temperature=temperature,
                preset_mode=preset_mode,
            )

        await self._async_command_received()

    async def async_set_hvac_mode(self, hvac_mode: str, context: Context | None = None) -> None:
        """Handle an explicit HVAC mode change."""
        self._ensure_unlocked(context)
        if hvac_mode not in MODES:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        self._clear_off_preset()
        from_user = self._is_user_context(context)
        defer = self._defers_schedule_command(context)
        if hvac_mode == HVAC_OFF:
            if defer:
                # Keep heating/cooling while manual mode is active, but return
                # to off when the manual timer expires.
                self._baseline.hvac_mode = HVAC_OFF
            else:
                self._end_manual("off")
                self._apply_mode(HVAC_OFF)
        elif self._manual is not None and from_user:
            self._manual.desired.hvac_mode = hvac_mode
        elif from_user and hvac_mode in (HVAC_HEAT, HVAC_COOL):
            # A user turning the proxy on (or switching heat/cool) starts a
            # manual session so the schedule cannot immediately override it.
            self._ensure_manual_baseline()
            desired = self._baseline.copy()
            desired.hvac_mode = hvac_mode
            self._start_manual(dt_util.utcnow(), desired=desired)
        else:
            self._apply_mode(hvac_mode)
        await self._async_command_received()

    async def async_set_preset_mode(self, preset_mode: str, context: Context | None = None) -> None:
        """Handle a preset change."""
        self._ensure_unlocked(context)
        if preset_mode == PRESET_OFF:
            await self._async_apply_off_preset(context)
            return
        self._clear_off_preset()
        if self._manual is not None and self._is_user_context(context):
            self._apply_setpoint(self._manual.desired, temperature=None, preset_mode=preset_mode)
        elif self._is_user_context(context):
            # A user preset change starts manual mode, like a setpoint change.
            self._ensure_manual_baseline()
            desired = self._baseline.copy()
            self._apply_setpoint(desired, temperature=None, preset_mode=preset_mode)
            if desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
                self._start_manual(dt_util.utcnow(), desired=desired)
            else:
                self._apply_setpoint(self._baseline, temperature=None, preset_mode=preset_mode)
        else:
            self._apply_setpoint(self._baseline, temperature=None, preset_mode=preset_mode)
        await self._async_command_received()

    async def async_set_fan_mode(self, fan_mode: str, context: Context | None = None) -> None:
        """Store a fan mode and apply it only while the AC target is active."""
        self._ensure_unlocked(context)
        if not fan_mode:
            raise HomeAssistantError("No fan mode supplied")
        ac_state = self._states[Target.AC]
        if not ac_state.available:
            raise HomeAssistantError("The AC target is not available")
        if ac_state.fan_modes and fan_mode not in ac_state.fan_modes:
            raise HomeAssistantError(f"Unsupported fan mode: {fan_mode}")

        # A fan setting is a device preference, not a setpoint: it never starts
        # or extends manual mode. While manual mode is active it is stored in
        # the manual desired state so returning to the schedule does not lose
        # it, but the timer keeps running.
        if self._manual is not None:
            self._manual.desired.fan_mode = fan_mode
        elif self._off_preset is not None:
            self._off_preset.desired.fan_mode = fan_mode
            self._sync_desired()
        else:
            self._baseline.fan_mode = fan_mode
        await self._async_command_received()

    async def async_turn_on(self, context: Context | None = None) -> None:
        """Turn the proxy on in the last known (or heat) mode."""
        self._ensure_unlocked(context)
        self._clear_off_preset()
        if self._baseline.hvac_mode in (None, HVAC_OFF):
            self._baseline.hvac_mode = HVAC_HEAT
        if self._is_user_context(context):
            # A user turning the proxy on starts manual mode, exactly like a
            # setpoint change, so the schedule cannot switch it off again.
            self._ensure_manual_baseline()
            desired = self._baseline.copy()
            if desired.hvac_mode in (None, HVAC_OFF):
                desired.hvac_mode = HVAC_HEAT
            if desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
                if self._manual is not None:
                    self._manual.desired.hvac_mode = desired.hvac_mode
                else:
                    self._start_manual(dt_util.utcnow(), desired=desired)
        await self._async_command_received()

    async def async_turn_off(self, context: Context | None = None) -> None:
        """Turn everything off immediately."""
        self._ensure_unlocked(context)
        self._clear_off_preset()
        if not self._defers_schedule_command(context):
            self._end_manual("off")
        # A scheduler off is remembered as the return state; a user off ends
        # manual mode and stops the targets through the normal path.
        self._baseline.hvac_mode = HVAC_OFF
        await self._async_command_received()

    async def async_set_route_override(self, value: str) -> None:
        """Set the built-in route override select."""
        if value not in self.route_override_options:
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
        configured = self._configured_targets()
        return [
            ROUTE_AUTO,
            *(target.value for target in Target if target in configured),
        ]

    async def async_recalculate(self) -> None:
        """Force a route evaluation."""
        await self.async_evaluate(explicit=True)

    async def async_force_handover(self) -> None:
        """Complete the current handover without waiting for the old target to idle."""
        async with self._lock:
            if self._handover_state not in (
                HandoverState.PENDING,
                HandoverState.STOPPING_OLD,
                HandoverState.STARTING_NEW,
            ):
                raise HomeAssistantError("No handover is in progress")

            self._refresh_inputs()
            target = self._pending_target
            if target is None:
                target = self._single_target(self._route_decision())
            if target is None:
                raise HomeAssistantError("No target can serve the requested mode")

            old = self._single_active()
            if self._handover_state is HandoverState.STARTING_NEW:
                await self._async_start_new(target)
            elif old is not None and old is not target:
                await self._async_stop_old(old, target)
                if self._handover_state is HandoverState.STOPPING_OLD:
                    # The off command went out. A forced handover does not wait
                    # for the idle confirmation or the off-confirm timeout; the
                    # old target is stopped first and conflict detection catches
                    # it if it stays on.
                    await self._async_start_new(target)
            else:
                await self._async_start_new(target)
            self._publish()

    async def async_clear_conflicts(self) -> None:
        """Acknowledge and clear the current conflict state."""
        now = dt_util.utcnow()
        for conflict in list(self._conflicts.values()):
            self._record_conflict_history(replace(conflict, resolved=True, last_seen=now))
            self._fire_conflict_cleared(conflict, now)
        self._conflicts.clear()
        self._conflict_cleared_since.clear()
        self._conflict_reasserted.clear()
        self._publish()

    @property
    def conflict_history(self) -> tuple[Conflict, ...]:
        """Return the bounded recent conflict history for diagnostics."""
        return tuple(self._conflict_history)

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
        if self._manual is not None:
            # Keep the last schedule command for return-to-schedule. This also
            # records commands that were deferred during manual mode.
            self._manual.baseline = self._baseline.copy()
        self._sync_desired()
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate(explicit=True)

    # ------------------------------------------------------------------
    # Manual mode
    # ------------------------------------------------------------------
    def _ensure_manual_baseline(self) -> None:
        """Adopt the active target when no schedule command is known yet."""
        if not self._baseline.is_empty:
            return
        active = self._single_active() or self._first_on_target()
        if active is not None:
            self._baseline = self._adopt_desired(active)

    def _manual_deadline(self, minutes: int, now: datetime) -> datetime:
        """Validate a manual duration and return its absolute deadline."""
        if minutes < 1 or minutes > self.config.max_manual_minutes:
            raise HomeAssistantError(
                f"Manual duration must be between 1 and {self.config.max_manual_minutes} minutes"
            )
        return now + timedelta(minutes=minutes)

    async def _async_start_manual(
        self,
        desired: DesiredState,
        *,
        duration_minutes: int | None = None,
        context: Context | None = None,
    ) -> None:
        """Start manual mode, preserving an existing timer when updating."""
        self._ensure_unlocked(context)
        now = dt_util.utcnow()
        self._ensure_manual_baseline()

        if self._manual is None:
            duration = (
                self.config.default_manual_minutes
                if duration_minutes is None
                else int(duration_minutes)
            )
            timer = duration if duration > 0 else None
            until = self._manual_deadline(timer, now) if timer is not None else None
            self._manual = ManualMode(
                desired=desired.copy(),
                started_at=now,
                until=until,
                baseline=self._baseline.copy(),
                timer_minutes=timer,
            )
            await self._async_velair_pause()
            self.hass.bus.async_fire(
                EVENT_MANUAL_MODE_STARTED,
                {
                    "entry_id": self.entry.entry_id,
                    "until": until.isoformat() if until else None,
                    "timer_minutes": timer,
                    "desired": self._manual.desired.to_dict(),
                },
            )
        else:
            # An additional move updates the value but never resets the timer
            # unless a new duration is supplied explicitly.
            self._manual.desired = desired.copy()
            if duration_minutes is not None:
                duration = int(duration_minutes)
                timer = duration if duration > 0 else None
                self._manual.started_at = now
                self._manual.timer_minutes = timer
                self._manual.until = (
                    self._manual_deadline(timer, now) if timer is not None else None
                )
                # Velair's pause was sized from the previous deadline, so align
                # it with the new remaining manual time.
                await self._async_velair_pause()

        self._manual.baseline = self._baseline.copy()
        self._last_command = now
        self._sync_desired()
        await self._async_set_pause_switch(True)
        self._schedule_manual_expiry()
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate(explicit=True)

    def _start_manual(
        self,
        now: datetime,
        *,
        desired: DesiredState,
    ) -> None:
        """Create manual mode from a UI move without awaiting evaluation."""
        self._ensure_manual_baseline()
        duration = self.config.default_manual_minutes
        timer = duration if duration > 0 else None
        until = self._manual_deadline(timer, now) if timer is not None else None
        self._manual = ManualMode(
            desired=desired.copy(),
            started_at=now,
            until=until,
            baseline=self._baseline.copy(),
            timer_minutes=timer,
        )
        self.hass.async_create_task(self._async_velair_pause())
        self.hass.async_create_task(self._async_set_pause_switch(True))
        self._schedule_manual_expiry()
        self._store.async_delay_save(self._data_to_save, 1)
        self.hass.bus.async_fire(
            EVENT_MANUAL_MODE_STARTED,
            {
                "entry_id": self.entry.entry_id,
                "until": until.isoformat() if until else None,
                "timer_minutes": timer,
                "desired": self._manual.desired.to_dict(),
            },
        )

    async def async_enter_manual_mode(
        self,
        *,
        temperature: float | None = None,
        preset_mode: str | None = None,
        hvac_mode: str | None = None,
        duration_minutes: int | None = None,
        context: Context | None = None,
    ) -> None:
        """Enter or update manual mode through a service call."""
        self._ensure_unlocked(context)
        self._ensure_manual_control_allowed(context)
        supplied = [value is not None for value in (temperature, preset_mode, hvac_mode)]
        if sum(supplied) > 1:
            raise HomeAssistantError(
                "Only one of temperature, preset_mode, or hvac_mode can be supplied"
            )

        if hvac_mode == HVAC_OFF:
            await self.async_return_to_schedule(cause="off")
            await self.async_set_hvac_mode(HVAC_OFF, context=context)
            return
        if preset_mode == PRESET_OFF:
            await self.async_return_to_schedule(cause="off")
            await self.async_set_preset_mode(PRESET_OFF, context=context)
            return
        if hvac_mode is not None and hvac_mode not in MODES:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")
        self._clear_off_preset()

        if self._manual is not None:
            desired = self._manual.desired.copy()
        else:
            self._ensure_manual_baseline()
            desired = self._baseline.copy()
        if hvac_mode is not None:
            desired.hvac_mode = hvac_mode
        self._apply_setpoint(desired, temperature=temperature, preset_mode=preset_mode)
        await self._async_start_manual(
            desired,
            duration_minutes=duration_minutes,
            context=context,
        )

    async def async_set_manual_override(
        self,
        *,
        temperature: float | None = None,
        preset_mode: str | None = None,
        hvac_mode: str | None = None,
        duration_minutes: int | None = None,
        context: Context | None = None,
    ) -> None:
        """Backward-compatible alias for entering manual mode."""
        await self.async_enter_manual_mode(
            temperature=temperature,
            preset_mode=preset_mode,
            hvac_mode=hvac_mode,
            duration_minutes=duration_minutes,
            context=context,
        )

    async def async_set_manual_timer(
        self,
        minutes: int | None = None,
        context: Context | None = None,
    ) -> None:
        """Set the manual countdown; ``None`` or ``0`` switches it off."""
        self._ensure_unlocked(context)
        self._ensure_manual_control_allowed(context)
        if self._manual is None:
            raise HomeAssistantError("Manual mode is not active")
        now = dt_util.utcnow()
        timer = int(minutes) if minutes is not None and int(minutes) > 0 else None
        if timer is None:
            self._manual.until = None
            self._manual.timer_minutes = None
        else:
            self._manual.until = self._manual_deadline(timer, now)
            self._manual.timer_minutes = timer
        self._schedule_manual_expiry()
        # Re-size the Velair pause to the new remaining manual time (or make it
        # open-ended again when the countdown was switched off).
        await self._async_velair_pause()
        self._store.async_delay_save(self._data_to_save, 1)
        self.hass.bus.async_fire(
            EVENT_MANUAL_TIMER_CHANGED,
            {
                "entry_id": self.entry.entry_id,
                "until": self._manual.until.isoformat() if self._manual.until else None,
                "minutes": timer,
            },
        )
        self._publish()

    async def _async_velair_pause(self) -> None:
        """Pause Velair for the remaining manual-mode duration.

        Velair counts the duration from the moment it receives the command, so
        the remaining minutes are derived from the manual deadline every time
        this is called (manual start, timer change, or a restored session).
        Without a countdown the pause stays open-ended.
        """
        if not self.config.velair_enabled:
            return
        if not self.hass.services.has_service("velair", "pause"):
            _LOGGER.debug("Velair is enabled but velair.pause is not registered")
            return
        data: dict[str, Any] = {}
        if self._manual is not None:
            remaining = self._manual.remaining_minutes(dt_util.utcnow())
            if remaining is not None:
                data["duration_minutes"] = max(1, remaining)
        try:
            await self.hass.services.async_call("velair", "pause", data, blocking=True)
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to pause Velair: %s", err)

    async def _async_velair_resume(self) -> None:
        """Resume Velair automatic control for the ClimateRouter proxy."""
        if not self.config.velair_enabled:
            return
        entity_id = self.climate_entity_id
        if not entity_id:
            _LOGGER.debug("Cannot resume Velair before the proxy entity exists")
            return
        if not self.hass.services.has_service("velair", "resume_automatic_control"):
            _LOGGER.debug("Velair is enabled but velair.resume_automatic_control is not registered")
            return
        try:
            await self.hass.services.async_call(
                "velair",
                "resume_automatic_control",
                {"entity_id": entity_id},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to resume Velair: %s", err)

    async def _async_set_pause_switch(self, manual_active: bool) -> None:
        """Drive an external scheduler pause switch for manual mode.

        The entity is deliberately generic: Chauffage's pause switch is the
        motivating use case, but any ``switch`` or ``input_boolean`` can be
        wired here. By default the entity is on while manual mode is active;
        ``scheduler_pause_switch_invert`` flips the polarity so on signals
        "free" instead of "busy".
        """
        entity_id = self.config.scheduler_pause_switch_entity_id
        if not entity_id:
            return
        if self._pause_switch_active is manual_active:
            return
        turn_on = manual_active != self.config.scheduler_pause_switch_invert
        service = "turn_on" if turn_on else "turn_off"
        try:
            await self.hass.services.async_call(
                "homeassistant",
                service,
                {"entity_id": entity_id},
                blocking=False,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to %s %s: %s", service, entity_id, err)
            return
        self._pause_switch_active = manual_active

    async def async_return_to_schedule(self, cause: str = "return_to_schedule") -> None:
        """End manual mode and restore the latest schedule command."""
        if self._manual is None:
            return
        self._end_manual(cause)
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate()

    async def async_cancel_manual_override(self, cause: str = "cancelled") -> None:
        """Backward-compatible alias for returning to the schedule."""
        await self.async_return_to_schedule(cause=cause)

    def _end_manual(self, cause: str) -> None:
        """Clear manual mode without forwarding; callers evaluate afterwards."""
        if self._manual is None:
            return
        manual = self._manual
        pending_off = self._off_preset_pending
        self._off_preset_pending = False
        if (
            pending_off
            and cause != "off"
            and self.config.off_preset_enabled
            and self.config.off_preset_keeps_live_state
        ):
            # A scheduler off preset arrived during manual mode. Keep the
            # proxy live and stop the underlying targets once manual ends.
            self._activate_off_preset_hold(manual.desired)
        if cause != "off" and self._baseline.is_empty:
            # No schedule command exists yet, so there is nothing to return to.
            # Keep the current manual state running instead of blanking the
            # proxy when the timer expires (or the user returns to schedule).
            self._baseline = manual.desired.copy()
        self._cancel_manual_timer()
        self._manual = None
        self._sync_desired()
        self.hass.async_create_task(self._async_velair_resume())
        self.hass.async_create_task(self._async_set_pause_switch(False))
        self.hass.bus.async_fire(
            EVENT_MANUAL_MODE_ENDED,
            {
                "entry_id": self.entry.entry_id,
                "cause": cause,
                "desired": manual.desired.to_dict(),
                "started_at": manual.started_at.isoformat(),
            },
        )

    def _sync_desired(self) -> None:
        """Recompute the effective desired state from baseline and manual mode."""
        if self._off_preset is not None:
            self._desired = self._off_preset.desired.copy()
        else:
            self._desired = self._baseline.with_manual_mode(self._manual)
        if self._desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
            # Remember the last live state. The decoupled off preset reuses it
            # when the underlying thermostats are already off.
            self._last_live = self._desired.copy()

    async def _async_manual_expired(self, _now: datetime) -> None:
        self._cancel_manual_timer()
        if self._manual is None:
            return
        if not self._manual.is_expired(dt_util.utcnow()):
            self._schedule_manual_expiry()
            return
        self._end_manual("expired")
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate()

    def _schedule_manual_expiry(self) -> None:
        """Schedule the exact deadline in addition to the watchdog check."""
        self._cancel_manual_timer()
        if self._manual is None or self._manual.until is None:
            return
        delay = (self._manual.until - dt_util.utcnow()).total_seconds()
        self._manual_unsub = async_call_later(self.hass, max(delay, 0), self._async_manual_expired)

    def _cancel_manual_timer(self) -> None:
        if self._manual_unsub is not None:
            self._manual_unsub()
            self._manual_unsub = None

    # ------------------------------------------------------------------
    # Boost
    # ------------------------------------------------------------------
    async def async_set_boost(
        self,
        *,
        duration_minutes: int | None = None,
        targets: str = "both",
        context: Context | None = None,
    ) -> None:
        """Activate every configured target for a bounded time (heat only)."""
        self._ensure_unlocked(context)
        if not self.config.boost_enabled:
            raise HomeAssistantError("Boost is disabled in the ClimateRouter options")
        if targets != "both":
            raise HomeAssistantError("Only targets=both is supported")

        duration = DEFAULT_BOOST_MINUTES if duration_minutes is None else int(duration_minutes)
        if duration < 1 or duration > DEFAULT_MAX_BOOST_MINUTES:
            raise HomeAssistantError(
                f"Boost duration must be between 1 and {DEFAULT_MAX_BOOST_MINUTES} minutes"
            )

        self._refresh_inputs()
        if self._desired.hvac_mode != HVAC_HEAT:
            raise HomeAssistantError("Boost requires the proxy to be heating")
        if self._handover_state in (
            HandoverState.PENDING,
            HandoverState.STOPPING_OLD,
            HandoverState.STARTING_NEW,
        ):
            raise HomeAssistantError("Cannot start boost while a handover is pending")

        self._clear_off_preset()

        for target in self._configured_targets():
            state = self._states[target]
            if not state.available:
                raise HomeAssistantError(f"{target.value} is unavailable")
            if state.hvac_mode == HVAC_COOL:
                raise HomeAssistantError(f"{target.value} is currently cooling")
            if not state.capability.can_handle(HVAC_HEAT):
                raise HomeAssistantError(f"{target.value} cannot heat")

        if self._boost is not None:
            self._end_boost("replaced")

        now = dt_util.utcnow()
        self._boost = BoostState(
            until=now + timedelta(minutes=duration),
            started_at=now,
            targets=self._configured_targets(),
        )
        self._last_command = now
        self._schedule_boost_expiry()
        self._store.async_delay_save(self._data_to_save, 1)
        self.hass.bus.async_fire(
            EVENT_BOOST_STARTED,
            {
                "entry_id": self.entry.entry_id,
                "until": self._boost.until.isoformat(),
                "duration_minutes": duration,
                "targets": sorted(target.value for target in self._boost.targets),
            },
        )
        await self.async_evaluate(explicit=True)

    async def async_cancel_boost(self, cause: str = "cancelled") -> None:
        """End an active boost and return to normal routing."""
        if self._boost is None:
            return
        self._end_boost(cause)
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate()

    def _end_boost(self, cause: str) -> None:
        """Clear the boost state without forwarding; callers evaluate afterwards."""
        if self._boost is None:
            return
        boost = self._boost
        self._cancel_boost_timer()
        self._boost = None
        if self._handover_state is HandoverState.BOOST:
            self._handover_state = HandoverState.STEADY
        self.hass.bus.async_fire(
            EVENT_BOOST_ENDED,
            {
                "entry_id": self.entry.entry_id,
                "until": boost.until.isoformat(),
                "cause": cause,
                "targets": sorted(target.value for target in boost.targets),
            },
        )

    async def _async_boost_expired(self, _now: datetime) -> None:
        self._cancel_boost_timer()
        if self._boost is None:
            return
        if not self._boost.is_expired(dt_util.utcnow()):
            self._schedule_boost_expiry()
            return
        self._end_boost("expired")
        self._store.async_delay_save(self._data_to_save, 1)
        await self.async_evaluate()

    def _schedule_boost_expiry(self) -> None:
        """Schedule the exact deadline in addition to the watchdog check."""
        self._cancel_boost_timer()
        if self._boost is None:
            return
        delay = (self._boost.until - dt_util.utcnow()).total_seconds()
        self._boost_unsub = async_call_later(self.hass, max(delay, 0), self._async_boost_expired)

    def _cancel_boost_timer(self) -> None:
        if self._boost_unsub is not None:
            self._boost_unsub()
            self._boost_unsub = None

    # ------------------------------------------------------------------
    # Lock
    # ------------------------------------------------------------------
    @property
    def lock_enabled(self) -> bool:
        """Return whether the native lock is enabled."""
        return self.config.lock_enabled

    @property
    def locked(self) -> bool:
        """Return whether the router currently rejects user/automation commands."""
        return self._locked

    async def async_lock(self) -> None:
        """Lock the router so user and automation commands are rejected."""
        if not self.config.lock_enabled:
            raise HomeAssistantError("The ClimateRouter lock is disabled")
        self._cancel_auto_relock()
        self._auto_relock_at = None
        if not self._locked:
            self._locked = True
            self._store.async_delay_save(self._data_to_save, 1)
            self._publish()

    async def async_unlock(self, code: str | None = None) -> None:
        """Unlock the router, optionally validating a configured code."""
        if not self.config.lock_enabled:
            raise HomeAssistantError("The ClimateRouter lock is disabled")
        if self.config.lock_code and (code or "") != self.config.lock_code:
            raise HomeAssistantError("Invalid ClimateRouter lock code")
        if self._locked:
            self._locked = False
            self._store.async_delay_save(self._data_to_save, 1)
            self._publish()
        self._schedule_auto_relock()

    def _defers_schedule_command(self, context: Context | None) -> bool:
        """Return whether manual mode should defer this schedule/automation command.

        While manual mode is active, schedule commands are never applied. They
        are stored as the baseline instead, so the latest schedule is what
        manual mode returns to when its timer expires (or the user returns
        manually). User commands always pass through.
        """
        user_id = context.user_id if context is not None else None
        return self._manual is not None and user_id is None

    def _ensure_manual_control_allowed(self, context: Context | None) -> None:
        """Reject automation changes to manual mode itself while it is active."""
        if self._defers_schedule_command(context):
            raise HomeAssistantError(
                "Manual mode is active; return to schedule before sending automation commands"
            )

    def _ensure_unlocked(self, context: Context | None) -> None:
        """Reject a command blocked by the accidental-touch UI lock (Lock A)."""
        user_id = context.user_id if context is not None else None
        if lock_blocks_context(
            enabled=self.config.lock_enabled,
            locked=self._locked,
            user_id=user_id,
        ):
            raise HomeAssistantError("ClimateRouter is locked; unlock it before sending commands")

    def _schedule_auto_relock(self, delay: float | None = None) -> None:
        """Lock the router again after the configured delay."""
        self._cancel_auto_relock()
        if not self.config.lock_enabled or self.config.auto_relock_sec <= 0:
            self._auto_relock_at = None
            return
        seconds = self.config.auto_relock_sec if delay is None else delay
        self._auto_relock_at = dt_util.utcnow() + timedelta(seconds=seconds)
        self._store.async_delay_save(self._data_to_save, 1)
        self._auto_relock_unsub = async_call_later(
            self.hass,
            max(seconds, 0),
            self._async_auto_relock,
        )

    def _cancel_auto_relock(self) -> None:
        if self._auto_relock_unsub is not None:
            self._auto_relock_unsub()
            self._auto_relock_unsub = None

    async def _async_auto_relock(self, _now: datetime) -> None:
        self._auto_relock_unsub = None
        self._auto_relock_at = None
        if not self.config.lock_enabled or self._locked:
            return
        self._locked = True
        self._store.async_delay_save(self._data_to_save, 1)
        self._publish()

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------
    async def _async_refresh_conflicts(self) -> None:
        """Compare target state with the expected state and apply the policy."""
        if not self._ready:
            return
        if self._read_only_mode() != READ_ONLY_OFF:
            # Differences are expected: the router is not allowed to write.
            return
        if self._handover_state not in (
            HandoverState.STEADY,
            HandoverState.OFF,
            HandoverState.BOOST,
        ):
            return

        now = dt_util.utcnow()
        if self._conflicts_suppressed(now):
            return

        tolerance = self.config.temperature_tolerance or DEFAULT_TEMPERATURE_TOLERANCE
        active = self._single_active()
        boost = self._handover_state is HandoverState.BOOST
        detected: dict[str, Conflict] = {}

        if boost:
            compare_targets = self._active_targets
        elif active is not None:
            compare_targets = frozenset({active})
        else:
            compare_targets = frozenset()

        if not self._desired.is_empty and self._desired.hvac_mode in (HVAC_HEAT, HVAC_COOL):
            for compare_target in compare_targets:
                state = self._states[compare_target]
                result = target_conflict(self._desired, state, tolerance)
                if result is None:
                    continue
                ctype, expected, actual = result
                if (
                    self.config.conflict_policy == "adopt"
                    and not boost
                    and ctype in ("setpoint_mismatch", "preset_mismatch", "hvac_mode_mismatch")
                    and not state.guard
                ):
                    self._adopt_external_state(compare_target)
                else:
                    key = f"{ctype}:{compare_target.value}"
                    existing = self._conflicts.get(key)
                    detected[key] = Conflict(
                        key=key,
                        type=ctype,
                        target=compare_target,
                        expected=expected,
                        actual=actual,
                        first_seen=existing.first_seen if existing else now,
                        last_seen=now,
                        source_guess=self._guess_source(compare_target),
                    )
                    if (
                        self.config.conflict_policy == "reassert"
                        and ctype in ("setpoint_mismatch", "preset_mismatch")
                        and state.hvac_mode == self._desired.hvac_mode
                        and key not in self._conflict_reasserted
                        and (now - detected[key].first_seen).total_seconds()
                        >= CONFLICT_REASSERT_GRACE
                    ):
                        self._conflict_reasserted.add(key)
                        await self._async_forward_desired(compare_target)

        if not boost:
            on_targets = [
                target
                for target in self._configured_targets()
                if self._states[target].available
                and self._states[target].hvac_mode not in (None, HVAC_OFF)
            ]
            if len(on_targets) > 1:
                key = "both_targets_on"
                existing = self._conflicts.get(key)
                detected[key] = Conflict(
                    key=key,
                    type="both_targets_on",
                    target=None,
                    expected=active.value if active else "one_target",
                    actual=sorted(target.value for target in on_targets),
                    first_seen=existing.first_seen if existing else now,
                    last_seen=now,
                    source_guess="unknown",
                )
                if self.config.auto_resolve_simultaneous:
                    for target in on_targets:
                        if target is not active and not self._states[target].is_active:
                            await self._async_turn_off_target(target)
            elif active is not None:
                for other in self._configured_targets():
                    if other is active:
                        continue
                    state = self._states[other]
                    if not state.available or state.hvac_mode in (None, HVAC_OFF):
                        continue
                    key = f"inactive_target_on:{other.value}"
                    existing = self._conflicts.get(key)
                    detected[key] = Conflict(
                        key=key,
                        type="inactive_target_on",
                        target=other,
                        expected=HVAC_OFF,
                        actual=state.hvac_mode,
                        first_seen=existing.first_seen if existing else now,
                        last_seen=now,
                        source_guess=self._guess_source(other),
                    )
                    if self.config.auto_resolve_idle_targets and not state.is_active:
                        await self._async_turn_off_target(other)

        self._reconcile_conflict_records(detected, now)
        if detected:
            self._publish()

    def _reconcile_conflict_records(self, detected: dict[str, Conflict], now: datetime) -> None:
        """Keep new conflicts, age out resolved ones, and emit events."""
        for key, conflict in detected.items():
            self._conflict_cleared_since.pop(key, None)
            if key not in self._conflicts:
                self._conflict_count += 1
                self._record_conflict_history(conflict)
                self.hass.bus.async_fire(
                    EVENT_CONFLICT_DETECTED,
                    {"entry_id": self.entry.entry_id, "conflict": conflict.to_dict()},
                )
                _LOGGER.warning(
                    "Conflict detected on %s: %s expected=%s actual=%s",
                    conflict.target.value if conflict.target else "router",
                    conflict.type,
                    conflict.expected,
                    conflict.actual,
                )
            self._conflicts[key] = conflict

        for key in list(self._conflicts):
            if key in detected:
                continue
            since = self._conflict_cleared_since.setdefault(key, now)
            if (now - since).total_seconds() < CONFLICT_CLEAR_AFTER:
                continue
            conflict = self._conflicts.pop(key)
            self._conflict_cleared_since.pop(key, None)
            self._conflict_reasserted.discard(key)
            self._record_conflict_history(replace(conflict, resolved=True, last_seen=now))
            self._fire_conflict_cleared(conflict, now)

    def _conflicts_suppressed(self, now: datetime) -> bool:
        """Return whether own calls or the settle window suppress comparison."""
        if self._suppress_conflicts_until is not None and now < self._suppress_conflicts_until:
            return True
        if self._last_command is not None:
            settle = max(self.config.settle_time, 0)
            if (now - self._last_command).total_seconds() < settle:
                return True
        return False

    def _has_target_conflict(self, target: Target) -> bool:
        """Return whether a target has an active conflict we should not fight."""
        types = {
            "setpoint_mismatch",
            "preset_mismatch",
            "hvac_mode_mismatch",
            "underlying_override",
            "target_unavailable",
        }
        return any(
            conflict.target is target and conflict.type in types
            for conflict in self._conflicts.values()
        )

    def _adopt_external_state(self, target: Target) -> None:
        """Adopt a direct change on the active target as the new baseline."""
        self._baseline = self._adopt_desired(target)
        self._sync_desired()
        self._store.async_delay_save(self._data_to_save, 1)
        _LOGGER.info(
            "Adopted external state from %s as the new baseline (conflict_policy=adopt)",
            target.value,
        )

    def _guess_source(self, target: Target) -> str:
        state = self._states.get(target)
        if state is not None and state.timed_preset_active:
            return "vtherm_timed_preset"
        if state is not None and state.guard:
            return "vtherm_guard"
        return self._last_state_source.get(target, "unknown")

    async def _async_turn_off_target(self, target: Target) -> None:
        """Turn off an idle target during automatic conflict resolution."""
        try:
            await self._async_climate_call(target, "set_hvac_mode", {"hvac_mode": HVAC_OFF})
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to auto-resolve %s: %s", target.value, err)
        self._states[target] = self._read_target(target)

    def _record_conflict_history(self, conflict: Conflict) -> None:
        self._conflict_history.append(conflict)
        if len(self._conflict_history) > 50:
            del self._conflict_history[:-50]

    def _fire_conflict_cleared(self, conflict: Conflict, now: datetime) -> None:
        data = conflict.to_dict()
        data["resolved_at"] = now.isoformat()
        self.hass.bus.async_fire(
            EVENT_CONFLICT_CLEARED,
            {"entry_id": self.entry.entry_id, "conflict": data},
        )

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

            if self._off_preset is not None:
                # The decoupled off preset keeps the proxy live while the
                # underlying targets are stopped.
                await self._async_stop_all()
                self._active_targets = frozenset()
                self._pending_target = None
                self._handover_state = HandoverState.OFF
                self._route_reason = "off_preset"
                self._publish()
                return

            if self._read_only_mode() != READ_ONLY_OFF:
                # No write can reach the underlying thermostats. Keep a
                # command visible in soft mode and mirror the real state in
                # hard mode, without running the handover state machine.
                self._evaluate_read_only()
                self._publish()
                return

            if self._boost is not None and self._desired.hvac_mode != HVAC_HEAT:
                self._end_boost("off" if self._desired.hvac_mode == HVAC_OFF else "mode_changed")
                self._store.async_delay_save(self._data_to_save, 1)

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

            await self._async_apply_ac_idle_bypass()

            if self._desired.is_empty:
                # Never issue commands before the first user command. If an
                # underlying thermostat came back on after a restart, adopt it.
                self._route_reason = self._route_decision().reason
                self._publish()
                return

            if self._boost is not None:
                decision = self._route_decision()
                await self._async_apply_boost(decision)
                await self._async_refresh_conflicts()
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
                if explicit and self._handover_state is HandoverState.PENDING:
                    active = self._single_active()
                    if active is not None and active is not self._pending_target:
                        # A command received during a pending handover must
                        # still reach the target that is heating/cooling now.
                        # The pending target receives the same desired state
                        # when the handover starts it.
                        await self._async_forward_desired(active)
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

            if len(self._active_targets) > 1:
                await self._async_begin_boost_exit(target, decision.reason, explicit=explicit)
                self._publish()
                return

            await self._async_refresh_conflicts()

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
                target_state = self._states[target]
                # Manual mode is authoritative: an external change to the
                # active target (for example a scheduler or automation writing
                # directly to the VTherm) must not win while it is active.
                manual_reassert = (
                    self._manual is not None
                    and target_state.available
                    and not target_state.guard
                    and not target_state.timed_preset_active
                )
                if (
                    explicit
                    or manual_reassert
                    or (
                        not self._conflicts_suppressed(dt_util.utcnow())
                        and not self._has_target_conflict(target)
                    )
                ):
                    await self._async_forward_desired(target)
            else:
                await self._async_begin_handover(target, decision.reason, explicit=explicit)

            self._publish()

    async def _async_apply_boost(self, decision: RouteDecision) -> None:
        """Start and configure every target that can serve boost."""
        targets = frozenset(
            target
            for target in decision.targets
            if self._states[target].available
            and self._states[target].capability.can_handle(HVAC_HEAT)
        )
        if not targets:
            self._end_boost("unavailable")
            self._active_targets = frozenset()
            self._pending_target = None
            self._handover_state = HandoverState.CONFLICT
            self._route_reason = "boost_unavailable"
            self._store.async_delay_save(self._data_to_save, 1)
            return

        self._active_targets = targets
        self._pending_target = None
        self._handover_state = HandoverState.BOOST
        self._route_reason = decision.reason
        for target in sorted(targets, key=lambda item: item.value):
            await self._async_forward_desired(target)

    async def _async_begin_boost_exit(
        self, target: Target, reason: str, *, explicit: bool = False
    ) -> None:
        """Return from boost to ``target`` without interrupting an active cycle."""
        extras = [active for active in self._active_targets if active is not target]
        if not extras:
            self._active_targets = frozenset({target})
            self._handover_state = HandoverState.STEADY
            self._route_reason = reason
            await self._async_forward_desired(target)
            return

        extra = extras[0]
        self._route_reason = reason
        self._pending_target = target
        self._handover_from = extra
        self._handover_started_at = dt_util.utcnow()
        self.hass.bus.async_fire(
            EVENT_HANDOVER_STARTED,
            {
                "entry_id": self.entry.entry_id,
                "from_target": extra.value,
                "to_target": target.value,
                "reason": "boost_end",
                "old_action": self._states[extra].hvac_action,
            },
        )

        extra_state = self._states[extra]
        if not extra_state.available or extra_state.is_off:
            self._active_targets = frozenset({target})
            self._pending_target = None
            self._handover_state = HandoverState.STEADY
            self._handover_from = None
            self._handover_started_at = None
            await self._async_forward_desired(target)
            return

        if extra_state.is_active and not (explicit and self._desired.hvac_mode == HVAC_COOL):
            self._handover_state = HandoverState.PENDING
            self._idle_since = None
            return

        await self._async_stop_old(extra, target)

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
        if not old_state.available or old_state.is_off:
            # An unavailable target cannot confirm an off command; start the new
            # one and let conflict detection catch it if it reappears on.
            await self._async_start_new(new_target)
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
        if old_target is None and self._handover_from in self._active_targets:
            # Boost leaves two targets active; the handover still stops one.
            old_target = self._handover_from
        now = dt_util.utcnow()

        if self._handover_state is HandoverState.PENDING:
            if route_target is None:
                return
            if old_target is None:
                # The route reverted before the handover completed.
                self._pending_target = None
                self._handover_state = HandoverState.STEADY
                self._route_reason = decision.reason
                return
            if route_target == old_target:
                other = next(
                    (active for active in self._active_targets if active is not old_target),
                    None,
                )
                if other is None:
                    self._pending_target = None
                    self._handover_state = HandoverState.STEADY
                    await self._async_forward_desired(old_target)
                    self._route_reason = decision.reason
                    return
                # The route reverted to the target we were about to stop; swap
                # which target is stopped and which one is kept.
                self._handover_from = other
                self._pending_target = old_target
                old_target = other

            old_state = self._states[old_target]
            if not old_state.available or old_state.is_off:
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
            if (
                old_target is None
                or not self._states[old_target].available
                or self._states[old_target].is_off
            ):
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

            if (
                target is Target.AC
                and self._desired.fan_mode is not None
                and self._states[target].fan_mode != self._desired.fan_mode
            ):
                await self._async_climate_call(
                    target,
                    "set_fan_mode",
                    {"fan_mode": self._desired.fan_mode},
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

    def _ac_idle_bypass_entity(self) -> str | None:
        """Return the device climate below the AC VTherm."""
        configured = self.config.ac_idle_bypass_entity_id
        if configured:
            return configured if configured != self.config.ac_entity_id else None

        vtherm = self.hass.states.get(self.config.ac_entity_id)
        if vtherm is None:
            return None
        details = vtherm.attributes.get("vtherm_over_climate")
        if not isinstance(details, dict):
            return None
        entities = details.get("underlying_entities")
        if not isinstance(entities, (list, tuple)):
            return None
        for entity_id in entities:
            if isinstance(entity_id, str) and entity_id.startswith("climate."):
                return entity_id if entity_id != self.config.ac_entity_id else None
        return None

    def _ac_idle_bypass_temperature(self) -> float | None:
        """Return the configured VTherm preset temperature, if usable."""
        vtherm = self.hass.states.get(self.config.ac_entity_id)
        if vtherm is None:
            return None
        presets = vtherm.attributes.get("preset_temperatures")
        if not isinstance(presets, dict):
            return None
        key = {
            "frost": "frost_temp",
            "eco": "eco_temp",
            "comfort": "comfort_temp",
        }.get(self.config.ac_idle_bypass_preset)
        if key is None:
            return None
        temperature = _as_float(presets.get(key))
        if temperature is None or temperature <= 0:
            return None
        return temperature

    async def _async_apply_ac_idle_bypass(self) -> None:
        """Stop the device thermostat while the AC VTherm reports idle heat.

        The VTherm stays the source of truth. Only its underlying device
        thermostat is written, and the VTherm is expected to restore the
        normal setpoint when heating resumes.
        """
        if self._read_only_mode() != READ_ONLY_OFF:
            return
        ac_state = self._states[Target.AC]
        idle_episode = (
            self.config.ac_idle_bypass_enabled
            and self._desired.hvac_mode == HVAC_HEAT
            and Target.AC in self._active_targets
            and ac_state.available
            and ac_state.hvac_mode == HVAC_HEAT
            and ac_state.hvac_action == "idle"
            and not ac_state.guard
            and not ac_state.timed_preset_active
        )
        if not idle_episode:
            self._idle_bypass_applied = False
            return
        if self._idle_bypass_applied:
            return

        entity_id = self._ac_idle_bypass_entity()
        temperature = self._ac_idle_bypass_temperature()
        if entity_id is None or temperature is None:
            _LOGGER.debug(
                "Cannot apply the AC idle bypass: entity=%s temperature=%s",
                entity_id,
                temperature,
            )
            return

        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        current = _as_float(state.attributes.get(ATTR_TEMPERATURE))
        tolerance = self.config.temperature_tolerance or DEFAULT_TEMPERATURE_TOLERANCE
        if current is not None and abs(current - temperature) <= tolerance:
            self._idle_bypass_applied = True
            return

        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": entity_id, "temperature": temperature},
                blocking=True,
                context=Context(),
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Failed to apply the AC idle bypass on %s: %s", entity_id, err)
            return
        self._idle_bypass_applied = True

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

        # Fan is AC-only. It is stored even while the radiator is active, but it
        # is never sent to the radiator or to an AC that is currently off.
        if (
            target is Target.AC
            and desired.fan_mode is not None
            and state.hvac_mode not in (None, HVAC_OFF)
            and state.fan_mode != desired.fan_mode
        ):
            await self._async_climate_call(target, "set_fan_mode", {"fan_mode": desired.fan_mode})

    async def _async_stop_all(self) -> None:
        """Turn off every target that is not already off."""
        for target in self._configured_targets():
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
                for target in self._configured_targets()
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
            if self._handover_state is not HandoverState.CONFLICT:
                self._route_reason = (
                    "off" if self._desired.hvac_mode == HVAC_OFF else decision.reason
                )
            self._publish()

    def _adopt_from_active(self) -> None:
        """Adopt an underlying target that is already on, without commanding it."""
        active = self._single_active()
        if active is None:
            on_targets = [
                target
                for target in self._configured_targets()
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
            fan_mode=state.fan_mode,
        )

    # ------------------------------------------------------------------
    # Inputs and snapshot
    # ------------------------------------------------------------------
    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Schedule evaluation, coalescing bursts of state changes."""
        self._refresh_inputs()
        self._remember_event_source(event)
        self._adopt_user_target_change(event)
        if not self._ready:
            self._publish()
            return
        if self._update_scheduled:
            return
        self._update_scheduled = True
        self.hass.async_create_task(self._async_run_scheduled_update())

    def _adopt_user_target_change(self, event: Event[EventStateChangedData]) -> None:
        """Treat a direct user move on the active VTherm as a manual move.

        Users sometimes adjust the underlying thermostat card instead of the
        proxy. Such a change must update the manual value, not be re-asserted
        away by the manual-mode protection.
        """
        context = getattr(event, "context", None)
        if not self._is_user_context(context) or self._event_is_own(event):
            return
        if self._read_only_mode() != READ_ONLY_OFF:
            # The proxy is a mirror here; do not turn an external VTherm move
            # into a proxy-owned manual session.
            return

        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, HVAC_OFF):
            return
        target = self._target_for_entity(new_state.entity_id)
        if target is None or target not in self._active_targets:
            return

        old_state = event.data.get("old_state")
        changed = False
        hvac_mode: str | None = None
        preset_mode: str | None = None
        temperature: float | None = None

        if old_state is None or old_state.state != new_state.state:
            hvac_mode = new_state.state
            changed = True

        old_preset = old_state.attributes.get(ATTR_PRESET_MODE) if old_state is not None else None
        new_preset = new_state.attributes.get(ATTR_PRESET_MODE)
        if new_preset != old_preset:
            preset_mode = new_preset
            changed = True

        old_temperature = (
            _as_float(old_state.attributes.get(ATTR_TEMPERATURE)) if old_state is not None else None
        )
        new_temperature = _as_float(new_state.attributes.get(ATTR_TEMPERATURE))
        if new_temperature != old_temperature:
            temperature = new_temperature
            changed = True

        if not changed:
            return

        now = dt_util.utcnow()
        self._last_command = now
        if self._manual is None:
            # Seed the baseline first: after a restart no schedule command may
            # be known yet, and the VTherm move itself tells us what is live.
            self._ensure_manual_baseline()
            desired = self._baseline.copy()
            if hvac_mode is not None:
                desired.hvac_mode = hvac_mode
            self._apply_setpoint(
                desired,
                temperature=temperature,
                preset_mode=preset_mode,
            )
            if desired.hvac_mode not in (HVAC_HEAT, HVAC_COOL):
                # The VTherm itself is live, so adopt its mode even when the
                # stored baseline still says off (for example after a restart).
                desired.hvac_mode = new_state.state
            if desired.hvac_mode not in (HVAC_HEAT, HVAC_COOL):
                return
            self._start_manual(now, desired=desired)
            self._sync_desired()
            return

        desired = self._manual.desired.copy()
        if hvac_mode is not None:
            desired.hvac_mode = hvac_mode
        self._apply_setpoint(
            desired,
            temperature=temperature,
            preset_mode=preset_mode,
        )
        self._manual.desired = desired
        self._manual.baseline = self._baseline.copy()
        self._sync_desired()
        self._schedule_manual_expiry()
        self._store.async_delay_save(self._data_to_save, 1)
        self._publish()

    def _remember_event_source(self, event: Event[EventStateChangedData]) -> None:
        """Track who changed a target and suppress our own calls."""
        new_state = event.data.get("new_state")
        entity_id = event.data.get("entity_id")
        if entity_id is None and new_state is not None:
            entity_id = new_state.entity_id
        target = self._target_for_entity(entity_id)
        if target is None:
            return

        if self._event_is_own(event):
            self._last_state_source[target] = "proxy"
            settle = max(self.config.settle_time, 1)
            until = dt_util.utcnow() + timedelta(seconds=settle)
            if self._suppress_conflicts_until is None or until > self._suppress_conflicts_until:
                self._suppress_conflicts_until = until
        else:
            self._last_state_source[target] = self._source_from_event(event)

    def _event_is_own(self, event: Event[EventStateChangedData]) -> bool:
        context = getattr(event, "context", None)
        ids = [
            getattr(context, "id", None) if context is not None else None,
            getattr(context, "parent_id", None) if context is not None else None,
        ]
        new_state = event.data.get("new_state")
        state_context = getattr(new_state, "context", None) if new_state is not None else None
        if state_context is not None:
            ids.extend([state_context.id, state_context.parent_id])
        return any(context_id and context_id in self._contexts for context_id in ids)

    @staticmethod
    def _source_from_event(event: Event[EventStateChangedData]) -> str:
        context = getattr(event, "context", None)
        if context is None:
            return "unknown"
        if context.user_id:
            return "user"
        if context.parent_id:
            return "automation"
        return "unknown"

    def _target_for_entity(self, entity_id: str | None) -> Target | None:
        if entity_id == self.config.radiator_entity_id:
            return Target.RADIATOR
        if entity_id == self.config.ac_entity_id:
            return Target.AC
        return None

    async def _async_run_scheduled_update(self) -> None:
        try:
            await self.async_evaluate()
        finally:
            self._update_scheduled = False

    async def _async_watchdog(self, _now: datetime) -> None:
        if not self._ready:
            return
        if self._manual is not None and self._manual.is_expired(dt_util.utcnow()):
            await self._async_manual_expired(dt_util.utcnow())
        if self._boost is not None and self._boost.is_expired(dt_util.utcnow()):
            await self._async_boost_expired(dt_util.utcnow())
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
            fan_mode=attrs.get(ATTR_FAN_MODE),
            target_temperature=_as_float(attrs.get(ATTR_TEMPERATURE)),
            current_temperature=_as_float(attrs.get(ATTR_CURRENT_TEMPERATURE)),
            min_temp=_as_float(attrs.get(ATTR_MIN_TEMP)),
            max_temp=_as_float(attrs.get(ATTR_MAX_TEMP)),
            target_temp_step=_as_float(attrs.get(ATTR_TARGET_TEMP_STEP)),
            hvac_modes=tuple(attrs.get(ATTR_HVAC_MODES) or ()),
            preset_modes=tuple(attrs.get(ATTR_PRESET_MODES) or ()),
            fan_modes=tuple(attrs.get(ATTR_FAN_MODES) or ()),
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

    def _route_override_value(self) -> str:
        """Return the effective route override."""
        return self._route_override

    def _route_decision(self) -> RouteDecision:
        capabilities = {target: self._states[target].capability for target in Target}
        inputs = RouteInputs(
            hvac_mode=self._desired.hvac_mode or HVAC_HEAT,
            route_override=self._route_override_value(),
            outdoor_temperature=self._outdoor_temperature,
            outdoor_fresh=not self._outdoor_stale,
            current_target=self._current_route_target(),
            capabilities=capabilities,
            cold_threshold=self.config.cold_threshold,
            mild_threshold=self.config.mild_threshold,
            fallback_on_unavailable=self.config.fallback_on_unavailable,
            boost_active=self._boost is not None,
            single_target=self._single_configured_target(),
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
        for target in self._configured_targets():
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
        configured = self._configured_targets()

        hvac_modes = [HVAC_OFF, HVAC_HEAT]
        if any(self._states[target].capability.can_handle(HVAC_COOL) for target in configured):
            hvac_modes.append(HVAC_COOL)

        if len(configured) > 1:
            presets = set(radiator.preset_modes) & set(ac.preset_modes)
            if not presets:
                presets = set(radiator.preset_modes) | set(ac.preset_modes)
        else:
            presets = set()
            for target in configured:
                presets.update(self._states[target].preset_modes)
        presets.add("none")
        if self.config.off_preset_enabled:
            presets.add(PRESET_OFF)

        active = self._single_active()
        route_target: Target | None
        if len(self._active_targets) > 1:
            route_target = None
        elif active is not None:
            route_target = active
        elif self._pending_target is not None:
            route_target = self._pending_target
        else:
            route_target = self._last_route
        active_state = self._states.get(active) if active is not None else None
        if active_state is None:
            for target in (Target.AC, Target.RADIATOR):
                if target in configured and self._states[target].available:
                    active_state = self._states[target]
                    break
        if active_state is None:
            active_state = next(
                (self._states[target] for target in configured),
                radiator,
            )

        return RouterSnapshot(
            ready=self._ready,
            available=any(self._states[target].available for target in configured),
            active_targets=self._active_targets,
            pending_target=self._pending_target,
            route_target=route_target,
            route_reason=self._route_reason,
            handover_state=self._handover_state,
            desired=self._desired,
            manual_mode=self._manual,
            boost_until=self._boost.until if self._boost is not None else None,
            boost_targets=(
                self._boost.targets & configured if self._boost is not None else frozenset()
            ),
            conflicts=tuple(self._conflicts.values()),
            conflict_count=self._conflict_count,
            outdoor_temperature=self._outdoor_temperature,
            outdoor_stale=self._outdoor_stale,
            route_override=self._route_override_value(),
            last_handover=self._last_handover,
            last_command=self._last_command,
            lock_enabled=self.config.lock_enabled,
            locked=self._locked,
            lock_has_code=bool(self.config.lock_code),
            auto_relock_sec=self.config.auto_relock_sec,
            read_only_mode=self._read_only_mode_value,
            configured_targets=configured,
            targets=dict(self._states),
            hvac_modes=tuple(hvac_modes),
            preset_modes=tuple(sorted(presets)),
            off_preset_active=self._off_preset is not None,
            off_preset_target=(self._off_preset.target if self._off_preset is not None else None),
            off_preset_hvac_action=(
                self._off_preset.hvac_action if self._off_preset is not None else None
            ),
            fan_modes=ac.fan_modes if Target.AC in configured else (),
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
        if self._read_only_mode() != READ_ONLY_OFF:
            _LOGGER.debug(
                "Read-only mode (%s); skipping climate.%s on %s: %s",
                self._read_only_mode(),
                service,
                state.entity_id,
                data,
            )
            return
        context = Context()
        self._contexts[context.id] = time.monotonic() + CONTEXT_TTL
        settle = max(self.config.settle_time, 1)
        until = dt_util.utcnow() + timedelta(seconds=settle)
        if self._suppress_conflicts_until is None or until > self._suppress_conflicts_until:
            self._suppress_conflicts_until = until
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
        manual_data = data.get("manual_mode")
        if not isinstance(manual_data, dict):
            # Migrate the 0.7.x key.
            manual_data = data.get("override")
        if isinstance(manual_data, dict):
            manual = ManualMode.from_dict(manual_data)
            if manual is not None and not manual.is_expired(dt_util.utcnow()):
                self._manual = manual
        boost_data = data.get("boost")
        if isinstance(boost_data, dict):
            boost = BoostState.from_dict(boost_data)
            if boost is not None and not boost.is_expired(dt_util.utcnow()):
                self._boost = boost
        off_preset_data = data.get("off_preset")
        if (
            isinstance(off_preset_data, dict)
            and self.config.off_preset_enabled
            and self.config.off_preset_keeps_live_state
        ):
            self._off_preset = OffPresetHold.from_dict(off_preset_data)
        last_live = data.get("last_live")
        if isinstance(last_live, dict):
            restored = DesiredState.from_dict(last_live)
            if restored.hvac_mode in (HVAC_HEAT, HVAC_COOL):
                self._last_live = restored
        if (
            data.get("off_preset_pending") is True
            and self._manual is not None
            and self.config.off_preset_enabled
            and self.config.off_preset_keeps_live_state
        ):
            self._off_preset_pending = True
        self._sync_desired()
        last_route = data.get("last_route")
        if last_route in (Target.RADIATOR.value, Target.AC.value):
            self._last_route = Target(last_route)
        locked = data.get("locked")
        if isinstance(locked, bool):
            self._locked = locked
        auto_relock_at = data.get("auto_relock_at")
        if isinstance(auto_relock_at, str):
            parsed = dt_util.parse_datetime(auto_relock_at)
            if parsed is not None and not self._locked:
                self._auto_relock_at = parsed
        last_handover = data.get("last_handover")
        if isinstance(last_handover, str):
            parsed = dt_util.parse_datetime(last_handover)
            if parsed is not None:
                self._last_handover = parsed
        if data.get("read_only_mode") in READ_ONLY_MODES:
            self._read_only_mode_value = data["read_only_mode"]
        if not self.config.lock_enabled:
            self._locked = False
            self._auto_relock_at = None

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "version": STORAGE_VERSION,
            "desired": self._baseline.to_dict(),
            "manual_mode": self._manual.to_dict() if self._manual is not None else None,
            "off_preset": self._off_preset.to_dict() if self._off_preset is not None else None,
            "off_preset_pending": self._off_preset_pending,
            "last_live": self._last_live.to_dict() if self._last_live is not None else None,
            "boost": self._boost.to_dict() if self._boost is not None else None,
            "last_route": self._last_route.value if self._last_route else None,
            "last_handover": (self._last_handover.isoformat() if self._last_handover else None),
            "locked": self._locked,
            "auto_relock_at": (self._auto_relock_at.isoformat() if self._auto_relock_at else None),
            "read_only_mode": self._read_only_mode_value,
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
