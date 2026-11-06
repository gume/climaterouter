"""Unit tests for the domain models."""

from __future__ import annotations

from climaterouter.models import (
    DesiredState,
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


def test_underlying_state_active_semantics() -> None:
    assert not UnderlyingState(hvac_mode="off", hvac_action="off").is_active
    assert not UnderlyingState(hvac_mode="heat", hvac_action="idle").is_active
    assert UnderlyingState(hvac_mode="heat", hvac_action="heating").is_active
    assert UnderlyingState(hvac_mode="cool", hvac_action="cooling").is_active
    # Unknown action is treated as active to protect an ongoing cycle.
    assert UnderlyingState(hvac_mode="heat", hvac_action=None).is_active
    # An unavailable entity reports no mode.
    assert not UnderlyingState(available=False).is_active
