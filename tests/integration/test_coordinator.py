"""Integration tests for coordinator routing and manual mode."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.const import STATE_OFF
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_mock_service,
)

from custom_components.climaterouter.const import (
    CONFLICT_REASSERT_GRACE,
    DOMAIN,
    EVENT_BOOST_ENDED,
    EVENT_CONFLICT_CLEARED,
    EVENT_CONFLICT_DETECTED,
    EVENT_HANDOVER_ABORTED,
    EVENT_MANUAL_MODE_ENDED,
)
from custom_components.climaterouter.models import HVAC_HEAT, ROUTE_AC, Target

RADIATOR = "climate.radiator"
AC = "climate.ac"
OUTDOOR = "sensor.outdoor"

USER = Context(user_id="user-1")


def _entry_data(**overrides: Any) -> dict[str, Any]:
    """Return entry data tuned for fast, deterministic routing."""
    data: dict[str, Any] = {
        "name": "Test Router",
        "radiator_entity_id": RADIATOR,
        "ac_entity_id": AC,
        "outdoor_sensor_entity_id": OUTDOOR,
        "startup_grace": 0,
        "settle_time": 0,
        "min_route_dwell": 0,
        "handover_idle_confirm": 0,
        "off_confirm_timeout": 1,
    }
    data.update(overrides)
    return data


def _set_entities(hass, *, outdoor: float = 5.0) -> None:
    hass.states.async_set(
        RADIATOR,
        STATE_OFF,
        {"hvac_modes": [HVAC_HEAT], "min_temp": 7, "max_temp": 35},
    )
    hass.states.async_set(
        AC,
        STATE_OFF,
        {"hvac_modes": [HVAC_HEAT, "cool"], "min_temp": 16, "max_temp": 30},
    )
    hass.states.async_set(OUTDOOR, str(outdoor), {"unit_of_measurement": "°C"})


async def _setup(hass, *, outdoor: float = 5.0, **data: Any):
    """Set up one entry and return it with its coordinator."""
    _set_entities(hass, outdoor=outdoor)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(**data),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, entry.runtime_data


async def test_routes_to_radiator_when_cold(hass) -> None:
    """A fresh heat command below the cold threshold starts the radiator."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)

    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    assert coordinator.data.ready is True
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert coordinator.data.route_reason == "outdoor_cold"
    assert coordinator.data.desired.target_temperature == 21


async def test_switches_to_ac_when_outdoors_get_mild(hass) -> None:
    """The route follows outdoor hysteresis once the radiator is idle."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(OUTDOOR, "15.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.route_reason == "hysteresis"


async def test_route_override_wins_over_outdoor_temperature(hass) -> None:
    """An explicit route override bypasses the hysteresis decision."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    await coordinator.async_set_route_override(ROUTE_AC)
    await hass.async_block_till_done()

    assert coordinator.data.route_override == ROUTE_AC
    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.route_reason == "manual_route"


async def test_user_setpoint_starts_and_ends_manual_mode(hass) -> None:
    """A user setpoint move starts manual mode without changing the baseline."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()
    assert coordinator.data.manual_mode is None

    await coordinator.async_set_temperature(temperature=23, context=USER)
    await hass.async_block_till_done()

    manual = coordinator.data.manual_mode
    assert manual is not None
    assert manual.desired.target_temperature == 23
    assert manual.desired.hvac_mode == HVAC_HEAT
    assert coordinator.data.desired.target_temperature == 23

    await coordinator.async_return_to_schedule()
    await hass.async_block_till_done()

    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.target_temperature == 20


async def test_turn_off_ends_manual_mode(hass) -> None:
    """An explicit off is a safety command and clears manual mode."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_set_temperature(temperature=23, context=USER)
    assert coordinator.data.manual_mode is not None

    await coordinator.async_turn_off(context=USER)
    await hass.async_block_till_done()

    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.hvac_mode == "off"
    assert coordinator.data.active_targets == frozenset()


async def test_falls_back_to_ac_when_radiator_unavailable(hass) -> None:
    """A cold route falls back to a capable target when the first one is gone."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    hass.states.async_set(RADIATOR, "unavailable")

    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.route_reason == "fallback_unavailable"


async def test_stale_outdoor_holds_current_target(hass) -> None:
    """A missing outdoor reading keeps the current target instead of flapping."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(OUTDOOR, "unknown")
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert coordinator.data.route_reason == "fallback_outdoor"


