"""Integration tests for the ClimateRouter config flow."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import STATE_OFF
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.config_flow import OPTION_MENU, SECTION_ROUTING
from custom_components.climaterouter.const import (
    CONF_AC_ENTITY_ID,
    CONF_COLD_THRESHOLD,
    CONF_MILD_THRESHOLD,
    CONF_MIN_ROUTE_DWELL,
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


async def test_duplicate_entities_abort(hass) -> None:
    """The same radiator/AC pair cannot be configured twice."""
    _set_entities(hass)

    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    first = await hass.config_entries.flow.async_configure(first["flow_id"], _form_input())
    assert first["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    second = await hass.config_entries.flow.async_configure(second["flow_id"], _form_input())

    assert second["type"] is data_entry_flow.FlowResultType.ABORT
    assert second["reason"] == "already_configured"


async def test_reconfigure_updates_entry(hass) -> None:
    """The reconfigure flow rewrites data and the title."""
    _set_entities(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data={
            CONF_NAME: "Test Router",
            CONF_RADIATOR_ENTITY_ID: RADIATOR,
            CONF_AC_ENTITY_ID: AC,
            CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
        },
        unique_id=f"{RADIATOR}|{AC}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _form_input(**{CONF_NAME: "Renamed Router"})
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Renamed Router"
    assert entry.data[CONF_NAME] == "Renamed Router"
    assert entry.options == {}


async def test_options_flow_saves_section_and_finishes(hass) -> None:
    """Saving one options section writes entry data and returns to the menu."""
    _set_entities(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Router",
        data=_form_input()["basic"],
        unique_id=f"{RADIATOR}|{AC}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "init"
    assert set(result["menu_options"]) == set(OPTION_MENU)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": SECTION_ROUTING}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SECTION_ROUTING

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_COLD_THRESHOLD: 5, CONF_MILD_THRESHOLD: 8, CONF_MIN_ROUTE_DWELL: 120},
    )
    assert result["type"] is data_entry_flow.FlowResultType.MENU
    assert entry.data[CONF_COLD_THRESHOLD] == 5
    assert entry.data[CONF_MILD_THRESHOLD] == 8
    assert entry.data[CONF_MIN_ROUTE_DWELL] == 120
    assert entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options == {}
