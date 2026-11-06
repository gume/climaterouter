# ClimateRouter integration package

Home Assistant custom integration that presents one virtual `climate` entity and routes it between a radiator
thermostat (VTherm `over_switch`) and an AC thermostat (VTherm `over_climate`).

Implemented milestones (see [`docs/PLAN.md`](../../docs/PLAN.md)):

- **M1** — config/options/reconfigure flow, device, proxy entity, services, diagnostics, translations, tests.
- **M2** — pure routing with outdoor hysteresis, manual switch, route override, `off`/`cool`, command forwarding,
  state mirroring, status sensors and override/route buttons.
- **M3** — handover state machine: idle detection, off confirmation, timeout, pending command carriage, startup
  reconciliation, handover events and the handover-pending binary sensor.
- **M4** — bounded manual override: temperature/preset/mode service, baseline capture/restore, absolute deadline,
  persistence, handover forwarding, override events, override binary sensor, remaining sensor and cancel button.
- **M5** — conflict detection: own-context suppression, guard classification, setpoint/preset/mode mismatch,
  inactive/both-on targets, unavailable targets, underlying timed presets, monitor/reassert/adopt policies,
  auto-resolve switches, conflict events/history, attributes and the clear button.

Boost (M6) is not implemented yet; the related entities exist as placeholders so dashboards and tests have stable
IDs.

## Entities

| Entity | Purpose |
|---|---|
| `climate.<name>` | Proxy thermostat used by Scheduler and the UI. |
| `sensor.<name>_active_target` | `radiator`, `ac`, `both` or `none`. |
| `sensor.<name>_pending_target` | Target waiting for the old one to become idle. |
| `sensor.<name>_route_reason` | Why the current route was chosen. |
| `binary_sensor.<name>_handover_pending` | A route change is waiting for an idle target. |
| `binary_sensor.<name>_manual_override` | A bounded manual override is active. |
| `binary_sensor.<name>_conflict` | An underlying VTherm differs from the expected state. |
| `sensor.<name>_conflict_count` | Total conflicts detected since startup. |
| `sensor.<name>_override_remaining` | Whole minutes left in the override. |
| `select.<name>_route_override` | Force `auto`, `radiator` or `ac`. |
| `button.<name>_recalculate_route` | Re-evaluate immediately. |
| `button.<name>_cancel_override` | Cancel the override and restore the baseline. |
| `sensor.<name>_outdoor_temperature` | Outdoor value the router used. |

## Services

- `climaterouter.recalculate`
- `climaterouter.set_route_override` (`route: auto|radiator|ac`)
- `climaterouter.clear_route_override`
- `climaterouter.set_manual_override` (`temperature`, `preset_mode`, or `hvac_mode` + optional `duration_minutes`)
- `climaterouter.cancel_manual_override`
- `climaterouter.clear_conflicts` (placeholder until M5)

All services target the proxy climate entity.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest
```

The unit tests cover the pure routing/domain layer and do not need a Home Assistant runtime.
