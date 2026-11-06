"""Read-only Versatile Thermostat attributes for Lovelace cards.

ClimateRouter is a proxy, so cards such as Equinox only render the
Versatile Thermostat (VTherm) extras when the proxy exposes part of VTherm's
attribute structure. This module builds a small, read-only subset from the
currently active target(s), which keeps indicators such as the power/valve
percentage and the window/presence/safety messages useful without turning the
proxy into a second VTherm.

The lock feature is deliberately **not** forwarded. Equinox implements its lock
button by calling ``versatile_thermostat.lock``/``unlock`` on the card entity.
Those services only work on real VTherm platform entities, so exposing
``is_lock_configured`` on the proxy would show a button that always fails.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_SIMPLE_KEYS = (
    "is_over_switch",
    "is_over_valve",
    "is_over_climate",
    "power_percent",
    "valve_open_percent",
    "on_percent",
    "is_power_configured",
    "is_presence_configured",
    "is_motion_configured",
    "is_window_configured",
    "is_window_auto_configured",
    "is_safety_configured",
    "is_heating_failure_detection_configured",
    "is_repair_incorrect_state_configured",
)

_MANAGER_KEYS = (
    "power_manager",
    "presence_manager",
    "window_manager",
    "safety_manager",
    "heating_failure_detection_manager",
)

_CONFIGURATION_KEYS = ("type", "have_valve_regulation", "proportional_function")

_SPECIFIC_STATE_KEYS = ("messages", "hvac_mode_reason", "hvac_off_reason")

_VALVE_KEYS = ("valve_open_percent", "on_percent", "function")

_VALVE_REGULATION_KEYS = ("power_percent", "valve_open_percent", "function")


def _is_number(value: Any) -> bool:
    """Return whether a value is a real number (booleans excluded)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_dict(value: Any) -> dict[str, Any] | None:
    """Return a plain dict for a mapping-like attribute value."""
    if not isinstance(value, Mapping):
        return None
    return dict(value)


def _copy_mapping(source: Mapping[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    """Copy the selected keys that exist in ``source``."""
    return {key: source[key] for key in keys if key in source}


def _score(attributes: Mapping[str, Any]) -> int:
    """Rank a target by how useful its VTherm display attributes are."""
    if _is_number(attributes.get("valve_open_percent")):
        return 3
    if _is_number(attributes.get("power_percent")):
        return 2
    if attributes.get("is_over_switch") or attributes.get("is_over_valve"):
        return 1
    return 0


def build_vt_display_attributes(
    active_attributes: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the read-only VTherm attributes shown by the proxy.

    ``active_attributes`` contains the Home Assistant attribute mappings of the
    currently active targets. When two targets are active (boost), the one with
    the most useful regulation information wins, so the power gauge reflects the
    device that actually reports a percentage.
    """
    candidates = list(active_attributes)
    if not candidates:
        return {}

    # ``max`` is stable and returns the first candidate on a tie.
    primary = max(candidates, key=_score)
    result: dict[str, Any] = {}

    for key in _SIMPLE_KEYS:
        if key in primary:
            result[key] = primary[key]

    for key in _MANAGER_KEYS:
        if (manager := _as_dict(primary.get(key))) is not None:
            result[key] = manager

    if (configuration := _as_dict(primary.get("configuration"))) is not None:
        result["configuration"] = _copy_mapping(configuration, _CONFIGURATION_KEYS)

    if (specific_states := _as_dict(primary.get("specific_states"))) is not None:
        # ``is_locked`` is intentionally omitted: the proxy has no lock command
        # that Equinox could call, and a locked-looking card could not be
        # unlocked from the same UI.
        curated = _copy_mapping(specific_states, _SPECIFIC_STATE_KEYS)
        if curated:
            result["specific_states"] = curated

    if (over_valve := _as_dict(primary.get("vtherm_over_valve"))) is not None:
        result["vtherm_over_valve"] = _copy_mapping(over_valve, _VALVE_KEYS)

    if (
        over_climate_valve := _as_dict(primary.get("vtherm_over_climate_valve"))
    ) is not None:
        curated_valve: dict[str, Any] = {
            "have_valve_regulation": bool(over_climate_valve.get("have_valve_regulation"))
        }
        if (regulation := _as_dict(over_climate_valve.get("valve_regulation"))) is not None:
            curated_valve["valve_regulation"] = _copy_mapping(
                regulation, _VALVE_REGULATION_KEYS
            )
        result["vtherm_over_climate_valve"] = curated_valve

    return result
