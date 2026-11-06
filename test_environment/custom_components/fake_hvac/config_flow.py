"""Config flow for the fake HVAC test integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.util import slugify

from .const import (
    CONF_AC_POWER_KW,
    CONF_LOSS_COEFFICIENT,
    CONF_NAME,
    CONF_OUTDOOR_TEMPERATURE,
    CONF_RADIATOR_POWER_KW,
    CONF_ROOM_TEMPERATURE,
    CONF_SIMULATION_ENABLED,
    CONF_THERMAL_MASS,
    CONF_TIME_SCALE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AC_POWER_KW,
    DEFAULT_LOSS_COEFFICIENT,
    DEFAULT_NAME,
    DEFAULT_OUTDOOR_TEMPERATURE,
    DEFAULT_RADIATOR_POWER_KW,
    DEFAULT_ROOM_TEMPERATURE,
    DEFAULT_SIMULATION_ENABLED,
    DEFAULT_THERMAL_MASS,
    DEFAULT_TIME_SCALE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): cv.string,
            vol.Optional(
                CONF_ROOM_TEMPERATURE,
                default=defaults.get(CONF_ROOM_TEMPERATURE, DEFAULT_ROOM_TEMPERATURE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_OUTDOOR_TEMPERATURE,
                default=defaults.get(CONF_OUTDOOR_TEMPERATURE, DEFAULT_OUTDOOR_TEMPERATURE),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_RADIATOR_POWER_KW,
                default=defaults.get(CONF_RADIATOR_POWER_KW, DEFAULT_RADIATOR_POWER_KW),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_AC_POWER_KW,
                default=defaults.get(CONF_AC_POWER_KW, DEFAULT_AC_POWER_KW),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_LOSS_COEFFICIENT,
                default=defaults.get(CONF_LOSS_COEFFICIENT, DEFAULT_LOSS_COEFFICIENT),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_THERMAL_MASS,
                default=defaults.get(CONF_THERMAL_MASS, DEFAULT_THERMAL_MASS),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
            vol.Optional(
                CONF_TIME_SCALE,
                default=defaults.get(CONF_TIME_SCALE, DEFAULT_TIME_SCALE),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=3600)),
            vol.Optional(
                CONF_SIMULATION_ENABLED,
                default=defaults.get(CONF_SIMULATION_ENABLED, DEFAULT_SIMULATION_ENABLED),
            ): cv.boolean,
        }
    )


class FakeHvacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a fake HVAC config entry."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create a simulated system from the UI."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_schema())

        return await self._async_create(user_input, update_existing=False)

    async def async_step_import(self, import_config: dict[str, Any]) -> ConfigFlowResult:
        """Import/update the YAML configuration."""
        return await self._async_create(import_config, update_existing=True)

    async def _async_create(
        self, config: dict[str, Any], *, update_existing: bool
    ) -> ConfigFlowResult:
        data = _schema()(config)
        title = str(data[CONF_NAME])
        unique_id = slugify(title)
        await self.async_set_unique_id(unique_id)

        if update_existing:
            for entry in self._async_current_entries():
                if entry.unique_id == unique_id:
                    return self.async_update_reload_and_abort(entry, data=data)

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)