async def test_startup_adopts_a_running_target(hass) -> None:
    """A target that is already heating is adopted without a command."""
    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 19,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    hass.states.async_set(AC, STATE_OFF, {"hvac_modes": [HVAC_HEAT, "cool"]})
    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert coordinator.data.desired.hvac_mode == HVAC_HEAT
    assert coordinator.data.desired.target_temperature == 19


async def test_desired_state_survives_reload(hass) -> None:
    """The persisted desired state is restored when the entry reloads."""
    entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reloaded = entry.runtime_data
    assert reloaded is not coordinator
    assert reloaded.data.desired.hvac_mode == HVAC_HEAT
    assert reloaded.data.desired.target_temperature == 21
    assert reloaded.data.active_targets == frozenset({Target.RADIATOR})


async def _setup_with_active_radiator(hass, **data: Any):
    """Set up an entry whose radiator is already heating."""
    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 20,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    hass.states.async_set(AC, STATE_OFF, {"hvac_modes": [HVAC_HEAT, "cool"]})
    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(**data),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    return entry, coordinator


async def _set_radiator(hass, state: str, **attrs: Any) -> None:
    hass.states.async_set(
        RADIATOR,
        state,
        {
            "hvac_modes": [HVAC_HEAT],
            "temperature": 20,
            "min_temp": 7,
            "max_temp": 35,
            **attrs,
        },
    )
    await hass.async_block_till_done()


async def test_handover_waits_for_idle_then_starts_new_target(hass) -> None:
    """The normal handover path waits for idle, stops, then starts."""
    _entry, coordinator = await _setup_with_active_radiator(hass)

    hass.states.async_set(OUTDOOR, "15.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    await hass.async_block_till_done()
    assert coordinator.data.handover_state == "pending"
    assert coordinator.data.pending_target is Target.AC

    await _set_radiator(hass, HVAC_HEAT, hvac_action="idle")
    await coordinator.async_recalculate()
    await hass.async_block_till_done()
    assert coordinator.data.handover_state in ("pending", "stopping_old")

    await coordinator.async_recalculate()
    await hass.async_block_till_done()
    assert coordinator.data.handover_state == "stopping_old"

    await _set_radiator(hass, STATE_OFF)
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.handover_state == "steady"
    assert coordinator.data.pending_target is None


async def test_handover_off_confirm_timeout_becomes_conflict(hass, monkeypatch) -> None:
    """A target that stays on after the off command aborts the handover."""
    from custom_components.climaterouter import coordinator as coordinator_module

    _entry, coordinator = await _setup_with_active_radiator(hass)
    events = async_capture_events(hass, EVENT_HANDOVER_ABORTED)

    hass.states.async_set(OUTDOOR, "15.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    await _set_radiator(hass, HVAC_HEAT, hvac_action="idle")
    await coordinator.async_recalculate()
    await coordinator.async_recalculate()
    await hass.async_block_till_done()
    assert coordinator.data.handover_state == "stopping_old"

    # dt_util.utcnow is a partial bound at import time, so freezegun cannot
    # move it; shift the coordinator's clock directly instead.
    now = coordinator_module.dt_util.utcnow()
    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: now + timedelta(seconds=2))
    await coordinator.async_recalculate()

    # Do not drain scheduled updates here: a fresh evaluation would immediately
    # begin a new handover and hide the abort.
    assert coordinator.data.handover_state == "conflict"
    assert coordinator.data.pending_target is None
    assert events and events[0].data["error"] == "off_confirm_timeout"


async def test_handover_reverts_when_route_changes_back(hass) -> None:
    """A pending handover is cancelled if the route returns to the old target."""
    _entry, coordinator = await _setup_with_active_radiator(hass)

    hass.states.async_set(OUTDOOR, "15.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    assert coordinator.data.handover_state == "pending"

    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert coordinator.data.handover_state == "steady"
    assert coordinator.data.pending_target is None


async def test_manual_deadline_survives_reload(hass) -> None:
    """An active manual timer is restored after an unload/setup cycle."""
    entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_enter_manual_mode(temperature=23, duration_minutes=30)
    await hass.async_block_till_done()
    until = coordinator.data.manual_mode.until
    assert coordinator.data.manual_mode.timer_minutes == 30

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    manual = entry.runtime_data.data.manual_mode
    assert manual is not None
    assert manual.timer_minutes == 30
    assert manual.until == until
    assert manual.desired.target_temperature == 23


async def test_boost_deadline_survives_reload(hass) -> None:
    """An active boost and its deadline are restored after a reload."""
    entry, coordinator = await _setup(hass, outdoor=5.0, boost_enabled=True)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_set_boost(duration_minutes=10)
    await hass.async_block_till_done()
    until = coordinator.data.boost_until
    assert until is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reloaded = entry.runtime_data
    assert reloaded.data.boost_until == until
    assert reloaded.data.active_targets == frozenset({Target.RADIATOR, Target.AC})


async def test_restored_desired_waits_for_targets(hass) -> None:
    """A restored desired state does not crash while targets are missing."""
    entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    for entity_id in (RADIATOR, AC, OUTDOOR):
        hass.states.async_remove(entity_id)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reloaded = entry.runtime_data
    assert reloaded.data.desired.target_temperature == 20
    assert reloaded.data.active_targets == frozenset()

    _set_entities(hass, outdoor=5.0)
    await reloaded.async_recalculate()
    await hass.async_block_till_done()

    assert reloaded.data.active_targets == frozenset({Target.RADIATOR})


async def test_lock_blocks_only_user_commands(hass) -> None:
    """The UI lock rejects user commands but leaves automations running."""
    _entry, coordinator = await _setup(hass, outdoor=5.0, lock_enabled=True, lock_code="1234")
    await coordinator.async_lock()
    assert coordinator.data.locked is True

    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT, context=USER)

    await coordinator.async_set_temperature(temperature=21, hvac_mode=HVAC_HEAT)
    assert coordinator.data.desired.target_temperature == 21

    with pytest.raises(HomeAssistantError):
        await coordinator.async_unlock(code="0000")

    await coordinator.async_unlock(code="1234")
    assert coordinator.data.locked is False
    await coordinator.async_set_temperature(temperature=22, context=USER)
    assert coordinator.data.manual_mode is not None


async def test_detects_setpoint_mismatch(hass, freezer) -> None:
    """An external setpoint change is reported under the monitor policy."""
    _entry, coordinator = await _setup(hass, outdoor=5.0, conflict_policy="monitor")
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 25,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=3))
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    conflicts = coordinator.data.conflicts
    assert any(conflict.type == "setpoint_mismatch" for conflict in conflicts)
    assert coordinator.data.conflict_count >= 1


