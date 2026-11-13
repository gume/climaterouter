"""Keep the runtime English translation file in sync with the source strings.

Custom integrations ship the compiled ``translations/en.json`` file; Home
Assistant never reads ``strings.json`` at runtime.  A partial or interrupted
update can leave the Python code new while the runtime translation file still
belongs to the previous release, which makes new form fields fall back to their
raw keys.  ``strings.json`` is the source of truth in the repository, so when
the runtime file is missing keys that the source has, rewrite it and invalidate
Home Assistant's translation cache.

The rewrite only happens when keys are missing.  A runtime file that already
contains every key is never overwritten, so a newer translation file cannot be
replaced by an older source.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PACKAGE = Path(__file__).parent
SOURCE_TRANSLATIONS = PACKAGE / "strings.json"
RUNTIME_TRANSLATIONS = PACKAGE / "translations" / "en.json"


def _flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a translation tree into dotted keys."""
    flat: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            flat.update(_flatten(value, f"{prefix}{key}."))
    else:
        flat[prefix.rstrip(".")] = data
    return flat


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON object, returning ``None`` when it is unusable."""
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _missing_keys(target: dict[str, Any], source: dict[str, Any]) -> set[str]:
    """Return the source keys the target does not contain."""
    return set(_flatten(source)) - set(_flatten(target))


def _write_text(path: Path, text: str) -> None:
    """Write a translation file, creating its directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _invalidate_translations(hass: HomeAssistant) -> None:
    """Drop Home Assistant's cached translations for this integration."""
    try:
        from homeassistant.helpers.translation import async_invalidate_translations
    except ImportError:
        # Older Home Assistant releases cache translations until a restart.
        return
    async_invalidate_translations(hass, {DOMAIN})


async def async_ensure_runtime_translations(
    hass: HomeAssistant,
    *,
    source: Path | None = None,
    target: Path | None = None,
) -> bool:
    """Repair a stale runtime translation file and invalidate the cache.

    Returns ``True`` when the runtime file had to be rewritten.
    """
    source = source or SOURCE_TRANSLATIONS
    target = target or RUNTIME_TRANSLATIONS

    source_data = await hass.async_add_executor_job(_read_json, source)
    target_data = await hass.async_add_executor_job(_read_json, target)
    missing = _missing_keys(target_data or {}, source_data or {})

    repaired = False
    if missing:
        try:
            text = await hass.async_add_executor_job(source.read_text, "utf-8")
            await hass.async_add_executor_job(_write_text, target, text)
        except OSError:
            _LOGGER.warning(
                "Could not repair the stale ClimateRouter translation file %s; "
                "reinstall the integration to restore the form labels",
                target,
            )
        else:
            repaired = True
            _LOGGER.warning(
                "ClimateRouter repaired %d missing runtime translation key(s) in %s; "
                "reload the browser to show the form labels",
                len(missing),
                target,
            )

    # Even when the file is current, the cache may still hold the previous
    # release after an in-place update.  Reloading it is cheap.
    _invalidate_translations(hass)
    return repaired
