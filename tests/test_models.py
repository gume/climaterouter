"""Unit tests for the domain models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from climaterouter.models import (
    BoostState,
    Conflict,
    DesiredState,
    OverrideState,
    RouterConfig,
    SetpointKind,
    Target,
    UnderlyingState,
)


def test_router_config_defaults() -> None:
    config = RouterConfig.from_mapping({})
    assert config.cold_threshold == 7.0
    assert config.mild_threshold == 9.0
    assert config.manual_switch_on_target is Target.AC
    assert config.boost_enabled is False


def test_router_config_parses_types() -> None:
    config = RouterConfig.from_mapping(
        {
            "name": "Living room",
            "cold_threshold": "5.5",
            "mild_threshold": 7,
            "min_route_dwell": "120",
            "manual_switch_on_target": "radiator",
            "boost_enabled": "true",
        }
    )
    assert config.name == "Living room"
    assert config.cold_threshold == 5.5
    assert config.mild_threshold == 7.0
    assert config.min_route_dwell == 120
    assert config.manual_switch_on_target is Target.RADIATOR
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


def test_override_applies_to_desired_state() -> None:
    now = datetime.now(timezone.utc)
    baseline = DesiredState(
        hvac_mode="heat",
        setpoint_kind=SetpointKind.PRESET,
        preset_mode="comfort",
    )

    temperature_override = OverrideState(
        kind="temperature",
        value=22.5,
        until=now + timedelta(minutes=45),
        baseline=baseline,
        started_at=now,
    )
    effective = baseline.with_override(temperature_override)
    assert effective.hvac_mode == "heat"
    assert effective.setpoint_kind == SetpointKind.TEMPERATURE
    assert effective.target_temperature == 22.5
    assert effective.preset_mode is None
    # The baseline itself must stay untouched.
    assert baseline.preset_mode == "comfort"

    preset_override = OverrideState(
        kind="preset",
        value="eco",
        until=now + timedelta(minutes=45),
        baseline=baseline,
        started_at=now,
    )
    effective = baseline.with_override(preset_override)
    assert effective.setpoint_kind == SetpointKind.PRESET
    assert effective.preset_mode == "eco"
    assert effective.target_temperature is None

    mode_override = OverrideState(
        kind="hvac_mode",
        value="cool",
        until=now + timedelta(minutes=45),
        baseline=baseline,
        started_at=now,
    )
    effective = baseline.with_override(mode_override)
    assert effective.hvac_mode == "cool"
    assert effective.preset_mode == "comfort"


def test_override_roundtrip_and_expiry() -> None:
    now = datetime.now(timezone.utc)
    override = OverrideState(
        kind="temperature",
        value=22.5,
        until=now + timedelta(minutes=45),
        baseline=DesiredState(hvac_mode="heat", setpoint_kind=SetpointKind.NONE),
        started_at=now,
    )
    restored = OverrideState.from_dict(override.to_dict())
    assert restored == override
    assert restored is not None
    assert not restored.is_expired(now)
    assert restored.is_expired(now + timedelta(minutes=46))
    assert restored.remaining_minutes(now) == 45
    assert restored.remaining_minutes(now + timedelta(minutes=46)) == 0


def test_override_from_dict_rejects_invalid_data() -> None:
    assert OverrideState.from_dict({}) is None
    assert OverrideState.from_dict({"kind": "temperature", "until": "not-a-date"}) is None
    assert (
        OverrideState.from_dict(
            {
                "kind": "temperature",
                "value": 20,
                "until": "2026-11-06T18:00:00",
                "started_at": "2026-11-06T17:00:00",
                "baseline": {},
            }
        )
        is None
    )


def test_boost_state_roundtrip_and_expiry() -> None:
    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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


def test_underlying_state_active_semantics() -> None:
    assert not UnderlyingState(hvac_mode="off", hvac_action="off").is_active
    assert not UnderlyingState(hvac_mode="heat", hvac_action="idle").is_active
    assert UnderlyingState(hvac_mode="heat", hvac_action="heating").is_active
    assert UnderlyingState(hvac_mode="cool", hvac_action="cooling").is_active
    # Unknown action is treated as active to protect an ongoing cycle.
    assert UnderlyingState(hvac_mode="heat", hvac_action=None).is_active
    # An unavailable entity reports no mode.
    assert not UnderlyingState(available=False).is_active