async def test_boost_runs_both_targets_and_cancels_back(hass) -> None:
    """Boost activates both targets and cancelling returns to normal routing."""
    _entry, coordinator = await _setup(hass, outdoor=5.0, boost_enabled=True)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})

    await coordinator.async_set_boost(duration_minutes=10)
    await hass.async_block_till_done()

    assert coordinator.data.boost_until is not None
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR, Target.AC})
    assert coordinator.data.handover_state == "boost"

    await coordinator.async_cancel_boost()
    await hass.async_block_till_done()

    assert coordinator.data.boost_until is None
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert coordinator.data.handover_state == "steady"


async def test_boost_requires_the_feature_flag(hass) -> None:
    """Boost is rejected unless it is enabled in the options."""
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)

    with pytest.raises(HomeAssistantError):
        await coordinator.async_set_boost(duration_minutes=10)


async def test_force_handover_completes_despite_active_old_target(hass) -> None:
    """Forcing a handover skips the wait for the old target to idle."""
    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 19,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    hass.states.async_set(AC, STATE_OFF, {"hvac_modes": [HVAC_HEAT, "cool"]})
    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})

    hass.states.async_set(OUTDOOR, "15.0", {"unit_of_measurement": "°C"})
    await coordinator.async_recalculate()
    assert coordinator.data.pending_target is Target.AC

    await coordinator.async_force_handover()
    await hass.async_block_till_done()

    assert coordinator.data.active_targets == frozenset({Target.AC})
    assert coordinator.data.handover_state == "steady"


