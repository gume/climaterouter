# ClimateRouter

A Home Assistant custom integration that presents **one ordinary `climate` entity** to the user and to the
[Scheduler Component](https://github.com/nielsfaber/scheduler-component), while routing commands to **two
Versatile Thermostat (VTherm) entities** behind it.

The proxy does not implement heating regulation. It only decides *which* VTherm should be in charge and forwards
standard climate commands to it. TPI, valve/switch cycling, preset temperatures, window/presence/power/safety
inhibit, and device-level regulation stay inside the VTherms.

```text
Scheduler / User UI / Automations
              │
              │  climate.set_temperature
              │  climate.set_hvac_mode
              │  climate.set_preset_mode
              ▼
   ┌─────────────────────────────┐
   │  climate.climaterouter      │  ← one ordinary climate entity
   │  (proxy + routing + state)  │
   └─────────────┬───────────────┘
                 │ selects exactly one target (two when boost is enabled)
        ┌────────┴─────────┐
        ▼                  ▼
┌──────────────────┐  ┌──────────────────┐
│ climate.vtherm_  │  │ climate.vtherm_  │
│ radiator         │  │ ac               │
│ (over_switch)    │  │ (over_climate)   │
└──────────────────┘  └──────────────────┘
```

## Status

**Planning.** This repository currently contains the design, architecture, conflict-handling, testing, and
delivery plan, plus a Docker-based test lab with simulated radiator/AC hardware. The integration package is added
in milestone M1. See [`docs/PLAN.md`](docs/PLAN.md) and [`docs/TEST_ENVIRONMENT.md`](docs/TEST_ENVIRONMENT.md).

## Why a proxy?

Scheduler Component works with a single climate entity. A radiator and an air conditioner are two separate
climate entities, each with its own VTherm regulation. The proxy gives Scheduler and the user a stable,
single-entity interface, while keeping the two VTherms independent and fully functional.

The proxy is deliberately thin:

- It selects a target using outdoor temperature, a manual switch, and explicit HVAC-mode intent.
- It forwards `set_temperature`, `set_hvac_mode`, and `set_preset_mode` to the selected target only.
- It never turns off a target that is actively heating/cooling just because the route changed.
- It reads current/target temperature and preset from the active target and mirrors them.
- It detects direct changes made to the underlying VTherms and reports conflicts instead of silently fighting them.

## Planned capabilities

| Capability | Summary |
|---|---|
| One climate entity | Scheduler/UI see `climate.climaterouter`; no scheduler changes required. |
| Temperature/manual routing | Outdoor sensor plus optional manual switch; hysteresis and minimum dwell time. |
| Safe handover | Route change is deferred until the old target is idle; old target is turned off before the new one starts. |
| Manual override | `climaterouter.set_manual_override` applies a temperature or preset for a duration, then restores the latest schedule command. |
| Observability | Binary sensors and sensors for active target, pending handover, override, boost, stale inputs, conflicts, and last handover. |
| Conflict detection | Detects direct changes to either VTherm, both-targets-on, unavailable targets, and stale outdoor data. |
| Boost preparation | Data model supports multiple active targets; logic is feature-flagged and intentionally not finalized. |

## Planned entities

- `climate.climaterouter` — the only climate entity Scheduler should use.
- `binary_sensor.climaterouter_radiator_active` / `_ac_active` — which route target is selected and on.
- `binary_sensor.climaterouter_heating` / `_cooling` — actual action of the active target.
- `binary_sensor.climaterouter_handover_pending` — route change waiting for the old target to become idle.
- `binary_sensor.climaterouter_manual_override` — timed manual override is active.
- `binary_sensor.climaterouter_boost_active` — boost scaffold is active (feature-flagged).
- `binary_sensor.climaterouter_conflict` — an underlying VTherm or input is inconsistent with the proxy.
- `binary_sensor.climaterouter_outdoor_sensor_stale` — outdoor temperature is unavailable or stale.
- `binary_sensor.climaterouter_ready` — startup reconciliation is complete.
- `sensor.climaterouter_active_target` — `radiator`, `ac`, `both`, or `none`.
- `sensor.climaterouter_pending_target` — pending handover target.
- `sensor.climaterouter_route_reason` — why the current route was chosen.
- `sensor.climaterouter_outdoor_temperature` — mirrored outdoor temperature for dashboards/history.
- `sensor.climaterouter_override_remaining` — minutes left in the manual override.
- `sensor.climaterouter_last_handover` — timestamp of the last completed handover.
- `sensor.climaterouter_conflict_count` — diagnostic conflict counter.
- `select.climaterouter_route_override` — `auto` / `radiator` / `ac` (manual route override).
- `button.climaterouter_cancel_override`, `_recalculate_route`, `_clear_conflicts`.

## Planned services

- `climaterouter.set_manual_override`
- `climaterouter.cancel_manual_override`
- `climaterouter.set_route_override`
- `climaterouter.clear_route_override`
- `climaterouter.set_boost` / `climaterouter.cancel_boost` (feature-flagged)
- `climaterouter.recalculate`
- `climaterouter.clear_conflicts`

## Documentation

- [`docs/PLAN.md`](docs/PLAN.md) — scope, routing, handover, override, milestones, acceptance criteria, risks.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — component/state diagrams, module layout, data model.
- [`docs/CONFLICTS.md`](docs/CONFLICTS.md) — conflict sources, detection, policies, resolution matrix.
- [`docs/TESTING.md`](docs/TESTING.md) — unit/integration/manual test plan.
- [`docs/SETUP.md`](docs/SETUP.md) — VTherm, Scheduler, and dashboard configuration.
- [`docs/TEST_ENVIRONMENT.md`](docs/TEST_ENVIRONMENT.md) — Docker-based fake-hardware lab and manual test scenarios.
- [`docs/ADR/`](docs/ADR/) — key architecture decisions.

## Requirements

- Home Assistant 2025.1 or newer (tested against current stable in CI).
- Two existing VTherm climate entities: one radiator (`over_switch`) and one AC (`over_climate`).
- An outdoor temperature sensor.
- Optional manual switch (`switch`, `input_boolean`, or `input_select`).
- Scheduler Component and Scheduler Card for scheduling.

## Non-goals

- Replacing VTherm's TPI, valve regulation, or device control.
- Implementing a scheduler UI.
- Cloud connectivity or vendor-specific device control.
- Finalized boost/dual-target optimization logic in v1.
- Automatic arbitration with arbitrary third-party automations; the proxy detects and reports conflicts rather than
  silently fighting them.

## License

MIT. See [`LICENSE`](LICENSE).
