"""Tests for the read-only VTherm display attributes."""

from __future__ import annotations

from climaterouter.vt_display import (
    build_vt_display_attributes,
)

OVER_SWITCH = {
    "configuration": {
        "type": "over_switch",
        "proportional_function": "tpi",
        "have_valve_regulation": False,
        "ac_mode": False,
    },
    "is_over_switch": True,
    "is_lock_configured": True,
    "lock_manager": {
        "is_locked": True,
        "lock_users": True,
        "lock_automations": True,
    },
    "power_percent": 42,
    "on_percent": 0.42,
    "is_power_configured": False,
    "is_window_configured": True,
    "power_manager": {
        "device_power": 1.0,
        "mean_cycle_power": 0.42,
        "overpowering_state": "off",
    },
    "window_manager": {
        "window_state": "off",
        "is_window_detected": False,
    },
    "specific_states": {
        "is_locked": True,
        "messages": ["target_temp_window_eco"],
        "hvac_mode_reason": "hvac_off_window_detection",
    },
    "vtherm_over_switch": {"power_percent": 42, "on_percent": 0.42, "function": "tpi"},
}

OVER_CLIMATE = {
    "configuration": {
        "type": "over_climate",
        "proportional_function": None,
        "have_valve_regulation": False,
    },
    "is_over_climate": True,
    "power_manager": {"device_power": 1.0, "mean_cycle_power": 1.0},
    "specific_states": {"is_locked": False, "messages": []},
}


def test_no_active_targets() -> None:
    """No active target means no VTherm display attributes."""
    assert build_vt_display_attributes([]) == {}


def test_display_keys_are_always_forwarded() -> None:
    """Read-only gauge data is safe and does not depend on the option."""
    attributes = build_vt_display_attributes([OVER_SWITCH])

    assert attributes["is_over_switch"] is True
    assert attributes["power_percent"] == 42
    assert attributes["on_percent"] == 0.42
    assert attributes["power_manager"]["mean_cycle_power"] == 0.42
    assert attributes["window_manager"]["window_state"] == "off"
    assert attributes["configuration"]["type"] == "over_switch"


def test_identity_keys_are_off_by_default() -> None:
    """Identity flags and specific states would enable dead VTherm controls."""
    attributes = build_vt_display_attributes([OVER_SWITCH])

    assert "is_power_configured" not in attributes
    assert "is_window_configured" not in attributes
    assert "specific_states" not in attributes


def test_identity_keys_can_be_enabled() -> None:
    """The opt-in keeps the previous VTherm-compatible attribute set."""
    attributes = build_vt_display_attributes([OVER_SWITCH], include_identity=True)

    assert attributes["is_window_configured"] is True
    assert attributes["is_power_configured"] is False
    assert attributes["specific_states"] == {
        "messages": ["target_temp_window_eco"],
        "hvac_mode_reason": "hvac_off_window_detection",
    }


def test_lock_is_never_forwarded() -> None:
    """Exposing the lock would show a card button that cannot work."""
    for include_identity in (False, True):
        attributes = build_vt_display_attributes(
            [OVER_SWITCH], include_identity=include_identity
        )

        assert "is_lock_configured" not in attributes
        assert "lock_manager" not in attributes
        assert "is_locked" not in attributes.get("specific_states", {})


def test_boost_prefers_the_target_with_a_percentage() -> None:
    """With both targets active, the regulation percentage wins."""
    attributes = build_vt_display_attributes([OVER_CLIMATE, OVER_SWITCH])

    assert attributes["is_over_switch"] is True
    assert "is_over_climate" not in attributes
    assert attributes["power_percent"] == 42


def test_climate_only_target_has_no_power_gauge() -> None:
    """An over_climate target has no regulation percentage."""
    attributes = build_vt_display_attributes([OVER_CLIMATE])

    assert attributes["is_over_climate"] is True
    assert "power_percent" not in attributes
    assert "is_over_switch" not in attributes


def test_missing_vtherm_attributes_return_empty() -> None:
    """A plain climate entity produces no VTherm extras."""
    assert build_vt_display_attributes([{"current_temperature": 21.0}]) == {}