async def test_manual_timer_expiry_returns_to_schedule(hass, monkeypatch) -> None:
    """An expired manual timer drops back to the scheduled setpoint."""
    from custom_components.climaterouter import coordinator as coordinator_module

    events = async_capture_events(hass, EVENT_MANUAL_MODE_ENDED)
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_enter_manual_mode(temperature=23, duration_minutes=30)
    await hass.async_block_till_done()

    manual = coordinator.data.manual_mode
    assert manual is not None
    assert manual.until is not None

    monkeypatch.setattr(
        coordinator_module.dt_util,
        "utcnow",
        lambda: manual.until + timedelta(seconds=1),
    )
    await coordinator._async_manual_expired(coordinator_module.dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data.manual_mode is None
    assert coordinator.data.desired.target_temperature == 20
    assert events and events[0].data["cause"] == "expired"


async def test_boost_expiry_returns_to_single_target(hass, monkeypatch) -> None:
    """An expired boost ends both-target routing and emits the end event."""
    from custom_components.climaterouter import coordinator as coordinator_module

    events = async_capture_events(hass, EVENT_BOOST_ENDED)
    _entry, coordinator = await _setup(hass, outdoor=5.0, boost_enabled=True)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_set_boost(duration_minutes=10)
    await hass.async_block_till_done()

    until = coordinator.data.boost_until
    assert until is not None
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR, Target.AC})

    monkeypatch.setattr(
        coordinator_module.dt_util,
        "utcnow",
        lambda: until + timedelta(seconds=1),
    )
    await coordinator._async_boost_expired(coordinator_module.dt_util.utcnow())
    await hass.async_block_till_done()

    assert coordinator.data.boost_until is None
    assert coordinator.data.handover_state == "steady"
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR})
    assert events and events[0].data["cause"] == "expired"


async def test_unlock_schedules_auto_relock(hass) -> None:
    """Unlocking schedules the configured automatic relock."""
    _entry, coordinator = await _setup(hass, outdoor=5.0, lock_enabled=True)
    await coordinator.async_lock()
    assert coordinator.data.locked is True

    await coordinator.async_unlock()
    assert coordinator.data.locked is False
    assert coordinator._auto_relock_at is not None

    coordinator._cancel_auto_relock()
    await coordinator._async_auto_relock(dt_util.utcnow())
    assert coordinator.data.locked is True


async def test_auto_relock_deadline_survives_reload(hass) -> None:
    """The pending auto-relock deadline is restored after a reload."""
    entry, coordinator = await _setup(hass, outdoor=5.0, lock_enabled=True)
    await coordinator.async_lock()
    await coordinator.async_unlock()
    until = coordinator._auto_relock_at
    assert until is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reloaded = entry.runtime_data
    assert reloaded._auto_relock_at is not None
    assert abs((reloaded._auto_relock_at - until).total_seconds()) < 5
    assert reloaded.data.locked is False


async def test_conflict_reassert_reenforces_desired_setpoint(hass, monkeypatch) -> None:
    """The reassert policy resends the desired setpoint after the grace period."""
    from custom_components.climaterouter import coordinator as coordinator_module

    _entry, coordinator = await _setup(hass, outdoor=5.0, conflict_policy="reassert")
    calls = async_mock_service(hass, "climate", "set_temperature")
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()
    calls.clear()

    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 25,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    await hass.async_block_till_done()
    await coordinator.async_evaluate()
    await hass.async_block_till_done()
    assert not any(call.data.get("temperature") == 20 for call in calls)

    # Move past the settle window so the mismatch is detected, then past the
    # reassert grace period so the desired setpoint is sent again.
    base = coordinator_module.dt_util.utcnow()
    clock = {"now": base + timedelta(seconds=2)}
    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: clock["now"])

    await coordinator.async_evaluate()
    await hass.async_block_till_done()
    assert coordinator.data.conflicts
    assert not any(call.data.get("temperature") == 20 for call in calls)

    clock["now"] = base + timedelta(seconds=CONFLICT_REASSERT_GRACE + 3)
    await coordinator.async_evaluate()
    await hass.async_block_till_done()

    assert any(call.data.get("temperature") == 20 for call in calls)


async def test_conflict_adopt_updates_baseline(hass, monkeypatch) -> None:
    """The adopt policy accepts an external setpoint as the new desired value."""
    from custom_components.climaterouter import coordinator as coordinator_module

    _entry, coordinator = await _setup(hass, outdoor=5.0, conflict_policy="adopt")
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 25,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    await hass.async_block_till_done()

    # Skip the settle window that follows our own service calls.
    base = coordinator_module.dt_util.utcnow()
    monkeypatch.setattr(
        coordinator_module.dt_util,
        "utcnow",
        lambda: base + timedelta(seconds=2),
    )
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert coordinator.data.desired.target_temperature == 25
    assert coordinator.data.conflict_count == 0


