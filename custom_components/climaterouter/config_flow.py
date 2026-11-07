"""Config, options, and reconfigure flows for ClimateRouter."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_AC_ENTITY_ID,
    CONF_AUTO_RELOCK_SEC,
    CONF_AUTO_RESOLVE_IDLE_TARGETS,
    CONF_AUTO_RESOLVE_SIMULTANEOUS,
    CONF_BOOST_ENABLED,
    CONF_COLD_THRESHOLD,
    CONF_CONFLICT_POLICY,
    CONF_DEFAULT_MANUAL_MINUTES,
    CONF_EXPOSE_VTHERM_IDENTITY,
    CONF_FALLBACK_ON_UNAVAILABLE,
    CONF_HANDOVER_IDLE_CONFIRM,
    CONF_LOCK_CODE,
    CONF_LOCK_ENABLED,
    CONF_MANUAL_BLOCKS_SCHEDULE,
    CONF_MAX_MANUAL_MINUTES,
    CONF_MILD_THRESHOLD,
    CONF_MIN_ROUTE_DWELL,
    CONF_NAME,
    CONF_OFF_CONFIRM_TIMEOUT,
    CONF_OUTDOOR_SENSOR_ENTITY_ID,
    CONF_OUTDOOR_STALE_AFTER,
    CONF_RADIATOR_ENTITY_ID,
    CONF_SETTLE_TIME,
    CONF_STARTUP_GRACE,
    CONF_TEMPERATURE_TOLERANCE,
    CONFLICT_POLICIES,
    DOMAIN,
)
from .models import (
    DEFAULT_AUTO_RELOCK_SEC,
    DEFAULT_COLD_THRESHOLD,
    DEFAULT_CONFLICT_POLICY,
    DEFAULT_HANDOVER_IDLE_CONFIRM,
    DEFAULT_MANUAL_MINUTES,
    DEFAULT_MAX_MANUAL_MINUTES,
    DEFAULT_MILD_THRESHOLD,
    DEFAULT_MIN_ROUTE_DWELL,
    DEFAULT_OFF_CONFIRM_TIMEOUT,
    DEFAULT_OUTDOOR_STALE_AFTER,
    DEFAULT_SETTLE_TIME,
    DEFAULT_STARTUP_GRACE,
    DEFAULT_TEMPERATURE_TOLERANCE,
)

SECTION_BASIC = "basic"
SECTION_ROUTING = "routing"
SECTION_MANUAL = "manual"
SECTION_CONFLICTS = "conflicts"
SECTION_BOOST = "boost"
SECTION_LOCK = "lock"
SECTION_DISPLAY = "display"

OPTION_MENU = [
    SECTION_BASIC,
    SECTION_ROUTING,
    SECTION_MANUAL,
    SECTION_CONFLICTS,
    SECTION_BOOST,
    SECTION_LOCK,
    SECTION_DISPLAY,
    "finish",
]


def _defaults(current: Mapping[str, Any] | None = None) -> dict[str, Any]:
    current = current or {}
    return {
        CONF_NAME: current.get(CONF_NAME, "ClimateRouter"),
        CONF_RADIATOR_ENTITY_ID: current.get(CONF_RADIATOR_ENTITY_ID, vol.UNDEFINED),
        CONF_AC_ENTITY_ID: current.get(CONF_AC_ENTITY_ID, vol.UNDEFINED),
        CONF_OUTDOOR_SENSOR_ENTITY_ID: current.get(
            CONF_OUTDOOR_SENSOR_ENTITY_ID, vol.UNDEFINED
        ),
        CONF_COLD_THRESHOLD: current.get(CONF_COLD_THRESHOLD, DEFAULT_COLD_THRESHOLD),
        CONF_MILD_THRESHOLD: current.get(CONF_MILD_THRESHOLD, DEFAULT_MILD_THRESHOLD),
        CONF_MIN_ROUTE_DWELL: current.get(CONF_MIN_ROUTE_DWELL, DEFAULT_MIN_ROUTE_DWELL),
        CONF_HANDOVER_IDLE_CONFIRM: current.get(
            CONF_HANDOVER_IDLE_CONFIRM, DEFAULT_HANDOVER_IDLE_CONFIRM
        ),
        CONF_OFF_CONFIRM_TIMEOUT: current.get(
            CONF_OFF_CONFIRM_TIMEOUT, DEFAULT_OFF_CONFIRM_TIMEOUT
        ),
        CONF_STARTUP_GRACE: current.get(CONF_STARTUP_GRACE, DEFAULT_STARTUP_GRACE),
        CONF_SETTLE_TIME: current.get(CONF_SETTLE_TIME, DEFAULT_SETTLE_TIME),
        CONF_CONFLICT_POLICY: current.get(CONF_CONFLICT_POLICY, DEFAULT_CONFLICT_POLICY),
        CONF_AUTO_RESOLVE_IDLE_TARGETS: current.get(CONF_AUTO_RESOLVE_IDLE_TARGETS, True),
        CONF_AUTO_RESOLVE_SIMULTANEOUS: current.get(CONF_AUTO_RESOLVE_SIMULTANEOUS, False),
        CONF_FALLBACK_ON_UNAVAILABLE: current.get(CONF_FALLBACK_ON_UNAVAILABLE, True),
        CONF_OUTDOOR_STALE_AFTER: current.get(
            CONF_OUTDOOR_STALE_AFTER, DEFAULT_OUTDOOR_STALE_AFTER
        ),
        CONF_DEFAULT_MANUAL_MINUTES: current.get(
            CONF_DEFAULT_MANUAL_MINUTES,
            current.get("default_override_minutes", DEFAULT_MANUAL_MINUTES),
        ),
        CONF_MAX_MANUAL_MINUTES: current.get(
            CONF_MAX_MANUAL_MINUTES,
            current.get("max_override_minutes", DEFAULT_MAX_MANUAL_MINUTES),
        ),
        CONF_MANUAL_BLOCKS_SCHEDULE: current.get(CONF_MANUAL_BLOCKS_SCHEDULE, True),
        CONF_TEMPERATURE_TOLERANCE: current.get(
            CONF_TEMPERATURE_TOLERANCE, DEFAULT_TEMPERATURE_TOLERANCE
        ),
        CONF_BOOST_ENABLED: current.get(CONF_BOOST_ENABLED, False),
        CONF_LOCK_ENABLED: current.get(CONF_LOCK_ENABLED, False),
        CONF_LOCK_CODE: current.get(CONF_LOCK_CODE, ""),
        CONF_AUTO_RELOCK_SEC: current.get(CONF_AUTO_RELOCK_SEC, DEFAULT_AUTO_RELOCK_SEC),
        CONF_EXPOSE_VTHERM_IDENTITY: current.get(CONF_EXPOSE_VTHERM_IDENTITY, False),
    }


def _number(
    minimum: float, maximum: float, step: float, unit: str | None = None
) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _basic_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults[CONF_NAME]): cv.string,
            vol.Required(
                CONF_RADIATOR_ENTITY_ID, default=defaults[CONF_RADIATOR_ENTITY_ID]
            ): EntitySelector(EntitySelectorConfig(domain="climate")),
            vol.Required(
                CONF_AC_ENTITY_ID, default=defaults[CONF_AC_ENTITY_ID]
            ): EntitySelector(EntitySelectorConfig(domain="climate")),
            vol.Required(
                CONF_OUTDOOR_SENSOR_ENTITY_ID,
                default=defaults[CONF_OUTDOOR_SENSOR_ENTITY_ID],
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
        }
    )


def _routing_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_COLD_THRESHOLD, default=defaults[CONF_COLD_THRESHOLD]
            ): _number(-50, 60, 0.5, "°C"),
            vol.Required(
                CONF_MILD_THRESHOLD, default=defaults[CONF_MILD_THRESHOLD]
            ): _number(-50, 60, 0.5, "°C"),
            vol.Required(
                CONF_MIN_ROUTE_DWELL, default=defaults[CONF_MIN_ROUTE_DWELL]
            ): _number(0, 86400, 10, "s"),
            vol.Required(
                CONF_HANDOVER_IDLE_CONFIRM,
                default=defaults[CONF_HANDOVER_IDLE_CONFIRM],
            ): _number(0, 3600, 1, "s"),
            vol.Required(
                CONF_OFF_CONFIRM_TIMEOUT, default=defaults[CONF_OFF_CONFIRM_TIMEOUT]
            ): _number(1, 3600, 1, "s"),
            vol.Required(
                CONF_STARTUP_GRACE, default=defaults[CONF_STARTUP_GRACE]
            ): _number(0, 600, 1, "s"),
            vol.Required(
                CONF_SETTLE_TIME, default=defaults[CONF_SETTLE_TIME]
            ): _number(0, 600, 1, "s"),
            vol.Required(
                CONF_FALLBACK_ON_UNAVAILABLE,
                default=defaults[CONF_FALLBACK_ON_UNAVAILABLE],
            ): BooleanSelector(),
        }
    )


def _manual_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DEFAULT_MANUAL_MINUTES,
                default=defaults[CONF_DEFAULT_MANUAL_MINUTES],
            ): _number(0, 1440, 1, "min"),
            vol.Required(
                CONF_MAX_MANUAL_MINUTES,
                default=defaults[CONF_MAX_MANUAL_MINUTES],
            ): _number(1, 1440, 1, "min"),
            vol.Required(
                CONF_MANUAL_BLOCKS_SCHEDULE,
                default=defaults[CONF_MANUAL_BLOCKS_SCHEDULE],
            ): BooleanSelector(),
        }
    )


def _conflicts_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_CONFLICT_POLICY, default=defaults[CONF_CONFLICT_POLICY]
            ): SelectSelector(
                SelectSelectorConfig(
                    options=CONFLICT_POLICIES,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_AUTO_RESOLVE_IDLE_TARGETS,
                default=defaults[CONF_AUTO_RESOLVE_IDLE_TARGETS],
            ): BooleanSelector(),
            vol.Required(
                CONF_AUTO_RESOLVE_SIMULTANEOUS,
                default=defaults[CONF_AUTO_RESOLVE_SIMULTANEOUS],
            ): BooleanSelector(),
            vol.Required(
                CONF_OUTDOOR_STALE_AFTER,
                default=defaults[CONF_OUTDOOR_STALE_AFTER],
            ): _number(60, 86400, 60, "s"),
            vol.Required(
                CONF_TEMPERATURE_TOLERANCE,
                default=defaults[CONF_TEMPERATURE_TOLERANCE],
            ): _number(0.05, 5, 0.05, "°C"),
        }
    )


def _boost_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_BOOST_ENABLED, default=defaults[CONF_BOOST_ENABLED]
            ): BooleanSelector(),
        }
    )


def _lock_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_LOCK_ENABLED, default=defaults[CONF_LOCK_ENABLED]
            ): BooleanSelector(),
            vol.Optional(
                CONF_LOCK_CODE, default=defaults[CONF_LOCK_CODE]
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(
                CONF_AUTO_RELOCK_SEC, default=defaults[CONF_AUTO_RELOCK_SEC]
            ): _number(0, 3600, 1, "s"),
        }
    )


def _display_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_EXPOSE_VTHERM_IDENTITY,
                default=defaults[CONF_EXPOSE_VTHERM_IDENTITY],
            ): BooleanSelector(),
        }
    )


def _sectioned_schema(current: Mapping[str, Any] | None = None) -> vol.Schema:
    defaults = _defaults(current)
    return vol.Schema(
        {
            vol.Required(SECTION_BASIC): section(_basic_schema(defaults)),
            vol.Required(SECTION_ROUTING): section(
                _routing_schema(defaults), {"collapsed": True}
            ),
            vol.Required(SECTION_MANUAL): section(
                _manual_schema(defaults), {"collapsed": True}
            ),
            vol.Required(SECTION_CONFLICTS): section(
                _conflicts_schema(defaults), {"collapsed": True}
            ),
            vol.Required(SECTION_BOOST): section(
                _boost_schema(defaults), {"collapsed": True}
            ),
            vol.Required(SECTION_LOCK): section(
                _lock_schema(defaults), {"collapsed": True}
            ),
            vol.Required(SECTION_DISPLAY): section(
                _display_schema(defaults), {"collapsed": True}
            ),
        }
    )


def _flatten_sections(data: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten the section wrappers returned by the form."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, Mapping):
            flat.update(value)
        else:
            flat[key] = value
    return flat


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validate_input(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, str]:
    """Validate the form values and return field errors."""
    errors: dict[str, str] = {}

    radiator = data.get(CONF_RADIATOR_ENTITY_ID)
    ac = data.get(CONF_AC_ENTITY_ID)
    outdoor = data.get(CONF_OUTDOOR_SENSOR_ENTITY_ID)

    if radiator == ac:
        errors[CONF_AC_ENTITY_ID] = "same_entities"

    for field, entity_id, domain in (
        (CONF_RADIATOR_ENTITY_ID, radiator, "climate"),
        (CONF_AC_ENTITY_ID, ac, "climate"),
        (CONF_OUTDOOR_SENSOR_ENTITY_ID, outdoor, "sensor"),
    ):
        if not entity_id or hass.states.get(entity_id) is None:
            errors[field] = "entity_not_found"
        elif not entity_id.startswith(f"{domain}."):
            errors[field] = "invalid_entity"

    cold = float(data.get(CONF_COLD_THRESHOLD, DEFAULT_COLD_THRESHOLD))
    mild = float(data.get(CONF_MILD_THRESHOLD, DEFAULT_MILD_THRESHOLD))
    if cold > mild:
        errors[CONF_MILD_THRESHOLD] = "threshold_order"

    default_manual = _as_int(
        data.get(CONF_DEFAULT_MANUAL_MINUTES), DEFAULT_MANUAL_MINUTES
    )
    max_manual = _as_int(data.get(CONF_MAX_MANUAL_MINUTES), DEFAULT_MAX_MANUAL_MINUTES)
    if default_manual > 0 and default_manual > max_manual:
        errors[CONF_DEFAULT_MANUAL_MINUTES] = "manual_order"

    if float(data.get(CONF_TEMPERATURE_TOLERANCE, 0.2)) <= 0:
        errors[CONF_TEMPERATURE_TOLERANCE] = "invalid_tolerance"

    if float(data.get(CONF_MIN_ROUTE_DWELL, 0)) < 0:
        errors[CONF_MIN_ROUTE_DWELL] = "invalid_duration"

    lock_code = str(data.get(CONF_LOCK_CODE) or "")
    if lock_code and not re.fullmatch(r"\d{4,8}", lock_code):
        errors[CONF_LOCK_CODE] = "invalid_lock_code"

    auto_relock = _as_int(data.get(CONF_AUTO_RELOCK_SEC), DEFAULT_AUTO_RELOCK_SEC)
    if auto_relock < 0:
        errors[CONF_AUTO_RELOCK_SEC] = "invalid_duration"

    return errors


def _unique_id(data: Mapping[str, Any]) -> str:
    return f"{data[CONF_RADIATOR_ENTITY_ID]}|{data[CONF_AC_ENTITY_ID]}"


class ClimateRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect the router configuration in sections."""
        errors: dict[str, str] = {}
        current: dict[str, Any] | None = None
        if user_input is not None:
            current = _flatten_sections(user_input)
            errors = _validate_input(self.hass, current)
            if not errors:
                await self.async_set_unique_id(_unique_id(current))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=str(current[CONF_NAME]), data=current)

        return self.async_show_form(
            step_id="user",
            data_schema=_sectioned_schema(current),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change entities or options of an existing entry."""
        entry: ConfigEntry | None = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if entry is None:
            return self.async_abort(reason="unknown_entry")

        errors: dict[str, str] = {}
        current = {**entry.data, **entry.options}
        if user_input is not None:
            current = _flatten_sections(user_input)
            errors = _validate_input(self.hass, current)
            if not errors:
                unique_id = _unique_id(current)
                for other in self._async_current_entries():
                    if other.entry_id != entry.entry_id and other.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=current,
                    options={},
                    unique_id=unique_id,
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_sectioned_schema(current),
            errors=errors,
        )


class ClimateRouterOptionsFlow(OptionsFlow):
    """Sectioned options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options menu."""
        return self.async_show_menu(step_id="init", menu_options=OPTION_MENU)

    async def _async_section_step(
        self,
        section_id: str,
        schema: Any,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        entry = self.config_entry
        current = {**entry.data, **entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**current, **user_input}
            errors = _validate_input(self.hass, merged)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    entry,
                    unique_id=_unique_id(merged),
                    options={**entry.options, **user_input},
                )
                return self.async_show_menu(step_id="init", menu_options=OPTION_MENU)
            current = merged

        return self.async_show_form(
            step_id=section_id,
            data_schema=schema(_defaults(current)),
            errors=errors,
        )

    async def async_step_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit entities and name."""
        return await self._async_section_step(SECTION_BASIC, _basic_schema, user_input)

    async def async_step_routing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit routing thresholds and timings."""
        return await self._async_section_step(
            SECTION_ROUTING, _routing_schema, user_input
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit manual-mode defaults."""
        return await self._async_section_step(SECTION_MANUAL, _manual_schema, user_input)

    async def async_step_conflicts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit conflict handling."""
        return await self._async_section_step(
            SECTION_CONFLICTS, _conflicts_schema, user_input
        )

    async def async_step_boost(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the boost feature flag."""
        return await self._async_section_step(SECTION_BOOST, _boost_schema, user_input)

    async def async_step_lock(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the optional UI lock."""
        return await self._async_section_step(SECTION_LOCK, _lock_schema, user_input)

    async def async_step_display(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit Lovelace compatibility options."""
        return await self._async_section_step(SECTION_DISPLAY, _display_schema, user_input)

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Persist the accumulated options and close the menu."""
        return self.async_create_entry(title="", data=dict(self.config_entry.options))
