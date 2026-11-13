"""Guards that Home Assistant really loads the form labels and hints.

The config and options dialogs render their text from the runtime
``translations/en.json`` through Home Assistant's translation cache.  A test
that only compares the JSON files cannot catch a runtime file that Home
Assistant refuses to load, so these tests resolve the labels through the real
``async_get_translations`` helper and assert every field the flow can render has
a label and a description.

The reported symptoms -- a bare ``scheduler_pause_switch_invert`` in the manual
step, an empty ``presets`` menu entry and raw ``off_preset_enabled`` keys -- all
come from those keys missing at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from homeassistant.const import STATE_OFF
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.climaterouter.config_flow import (
    OPTION_MENU,
    SECTION_BASIC,
    SECTION_BOOST,
    SECTION_CONFLICTS,
    SECTION_DISPLAY,
    SECTION_LOCK,
    SECTION_MANUAL,
    SECTION_PRESETS,
    SECTION_ROUTING,
    _basic_schema,
    _boost_schema,
    _conflicts_schema,
    _defaults,
    _display_schema,
    _lock_schema,
    _manual_schema,
    _presets_schema,
    _routing_schema,
    _sectioned_schema,
)
from custom_components.climaterouter.const import (
    CONF_NAME,
    CONF_RADIATOR_ENTITY_ID,
    DOMAIN,
)
from custom_components.climaterouter.runtime_translations import (
    _flatten,
    _missing_keys,
    async_ensure_runtime_translations,
)

PACKAGE = Path(__file__).resolve().parents[2] / "custom_components" / "climaterouter"
STRINGS = PACKAGE / "strings.json"
RUNTIME = PACKAGE / "translations" / "en.json"

RADIATOR = "climate.radiator"

SECTION_SCHEMAS = {
    SECTION_BASIC: _basic_schema,
    SECTION_ROUTING: _routing_schema,
    SECTION_MANUAL: _manual_schema,
    SECTION_PRESETS: _presets_schema,
    SECTION_CONFLICTS: _conflicts_schema,
    SECTION_BOOST: _boost_schema,
    SECTION_LOCK: _lock_schema,
    SECTION_DISPLAY: _display_schema,
}


def _field_names(schema: Any) -> list[str]:
    """Return the field names of a voluptuous schema in declaration order."""
    return [str(key) for key in schema.schema]


async def _loaded(hass, category: str) -> dict[str, str]:
    """Return the translations Home Assistant serves for one category."""
    return await async_get_translations(hass, "en", category, {DOMAIN})


@pytest.fixture
async def loaded_entry(hass):
    """Set up an entry so Home Assistant knows the integration is installed."""
    hass.states.async_set(RADIATOR, STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "Test Router", CONF_RADIATOR_ENTITY_ID: RADIATOR},
        options={},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _assert_label(translations: dict[str, str], key: str) -> None:
    assert translations.get(key), f"missing translation: {key}"


async def test_options_fields_have_labels_and_hints(hass, loaded_entry) -> None:
    """Every options section renders a labelled field with a hint."""
    options = await _loaded(hass, "options")

    for option in OPTION_MENU:
        _assert_label(options, f"component.{DOMAIN}.options.step.init.menu_options.{option}")

    for section, factory in SECTION_SCHEMAS.items():
        schema = factory(_defaults({}))
        _assert_label(options, f"component.{DOMAIN}.options.step.{section}.title")
        for field in _field_names(schema):
            _assert_label(options, f"component.{DOMAIN}.options.step.{section}.data.{field}")
            _assert_label(
                options,
                f"component.{DOMAIN}.options.step.{section}.data_description.{field}",
            )


async def test_options_section_fields_match_the_reported_symptoms(hass, loaded_entry) -> None:
    """The manual polarity switch and the whole presets section are labelled."""
    options = await _loaded(hass, "options")

    _assert_label(
        options,
        f"component.{DOMAIN}.options.step.manual.data.scheduler_pause_switch_invert",
    )
    _assert_label(
        options,
        f"component.{DOMAIN}.options.step.manual.data_description.scheduler_pause_switch_invert",
    )
    _assert_label(options, f"component.{DOMAIN}.options.step.init.menu_options.presets")
    _assert_label(options, f"component.{DOMAIN}.options.step.presets.title")
    for field in _field_names(_presets_schema(_defaults({}))):
        _assert_label(options, f"component.{DOMAIN}.options.step.presets.data.{field}")
        _assert_label(
            options,
            f"component.{DOMAIN}.options.step.presets.data_description.{field}",
        )


async def test_config_sections_have_labels_and_hints(hass, loaded_entry) -> None:
    """Every initial-setup section and field renders a label and a hint."""
    config = await _loaded(hass, "config")
    _assert_label(config, f"component.{DOMAIN}.config.step.user.title")

    schema = _sectioned_schema(None)
    for section, wrapper in schema.schema.items():
        name = str(section)
        _assert_label(config, f"component.{DOMAIN}.config.step.user.sections.{name}.name")
        for field in _field_names(wrapper.schema):
            _assert_label(
                config, f"component.{DOMAIN}.config.step.user.sections.{name}.data.{field}"
            )
            _assert_label(
                config,
                f"component.{DOMAIN}.config.step.user.sections.{name}.data_description.{field}",
            )


async def test_reconfigure_step_reuses_the_config_labels(hass, loaded_entry) -> None:
    """The reconfigure step looks up the same field labels."""
    config = await _loaded(hass, "config")
    _assert_label(config, f"component.{DOMAIN}.config.step.reconfigure.title")
    for section in SECTION_SCHEMAS:
        _assert_label(config, f"component.{DOMAIN}.config.step.reconfigure.sections.{section}.name")


async def test_runtime_file_contains_every_source_key() -> None:
    """The shipped runtime file is a superset of the source strings."""
    source = json.loads(STRINGS.read_text(encoding="utf-8"))
    runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
    assert _missing_keys(runtime, source) == set()


def test_missing_keys_reports_only_absent_keys() -> None:
    """The repair helper compares flattened key sets."""
    source = {"a": {"b": 1, "c": 2}, "d": 3}
    target = {"a": {"b": 1}, "d": 3}
    assert _missing_keys(target, source) == {"a.c"}
    assert _missing_keys(source, source) == set()
    assert _flatten({"a": {"b": 1}}) == {"a.b": 1}


async def test_repair_rewrites_a_stale_runtime_file(hass, tmp_path: Path) -> None:
    """A runtime file missing keys is replaced by the source strings."""
    source = tmp_path / "strings.json"
    target = tmp_path / "translations" / "en.json"
    source.write_text('{"options": {"step": {"presets": {"title": "Presets"}}}}', "utf-8")
    target.parent.mkdir(parents=True)
    target.write_text('{"options": {"step": {"init": {"title": "Init"}}}}', "utf-8")

    repaired = await async_ensure_runtime_translations(hass, source=source, target=target)

    assert repaired is True
    assert json.loads(target.read_text("utf-8")) == json.loads(source.read_text("utf-8"))


async def test_repair_keeps_a_current_runtime_file(hass, tmp_path: Path) -> None:
    """A runtime file that already has every key is not rewritten."""
    source = tmp_path / "strings.json"
    target = tmp_path / "translations" / "en.json"
    source.write_text('{"title": "Source"}', "utf-8")
    target.parent.mkdir(parents=True)
    target.write_text('{"title": "Runtime", "extra": "kept"}', "utf-8")

    repaired = await async_ensure_runtime_translations(hass, source=source, target=target)

    assert repaired is False
    assert json.loads(target.read_text("utf-8")) == {"title": "Runtime", "extra": "kept"}


async def test_integration_setup_runs_the_self_heal(hass, monkeypatch) -> None:
    """The translation repair is wired into the integration setup."""
    from custom_components import climaterouter

    calls: list[Any] = []

    async def fake_ensure(hass_arg, **kwargs: Any) -> bool:
        calls.append(hass_arg)
        return False

    monkeypatch.setattr(climaterouter, "async_ensure_runtime_translations", fake_ensure)

    assert await climaterouter.async_setup(hass, {}) is True
    assert calls == [hass]