async def test_both_targets_on_auto_resolve_stops_spare(hass, monkeypatch) -> None:
    """Both-on detection can stop the idle spare target automatically."""
    from custom_components.climaterouter import coordinator as coordinator_module

    _entry, coordinator = await _setup(hass, outdoor=5.0, auto_resolve_simultaneous=True)
    calls = async_mock_service(hass, "climate", "set_hvac_mode")
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 20,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    hass.states.async_set(
        AC,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT, "cool"],
            "hvac_action": "idle",
            "temperature": 20,
            "min_temp": 16,
            "max_temp": 30,
        },
    )
    await hass.async_block_till_done()

    # Skip the settle window that follows our own service calls.
    base = coordinator_module.dt_util.utcnow()
    monkeypatch.setattr(
        coordinator_module.dt_util,
        "utcnow",
        lambda: base + timedelta(seconds=2),
    )
    await coordinator.async_recalculate()
    await hass.async_block_till_done()

    assert any(conflict.type == "both_targets_on" for conflict in coordinator.data.conflicts)
    assert any(
        call.data.get("entity_id") == AC and call.data.get("hvac_mode") == "off" for call in calls
    )


async def test_startup_with_both_targets_active_reports_conflict(hass) -> None:
    """Two targets already heating at startup are adopted with a conflict state."""
    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 20,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    hass.states.async_set(
        AC,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT, "cool"],
            "hvac_action": "heating",
            "temperature": 20,
            "min_temp": 16,
            "max_temp": 30,
        },
    )
    hass.states.async_set(OUTDOOR, "5.0", {"unit_of_measurement": "°C"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_entry_data(),
        unique_id="test-router",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data
    assert coordinator.data.active_targets == frozenset({Target.RADIATOR, Target.AC})
    assert coordinator.data.handover_state == "conflict"
    assert coordinator.data.route_reason == "startup_conflict"


async def test_conflict_history_and_clear(hass, monkeypatch) -> None:
    """Clearing a conflict records it as resolved and fires the event."""
    from custom_components.climaterouter import coordinator as coordinator_module

    detected = async_capture_events(hass, EVENT_CONFLICT_DETECTED)
    cleared = async_capture_events(hass, EVENT_CONFLICT_CLEARED)
    _entry, coordinator = await _setup(hass, outdoor=5.0)
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await hass.async_block_till_done()

    hass.states.async_set(
        RADIATOR,
        HVAC_HEAT,
        {
            "hvac_modes": [HVAC_HEAT],
            "hvac_action": "heating",
            "temperature": 25,
            "min_temp": 7,
            "max_temp": 35,
        },
    )
    await hass.async_block_till_done()

    base = coordinator_module.dt_util.utcnow()
    monkeypatch.setattr(
        coordinator_module.dt_util,
        "utcnow",
        lambda: base + timedelta(seconds=2),
    )
    await coordinator.async_evaluate()
    await hass.async_block_till_done()

    assert coordinator.data.conflict_count == 1
    assert coordinator.data.conflicts
    assert detected

    await coordinator.async_clear_conflicts()
    await hass.async_block_till_done()

    assert coordinator.data.conflicts == ()
    assert coordinator.conflict_history[-1].resolved is True
    assert cleared


async def test_watchdog_expires_manual_and_boost(hass, monkeypatch) -> None:
    """The periodic watchdog ends expired manual mode and boost."""
    from custom_components.climaterouter import coordinator as coordinator_module

    manual_events = async_capture_events(hass, EVENT_MANUAL_MODE_ENDED)
    boost_events = async_capture_events(hass, EVENT_BOOST_ENDED)
    _entry, coordinator = await _setup(
        hass,
        outdoor=5.0,
        boost_enabled=True,
        manual_blocks_schedule=False,
    )
    await coordinator.async_set_temperature(temperature=20, hvac_mode=HVAC_HEAT)
    await coordinator.async_enter_manual_mode(temperature=23, duration_minutes=30)
    await coordinator.async_set_boost(duration_minutes=10)
    await hass.async_block_till_done()

    manual = coordinator.data.manual_mode
    boost_until = coordinator.data.boost_until
    assert manual is not None and manual.until is not None
    assert boost_until is not None

    later = max(manual.until, boost_until) + timedelta(seconds=1)
    monkeypatch.setattr(coordinator_module.dt_util, "utcnow", lambda: later)
    await coordinator._async_watchdog(later)
    await hass.async_block_till_done()

    assert coordinator.data.manual_mode is None
    assert coordinator.data.boost_until is None
    assert manual_events and manual_events[0].data["cause"] == "expired"
    assert boost_events and boost_events[0].data["cause"] == "expired"
