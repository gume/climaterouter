"""Pure routing, hysteresis, and comparison helpers."""

from __future__ import annotations

from datetime import datetime

from .models import (
    HVAC_COOL,
    HVAC_OFF,
    ROUTE_AC,
    ROUTE_AUTO,
    ROUTE_RADIATOR,
    RouteDecision,
    RouteInputs,
    Target,
    TargetCapability,
)


def choose_route(inputs: RouteInputs) -> RouteDecision:
    """Choose the target(s) for the current inputs.

    Precedence (PLAN.md section 7.2): off, cool, route override, manual switch,
    outdoor hysteresis, stale fallback, then capability fallback.
    """
    if inputs.hvac_mode == HVAC_OFF:
        return RouteDecision(frozenset(), "off")

    if inputs.hvac_mode == HVAC_COOL:
        return _with_capability(
            frozenset({Target.AC}), "hvac_mode_cool", inputs, explicit_cool=True
        )

    if inputs.boost_active:
        return _with_capability(frozenset({Target.RADIATOR, Target.AC}), "boost", inputs)

    if inputs.route_override == ROUTE_RADIATOR:
        return _with_capability(frozenset({Target.RADIATOR}), "manual_route", inputs)
    if inputs.route_override == ROUTE_AC:
        return _with_capability(frozenset({Target.AC}), "manual_route", inputs)

    if inputs.manual_switch == "on":
        return _with_capability(
            frozenset({inputs.manual_switch_on_target}), "manual_switch", inputs
        )

    if inputs.outdoor_temperature is None or not inputs.outdoor_fresh:
        fallback = inputs.current_target or Target.RADIATOR
        return _with_capability(frozenset({fallback}), "fallback_outdoor", inputs)

    temperature = inputs.outdoor_temperature

    if inputs.current_target is Target.AC:
        if temperature > inputs.cold_threshold:
            return _with_capability(frozenset({Target.AC}), "hysteresis", inputs)
        return _with_capability(frozenset({Target.RADIATOR}), "hysteresis", inputs)

    if inputs.current_target is Target.RADIATOR:
        if temperature <= inputs.mild_threshold:
            return _with_capability(frozenset({Target.RADIATOR}), "hysteresis", inputs)
        return _with_capability(frozenset({Target.AC}), "hysteresis", inputs)

    if temperature > inputs.mild_threshold:
        return _with_capability(frozenset({Target.AC}), "outdoor_mild", inputs)
    if temperature <= inputs.cold_threshold:
        return _with_capability(frozenset({Target.RADIATOR}), "outdoor_cold", inputs)
    return _with_capability(frozenset({Target.RADIATOR}), "deadband_default", inputs)


def _with_capability(
    targets: frozenset[Target],
    reason: str,
    inputs: RouteInputs,
    *,
    explicit_cool: bool = False,
) -> RouteDecision:
    """Apply availability and mode capability fallback to a route decision."""
    if not targets:
        return RouteDecision(targets, reason)

    mode = inputs.hvac_mode
    if explicit_cool:
        mode = HVAC_COOL

    resolved: set[Target] = set()
    used_fallback = False

    for target in targets:
        capability = inputs.capabilities.get(target)
        if _can_serve(capability, mode):
            resolved.add(target)
            continue

        if not inputs.fallback_on_unavailable:
            continue

        other = target.other
        other_capability = inputs.capabilities.get(other)
        if _can_serve(other_capability, mode):
            resolved.add(other)
            used_fallback = True

    if not resolved:
        return RouteDecision(frozenset(), "unsupported_mode" if explicit_cool else "unavailable")

    if used_fallback:
        return RouteDecision(frozenset(resolved), "fallback_unavailable")

    return RouteDecision(frozenset(resolved), reason)


def _can_serve(capability: TargetCapability | None, mode: str | None) -> bool:
    """Return whether a target is available and supports the mode."""
    if capability is None or not capability.available:
        return False
    return capability.can_handle(mode)


def override_is_expired(until: datetime, now: datetime) -> bool:
    """Return whether an override deadline has passed."""
    return now >= until


def setpoint_differs(expected: float | None, actual: float | None, tolerance: float) -> bool:
    """Return whether two temperatures differ beyond the tolerance."""
    if expected is None or actual is None:
        return expected is not actual
    return abs(expected - actual) > tolerance


def values_differ(expected: object, actual: object) -> bool:
    """Return whether two plain values differ."""
    return expected != actual


def normalize_manual_select(value: str | None) -> str | None:
    """Map an input_select state to the router's manual switch language."""
    if value in (ROUTE_AUTO, ROUTE_RADIATOR, ROUTE_AC):
        return value
    return None
