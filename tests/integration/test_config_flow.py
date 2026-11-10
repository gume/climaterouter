"""Integration tests for the ClimateRouter config flow."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import STATE_OFF
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.config_flow import (
    OPTION_MENU,
    SECTION_BASIC,
    SECTION_BOOST,
    SECTION_CONFLICTS,
    SECTION_DISPLAY,
    SECTION_LOCK,
    SECTION_MANUAL,
    SECTION_ROUTING,
    _flatten_sections,
    _validate_input,
)
from custom_components.climaterouter.const import (
    CONF_AC_ENTITY_ID,
    CONF_AUTO_RELOCK_SEC,
    CONF_AUTO_RESOLVE_IDLE_TARGETS,
    CONF_AUTO_RESOLVE_SIMULTANEOUS,
    CONF_BOOST_ENABLED,
    CONF_COLD_THRESHOLD,
    CONF_CONFLICT_POLICY,
    CONF_DEFAULT_MANUAL_MINUTES,
    CONF_EXPOSE_VTHERM_IDENTITY,
    CONF_LOCK_CODE,
    CONF_LOCK_ENABLED,
    CONF_MAX_MANUAL_MINUTES,
    CONF_MILD_THRESHOLD,
    CONF_MIN_ROUTE_DWELL,
    CONF_NAME,
    CONF_OUTDOOR_SENSOR_ENTITY_ID,
    CONF_OUTDOOR_STALE_AFTER,
    CONF_RADIATOR_ENTITY_ID,
    CONF_TEMPERATURE_TOLERANCE,
    CONF_VELAIR_ENABLED,
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


async def test_validate_input_rejects_wrong_entity_domain(hass) -> None:
    """An existing entity from the wrong domain is rejected."""
    _set_entities(hass)
    hass.states.async_set("sensor.not_a_radiator", STATE_OFF)

    errors = _validate_input(
        hass,
        {
            CONF_RADIATOR_ENTITY_ID: "sensor.not_a_radiator",
            CONF_AC_ENTITY_ID: AC,
            CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
        },
    )

    assert errors == {CONF_RADIATOR_ENTITY_ID: "invalid_entity"}


async def test_user_flow_rejects_manual_order(hass) -> None:
    """The default manual duration may not exceed the maximum."""
    _set_entities(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    payload = _form_input()
    payload["manual"] = {
        CONF_DEFAULT_MANUAL_MINUTES: 90,
        CONF_MAX_MANUAL_MINUTES: 30,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_DEFAULT_MANUAL_MINUTES: "manual_order"}


async def test_user_flow_rejects_invalid_lock_code(hass) -> None:
    """The lock code must be four to eight digits."""
    _set_entities(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    payload = _form_input()
    payload["lock"] = {
        CONF_LOCK_ENABLED: True,
        CONF_LOCK_CODE: "abc",
        CONF_AUTO_RELOCK_SEC: 30,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_LOCK_CODE: "invalid_lock_code"}


async def test_reconfigure_rejects_duplicate_unique_id(hass) -> None:
    """Reconfiguring onto another entry's entity pair aborts."""
    _set_entities(hass)
    hass.states.async_set("climate.other_radiator", STATE_OFF)
    hass.states.async_set("climate.other_ac", STATE_OFF)

    first = MockConfigEntry(
        domain=DOMAIN,
        title="First",
        data={
            CONF_NAME: "First",
            CONF_RADIATOR_ENTITY_ID: RADIATOR,
            CONF_AC_ENTITY_ID: AC,
            CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
        },
        unique_id=f"{RADIATOR}|{AC}",
    )
    first.add_to_hass(hass)
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second",
        data={
            CONF_NAME: "Second",
            CONF_RADIATOR_ENTITY_ID: "climate.other_radiator",
            CONF_AC_ENTITY_ID: "climate.other_ac",
            CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
        },
        unique_id="climate.other_radiator|climate.other_ac",
    )
    second.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": second.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], _form_input())

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_lock_section_saves_code(hass) -> None:
    """The lock options section stores a valid code."""
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
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": SECTION_LOCK}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LOCK_ENABLED: True,
            CONF_LOCK_CODE: "4321",
            CONF_AUTO_RELOCK_SEC: 60,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.MENU
    assert entry.data[CONF_LOCK_ENABLED] is True
    assert entry.data[CONF_LOCK_CODE] == "4321"
    assert entry.data[CONF_AUTO_RELOCK_SEC] == 60


