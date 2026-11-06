"""Diagnostics for ClimateRouter."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import VERSION
from .coordinator import ClimateRouterCoordinator
from .models import RouterSnapshot


def _serialize_state(state: Any) -> dict[str, Any]:
    data = asdict(state)
    if data.get("last_updated") is not None:
        data["last_updated"] = data["last_updated"].isoformat()
    return data


def _serialize_snapshot(snapshot: RouterSnapshot) -> dict[str, Any]:
    return {
        "ready": snapshot.ready,
        "available": snapshot.available,
        "active_targets": sorted(target.value for target in snapshot.active_targets),
        "pending_target": (snapshot.pending_target.value if snapshot.pending_target else None),
        "route_reason": snapshot.route_reason,
        "handover_state": snapshot.handover_state.value,
        "desired": snapshot.desired.to_dict(),
        "override": snapshot.override.to_dict() if snapshot.override else None,
        "outdoor_temperature": snapshot.outdoor_temperature,
        "outdoor_stale": snapshot.outdoor_stale,
        "manual_switch_state": snapshot.manual_switch_state,
        "manual_switch_stale": snapshot.manual_switch_stale,
        "route_override": snapshot.route_override,
        "last_handover": snapshot.last_handover.isoformat() if snapshot.last_handover else None,
        "last_command": snapshot.last_command.isoformat() if snapshot.last_command else None,
        "hvac_modes": list(snapshot.hvac_modes),
        "preset_modes": list(snapshot.preset_modes),
        "targets": {
            target.value: _serialize_state(state) for target, state in snapshot.targets.items()
        },
        "conflicts": [conflict.to_dict() for conflict in snapshot.conflicts],
        "conflict_count": snapshot.conflict_count,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for one config entry."""
    coordinator: ClimateRouterCoordinator | None = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return {"version": VERSION, "error": "entry not loaded"}

    config = asdict(coordinator.config)
    config["manual_switch_on_target"] = coordinator.config.manual_switch_on_target.value

    return {
        "version": VERSION,
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "config": config,
        "snapshot": _serialize_snapshot(coordinator.data),
        "targets_present": sorted(target.value for target in coordinator.data.targets),
        "active_targets": sorted(target.value for target in coordinator.data.active_targets),
        "conflict_count": coordinator.data.conflict_count,
        "conflict_history": [
            conflict.to_dict() for conflict in coordinator.conflict_history
        ],
    }
