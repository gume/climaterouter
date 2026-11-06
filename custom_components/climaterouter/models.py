"""Domain models for ClimateRouter.

This module is intentionally free of Home Assistant imports so the routing
logic can be unit-tested without a running Home Assistant instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

HVAC_OFF = "off"
HVAC_HEAT = "heat"
HVAC_COOL = "cool"

MODES = (HVAC_OFF, HVAC_HEAT, HVAC_COOL)

ROUTE_AUTO = "auto"
ROUTE_RADIATOR = "radiator"
ROUTE_AC = "ac"
ROUTE_BOTH = "both"


class Target(str, Enum):  # noqa: UP042
    """One of the two underlying climate entities."""

    RADIATOR = "radiator"
    AC = "ac"

    @property
    def other(self) -> Target:
        """Return the opposite target."""
        return Target.AC if self is Target.RADIATOR else Target.RADIATOR


class SetpointKind(str, Enum):  # noqa: UP042
    """Which kind of setpoint the desired state carries."""

    PRESET = "preset"
    TEMPERATURE = "temperature"
    NONE = "none"


class HandoverState(str, Enum):  # noqa: UP042
    """State of the handover state machine."""

    OFF = "off"
    STEADY = "steady"
    PENDING = "pending"
    STOPPING_OLD = "stopping_old"
    STARTING_NEW = "starting_new"
    CONFLICT = "conflict"
    BOOST = "boost"


@dataclass(frozen=True)
class TargetCapability:
    """What a target can do right now."""

    available: bool = False
    hvac_modes: frozenset[str] = frozenset()
    preset_modes: frozenset[str] = frozenset()

    def can_handle(self, hvac_mode: str | None) -> bool:
        """Return whether the target supports the requested mode."""
        if hvac_mode in (None, HVAC_OFF):
            return True
        return hvac_mode in self.hvac_modes


@dataclass(frozen=True)
class UnderlyingState:
    """Snapshot of one underlying climate entity."""

    entity_id: str = ""
    available: bool = False
    hvac_mode: str | None = None
    hvac_action: str | None = None
    preset_mode: str | None = None
    target_temperature: float | None = None
    current_temperature: float | None = None
    min_temp: float | None = None
    max_temp: float | None = None
    target_temp_step: float | None = None
    hvac_modes: tuple[str, ...] = ()
    preset_modes: tuple[str, ...] = ()
    last_updated: datetime | None = None
    guard: str | None = None
    timed_preset_active: bool = False

    @property
    def is_off(self) -> bool:
        """Return whether the entity is explicitly off."""
        return self.hvac_mode == HVAC_OFF

    @property
    def is_active(self) -> bool:
        """Return whether the target is actively heating or cooling.

        An unknown action is treated as active so a handover never interrupts
        a cycle whose state we cannot see.
        """
        if self.hvac_mode in (None, HVAC_OFF):
            return False
        return self.hvac_action in (None, "heating", "cooling")

    @property
    def capability(self) -> TargetCapability:
        """Build the capability object for this state."""
        return TargetCapability(
            available=self.available,
            hvac_modes=frozenset(self.hvac_modes),
            preset_modes=frozenset(self.preset_modes),
        )


@dataclass
class DesiredState:
    """The latest command received through the proxy."""

    hvac_mode: str | None = None
    setpoint_kind: SetpointKind = SetpointKind.NONE
    preset_mode: str | None = None
    target_temperature: float | None = None
    fan_mode: str | None = None
    swing_mode: str | None = None

    @property
    def is_empty(self) -> bool:
        """Return whether no command has been received yet."""
        return self.hvac_mode is None and self.setpoint_kind == SetpointKind.NONE

    def copy(self) -> DesiredState:
        """Return an independent copy of this desired state."""
        return DesiredState(
            hvac_mode=self.hvac_mode,
            setpoint_kind=self.setpoint_kind,
            preset_mode=self.preset_mode,
            target_temperature=self.target_temperature,
            fan_mode=self.fan_mode,
            swing_mode=self.swing_mode,
        )

    def with_override(self, override: OverrideState | None) -> DesiredState:
        """Return a copy with an active manual override applied.

        The override value wins over the stored baseline. ``hvac_mode``
        overrides only change the mode and keep the baseline setpoint.
        """
        result = self.copy()
        if override is None:
            return result

        if override.kind == "temperature":
            result.setpoint_kind = SetpointKind.TEMPERATURE
            result.target_temperature = float(override.value)
            result.preset_mode = None
        elif override.kind == "preset":
            result.setpoint_kind = SetpointKind.PRESET
            result.preset_mode = str(override.value)
            result.target_temperature = None
        elif override.kind == "hvac_mode":
            result.hvac_mode = str(override.value)
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the store."""
        return {
            "hvac_mode": self.hvac_mode,
            "setpoint_kind": self.setpoint_kind.value,
            "preset_mode": self.preset_mode,
            "target_temperature": self.target_temperature,
            "fan_mode": self.fan_mode,
            "swing_mode": self.swing_mode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DesiredState:
        """Deserialize from the store."""
        kind = data.get("setpoint_kind", SetpointKind.NONE.value)
        try:
            setpoint_kind = SetpointKind(kind)
        except ValueError:
            setpoint_kind = SetpointKind.NONE
        return cls(
            hvac_mode=data.get("hvac_mode"),
            setpoint_kind=setpoint_kind,
            preset_mode=data.get("preset_mode"),
            target_temperature=data.get("target_temperature"),
            fan_mode=data.get("fan_mode"),
            swing_mode=data.get("swing_mode"),
        )


@dataclass
class OverrideState:
    """A bounded manual override."""

    kind: Literal["temperature", "preset", "hvac_mode"]
    value: Any
    until: datetime
    baseline: DesiredState
    started_at: datetime

    def is_expired(self, now: datetime) -> bool:
        """Return whether the absolute deadline has passed."""
        return now >= self.until

    def remaining_minutes(self, now: datetime) -> int:
        """Return the whole minutes left, rounded up for a useful countdown."""
        seconds = (self.until - now).total_seconds()
        if seconds <= 0:
            return 0
        return int((seconds + 59.9) // 60)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for the store."""
        return {
            "kind": self.kind,
            "value": self.value,
            "until": self.until.isoformat(),
            "started_at": self.started_at.isoformat(),
            "baseline": self.baseline.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverrideState | None:
        """Deserialize an override from the store, tolerating bad data."""
        kind = data.get("kind")
        if kind not in ("temperature", "preset", "hvac_mode"):
            return None
        try:
            until = datetime.fromisoformat(str(data["until"]))
            started_at = datetime.fromisoformat(str(data["started_at"]))
        except (KeyError, TypeError, ValueError):
            return None
        if until.tzinfo is None or started_at.tzinfo is None:
            return None
        baseline = data.get("baseline")
        return cls(
            kind=kind,
            value=data.get("value"),
            until=until,
            baseline=DesiredState.from_dict(baseline)
            if isinstance(baseline, dict)
            else DesiredState(),
            started_at=started_at,
        )


@dataclass(frozen=True)
class Conflict:
    """One detected divergence from the expected state."""

    key: str
    type: str
    target: Target | None
    expected: Any
    actual: Any
    first_seen: datetime
    last_seen: datetime
    source_guess: str = ""
    resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for events, attributes, and diagnostics."""
        return {
            "key": self.key,
            "type": self.type,
            "target": self.target.value if self.target else None,
            "expected": self.expected,
            "actual": self.actual,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "source_guess": self.source_guess,
            "resolved": self.resolved,
        }


@dataclass(frozen=True)
class RouterSnapshot:
    """Immutable view of the router, consumed by entities."""

    ready: bool = False
    available: bool = True
    active_targets: frozenset[Target] = frozenset()
    pending_target: Target | None = None
    route_reason: str = "off"
    handover_state: HandoverState = HandoverState.OFF
    desired: DesiredState = field(default_factory=DesiredState)
    override: OverrideState | None = None
    boost_until: datetime | None = None
    conflicts: tuple[Conflict, ...] = ()
    conflict_count: int = 0
    outdoor_temperature: float | None = None
    outdoor_stale: bool = True
    manual_switch_state: str | None = None
    manual_switch_stale: bool = False
    route_override: str = ROUTE_AUTO
    last_handover: datetime | None = None
    last_command: datetime | None = None
    targets: dict[Target, UnderlyingState] = field(default_factory=dict)
    hvac_modes: tuple[str, ...] = (HVAC_OFF, HVAC_HEAT)
    preset_modes: tuple[str, ...] = ("none",)
    min_temp: float = 7.0
    max_temp: float = 35.0
    target_temp_step: float = 0.5

    @property
    def active_target(self) -> Target | None:
        """Return the single active target, if exactly one is active."""
        if len(self.active_targets) == 1:
            return next(iter(self.active_targets))
        return None

    @property
    def active_label(self) -> str:
        """Return a human readable active target label."""
        if len(self.active_targets) > 1:
            return ROUTE_BOTH
        if self.active_targets:
            return next(iter(self.active_targets)).value
        return "none"


@dataclass(frozen=True)
class RouteDecision:
    """Result of the pure routing function."""

    targets: frozenset[Target]
    reason: str


@dataclass(frozen=True)
class RouteInputs:
    """All inputs needed by :func:`choose_route`."""

    hvac_mode: str | None
    route_override: str = ROUTE_AUTO
    manual_switch: str | None = None
    manual_switch_on_target: Target = Target.AC
    outdoor_temperature: float | None = None
    outdoor_fresh: bool = True
    current_target: Target | None = None
    capabilities: dict[Target, TargetCapability] = field(default_factory=dict)
    cold_threshold: float = 7.0
    mild_threshold: float = 9.0
    fallback_on_unavailable: bool = True
    boost_active: bool = False


DEFAULT_COLD_THRESHOLD = 7.0
DEFAULT_MILD_THRESHOLD = 9.0
DEFAULT_MIN_ROUTE_DWELL = 600
DEFAULT_HANDOVER_IDLE_CONFIRM = 30
DEFAULT_OFF_CONFIRM_TIMEOUT = 30
DEFAULT_STARTUP_GRACE = 10
DEFAULT_SETTLE_TIME = 10
DEFAULT_CONFLICT_POLICY = "monitor"
DEFAULT_OUTDOOR_STALE_AFTER = 3600
DEFAULT_OVERRIDE_MINUTES = 60
DEFAULT_MAX_OVERRIDE_MINUTES = 1440
DEFAULT_TEMPERATURE_TOLERANCE = 0.2


@dataclass(frozen=True)
class RouterConfig:
    """Validated configuration for one router entry."""

    name: str = "ClimateRouter"
    radiator_entity_id: str = ""
    ac_entity_id: str = ""
    outdoor_sensor_entity_id: str = ""
    manual_switch_entity_id: str | None = None
    manual_switch_on_target: Target = Target.AC
    cold_threshold: float = DEFAULT_COLD_THRESHOLD
    mild_threshold: float = DEFAULT_MILD_THRESHOLD
    min_route_dwell: int = DEFAULT_MIN_ROUTE_DWELL
    handover_idle_confirm: int = DEFAULT_HANDOVER_IDLE_CONFIRM
    off_confirm_timeout: int = DEFAULT_OFF_CONFIRM_TIMEOUT
    startup_grace: int = DEFAULT_STARTUP_GRACE
    settle_time: int = DEFAULT_SETTLE_TIME
    conflict_policy: str = DEFAULT_CONFLICT_POLICY
    auto_resolve_idle_targets: bool = True
    auto_resolve_simultaneous: bool = False
    fallback_on_unavailable: bool = True
    outdoor_stale_after: int = DEFAULT_OUTDOOR_STALE_AFTER
    default_override_minutes: int = DEFAULT_OVERRIDE_MINUTES
    max_override_minutes: int = DEFAULT_MAX_OVERRIDE_MINUTES
    temperature_tolerance: float = DEFAULT_TEMPERATURE_TOLERANCE
    boost_enabled: bool = False

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> RouterConfig:
        """Build a config from entry data merged with options."""
        target = str(data.get("manual_switch_on_target", Target.AC.value))

        def _float(key: str, default: float) -> float:
            try:
                return float(data.get(key, default))
            except (TypeError, ValueError):
                return default

        def _int(key: str, default: int) -> int:
            try:
                return int(data.get(key, default))
            except (TypeError, ValueError):
                return default

        def _bool(key: str, default: bool) -> bool:
            value = data.get(key, default)
            if isinstance(value, str):
                return value.lower() in ("1", "true", "yes", "on")
            return bool(value)

        manual = data.get("manual_switch_entity_id") or None
        return cls(
            name=str(data.get("name") or "ClimateRouter"),
            radiator_entity_id=str(data.get("radiator_entity_id") or ""),
            ac_entity_id=str(data.get("ac_entity_id") or ""),
            outdoor_sensor_entity_id=str(data.get("outdoor_sensor_entity_id") or ""),
            manual_switch_entity_id=str(manual) if manual else None,
            manual_switch_on_target=Target.RADIATOR
            if target == Target.RADIATOR.value
            else Target.AC,
            cold_threshold=_float("cold_threshold", DEFAULT_COLD_THRESHOLD),
            mild_threshold=_float("mild_threshold", DEFAULT_MILD_THRESHOLD),
            min_route_dwell=_int("min_route_dwell", DEFAULT_MIN_ROUTE_DWELL),
            handover_idle_confirm=_int("handover_idle_confirm", DEFAULT_HANDOVER_IDLE_CONFIRM),
            off_confirm_timeout=_int("off_confirm_timeout", DEFAULT_OFF_CONFIRM_TIMEOUT),
            startup_grace=_int("startup_grace", DEFAULT_STARTUP_GRACE),
            settle_time=_int("settle_time", DEFAULT_SETTLE_TIME),
            conflict_policy=str(data.get("conflict_policy", DEFAULT_CONFLICT_POLICY)),
            auto_resolve_idle_targets=_bool("auto_resolve_idle_targets", True),
            auto_resolve_simultaneous=_bool("auto_resolve_simultaneous", False),
            fallback_on_unavailable=_bool("fallback_on_unavailable", True),
            outdoor_stale_after=_int("outdoor_stale_after", DEFAULT_OUTDOOR_STALE_AFTER),
            default_override_minutes=_int("default_override_minutes", DEFAULT_OVERRIDE_MINUTES),
            max_override_minutes=_int("max_override_minutes", DEFAULT_MAX_OVERRIDE_MINUTES),
            temperature_tolerance=_float("temperature_tolerance", DEFAULT_TEMPERATURE_TOLERANCE),
            boost_enabled=_bool("boost_enabled", False),
        )
