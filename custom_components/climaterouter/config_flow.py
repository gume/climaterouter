"""Config, options, and reconfigure flows for ClimateRouter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant
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
)

from .const import (
    CONF_AC_ENTITY_ID,
    CONF_AUTO_RESOLVE_IDLE_TARGETS,
    CONF_AUTO_RESOLVE_SIMULTANEOUS,
    CONF_BOOST_ENABLED,
    CONF_COLD_THRESHOLD,
    CONF_CONFLICT_POLICY,
    CONF_DEFAULT_OVERRIDE_MINUTES,
    CONF_FALLBACK_ON_UNAVAILABLE,
    CONF_HANDOVER_IDLE_CONFIRM,
    CONF_MANUAL_SWITCH_ENTITY_ID,
    CONF_MANUAL_SWITCH_ON_TARGET,
    CONF_MAX_OVERRIDE_MINUTES,
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
    DEFAULT_COLD_THRESHOLD,
    DEFAULT_CONFLICT_POLICY,
    DEFAULT_HANDOVER_IDLE_CONFIRM,
    DEFAULT_MAX_OVERRIDE_MINUTES,
    DEFAULT_MILD_THRESHOLD,
    DEFAULT_MIN_ROUTE_DWELL,
    DEFAULT_OFF_CONFIRM_TIMEOUT,
    DEFAULT_OUTDOOR_STALE_AFTER,
    DEFAULT_OVERRIDE_MINUTES,
    DEFAULT_SETTLE_TIME,
    DEFAULT_STARTUP_GRACE,
    DEFAULT_TEMPERATURE_TOLERANCE,
    Target,
)

MANUAL_SWITCH_DOMAINS = ["switch", "input_boolean", "input_select"]


def _defaults(current: Mapping[str, Any] | None = None) -> dict[str, Any]:
    current = current or {}
    return {
        CONF_NAME: current.get(CONF_NAME, "ClimateRouter"),
        CONF_RADIATOR_ENTITY_ID: current.get(CONF_RADIATOR_ENTITY_ID, vol.UNDEFINED),
        CONF_AC_ENTITY_ID: current.get(CONF_AC_ENTITY_ID, vol.UNDEFINED),
        CONF_OUTDOOR_SENSOR_ENTITY_ID: current.get(CONF_OUTDOOR_SENSOR_ENTITY_ID, vol.UNDEFINED),
        CONF_MANUAL_SWITCH_ENTITY_ID: current.get(CONF_MANUAL_SWITCH_ENTITY_ID, None),
        CONF_MANUAL_SWITCH_ON_TARGET: current.get(CONF_MANUAL_SWITCH_ON_TARGET, Target.AC.value),
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
        CONF_DEFAULT_OVERRIDE_MINUTES: current.get(
            CONF_DEFAULT_OVERRIDE_MINUTES, DEFAULT_OVERRIDE_MINUTES
        ),
        CONF_MAX_OVERRIDE_MINUTES: current.get(
            CONF_MAX_OVERRIDE_MINUTES, DEFAULT_MAX_OVERRIDE_MINUTES
        ),
        CONF_TEMPERATURE_TOLERANCE: current.get(
            CONF_TEMPERATURE_TOLERANCE, DEFAULT_TEMPERATURE_TOLERANCE
        ),
        CONF_BOOST_ENABLED: current.get(CONF_BOOST_ENABLED, False),
    }


def _number(minimum: float, maximum: float, step: float, unit: str | None = None) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement=unit,
            mode=NumberSelectorMode.BOX,
        )
    )


def _schema(current: Mapping[str, Any] | None = None) -> vol.Schema:
    defaults = _defaults(current)
    manual_switch = defaults[CONF_MANUAL_SWITCH_ENTITY_ID]
    manual_switch_key = (
        vol.Optional(CONF_MANUAL_SWITCH_ENTITY_ID)
        if manual_switch is None
        else vol.Optional(CONF_MANUAL_SWITCH_ENTITY_ID, default=manual_switch)
    )
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults[CONF_NAME]): cv.string,
            vol.Required(
                CONF_RADIATOR_ENTITY_ID, default=defaults[CONF_RADIATOR_ENTITY_ID]
            ): EntitySelector(EntitySelectorConfig(domain="climate")),
            vol.Required(CONF_AC_ENTITY_ID, default=defaults[CONF_AC_ENTITY_ID]): EntitySelector(
                EntitySelectorConfig(domain="climate")
            ),
            vol.Required(
                CONF_OUTDOOR_SENSOR_ENTITY_ID,
                default=defaults[CONF_OUTDOOR_SENSOR_ENTITY_ID],
            ): EntitySelector(EntitySelectorConfig(domain="sensor")),
            manual_switch_key: EntitySelector(EntitySelectorConfig(domain=MANUAL_SWITCH_DOMAINS)),
            vol.Required(
                CONF_MANUAL_SWITCH_ON_TARGET,
                default=defaults[CONF_MANUAL_SWITCH_ON_TARGET],
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[Target.AC.value, Target.RADIATOR.value],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_COLD_THRESHOLD, default=defaults[CONF_COLD_THRESHOLD]): _number(
                -50, 60, 0.5, "°C"
            ),
            vol.Required(CONF_MILD_THRESHOLD, default=defaults[CONF_MILD_THRESHOLD]): _number(
                -50, 60, 0.5, "°C"
            ),
            vol.Required(CONF_MIN_ROUTE_DWELL, default=defaults[CONF_MIN_ROUTE_DWELL]): _number(
                0, 86400, 10, "s"
            ),
            vol.Required(
                CONF_HANDOVER_IDLE_CONFIRM,
                default=defaults[CONF_HANDOVER_IDLE_CONFIRM],
            ): _number(0, 3600, 1, "s"),
            vol.Required(
                CONF_OFF_CONFIRM_TIMEOUT, default=defaults[CONF_OFF_CONFIRM_TIMEOUT]
            ): _number(1, 3600, 1, "s"),
            vol.Required(CONF_STARTUP_GRACE, default=defaults[CONF_STARTUP_GRACE]): _number(
                0, 600, 1, "s"
            ),
            vol.Required(CONF_SETTLE_TIME, default=defaults[CONF_SETTLE_TIME]): _number(
                0, 600, 1, "s"
            ),
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
                CONF_FALLBACK_ON_UNAVAILABLE,
                default=defaults[CONF_FALLBACK_ON_UNAVAILABLE],
            ): BooleanSelector(),
            vol.Required(
                CONF_OUTDOOR_STALE_AFTER,
                default=defaults[CONF_OUTDOOR_STALE_AFTER],
            ): _number(60, 86400, 60, "s"),
            vol.Required(
                CONF_DEFAULT_OVERRIDE_MINUTES,
                default=defaults[CONF_DEFAULT_OVERRIDE_MINUTES],
            ): _number(1, 1440, 1, "min"),
            vol.Required(
                CONF_MAX_OVERRIDE_MINUTES,
                default=defaults[CONF_MAX_OVERRIDE_MINUTES],
            ): _number(1, 1440, 1, "min"),
            vol.Required(
                CONF_TEMPERATURE_TOLERANCE,
                default=defaults[CONF_TEMPERATURE_TOLERANCE],
            ): _number(0.05, 5, 0.05, "°C"),
            vol.Required(
                CONF_BOOST_ENABLED, default=defaults[CONF_BOOST_ENABLED]
            ): BooleanSelector(),
        }
    )


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

    manual = data.get(CONF_MANUAL_SWITCH_ENTITY_ID)
    if manual:
        if hass.states.get(manual) is None:
            errors[CONF_MANUAL_SWITCH_ENTITY_ID] = "entity_not_found"
        elif manual.split(".", 1)[0] not in MANUAL_SWITCH_DOMAINS:
            errors[CONF_MANUAL_SWITCH_ENTITY_ID] = "invalid_entity"

    cold = float(data.get(CONF_COLD_THRESHOLD, DEFAULT_COLD_THRESHOLD))
    mild = float(data.get(CONF_MILD_THRESHOLD, DEFAULT_MILD_THRESHOLD))
    if cold > mild:
        errors[CONF_MILD_THRESHOLD] = "threshold_order"

    default_override = int(data.get(CONF_DEFAULT_OVERRIDE_MINUTES, DEFAULT_OVERRIDE_MINUTES))
    max_override = int(data.get(CONF_MAX_OVERRIDE_MINUTES, DEFAULT_MAX_OVERRIDE_MINUTES))
    if default_override > max_override:
        errors[CONF_DEFAULT_OVERRIDE_MINUTES] = "override_order"

    if float(data.get(CONF_TEMPERATURE_TOLERANCE, 0.2)) <= 0:
        errors[CONF_TEMPERATURE_TOLERANCE] = "invalid_tolerance"

    if float(data.get(CONF_MIN_ROUTE_DWELL, 0)) < 0:
        errors[CONF_MIN_ROUTE_DWELL] = "invalid_duration"

    return errors


def _unique_id(data: Mapping[str, Any]) -> str:
    return f"{data[CONF_RADIATOR_ENTITY_ID]}|{data[CONF_AC_ENTITY_ID]}"


class ClimateRouterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the router configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_input(self.hass, user_input)
            if not errors:
                await self.async_set_unique_id(_unique_id(user_input))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=str(user_input[CONF_NAME]), data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
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
            errors = _validate_input(self.hass, user_input)
            if not errors:
                unique_id = _unique_id(user_input)
                for other in self._async_current_entries():
                    if other.entry_id != entry.entry_id and other.unique_id == unique_id:
                        return self.async_abort(reason="already_configured")
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=user_input,
                    options={},
                    unique_id=unique_id,
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            current = user_input

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(current),
            errors=errors,
        )


class ClimateRouterOptionsFlow(OptionsFlow):
    """Options flow for thresholds and timings."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Edit the non-destructive options."""
        entry = self.config_entry
        current = {**entry.data, **entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_input(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(entry, unique_id=_unique_id(user_input))
                return self.async_create_entry(title="", data=user_input)
            current = user_input

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current),
            errors=errors,
        )
