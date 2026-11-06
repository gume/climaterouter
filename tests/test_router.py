"""Unit tests for the pure routing layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from climaterouter.models import (
    RouteInputs,
    Target,
    TargetCapability,
)
from climaterouter.router import (
    choose_route,
    override_is_expired,
    setpoint_differs,
)


def _capabilities(
    *,
    radiator_available: bool = True,
    ac_available: bool = True,
    ac_can_cool: bool = True,
) -> dict[Target, TargetCapability]:
    return {
        Target.RADIATOR: TargetCapability(
            available=radiator_available,
            hvac_modes=frozenset({"off", "heat"}),
        ),
        Target.AC: TargetCapability(
            available=ac_available,
            hvac_modes=frozenset({"off", "heat", "cool"} if ac_can_cool else {"off", "heat"}),
        ),
    }


def _inputs(**overrides) -> RouteInputs:
    values = {
        "hvac_mode": "heat",
        "route_override": "auto",
        "manual_switch": "off",
        "manual_switch_on_target": Target.AC,
        "outdoor_temperature": 10.0,
        "outdoor_fresh": True,
        "current_target": None,
        "capabilities": _capabilities(),
        "cold_threshold": 7.0,
        "mild_threshold": 9.0,
        "fallback_on_unavailable": True,
    }
    values.update(overrides)
    return RouteInputs(**values)


def _targets(decision) -> set[Target]:
    return set(decision.targets)


def test_route_ac_above_mild() -> None:
    decision = choose_route(_inputs(outdoor_temperature=10.0))
    assert _targets(decision) == {Target.AC}
    assert decision.reason == "outdoor_mild"


def test_route_radiator_at_or_below_cold() -> None:
    decision = choose_route(_inputs(outdoor_temperature=7.0))
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "outdoor_cold"


def test_route_deadband_no_history() -> None:
    decision = choose_route(_inputs(outdoor_temperature=8.0))
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "deadband_default"


def test_route_deadband_holds_ac() -> None:
    decision = choose_route(_inputs(outdoor_temperature=8.0, current_target=Target.AC))
    assert _targets(decision) == {Target.AC}
    assert decision.reason == "hysteresis"


def test_route_deadband_holds_radiator() -> None:
    decision = choose_route(_inputs(outdoor_temperature=8.0, current_target=Target.RADIATOR))
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "hysteresis"


def test_route_ac_to_radiator_at_cold() -> None:
    decision = choose_route(_inputs(outdoor_temperature=6.0, current_target=Target.AC))
    assert _targets(decision) == {Target.RADIATOR}


def test_route_radiator_to_ac_above_mild() -> None:
    decision = choose_route(_inputs(outdoor_temperature=10.0, current_target=Target.RADIATOR))
    assert _targets(decision) == {Target.AC}


def test_route_manual_switch_forces_ac() -> None:
    decision = choose_route(_inputs(manual_switch="on", outdoor_temperature=0.0))
    assert _targets(decision) == {Target.AC}
    assert decision.reason == "manual_switch"


def test_route_manual_switch_forces_radiator() -> None:
    decision = choose_route(
        _inputs(
            manual_switch="on",
            manual_switch_on_target=Target.RADIATOR,
            outdoor_temperature=20.0,
        )
    )
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "manual_switch"


def test_route_override_beats_switch() -> None:
    decision = choose_route(_inputs(route_override="radiator", manual_switch="on"))
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "manual_route"


def test_route_cool_forces_ac() -> None:
    decision = choose_route(_inputs(hvac_mode="cool", outdoor_temperature=0.0))
    assert _targets(decision) == {Target.AC}
    assert decision.reason == "hvac_mode_cool"


def test_route_off_wins() -> None:
    decision = choose_route(_inputs(hvac_mode="off", manual_switch="on"))
    assert _targets(decision) == set()
    assert decision.reason == "off"


def test_route_outdoor_stale_holds_last() -> None:
    decision = choose_route(_inputs(outdoor_fresh=False, current_target=Target.AC))
    assert _targets(decision) == {Target.AC}
    assert decision.reason == "fallback_outdoor"


def test_route_outdoor_stale_no_history() -> None:
    decision = choose_route(
        _inputs(outdoor_temperature=None, outdoor_fresh=False, current_target=None)
    )
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "fallback_outdoor"


def test_route_unavailable_target_fallback() -> None:
    decision = choose_route(
        _inputs(
            outdoor_temperature=10.0,
            capabilities=_capabilities(ac_available=False),
        )
    )
    assert _targets(decision) == {Target.RADIATOR}
    assert decision.reason == "fallback_unavailable"


def test_route_unavailable_no_fallback() -> None:
    decision = choose_route(
        _inputs(
            outdoor_temperature=10.0,
            capabilities=_capabilities(ac_available=False),
            fallback_on_unavailable=False,
        )
    )
    assert _targets(decision) == set()


def test_route_cool_unsupported() -> None:
    decision = choose_route(
        _inputs(
            hvac_mode="cool",
            capabilities=_capabilities(ac_can_cool=False),
        )
    )
    assert _targets(decision) == set()
    assert decision.reason == "unsupported_mode"


def test_boost_targets_both() -> None:
    decision = choose_route(_inputs(boost_active=True))
    assert _targets(decision) == {Target.RADIATOR, Target.AC}
    assert decision.reason == "boost"


def test_override_expiry_helper() -> None:
    now = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)  # noqa: UP017
    assert override_is_expired(now - timedelta(seconds=1), now)
    assert not override_is_expired(now + timedelta(minutes=1), now)


def test_setpoint_differs_tolerance() -> None:
    assert not setpoint_differs(21.0, 21.1, 0.2)
    assert setpoint_differs(21.0, 21.5, 0.2)
    assert setpoint_differs(21.0, None, 0.2)
