"""Unit tests for the domain models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from climaterouter.models import (
    PRESET_OFF,
    READ_ONLY_OFF,
    READ_ONLY_SOFT,
    BoostState,
    Conflict,
    DesiredState,
    ManualMode,
    RouterConfig,
    RouterSnapshot,
    SetpointKind,
    Target,
    UnderlyingState,
    lock_blocks_context,
)


def test_router_config_defaults() -> None:
    config = RouterConfig.from_mapping({})
    assert config.cold_threshold == 7.0
    assert config.mild_threshold == 9.0
    assert config.boost_enabled is False
    assert config.default_manual_minutes == 60
    assert config.max_manual_minutes == 1440


def test_router_config_manual_timer_falls_back_to_override_keys() -> None:
    config = RouterConfig.from_mapping(
        {"default_override_minutes": "15", "max_override_minutes": "120"}
    )
    assert config.default_manual_minutes == 15
    assert config.max_manual_minutes == 120
    explicit = RouterConfig.from_mapping({"default_manual_minutes": 5, "max_manual_minutes": 30})
    assert explicit.default_manual_minutes == 5
    assert explicit.max_manual_minutes == 30


def test_router_config_parses_types() -> None:
    config = RouterConfig.from_mapping(
        {
            "name": "Living room",
            "cold_threshold": "5.5",
            "mild_threshold": 7,
            "min_route_dwell": "120",
            "boost_enabled": "true",
        }
    )
    assert config.name == "Living room"
    assert config.cold_threshold == 5.5
    assert config.mild_threshold == 7.0
    assert config.min_route_dwell == 120
    assert config.boost_enabled is True


def test_desired_state_roundtrip() -> None:
    desired = DesiredState(
        hvac_mode="heat",
        setpoint_kind=SetpointKind.TEMPERATURE,
        target_temperature=21.5,
    )
    restored = DesiredState.from_dict(desired.to_dict())
    assert restored == desired


def test_desired_state_copy_is_independent() -> None:
    desired = DesiredState(
        hvac_mode="heat",
        setpoint_kind=SetpointKind.TEMPERATURE,
        target_temperature=21.5,
    )
    copied = desired.copy()
    copied.target_temperature = 25.0
    assert desired.target_temperature == 21.5


def test_manual_mode_applies_to_desired_state() -> None:
    now = datetime.now(timezone.utc)  # noqa: UP017
    baseline = DesiredState(
        hvac_mode="heat",
        setpoint_kind=SetpointKind.PRESET,
        preset_mode="comfort",
    )

    manual = ManualMode(
        desired=DesiredState(
            hvac_mode="heat",
            setpoint_kind=SetpointKind.TEMPERATURE,
            target_temperature=22.5,
        ),
        until=now + timedelta(minutes=45),
        baseline=baseline,
        started_at=now,
    )
    effective = baseline.with_manual_mode(manual)
    assert effective.hvac_mode == "heat"
    assert effective.setpoint_kind == SetpointKind.TEMPERATURE
    assert effective.target_temperature == 22.5
    assert effective.preset_mode is None
    # The baseline itself must stay untouched.
    assert baseline.preset_mode == "comfort"
    assert baseline.with_manual_mode(None) == baseline


def test_manual_mode_roundtrip_and_expiry() -> None:
    now = datetime.now(timezone.utc)  # noqa: UP017
    manual = ManualMode(
        desired=DesiredState(
            hvac_mode="heat",
            setpoint_kind=SetpointKind.TEMPERATURE,
            target_temperature=22.5,
        ),
        until=now + timedelta(minutes=45),
        baseline=DesiredState(hvac_mode="heat", setpoint_kind=SetpointKind.NONE),
        started_at=now,
    )
    restored = ManualMode.from_dict(manual.to_dict())
    assert restored == manual
    assert restored is not None
    assert not restored.is_expired(now)
    assert restored.is_expired(now + timedelta(minutes=46))
    assert restored.remaining_minutes(now) == 45
    assert restored.remaining_minutes(now + timedelta(minutes=46)) == 0


def test_manual_mode_infinite_timer() -> None:
    now = datetime.now(timezone.utc)  # noqa: UP017
    manual = ManualMode(
        desired=DesiredState(hvac_mode="heat"),
        started_at=now,
        until=None,
    )
    assert not manual.has_deadline
    assert not manual.is_expired(now + timedelta(days=365))
    assert manual.remaining_minutes(now) is None
    restored = ManualMode.from_dict(manual.to_dict())
    assert restored == manual
    assert restored is not None
    assert restored.until is None


def test_manual_mode_migrates_legacy_override() -> None:
    now = datetime.now(timezone.utc)  # noqa: UP017
    legacy = {
        "kind": "temperature",
        "value": 20,
        "until": (now + timedelta(minutes=30)).isoformat(),
        "started_at": now.isoformat(),
        "baseline": DesiredState(
            hvac_mode="heat",
            setpoint_kind=SetpointKind.PRESET,
            preset_mode="comfort",
        ).to_dict(),
    }
    migrated = ManualMode.from_dict(legacy)
    assert migrated is not None
    assert migrated.desired.setpoint_kind == SetpointKind.TEMPERATURE
    assert migrated.desired.target_temperature == 20.0
    assert migrated.baseline.preset_mode == "comfort"


def test_manual_mode_from_dict_rejects_invalid_data() -> None:
    assert ManualMode.from_dict({}) is None
    assert ManualMode.from_dict({"started_at": "not-a-date"}) is None
    assert (
        ManualMode.from_dict(
            {
                "started_at": "2026-11-06T17:00:00",
                "until": "2026-11-06T18:00:00",
                "desired": {},
            }
        )
        is None
    )
    assert (
        ManualMode.from_dict(
            {
                "started_at": "2026-11-06T17:00:00+00:00",
                "until": "not-a-date",
                "desired": {},
            }
        )
        is None
    )


def test_boost_state_roundtrip_and_expiry() -> None:
    now = datetime.now(timezone.utc)  # noqa: UP017
    boost = BoostState(
        until=now + timedelta(minutes=30),
        started_at=now,
        targets=frozenset({Target.RADIATOR, Target.AC}),
    )
    restored = BoostState.from_dict(boost.to_dict())
    assert restored == boost
    assert restored is not None
    assert not restored.is_expired(now)
    assert restored.is_expired(now + timedelta(minutes=31))
    assert restored.remaining_minutes(now) == 30
    assert restored.remaining_minutes(now + timedelta(minutes=31)) == 0


def test_boost_state_from_dict_tolerates_bad_data() -> None:
    assert BoostState.from_dict({}) is None
    assert BoostState.from_dict({"until": "not-a-date", "started_at": "x"}) is None
    assert (
        BoostState.from_dict(
            {
                "until": "2026-11-06T18:00:00",
                "started_at": "2026-11-06T17:00:00",
            }
        )
        is None
    )
    partial = BoostState.from_dict(
        {
            "until": "2026-11-06T18:00:00+00:00",
            "started_at": "2026-11-06T17:00:00+00:00",
            "targets": ["ac", "bogus"],
        }
    )
    assert partial is not None
    assert partial.targets == frozenset({Target.AC})


def test_conflict_serialization_is_json_safe() -> None:
    now = datetime.now(timezone.utc)  # noqa: UP017
    conflict = Conflict(
        key="setpoint_mismatch:ac",
        type="setpoint_mismatch",
        target=Target.AC,
        expected=21.0,
        actual=24.0,
        first_seen=now,
        last_seen=now,
        source_guess="user",
    )
    data = conflict.to_dict()
    assert data["target"] == "ac"
    assert data["expected"] == 21.0
    assert isinstance(data["first_seen"], str)


def test_router_config_parses_read_only_and_pause_settings() -> None:
    config = RouterConfig.from_mapping(
        {
            "read_only_mode": "soft",
            "scheduler_pause_switch_entity_id": "switch.chauffage_pause",
            "scheduler_pause_switch_invert": "on",
        }
    )
    assert config.read_only_mode == READ_ONLY_SOFT
    assert config.scheduler_pause_switch_entity_id == "switch.chauffage_pause"
    assert config.scheduler_pause_switch_invert is True


def test_router_config_read_only_defaults_and_invalid_values() -> None:
    config = RouterConfig.from_mapping({})
    assert config.read_only_mode == READ_ONLY_OFF
    assert config.scheduler_pause_switch_invert is False

    invalid = RouterConfig.from_mapping({"read_only_mode": "frozen"})
    assert invalid.read_only_mode == READ_ONLY_OFF


def test_router_config_configured_targets_and_single_target() -> None:
    both = RouterConfig.from_mapping(
        {"radiator_entity_id": "climate.radiator", "ac_entity_id": "climate.ac"}
    )
    assert both.configured_targets == frozenset({Target.RADIATOR, Target.AC})
    assert both.single_target is None

    radiator_only = RouterConfig.from_mapping({"radiator_entity_id": "climate.radiator"})
    assert radiator_only.configured_targets == frozenset({Target.RADIATOR})
    assert radiator_only.single_target is Target.RADIATOR

    ac_only = RouterConfig.from_mapping({"ac_entity_id": "climate.ac"})
    assert ac_only.configured_targets == frozenset({Target.AC})
    assert ac_only.single_target is Target.AC

    assert RouterConfig.from_mapping({}).single_target is None


def test_snapshot_effective_read_only_ignores_manual_mode() -> None:
    snapshot = RouterSnapshot(read_only_mode=READ_ONLY_SOFT)
    assert snapshot.effective_read_only == READ_ONLY_SOFT
    assert snapshot.soft_read_only is True
    assert snapshot.hard_read_only is False

    now = datetime.now(timezone.utc)  # noqa: UP017
    snapshot = RouterSnapshot(
        read_only_mode=READ_ONLY_SOFT,
        manual_mode=ManualMode(
            desired=DesiredState(hvac_mode="heat"),
            started_at=now,
        ),
    )
    assert snapshot.effective_read_only == READ_ONLY_OFF
    assert snapshot.soft_read_only is False
    assert snapshot.hard_read_only is False
    assert snapshot.schedule_locked is True


def test_snapshot_preset_modes_include_off() -> None:
    assert PRESET_OFF in RouterSnapshot().preset_modes


def test_snapshot_ignores_mismatch_for_a_single_configured_target() -> None:
    snapshot = RouterSnapshot(
        configured_targets=frozenset({Target.RADIATOR}),
        targets={
            Target.RADIATOR: UnderlyingState(target_temperature=23.0),
            Target.AC: UnderlyingState(target_temperature=19.0),
        },
    )
    assert snapshot.target_mismatch_reasons() == ()


def test_underlying_state_active_semantics() -> None:
    assert not UnderlyingState(hvac_mode="off", hvac_action="off").is_active
    assert not UnderlyingState(hvac_mode="heat", hvac_action="idle").is_active
    assert UnderlyingState(hvac_mode="heat", hvac_action="heating").is_active
    assert UnderlyingState(hvac_mode="cool", hvac_action="cooling").is_active
    # Unknown action is treated as active to protect an ongoing cycle.
    assert UnderlyingState(hvac_mode="heat", hvac_action=None).is_active
    # An unavailable entity reports no mode.
    assert not UnderlyingState(available=False).is_active


def test_router_config_parses_lock_settings() -> None:
    config = RouterConfig.from_mapping(
        {
            "lock_enabled": "on",
            "lock_code": 1234,
            "auto_relock_sec": "60",
        }
    )
    assert config.lock_enabled is True
    assert config.lock_code == "1234"
    assert config.auto_relock_sec == 60


def test_router_config_lock_defaults() -> None:
    config = RouterConfig.from_mapping({})
    assert config.lock_enabled is False
    assert config.lock_code == ""
    assert config.auto_relock_sec == 30


def test_ui_lock_blocks_only_user_commands() -> None:
    base = {
        "enabled": True,
        "locked": True,
    }
    assert lock_blocks_context(**base, user_id="user-1") is True
    # Automations must keep working so handovers can complete.
    assert lock_blocks_context(**base, user_id=None) is False
    assert lock_blocks_context(**{**base, "locked": False}, user_id="user-1") is False
    assert lock_blocks_context(**{**base, "enabled": False}, user_id="user-1") is False


def test_target_mismatch_reasons_describe_setpoint_and_preset_differences() -> None:
    snapshot = RouterSnapshot(
        targets={
            Target.RADIATOR: UnderlyingState(
                target_temperature=23.0,
                preset_mode="comfort",
            ),
            Target.AC: UnderlyingState(
                target_temperature=21.0,
                preset_mode="eco",
            ),
        }
    )
    assert snapshot.target_mismatch_reasons() == (
        "setpoint 23 vs 21",
        "preset comfort vs eco",
    )

    matching = RouterSnapshot(
        targets={
            Target.RADIATOR: UnderlyingState(
                target_temperature=23.0,
                preset_mode="comfort",
            ),
            Target.AC: UnderlyingState(
                target_temperature=23.1,
                preset_mode="comfort",
            ),
        }
    )
    assert matching.target_mismatch_reasons() == ()
    assert RouterSnapshot().target_mismatch_reasons() == ()
