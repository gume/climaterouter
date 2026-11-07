"""Translation consistency tests.

``strings.json`` is the source of truth for Home Assistant, while
``translations/en.json`` is what the runtime loads. The repository keeps them
as two files, so these tests guard against drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1] / "custom_components" / "climaterouter"
STRINGS = PACKAGE / "strings.json"
EN_TRANSLATIONS = PACKAGE / "translations" / "en.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_english_translation_matches_strings() -> None:
    assert _load(STRINGS) == _load(EN_TRANSLATIONS)


def _assert_descriptions(node: Any, path: str) -> None:
    if not isinstance(node, dict):
        return
    data = node.get("data")
    if isinstance(data, dict):
        descriptions = node.get("data_description")
        assert isinstance(descriptions, dict), f"{path}: missing data_description"
        missing = sorted(set(data) - set(descriptions))
        assert not missing, f"{path}: missing data_description for {missing}"
        empty = sorted(key for key, value in descriptions.items() if not value)
        assert not empty, f"{path}: empty data_description for {empty}"
    for key, value in node.items():
        _assert_descriptions(value, f"{path}.{key}")


def test_every_config_and_options_field_has_a_description() -> None:
    strings = _load(STRINGS)
    _assert_descriptions(strings["config"], "config")
    _assert_descriptions(strings["options"], "options")
