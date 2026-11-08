"""Integration tests for the ClimateRouter config flow."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import STATE_OFF

from custom_components.climaterouter.const import (
    CONF_AC_ENTITY_ID,
    CONF_COLD_THRESHOLD,
    CONF_MILD_THRESHOLD,
    CONF_NAME,
    CONF_OUTDOOR_SENSOR_ENTITY_ID,
    CONF_RADIATOR_ENTITY_ID,
    DOMAIN,
)

RADIATOR = "climate.radiator"
AC = "climate.ac"
OUTDOOR = "sensor.outdoor"


def _form_input(**basic: Any) -> dict[str, Any]:
    """Return a sectioned form payload with form defaults for all sections."""
    return {
        "basic": {
            CONF_NAME: "Test Router",
            CONF_RADIATOR_ENTITY_ID: RADIATOR,
            CONF_AC_ENTITY_ID: AC,
            CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
            **basic,
        },
        "routing": {},
        "manual": {},
        "conflicts": {},
        "boost": {},
        "lock": {},
        "display": {},
    }


def _set_entities(hass) -> None:
    hass.states.async_set(RADIATOR, STATE_OFF)
    hass.states.async_set(AC, STATE_OFF)
    hass.states.async_set(OUTDOOR, "5.0")


async def test_user_flow_creates_entry(hass) -> None:
    """The happy path stores the flattened configuration."""
    _set_entities(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert set(result["data_schema"].schema) == {
        "basic",
        "routing",
        "manual",
        "conflicts",
        "boost",
        "lock",
        "display",
    }

    result = await hass.config_entries.flow.async_configure(result["flow_id"], _form_input())

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test Router"
    assert result["data"][CONF_RADIATOR_ENTITY_ID] == RADIATOR
    assert result["data"][CONF_AC_ENTITY_ID] == AC
    assert result["data"][CONF_OUTDOOR_SENSOR_ENTITY_ID] == OUTDOOR
    assert "basic" not in result["data"]


async def test_user_flow_reports_missing_entities(hass) -> None:
    """Entity existence is validated against the state machine."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], _form_input())

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {
        CONF_RADIATOR_ENTITY_ID: "entity_not_found",
        CONF_AC_ENTITY_ID: "entity_not_found",
        CONF_OUTDOOR_SENSOR_ENTITY_ID: "entity_not_found",
    }


async def test_user_flow_rejects_same_entities(hass) -> None:
    """The radiator and AC must be different entities."""
    _set_entities(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _form_input(**{CONF_AC_ENTITY_ID: RADIATOR})
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_AC_ENTITY_ID: "same_entities"}


async def test_user_flow_rejects_threshold_order(hass) -> None:
    """The cold threshold may not exceed the mild threshold."""
    _set_entities(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    payload = _form_input()
    payload["routing"] = {CONF_COLD_THRESHOLD: 20, CONF_MILD_THRESHOLD: 10}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_MILD_THRESHOLD: "threshold_order"}
