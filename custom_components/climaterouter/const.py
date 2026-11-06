"""Constants for the ClimateRouter integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "climaterouter"
NAME: Final = "ClimateRouter"
VERSION: Final = "0.2.0"

PLATFORMS: Final = [
    Platform.CLIMATE,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
]

# Configuration keys.
CONF_NAME: Final = "name"
CONF_RADIATOR_ENTITY_ID: Final = "radiator_entity_id"
CONF_AC_ENTITY_ID: Final = "ac_entity_id"
CONF_OUTDOOR_SENSOR_ENTITY_ID: Final = "outdoor_sensor_entity_id"
CONF_MANUAL_SWITCH_ENTITY_ID: Final = "manual_switch_entity_id"
CONF_MANUAL_SWITCH_ON_TARGET: Final = "manual_switch_on_target"
CONF_COLD_THRESHOLD: Final = "cold_threshold"
CONF_MILD_THRESHOLD: Final = "mild_threshold"
CONF_MIN_ROUTE_DWELL: Final = "min_route_dwell"
CONF_HANDOVER_IDLE_CONFIRM: Final = "handover_idle_confirm"
CONF_OFF_CONFIRM_TIMEOUT: Final = "off_confirm_timeout"
CONF_STARTUP_GRACE: Final = "startup_grace"
CONF_SETTLE_TIME: Final = "settle_time"
CONF_CONFLICT_POLICY: Final = "conflict_policy"
CONF_AUTO_RESOLVE_IDLE_TARGETS: Final = "auto_resolve_idle_targets"
CONF_AUTO_RESOLVE_SIMULTANEOUS: Final = "auto_resolve_simultaneous"
CONF_FALLBACK_ON_UNAVAILABLE: Final = "fallback_on_unavailable"
CONF_OUTDOOR_STALE_AFTER: Final = "outdoor_stale_after"
CONF_DEFAULT_OVERRIDE_MINUTES: Final = "default_override_minutes"
CONF_MAX_OVERRIDE_MINUTES: Final = "max_override_minutes"
CONF_TEMPERATURE_TOLERANCE: Final = "temperature_tolerance"
CONF_BOOST_ENABLED: Final = "boost_enabled"

CONFLICT_POLICIES: Final = ["monitor", "reassert", "adopt"]

# Services.
SERVICE_RECALCULATE: Final = "recalculate"
SERVICE_SET_ROUTE_OVERRIDE: Final = "set_route_override"
SERVICE_CLEAR_ROUTE_OVERRIDE: Final = "clear_route_override"
SERVICE_CLEAR_CONFLICTS: Final = "clear_conflicts"
SERVICE_SET_MANUAL_OVERRIDE: Final = "set_manual_override"
SERVICE_CANCEL_MANUAL_OVERRIDE: Final = "cancel_manual_override"

# Events.
EVENT_ROUTE_CHANGED: Final = f"{DOMAIN}_route_changed"
EVENT_HANDOVER_STARTED: Final = f"{DOMAIN}_handover_started"
EVENT_HANDOVER_COMPLETED: Final = f"{DOMAIN}_handover_completed"
EVENT_HANDOVER_ABORTED: Final = f"{DOMAIN}_handover_aborted"
EVENT_OVERRIDE_STARTED: Final = f"{DOMAIN}_override_started"
EVENT_OVERRIDE_ENDED: Final = f"{DOMAIN}_override_ended"
EVENT_CONFLICT_DETECTED: Final = f"{DOMAIN}_conflict_detected"
EVENT_CONFLICT_CLEARED: Final = f"{DOMAIN}_conflict_cleared"
EVENT_BOOST_STARTED: Final = f"{DOMAIN}_boost_started"
EVENT_BOOST_ENDED: Final = f"{DOMAIN}_boost_ended"

# Storage.
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}.{{entry_id}}"

# Internal timings that are not user-configurable.
WATCHDOG_INTERVAL: Final = 30
CONTEXT_TTL: Final = 30

ATTR_ACTIVE_TARGET: Final = "active_target"
ATTR_PENDING_TARGET: Final = "pending_target"
ATTR_ROUTE_REASON: Final = "route_reason"
ATTR_HANDOVER_STATE: Final = "handover_state"