async def test_options_section_reports_validation_errors(hass) -> None:
    """An invalid value keeps the section form open with an error."""
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
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": SECTION_MANUAL}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_DEFAULT_MANUAL_MINUTES: 90,
            CONF_MAX_MANUAL_MINUTES: 30,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {CONF_DEFAULT_MANUAL_MINUTES: "manual_order"}


async def test_validate_input_rejects_out_of_range_values(hass) -> None:
    """Tolerance and requested durations must stay positive."""
    _set_entities(hass)

    errors = _validate_input(
        hass,
        {
            CONF_RADIATOR_ENTITY_ID: RADIATOR,
            CONF_AC_ENTITY_ID: AC,
            CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
            CONF_TEMPERATURE_TOLERANCE: 0,
            CONF_MIN_ROUTE_DWELL: -1,
            CONF_AUTO_RELOCK_SEC: -5,
        },
    )

    assert errors == {
        CONF_TEMPERATURE_TOLERANCE: "invalid_tolerance",
        CONF_MIN_ROUTE_DWELL: "invalid_duration",
        CONF_AUTO_RELOCK_SEC: "invalid_duration",
    }


async def test_reconfigure_unknown_entry_aborts(hass) -> None:
    """A reconfigure flow for a missing entry aborts cleanly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": "missing-entry",
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "unknown_entry"


@pytest.mark.parametrize(
    ("section", "payload"),
    [
        (
            SECTION_BASIC,
            {
                CONF_NAME: "Renamed Router",
                CONF_RADIATOR_ENTITY_ID: RADIATOR,
                CONF_AC_ENTITY_ID: AC,
                CONF_OUTDOOR_SENSOR_ENTITY_ID: OUTDOOR,
            },
        ),
        (
            SECTION_CONFLICTS,
            {
                CONF_CONFLICT_POLICY: "adopt",
                CONF_AUTO_RESOLVE_IDLE_TARGETS: False,
                CONF_AUTO_RESOLVE_SIMULTANEOUS: True,
                CONF_OUTDOOR_STALE_AFTER: 3600,
                CONF_TEMPERATURE_TOLERANCE: 0.5,
            },
        ),
        (SECTION_BOOST, {CONF_BOOST_ENABLED: True}),
        (SECTION_DISPLAY, {CONF_EXPOSE_VTHERM_IDENTITY: True}),
    ],
)
async def test_options_remaining_sections_save(hass, section, payload) -> None:
    """Every remaining options section persists its values and returns to the menu."""
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
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": section}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(result["flow_id"], payload)

    assert result["type"] is data_entry_flow.FlowResultType.MENU
    for key, value in payload.items():
        assert entry.data[key] == value


def test_flatten_sections_keeps_legacy_scalars() -> None:
    """Top-level scalar values survive while section wrappers are flattened."""
    assert _flatten_sections({"basic": {"a": 1}, "legacy_key": 2}) == {
        "a": 1,
        "legacy_key": 2,
    }


async def test_options_manual_section_saves_velair_flag(hass) -> None:
    """The manual section persists the opt-in Velair integration flag."""
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
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": SECTION_MANUAL}
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_VELAIR_ENABLED: True}
    )

    assert result["type"] is data_entry_flow.FlowResultType.MENU
    assert entry.data[CONF_VELAIR_ENABLED] is True
