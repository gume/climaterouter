"""Constants for the ClimateRouter integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "climaterouter"
NAME: Final = "ClimateRouter"
VERSION: Final = "0.10.1"

PLATFORMS: Final = [
    Platform.CLIMATE,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.LOCK,
    Platform.SWITCH,
]

# Configuration keys.
CONF_NAME: Final = "name"
CONF_RADIATOR_ENTITY_ID: Final = "radiator_entity_id"
CONF_AC_ENTITY_ID: Final = "ac_entity_id"
CONF_OUTDOOR_SENSOR_ENTITY_ID: Final = "outdoor_sensor_entity_id"
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
CONF_DEFAULT_MANUAL_MINUTES: Final = "default_manual_minutes"
CONF_MAX_MANUAL_MINUTES: Final = "max_manual_minutes"
CONF_TEMPERATURE_TOLERANCE: Final = "temperature_tolerance"
CONF_BOOST_ENABLED: Final = "boost_enabled"
CONF_LOCK_ENABLED: Final = "lock_enabled"
CONF_LOCK_CODE: Final = "lock_code"
CONF_AUTO_RELOCK_SEC: Final = "auto_relock_sec"
CONF_EXPOSE_VTHERM_IDENTITY: Final = "expose_vtherm_identity"
CONF_VELAIR_ENABLED: Final = "velair_enabled"
CONF_AC_IDLE_BYPASS_ENABLED: Final = "ac_idle_bypass_enabled"
CONF_AC_IDLE_BYPASS_ENTITY_ID: Final = "ac_idle_bypass_entity_id"
CONF_AC_IDLE_BYPASS_PRESET: Final = "ac_idle_bypass_preset"
CONF_SCHEDULER_PAUSE_SWITCH_ENTITY_ID: Final = "scheduler_pause_switch_entity_id"
CONF_SCHEDULER_PAUSE_SWITCH_INVERT: Final = "scheduler_pause_switch_invert"

CONFLICT_POLICIES: Final = ["monitor", "reassert", "adopt"]

# Services.
SERVICE_RECALCULATE: Final = "recalculate"
SERVICE_SET_ROUTE_OVERRIDE: Final = "set_route_override"
SERVICE_CLEAR_ROUTE_OVERRIDE: Final = "clear_route_override"
SERVICE_CLEAR_CONFLICTS: Final = "clear_conflicts"
SERVICE_FORCE_HANDOVER: Final = "force_handover"
SERVICE_SET_MANUAL_OVERRIDE: Final = "set_manual_override"
SERVICE_CANCEL_MANUAL_OVERRIDE: Final = "cancel_manual_override"
SERVICE_ENTER_MANUAL_MODE: Final = "enter_manual_mode"
SERVICE_SET_MANUAL_TIMER: Final = "set_manual_timer"
SERVICE_RETURN_TO_SCHEDULE: Final = "return_to_schedule"
SERVICE_SET_BOOST: Final = "set_boost"
SERVICE_CANCEL_BOOST: Final = "cancel_boost"
SERVICE_LOCK: Final = "lock"
SERVICE_UNLOCK: Final = "unlock"

# Events.
EVENT_ROUTE_CHANGED: Final = f"{DOMAIN}_route_changed"
EVENT_HANDOVER_STARTED: Final = f"{DOMAIN}_handover_started"
EVENT_HANDOVER_COMPLETED: Final = f"{DOMAIN}_handover_completed"
EVENT_HANDOVER_ABORTED: Final = f"{DOMAIN}_handover_aborted"
EVENT_OVERRIDE_STARTED: Final = f"{DOMAIN}_override_started"
EVENT_OVERRIDE_ENDED: Final = f"{DOMAIN}_override_ended"
EVENT_MANUAL_MODE_STARTED: Final = f"{DOMAIN}_manual_mode_started"
EVENT_MANUAL_MODE_ENDED: Final = f"{DOMAIN}_manual_mode_ended"
EVENT_MANUAL_TIMER_CHANGED: Final = f"{DOMAIN}_manual_timer_changed"
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
CONFLICT_CLEAR_AFTER: Final = 60
CONFLICT_REASSERT_GRACE: Final = 15

ATTR_ACTIVE_TARGET: Final = "active_target"
ATTR_PENDING_TARGET: Final = "pending_target"
ATTR_ROUTE_REASON: Final = "route_reason"
ATTR_HANDOVER_STATE: Final = "handover_state"
