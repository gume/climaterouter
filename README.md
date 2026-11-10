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

**M1–M6 implemented, plus the 0.8.x proxy rework (current version 0.8.6).** The integration package provides the config flow, proxy climate
entity, outdoor routing, safe handover, proxy-owned manual mode/timer, conflict detection, feature-flagged boost,
two separate locks, status entities, services and diagnostics. See [`docs/HANDOVER.md`](docs/HANDOVER.md) for the
exact state, test results, known gaps and next steps.

## Why a proxy?

Scheduler Component works with a single climate entity. A radiator and an air conditioner are two separate
climate entities, each with its own VTherm regulation. The proxy gives Scheduler and the user a stable,
single-entity interface, while keeping the two VTherms independent and fully functional.

The proxy is deliberately thin:

- It selects a target using outdoor temperature, an optional route override, and explicit HVAC-mode intent.
- It forwards `set_temperature`, `set_hvac_mode`, and `set_preset_mode` to the selected target only.
- It never turns off a target that is actively heating/cooling just because the route changed.
- It reads current/target temperature and preset from the active target and mirrors them.
- It detects direct changes made to the underlying VTherms and reports conflicts instead of silently fighting them.

### Lovelace cards (Equinox / VTherm)

The proxy forwards a **read-only** subset of the active target's VTherm attributes, so cards that render VTherm
extras (for example Equinox) can show the radiator's power percentage and similar status. The AC is an
`over_climate` thermostat and has no regulation percentage, so the power gauge only appears while the radiator is
active.

VTherm identity-detection keys (the `is_*_configured` flags and `specific_states`) are **off by default**. They
make some cards switch into their full VTherm mode, which renders controls backed by `versatile_thermostat.*`
services that cannot run on the proxy. Enable **Expose VTherm identity-detection attributes** in the options only
for a card that needs them.

The Equinox **lock button still cannot drive the proxy's lock**: Equinox calls
`versatile_thermostat.lock`/`unlock` on the card entity, and those services only work on real VTherm entities.
Keep `hide_lock_button: true` on the card when it targets `climate.climaterouter` and use the UI lock entity
`lock.climaterouter_lock` (or `climaterouter.lock` / `climaterouter.unlock`) instead. The UI lock only blocks
user-initiated commands; schedule and automation traffic keeps running. See
[`docs/HANDOVER.md`](docs/HANDOVER.md) §3.9 and §3.10.

## Planned capabilities

| Capability | Summary |
|---|---|
| One climate entity | Scheduler/UI see `climate.climaterouter`; no scheduler changes required. |
| Temperature-based routing | Outdoor sensor plus optional `select` override; hysteresis and minimum dwell time. |
| Safe handover | Route change is deferred until the old target is idle; old target is turned off before the new one starts. |
| Manual mode | Moving the temperature/preset or `climaterouter.enter_manual_mode` starts proxy-owned manual mode with an optional timer; additional moves do not reset it. While it is active, scheduler/automation moves are remembered but not applied, and `return_to_schedule` (or timer expiry) returns to the latest schedule state. A direct user move on the VTherm card itself is adopted into manual mode. Survives handover/restart. |
| Observability | Binary sensors and sensors for active target, pending handover, manual mode, boost, stale inputs, conflicts, and last handover. |
| Conflict detection | Detects direct changes to either VTherm, both-targets-on, unavailable targets, and stale inputs; `monitor` by default, with `reassert`/`adopt` policies and guarded states excluded. |
| Boost | `climaterouter.set_boost` runs both targets for a bounded time when `boost_enabled` is on; heat-only, both targets must be available, and ending boost hands back to single-target routing. |
| AC fan proxy | The AC fan mode is mirrored, stored while the AC is inactive, and applied or replayed only when the AC is active. Fan changes do not start manual mode. |
| AC idle bypass | Optional: while the AC VTherm reports idle in heat mode, write a `frost`/`eco`/`comfort` preset temperature to the device thermostat below it. The VTherm restores its own setpoint when heating resumes. |
| Velair | Optional: pause Velair when manual mode starts and resume automatic control on the ClimateRouter proxy when it ends. |
| Two locks | Optional `lock.climaterouter_lock` (UI lock, user commands only) with a 4–8 digit code and auto-relock; `manual_blocks_schedule` keeps scheduler/automation moves out of manual mode and remembers the latest schedule state. |

## Planned entities

