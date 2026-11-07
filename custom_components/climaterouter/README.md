# ClimateRouter integration package

Home Assistant custom integration that presents one virtual `climate` entity and routes it between a radiator
thermostat (VTherm `over_switch`) and an AC thermostat (VTherm `over_climate`).

Implemented milestones (see [`docs/PLAN.md`](../../docs/PLAN.md)):

- **M1** — config/options/reconfigure flow, device, proxy entity, services, diagnostics, translations, tests.
- **M2** — pure routing with outdoor hysteresis, route override, `off`/`cool`, command forwarding,
  state mirroring, status sensors and override/route buttons.
- **M3** — handover state machine: idle detection, off confirmation, timeout, pending command carriage, startup
  reconciliation, handover events and the handover-pending binary sensor.
- **M4** — bounded manual override: temperature/preset/mode service, baseline capture/restore, absolute deadline,
  persistence, handover forwarding, override events, override binary sensor, remaining sensor and cancel button.
- **M5** — conflict detection: own-context suppression, guard classification, setpoint/preset/mode mismatch,
  inactive/both-on targets, unavailable targets, underlying timed presets, monitor/reassert/adopt policies,
  auto-resolve switches, conflict events/history, attributes and the clear button.
- **M6** — feature-flagged boost: bounded both-target operation with heat-only and availability interlocks,
  persistence, boost events, active/remaining entities, and a safe handover back to single-target routing.

## Lovelace cards

The proxy exposes a read-only subset of the active target's VTherm attributes (`vt_display.py`), so Equinox and
similar cards can show the regulation percentage of the active target. VTherm identity-detection attributes
(`is_*_configured` and `specific_states`) are only exposed when the `expose_vtherm_identity` option is enabled,
because they make cards render controls the proxy cannot operate. The lock is deliberately not exposed: Equinox
calls `versatile_thermostat.lock`/`unlock` on the card entity, which a proxy cannot receive. Set
`hide_lock_button: true` when the card targets the proxy.

## Entities

| Entity | Purpose |
|---|---|
| `climate.<name>` | Proxy thermostat used by Scheduler and the UI. |
| `sensor.<name>_active_target` | `radiator`, `ac`, `both` or `none`. |
| `sensor.<name>_pending_target` | Target waiting for the old one to become idle. |
| `sensor.<name>_route_reason` | Why the current route was chosen. |
| `binary_sensor.<name>_handover_pending` | A route change is waiting for an idle target. |
| `binary_sensor.<name>_manual_override` | A bounded manual override is active. |
| `binary_sensor.<name>_boost_active` | Both targets are active during a bounded boost. |
| `binary_sensor.<name>_conflict` | An underlying VTherm differs from the expected state. |
| `sensor.<name>_conflict_count` | Total conflicts detected since startup. |
| `sensor.<name>_override_remaining` | Whole minutes left in the override. |
| `sensor.<name>_boost_remaining` | Whole minutes left in boost. |
| `select.<name>_route_override` | Force `auto`, `radiator` or `ac`. |
| `button.<name>_recalculate_route` | Re-evaluate immediately. |
| `button.<name>_cancel_override` | Cancel the override and restore the baseline. |
| `button.<name>_clear_conflicts` | Acknowledge and clear current conflicts. |
| `button.<name>_force_handover` | Finish a pending handover without waiting for the old target to idle. |
| `sensor.<name>_outdoor_temperature` | Outdoor value the router used. |

## Services

- `climaterouter.recalculate`
- `climaterouter.set_route_override` (`route: auto|radiator|ac`)
- `climaterouter.clear_route_override`
- `climaterouter.set_manual_override` (`temperature`, `preset_mode`, or `hvac_mode` + optional `duration_minutes`)
- `climaterouter.cancel_manual_override`
- `climaterouter.set_boost` (`duration_minutes`, `targets: both`; requires `boost_enabled` and heat mode)
- `climaterouter.cancel_boost`
- `climaterouter.clear_conflicts`
- `climaterouter.force_handover`

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