- `climate.climaterouter` — the only climate entity Scheduler should use.
- `binary_sensor.climaterouter_radiator_active` / `_ac_active` — which route target is selected and on.
- `binary_sensor.climaterouter_heating` / `_cooling` — actual action of the active target.
- `binary_sensor.climaterouter_handover_pending` — route change waiting for the old target to become idle.
- `binary_sensor.climaterouter_manual_mode` — proxy-owned manual mode is active.
- `binary_sensor.climaterouter_boost_active` — both targets are active for a bounded boost.
- `binary_sensor.climaterouter_conflict` — an underlying VTherm or input is inconsistent with the proxy.
- `binary_sensor.climaterouter_outdoor_sensor_stale` — outdoor temperature is unavailable or stale.
- `binary_sensor.climaterouter_ready` — startup reconciliation is complete.
- `sensor.climaterouter_active_target` — `radiator`, `ac`, `both`, or `none`.
- `sensor.climaterouter_pending_target` — pending handover target.
- `sensor.climaterouter_route_reason` — why the current route was chosen.
- `sensor.climaterouter_outdoor_temperature` — mirrored outdoor temperature for dashboards/history.
- `sensor.climaterouter_manual_remaining` — minutes left in manual mode (`0` when the timer is off or expired).
- `sensor.climaterouter_manual_until` — absolute manual-mode deadline.
- `sensor.climaterouter_boost_remaining` — minutes left in boost (`0` when boost is inactive).
- `sensor.climaterouter_last_handover` — timestamp of the last completed handover.
- `sensor.climaterouter_conflict_count` — diagnostic conflict counter.
- `select.climaterouter_route_override` — `auto` / `radiator` / `ac` (manual route override).
- `switch.climaterouter_manual_mode` — enter manual mode / return to schedule.
- `select.climaterouter_manual_timer` — timer length or `off`.
- `sensor.climaterouter_manual_timer_minutes` — selected timer length (diagnostic).
- `button.climaterouter_return_to_schedule`, `_recalculate_route`, `_clear_conflicts`, `_force_handover`.
- `lock.climaterouter_lock` — optional UI lock (only created when `lock_enabled` is on).

## Services

- `climaterouter.enter_manual_mode`
- `climaterouter.set_manual_timer`
- `climaterouter.return_to_schedule`
- `climaterouter.set_manual_override` / `climaterouter.cancel_manual_override` (deprecated aliases)
- `climaterouter.set_route_override`
- `climaterouter.clear_route_override`
- `climaterouter.set_boost` / `climaterouter.cancel_boost` (requires `boost_enabled`)
- `climaterouter.recalculate`
- `climaterouter.clear_conflicts`
- `climaterouter.force_handover`
- `climaterouter.lock` / `climaterouter.unlock` (optional `code`; requires `lock_enabled`)

## Releasing

The repository owner can run `scripts/release.sh` to see a release plan without changing anything. It reads the
version from `manifest.json`, `const.py` and `pyproject.toml` (they must agree), lists the commits since the latest
`v*` tag, includes the open items from `issues.txt`, and previews the generated release notes. `--push` runs the
checks, pushes `main`, creates and pushes the `v<version>` tag, and creates the GitHub release.

## Documentation

- [`docs/HANDOVER.md`](docs/HANDOVER.md) — current implementation state, verification, gaps and next steps.
- [`docs/PLAN.md`](docs/PLAN.md) — scope, routing, handover, override, milestones, acceptance criteria, risks.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — component/state diagrams, module layout, data model.
- [`docs/CONFLICTS.md`](docs/CONFLICTS.md) — conflict sources, detection, policies, resolution matrix.
- [`docs/TESTING.md`](docs/TESTING.md) — unit/integration/manual test plan.
- [`docs/SETUP.md`](docs/SETUP.md) — VTherm, Scheduler, and dashboard configuration.
- [`docs/TEST_ENVIRONMENT.md`](docs/TEST_ENVIRONMENT.md) — Docker-based fake-hardware lab and manual test scenarios.
- [`docs/ADR/`](docs/ADR/) — key architecture decisions.

## Requirements

- Home Assistant 2025.1.4 or newer. The integration is developed against 2026.11, and the automated suite is also
  run against a 2025.1.4 harness. Releases between the two are expected to work but are not individually tested.
- Two existing VTherm climate entities: one radiator (`over_switch`) and one AC (`over_climate`).
- An outdoor temperature sensor.
- Optional route override through the built-in `select.climaterouter_route_override` entity.
- Scheduler Component and Scheduler Card for scheduling.

## Non-goals

- Replacing VTherm's TPI, valve regulation, or device control.
- Implementing a scheduler UI.
- Cloud connectivity or vendor-specific device control.
- Per-target boost strategies beyond activating both targets for a bounded time.
- Automatic arbitration with arbitrary third-party automations; the proxy detects and reports conflicts rather than
  silently fighting them.

## License

MIT. See [`LICENSE`](LICENSE).
