# ClimateRouter — Implementation Plan

Status: **implemented through 0.8.0; see [`HANDOVER.md`](HANDOVER.md) for the live state**
Owner: Gabor Feher
Target: Home Assistant custom integration (`custom_components/climaterouter`)

Key decisions are recorded in [`ADR/`](ADR/README.md): proxy climate entity, deferred handover, proxy-level
override, monitor-first conflict policy, and set-based targets for boost.

> **Historical note (0.8.0):** several parts of this document describe the original design and are kept for
> context. The authoritative description of the current runtime behaviour is [`HANDOVER.md`](HANDOVER.md). In
> particular:
>
> - the optional external manual-routing switch was removed; routing is forced only through the built-in
>   `select.climaterouter_route_override` entity (or the `set_route_override` / `clear_route_override` services);
> - the bounded `set_manual_override` was replaced by proxy-owned **manual mode** with an optional timer
>   (`enter_manual_mode`, `set_manual_timer`, `return_to_schedule`, plus the manual-mode entities);
> - there are two separate locks: the optional accidental-touch UI lock (`lock.<name>_lock`) and the
>   manual/schedule lock (`manual_blocks_schedule`).
>
> Sections below are updated to the 0.8.x state where practical. Mentions of a "manual switch" or the old
> "override" service are historical unless explicitly marked otherwise.

---

## 1. Purpose

ClimateRouter exposes **one ordinary Home Assistant climate entity** to the user and to the Scheduler Component,
and delegates actual heating/cooling to **two underlying Versatile Thermostat (VTherm) entities**:

- a radiator VTherm, normally `over_switch` (TPI-controlled);
- an AC VTherm, normally `over_climate`.

The proxy is intentionally not a thermostat implementation. It is a **routing and arbitration layer**:

- Scheduler/UI call standard `climate.*` services on the proxy.
- The proxy chooses the active target (radiator or AC) from outdoor temperature, a route override, and explicit
  HVAC-mode intent.
- The proxy forwards only the commands that belong to the selected target.
- The proxy mirrors the selected target's current temperature, target temperature, preset, HVAC mode, and action.
- The proxy detects direct changes made to the underlying VTherms and reports them rather than silently fighting.

The VTherms remain responsible for TPI, valve/switch cycling, preset temperatures, window/presence/power/safety
inhibit, and device-level regulation.

---

## 2. Goals and non-goals

### Goals

1. A single `climate.climaterouter` entity that works with Scheduler Component without custom scheduler actions.
2. Deterministic, hysteresis-based routing between radiator and AC.
3. A safe handover that never interrupts an active heating/cooling cycle merely because the route changed.
4. Proxy-owned manual mode (temperature, preset, or mode) with an optional timer that restores the latest
   schedule command.
5. Rich observability: active target, pending handover, manual mode, boost, stale inputs, conflicts.
6. Conflict detection for direct underlying changes, simultaneous targets, unavailable entities, and stale inputs.
7. A data model that already supports two simultaneously active targets, so boost can be added without a rewrite.
8. HACS-installable, testable, and maintainable as a standard HA custom integration.

### Non-goals (v1)

- Replacing VTherm's TPI or device regulation.
- Implementing a scheduler UI or storing schedules.
- Controlling the radiator/AC devices directly.
- Cloud services, vendor APIs, or energy optimization.
- Advanced boost strategies beyond the feature-flagged both-target v1 (per-target, delta/energy triggers).
- Automatic adoption of arbitrary third-party automation changes. The default is detect-and-report, not fight.
- Multi-room grouping. Multiple independent config entries are supported, but there is no group entity.

---

## 3. Assumptions and constraints

| Assumption | Consequence |
|---|---|
| Radiator VTherm supports `heat` and `off`; AC VTherm supports `heat`, `cool`, and `off`. | Proxy exposes `off`/`heat`/`cool`; validates per-target capability. |
| Both VTherms control the same room and should use the same target temperature. | Proxy mirrors the active target and exposes a diagnostic mismatch sensor. |
| VTherm preset names are the common set `none`, `frost`, `eco`, `comfort`, `boost`. | v1 forwards names directly; a preset map can be added later. |
| The outdoor sensor is a numeric temperature sensor. | Staleness and unit conversion are handled explicitly. |
| Scheduler Component calls standard `climate.set_temperature`, `climate.set_hvac_mode`, and `climate.set_preset_mode`. | No scheduler-specific code is required. |
| Only the proxy should be scheduled/automated; underlying VTherms are managed entities. | Direct underlying changes are treated as conflicts. |
| Home Assistant 2025.1+; Python 3.12/3.13. | CI tests current stable HA via `pytest-homeassistant-custom-component`. |
| VTherm's own window/presence/power/safety/central-mode features remain enabled. | Proxy treats those as legitimate guards and does not fight them. |

---

## 4. Terminology

| Term | Meaning |
|---|---|
| **Proxy** | `climate.climaterouter`, the single entity exposed to Scheduler/UI. |
| **Target** | One of the two underlying VTherm entities: `radiator` or `ac`. |
| **Active target** | The target currently receiving forwarded commands. Normally exactly one; two during boost. |
| **Route** | The target selected by routing logic, before handover completes. |
| **Pending target** | A newly selected route that cannot be activated yet because the old target is active. |
| **Handover** | The sequence: wait for old target to become idle → turn old off → configure new target. |
| **Desired state** | The last state requested through the proxy (`hvac_mode`, `preset` or `temperature`). |
| **Baseline** | The desired state snapshot captured when manual mode starts; restored when it ends. |
| **Guard** | A legitimate VTherm-internal restriction (window, presence, power, safety, central mode) that may override the proxy. |
| **Conflict** | An underlying state or input that does not match the proxy's expectation and was not caused by the proxy or a known guard. |

---

## 5. Architecture

### 5.1 Component diagram

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Home Assistant                                                      │
│                                                                     │
│  Scheduler Component / User UI / Automations                        │
│            │  climate.set_temperature / set_hvac_mode / set_preset  │
│            ▼                                                        │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ climate.climaterouter (ClimateRouterEntity)                   │  │
│  │                                                               │  │
│  │  desired state ──► router decision ──► handover state machine│  │
│  │        ▲                    │                    │            │  │
│  │        │                    │                    ▼            │  │
│  │  state mirror ◄──── coordinator ◄──── forwarded service calls │  │
│  └───────────────────────────────────────────────────────────────┘  │
│            │                                      │                 │
│            │ reads states                         │ climate.* calls │
│            ▼                                      ▼                 │
│  ┌──────────────────────┐              ┌──────────────────────┐     │
│  │ climate.vtherm_      │              │ climate.vtherm_ac    │     │
│  │ radiator             │              │                      │     │
│  │ over_switch / TPI    │              │ over_climate         │     │
│  └──────────────────────┘              └──────────────────────┘     │
│            │                                      │                 │
│       radiator switch / TRV                 AC unit / heat pump     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 Ownership boundaries

| Layer | Owns | Must not own |
|---|---|---|
| **ClimateRouter proxy** | Route selection, hysteresis, handover sequencing, cross-target manual mode, conflict detection, scheduler-facing state, diagnostics. | TPI, valve/switch cycling, device regulation, preset temperatures. |
| **Radiator VTherm** | TPI, switch/valve control, preset temperatures, window/presence/power/safety inhibit, device-level state. | Cross-target routing, scheduler-facing entity. |
| **AC VTherm** | AC regulation, mode handling, preset temperatures, window/presence/power/safety inhibit, device-level state. | Cross-target routing, scheduler-facing entity. |
| **Scheduler** | Time slots and commands. | Direct control of underlying VTherms. |
| **User** | Commands through the proxy, manual-mode services, route override. | Direct control of underlying VTherms (discouraged; detected as conflict). |

### 5.3 Data flow

1. A command arrives at the proxy (`async_set_temperature`, `async_set_hvac_mode`, `async_set_preset_mode`,
   `async_turn_on`, `async_turn_off`).
2. The proxy updates its **desired state** and writes an optimistic entity state.
3. The router computes a **route decision** from outdoor temperature, route override, HVAC mode,
   current active target, and target availability.
4. If the route equals the active target, the command is forwarded to that target.
5. If the route differs, the **handover state machine** decides whether it can switch now or must wait.
6. Forwarded service calls are tagged with an internal `Context` so the resulting state changes are not mistaken
   for external interference.
7. State changes from both VTherms update the mirror. The climate entity reports the active target's state, with a
   short optimistic window for commands that are still in flight.
8. A watchdog re-evaluates manual/boost expiry, stale inputs, pending handovers, and conflict clearing.

---

## 6. Configuration model

The integration uses a config flow (no YAML setup). One config entry represents one radiator/AC pair. Multiple
entries are allowed (e.g., living room, bedroom), each with its own device and entities.

### 6.1 Initial config fields

| Field | Type | Default | Required | Notes |
|---|---|---:|---|---|
| `name` | string | `ClimateRouter` | yes | Device/entry name. |
| `radiator_entity_id` | climate | — | yes | VTherm over_switch entity. |
| `ac_entity_id` | climate | — | yes | VTherm over_climate entity. |
| `outdoor_sensor_entity_id` | sensor | — | yes | Temperature device class recommended. |
| `cold_threshold` | float | `7.0` | yes | At or below → radiator. |
| `mild_threshold` | float | `9.0` | yes | Above → AC. |
| `min_route_dwell` | int (s) | `600` | yes | Anti-flapping dwell after a handover. |
| `handover_idle_confirm` | int (s) | `30` | yes | How long the old target must stay idle before switching. |
| `off_confirm_timeout` | int (s) | `30` | yes | Wait for old target `off` confirmation. |
| `startup_grace` | int (s) | `10` | yes | Ignore commands/conflicts while entities initialize. |
| `settle_time` | int (s) | `10` | yes | Suppress conflict checks after proxy commands. |
| `conflict_policy` | `monitor` / `reassert` / `adopt` | `monitor` | yes | Default is observe, not fight. |
| `auto_resolve_idle_targets` | bool | `true` | yes | Turn off a non-selected target when it is idle. |
| `auto_resolve_simultaneous` | bool | `false` | yes | Turn off non-selected target when both are on and idle. |
| `fallback_on_unavailable` | bool | `true` | yes | Use the other target if the selected one is unavailable. |
| `outdoor_stale_after` | int (s) | `3600` | yes | Outdoor sensor staleness. |
| `default_manual_minutes` | int | `60` | yes | Timer for a new manual session; `0` = no timer. |
| `max_manual_minutes` | int | `1440` | yes | Maximum manual timer (24 h). |
| `manual_blocks_schedule` | bool | `true` | yes | Lock B: reject schedule/automation commands while manual. |
| `temperature_tolerance` | float | `0.2` | yes | Setpoint mismatch tolerance. |
| `boost_enabled` | bool | `false` | yes | Enables bounded both-target boost. |
| `lock_enabled` | bool | `false` | yes | Enables the optional `lock.<name>_lock` UI lock. |
| `lock_code` | string | `""` | no | Optional 4–8 digit unlock code. |
| `auto_relock_sec` | int (s) | `0` | yes | Auto-relock delay; `0` keeps the lock unlocked. |
| `expose_vtherm_identity` | bool | `false` | yes | Opt-in VTherm identity attributes for some cards. |

`cold_threshold` must be less than or equal to `mild_threshold`. Setting both to `8.0` reproduces the simple
`> 8 °C → AC; ≤ 8 °C → radiator` rule. The default `7/9` creates a 2 °C deadband to avoid flapping.

The former `manual_switch_entity_id` / `manual_switch_on_target` and `default_override_minutes` /
`max_override_minutes` keys are no longer part of the schema. `RouterConfig.from_mapping` still reads the old
override keys as a fallback for entries created before 0.8.0; they are dropped the next time any form is saved.

### 6.2 Options flow

All three flows (setup, options, reconfigure) share the same sectioned schema: Thermostats, Routing, Manual mode,
Conflicts, Boost, UI lock, and Lovelace display. Setup and reconfigure show every section in one form; the options
flow is a menu where each section is saved immediately and **Finish** closes it.

The options flow validates the same constraints as the initial flow. `async_step_reconfigure` is implemented.
Every save writes a cleaned, schema-only config into `entry.data` and clears `entry.options`, so removed legacy keys
disappear and the coordinator can keep merging `{**entry.data, **entry.options}`.

### 6.3 Validation

- All entity IDs exist and have the expected domain.
- Radiator and AC entities are distinct and are not the proxy itself.
- `cold_threshold <= mild_threshold`.
- Durations and timeouts are non-negative; `default_manual_minutes` must not exceed `max_manual_minutes` unless it
  is `0`.
- The lock code, when set, is 4–8 digits.
- `temperature_tolerance > 0`.
- Unique ID is derived from `radiator_entity_id|ac_entity_id`; duplicate pairs abort with `already_configured`.

Not validated today: the outdoor sensor device class/temperature unit, and VTherm-specific custom attributes. A
non-VTherm climate is accepted so the integration can be tested with mock entities.

### 6.4 Unit handling

- Thresholds are stored in the Home Assistant configured temperature unit.
- Outdoor sensor values are converted to the HA unit if the sensor reports a different unit.
- The proxy exposes temperatures in the HA unit and uses the active target's `target_temp_step` (fallback `0.5`).
- `min_temp`/`max_temp` are the intersection of the active target's limits, with a safe fallback of `7..35 °C`
  equivalent.

---

## 7. Routing logic

### 7.1 Inputs

- `outdoor_temp`: current numeric value, or `None` if unavailable/unknown.
- `outdoor_fresh`: `last_updated` within `outdoor_stale_after`.
- `route_override`: `auto` / `radiator` / `ac` (from `select.climaterouter_route_override`).
- `hvac_mode`: desired mode (`off`, `heat`, `cool`).
- `current_target`: the last active target, used for hysteresis.
- `target_capabilities`: supported HVAC modes and availability.
- `boost_active`: feature-flagged; if true, both targets may be selected.

### 7.2 Precedence

1. **`off` wins.** Turn off all targets; no route is active.
2. **Explicit `cool` wins.** Route to AC; if AC cannot cool, fail the command.
3. **Route override** (`select`) wins over automatic logic.
4. **Outdoor hysteresis** selects AC or radiator.
5. **Fallback** when outdoor is stale/unknown: hold the last route; if no last route, use radiator.
6. **Capability/availability fallback**: if the selected target cannot handle the requested mode or is unavailable,
   use the other target if it can; otherwise no target and a conflict/unavailable state.

`off` and `cool` are explicit user intent and may interrupt an active cycle. Route-driven changes (outdoor,
route override) are subject to the handover rules in section 8.

### 7.3 Hysteresis

```python
def choose_route(inputs) -> RouteDecision:
    if inputs.hvac_mode == OFF:
        return RouteDecision(targets=set(), reason="off")

    if inputs.hvac_mode == COOL:
        return RouteDecision(targets={AC}, reason="hvac_mode_cool")

    if inputs.route_override != AUTO:
        return RouteDecision(targets=route_override_targets(inputs), reason="manual_route")

    if inputs.outdoor_temp is None or not inputs.outdoor_fresh:
        fallback = inputs.current_target or RADIATOR
        return RouteDecision(targets={fallback}, reason="fallback_outdoor")

    # Hysteresis: a target only gives way when the other threshold is crossed.
    if inputs.current_target == AC:
        target = AC if inputs.outdoor_temp > inputs.cold_threshold else RADIATOR
        return RouteDecision(targets={target}, reason="hysteresis")

    if inputs.current_target == RADIATOR:
        target = RADIATOR if inputs.outdoor_temp <= inputs.mild_threshold else AC
        return RouteDecision(targets={target}, reason="hysteresis")

    # No previous target: use the explicit thresholds.
    if inputs.outdoor_temp > inputs.mild_threshold:
        return RouteDecision(targets={AC}, reason="outdoor_mild")
    if inputs.outdoor_temp <= inputs.cold_threshold:
        return RouteDecision(targets={RADIATOR}, reason="outdoor_cold")

    # Deadband with no history: prefer heating safety.
    return RouteDecision(targets={RADIATOR}, reason="deadband_default")
```

This yields:

| Current target | Outdoor | Result |
|---|---|---|
| AC | `> cold_threshold` | stays AC |
| AC | `<= cold_threshold` | radiator |
| Radiator | `<= mild_threshold` | stays radiator |
| Radiator | `> mild_threshold` | AC |
| none | `> mild_threshold` | AC |
| none | `<= cold_threshold` | radiator |
| none | between thresholds | radiator (safe default) |

### 7.4 Route override

`select.climaterouter_route_override` is the only manual routing input:

- `auto` → no override; outdoor hysteresis decides.
- `radiator` / `ac` → force that target.
- `both` is reserved for boost and is rejected unless `boost_enabled` is true.

The override is proxy-owned and can also be set with `climaterouter.set_route_override` or cleared with
`climaterouter.clear_route_override`. The proxy exposes `sensor.route_reason` so the active reason is always
visible. The former external switch input was removed in 0.8.0.

### 7.5 Debouncing and dwell

- Outdoor temperature and route-override changes are evaluated immediately but handover is subject to hysteresis
  and `min_route_dwell`.
- After a completed handover, no new route-driven handover is started for `min_route_dwell` (default 10 min)
  unless the new command is explicit `off`/`cool`.
- The watchdog re-evaluates every 30 seconds, so a missed state event cannot leave the router stuck.

---

## 8. Handover state machine

### 8.1 Core rule

> **Never turn off a target that is actively heating or cooling merely because the route changed.**

A target is considered **active** when:

- `hvac_mode != off`, and
- `hvac_action in {heating, cooling}`.

If `hvac_action` is `unknown`, treat the target as active (conservative). If `hvac_action` is `idle` or `off`, it
is safe to hand over.

Route-driven handovers wait. Explicit `off` and explicit `cool` are user intent and may stop an active cycle
immediately; this exception is logged and surfaced in the handover event.

### 8.2 States

| State | Meaning |
|---|---|
| `STEADY` | Active target matches the route; no handover in progress. |
| `PENDING` | Route changed, but old target is active; waiting for idle. |
| `STOPPING_OLD` | Old target has been sent `off`; waiting for confirmation. |
| `STARTING_NEW` | Old target is off; configuring the new target. |
| `OFF` | Proxy desired mode is off; all targets off. |
| `CONFLICT` | Handover or command failed; manual/automatic resolution required. |
| `BOOST` | Both targets active (feature-flagged). |

### 8.3 Transition table

| From | Trigger | Action | To |
|---|---|---|---|
| `STEADY` | route == active | Apply any desired change to active target. | `STEADY` |
| `STEADY` | route != active, old idle | Send `off` to old target. | `STOPPING_OLD` |
| `STEADY` | route != active, old active | Store pending route/desired, notify. | `PENDING` |
| `PENDING` | old becomes idle for `handover_idle_confirm` | Send `off` to old target. | `STOPPING_OLD` |
| `PENDING` | route reverts to active | Clear pending, apply latest desired. | `STEADY` |
| `PENDING` | explicit `off` | Cancel pending, turn off all. | `OFF` |
| `PENDING` | explicit `cool` | Cancel pending, stop old, route to AC. | `STARTING_NEW` |
| `PENDING` | wait exceeds `handover_max_wait` (if set) | Alert; keep waiting unless force is enabled. | `PENDING`/`CONFLICT` |
| `STOPPING_OLD` | old reports `off` | Configure new target: mode → preset/temperature. | `STARTING_NEW` |
| `STOPPING_OLD` | timeout / unavailable | Abort handover, keep old target, raise conflict. | `CONFLICT`/`PENDING` |
| `STARTING_NEW` | new target accepts commands | Set active = new, clear pending. | `STEADY` |
| `STARTING_NEW` | command failure | Keep old off, mark conflict, try fallback if configured. | `CONFLICT` |
| `OFF` | explicit `heat`/`cool`/`turn_on` | Choose route and configure new target. | `STARTING_NEW`/`STEADY` |
| `CONFLICT` | state matches expected / user clears | Return to `STEADY` or `OFF`. | `STEADY`/`OFF` |

`handover_max_wait` defaults to `0` (wait indefinitely). The plan does **not** force off an active target by
default. If an operator explicitly enables a force timeout, the proxy logs a warning and fires a handover event
before interrupting. **Not implemented in 0.8.x:** use the manual `force_handover` button/service when a handover is
stuck.

### 8.4 Sequence

```mermaid
sequenceDiagram
    participant S as Scheduler/UI
    participant P as ClimateRouter
    participant R as VTherm Radiator
    participant A as VTherm AC

    S->>P: climate.set_temperature(21)
    P->>P: route = radiator
    P->>R: climate.set_temperature(21)
    R-->>P: hvac_action = heating

    Note over P: Outdoor rises above mild_threshold
    P->>P: route = AC; radiator is active → PENDING
    P-->>S: state: radiator active, AC pending

    R-->>P: hvac_action = idle (cycle ended)
    P->>R: climate.set_hvac_mode(off)
    R-->>P: hvac_mode = off
    P->>A: climate.set_hvac_mode(heat)
    P->>A: climate.set_preset_mode(comfort) or set_temperature(21)
    A-->>P: state mirrors AC
    P-->>S: state: AC active
```

### 8.5 Command order on the new target

1. `climate.set_hvac_mode(desired_mode)` — ensure the target is on in the right mode.
2. `climate.set_preset_mode(desired_preset)` **or** `climate.set_temperature(desired_temp)` — never both as a
   final state, because VTherm treats a temperature change as `preset: none`.
3. If both were requested in the same original call, temperature wins (the proxy clears the desired preset when a
   temperature is set).
4. There is no separate command-confirmation timeout today. The settle window and state mirroring cover in-flight
   commands; a failed target is reported through conflicts and handover events.

### 8.6 Pending commands

If a command arrives while a handover is pending:

- The proxy updates its desired state immediately.
- The command is forwarded to the currently active target **and** kept for the pending target, so the old target
  does not keep running on its old setpoint (0.5.0 behaviour).
- The latest desired state is applied to the new target when the handover completes.
- The climate entity reports an optimistic target/preset for a short window, and `binary_sensor.handover_pending`
  is `on`.
- If the route reverts before the handover starts, the latest desired state is applied to the original target.

### 8.7 Startup reconciliation

On startup or integration reload:

1. Load persisted desired state, manual mode, boost, lock state, last route, and last handover timestamp.
2. Wait `startup_grace` for entities to populate.
3. Read both targets.
4. If exactly one is on/heating, adopt it as active; if it does not match the route, set a pending handover.
5. If both are on:
   - boost restored → `BOOST`;
   - one heating → adopt it, turn off the other only if idle;
   - both heating → conflict, do not interrupt;
   - both idle → turn off the non-route target if `auto_resolve_idle_targets`, then activate the route.
6. If neither is on and the restored desired mode is `heat`/`cool`, configure the route target after grace.
7. Mark `binary_sensor.ready` on.
8. Never send `off` to a target that is actively heating during startup reconciliation.

---

## 9. Command forwarding

### 9.1 Desired state model

```python
@dataclass
class DesiredState:
    hvac_mode: HVACMode | None  # off / heat / cool
    setpoint_kind: Literal["preset", "temperature", "none"]
    preset_mode: str | None
    target_temperature: float | None
    fan_mode: str | None  # optional pass-through
    swing_mode: str | None  # optional pass-through
```

Rules:

- `set_hvac_mode(off)` sets `hvac_mode=off`, ends manual mode and boost, cancels a pending handover, and turns
  off all targets.
- `set_hvac_mode(heat)` sets the mode and keeps the existing preset/temperature.
- `set_hvac_mode(cool)` forces AC and sets the mode.
- `set_preset_mode(p)` sets `setpoint_kind=preset`, `preset_mode=p`, clears `target_temperature`.
- `set_temperature(t)` sets `setpoint_kind=temperature`, `target_temperature=t`, clears `preset_mode`.
- If a service call supplies both `temperature` and `hvac_mode`, both are applied; mode first, then temperature.
- If a service call supplies both `preset` and `temperature` (possible through a script), temperature wins because
  it is applied last and VTherm switches to `preset: none`.

### 9.2 Forwarded services

| Proxy method | Underlying call | Notes |
|---|---|---|
| `async_set_temperature` | `climate.set_temperature` | Forward `temperature`; optionally `hvac_mode` first. |
| `async_set_hvac_mode` | `climate.set_hvac_mode` | Validate target supports the mode. |
| `async_set_preset_mode` | `climate.set_preset_mode` | Validate target supports the preset. |
| `async_turn_on` | `climate.set_hvac_mode(heat)` | Uses the current route. |
| `async_turn_off` | `climate.set_hvac_mode(off)` | Immediate; turns off all targets. |
| `async_set_fan_mode` | `climate.set_fan_mode` | Only when the active target supports it; otherwise error/warn. |
| `async_set_swing_mode` | `climate.set_swing_mode` | Same. |
| `async_set_humidity` | `climate.set_humidity` | Same. |

`set_fan_mode`, `set_swing_mode`, and `set_humidity` are optional v1 pass-throughs. They are not required for
Scheduler compatibility and may be deferred to a later milestone if they complicate the state machine.

### 9.3 Forwarding rules

- Forward to the **active target only**, unless boost is active (then fan out to all active targets).
- If the route is pending, queue the desired state and return immediately; do not block Scheduler.
- If the active target is unavailable and `fallback_on_unavailable` is true, use the other capable target and mark
  `route_reason=fallback_unavailable`.
- If no target can handle the request, raise `HomeAssistantError` with a clear message.
- Use `blocking=True` with a timeout for service calls so failures are surfaced.
- Tag every internal call with a `Context` and record its id/parent id for conflict suppression.
- Do not send redundant commands if the target already matches the desired state (idempotence), except when
  reasserting after a conflict.
- Never call underlying VTherm-specific services (`versatile_thermostat.set_timed_preset`, etc.) in v1. The proxy
  uses only standard `climate.*` services. This keeps it compatible with any climate entity and avoids coupling to
  VTherm internals.

### 9.4 State mirroring

| Property | Source |
|---|---|
| `current_temperature` | Active target's `current_temperature`; if both active, average available values; if none, last known or `None`. |
| `target_temperature` | Active target's `temperature`; if a command is in flight/pending, the desired value wins briefly. |
| `preset_mode` | Active target's `preset_mode`; desired value during the optimistic window. |
| `hvac_mode` | Active target's `hvac_mode`; `off` if the proxy is off; desired value during the optimistic window. |
| `hvac_action` | Active target's `hvac_action`; both active → `heating` if any heating, `cooling` if any cooling, else `idle`. |
| `fan_mode` / `swing_mode` | Active target if supported. |
| `min_temp` / `max_temp` / `step` | Active target's values, intersected/fallback. |

The optimistic window is cleared when the underlying state matches the desired state, or after `settle_time`. The
`extra_state_attributes` always expose the actual active-target values separately so debugging is unambiguous.

### 9.5 HVAC mode and preset capability handling

- Proxy `hvac_modes`: `[off, heat]` if the AC target is absent or does not support cooling; otherwise
  `[off, heat, cool]`. No `auto`, `heat_cool`, `dry`, or `fan_only` in v1.
- Proxy `preset_modes`: intersection of the two targets' visible presets plus `none`. If a target lacks a preset,
  the proxy still exposes the intersection; unsupported presets raise a clear error.
- A future `preset_map` option can map proxy names to per-target names.
- If a requested mode is not supported by the routed target, try the other target if capable; otherwise raise.

---

## 10. Entity model

### 10.1 Climate entity

`climate.climaterouter`

- `supported_features`: `TARGET_TEMPERATURE`, `PRESET_MODE`, `TURN_ON`, `TURN_OFF`.
- `hvac_modes`: `off`, `heat`, `cool` (capability-dependent).
- `preset_modes`: intersection of target presets plus `none`.
- `current_temperature`, `target_temperature`, `hvac_mode`, `hvac_action`, `preset_mode` per section 9.4.
- `extra_state_attributes`:
  - `active_target`: `radiator` / `ac` / `both` / `none`
  - `pending_target`: `none` / `radiator` / `ac`
  - `route_reason`
  - `outdoor_temperature`, `outdoor_sensor_stale`
  - `route_override`
  - `desired_hvac_mode`, `desired_preset_mode`, `desired_temperature`
  - `active_target_hvac_mode`, `active_target_preset_mode`, `active_target_temperature`
  - `override` (legacy alias), `manual_mode`, `manual_active`, `manual_until`, `manual_timer_minutes`,
    `manual_remaining_minutes`
  - `ui_lock_active`, `schedule_lock_active`
  - `boost_active`, `boost_until`, `boost_targets`
  - `conflict_count`, `conflicts` (summary list)
  - `handover_state`, `last_handover`
  - `targets`: per-target diagnostic dict (available, mode, action, preset, temperature)
  - `ready`

### 10.2 Binary sensors

| Entity | State | Category | Meaning |
|---|---|---|---|
| `binary_sensor.climaterouter_radiator_active` | on/off | — | Radiator is the selected target and the proxy is not off. |
| `binary_sensor.climaterouter_ac_active` | on/off | — | AC is the selected target and the proxy is not off. |
| `binary_sensor.climaterouter_heating` | on/off | — | Active target `hvac_action == heating`. |
| `binary_sensor.climaterouter_cooling` | on/off | — | Active target `hvac_action == cooling`. |
| `binary_sensor.climaterouter_handover_pending` | on/off | — | A route change is waiting for the old target to become idle. |
| `binary_sensor.climaterouter_manual_mode` | on/off | — | Proxy-owned manual mode is active. |
| `binary_sensor.climaterouter_boost_active` | on/off | — | Both targets are active during a bounded boost. |
| `binary_sensor.climaterouter_conflict` | on/off | diagnostic | At least one unresolved conflict. |
| `binary_sensor.climaterouter_outdoor_sensor_stale` | on/off | diagnostic | Outdoor value is unavailable or older than `outdoor_stale_after`. |
| `binary_sensor.climaterouter_target_mismatch` | on/off | diagnostic | Radiator and AC target temperatures/presets differ beyond tolerance. |
| `binary_sensor.climaterouter_ready` | on/off | diagnostic | Startup reconciliation completed. |

### 10.3 Sensors

| Entity | State | Category | Notes |
|---|---|---|---|
| `sensor.climaterouter_active_target` | `none` / `radiator` / `ac` / `both` | — | Current active target(s). Uses a state-dependent icon. |
| `sensor.climaterouter_pending_target` | `none` / `radiator` / `ac` | — | Pending handover target. Uses a state-dependent icon. |
| `sensor.climaterouter_route_reason` | enum | — | `off`, `outdoor_cold`, `outdoor_mild`, `hysteresis`, `deadband_default`, `manual_route`, `hvac_mode_cool`, `fallback_outdoor`, `fallback_unavailable`, `boost`, `boost_unavailable`, `dwell`, `startup_conflict`. |
| `sensor.climaterouter_outdoor_temperature` | float | — | Mirrored for dashboards/history; unit from HA. |
| `sensor.climaterouter_manual_remaining` | int minutes | — | Minutes left in manual mode; unknown when the timer is off. |
| `sensor.climaterouter_manual_until` | timestamp | — | Absolute manual-mode deadline; unknown when the timer is off. |
| `sensor.climaterouter_manual_timer_minutes` | int minutes | diagnostic | Selected manual timer length. |
| `sensor.climaterouter_boost_remaining` | int minutes | — | `0` when no boost. |
| `sensor.climaterouter_last_handover` | timestamp | diagnostic | Last completed handover; persisted across restarts. |
| `sensor.climaterouter_conflict_count` | int | diagnostic | Total conflicts detected since startup. |
| `sensor.climaterouter_last_command` | timestamp | diagnostic | Last command received through the proxy. |

### 10.4 Buttons, selects, and switches

| Entity | Action |
|---|---|
| `button.climaterouter_return_to_schedule` | End manual mode and restore the latest schedule command. |
| `button.climaterouter_recalculate_route` | Force an immediate route evaluation. |
| `button.climaterouter_clear_conflicts` | Clear resolved/acknowledged conflict state. |
| `button.climaterouter_force_handover` | Complete a pending handover immediately. |
| `select.climaterouter_route_override` | `auto` / `radiator` / `ac` (and `both` only when boost is enabled). |
| `select.climaterouter_manual_timer` | `off` or a timer length in minutes. |
| `switch.climaterouter_manual_mode` | On enters manual mode, off returns to the schedule. |
| `lock.climaterouter_lock` | Optional UI lock (created only when `lock_enabled` is on). |

### 10.5 Device

All entities belong to one HA device:

- Name: config entry name (default `ClimateRouter`).
- Manufacturer: `ClimateRouter`.
- Model: `Virtual climate router`.
- Identifiers: `{(DOMAIN, entry.entry_id)}`.
- `sw_version` from `manifest.json`.
- `has_entity_name = True`; stable unique IDs based on `entry.entry_id`.

---

## 11. Manual mode (proxy-owned)

### 11.1 Purpose

The user can override the temperature, preset, or mode for a bounded or infinite time, then return to the **latest
schedule command**. Manual mode is owned by the proxy, is not mirrored to either VTherm, and must survive a route
handover and a Home Assistant restart.

### 11.2 Services

`climaterouter.enter_manual_mode`

| Field | Type | Required | Notes |
|---|---|---|---|
| `temperature` | float | one of | Manual target temperature. |
| `preset_mode` | string | one of | Must be supported by the active target. |
| `hvac_mode` | `heat`/`cool`/`off` | no | `off` ends manual mode and turns the proxy off. |
| `duration_minutes` | int | no | `0..max_manual_minutes`; omitted/`0` = no countdown. |
| `target` | climate entity | yes | The proxy entity. |

`climaterouter.set_manual_timer` changes or switches off the countdown without changing the setpoint.
`climaterouter.return_to_schedule` ends manual mode and restores the latest schedule command.
`set_manual_override` / `cancel_manual_override` remain as deprecated aliases.

Examples:

```yaml
action: climaterouter.enter_manual_mode
target:
  entity_id: climate.climaterouter
data:
  temperature: 22.5
  duration_minutes: 45
```

```yaml
action: climaterouter.enter_manual_mode
target:
  entity_id: climate.climaterouter
data:
  preset_mode: comfort
  duration_minutes: 90
```

### 11.3 Lifecycle

1. **Start**
   - A user move of the temperature/preset in the UI, or an explicit service call, starts manual mode.
   - Snapshot the current **baseline** desired state (`hvac_mode`, `setpoint_kind`, `preset_mode`,
     `target_temperature`).
   - Use `default_manual_minutes` as the initial timer; `0` means no countdown.
   - Fire `climaterouter_manual_mode_started`.
2. **During**
   - The manual desired state wins over the baseline.
   - Additional user moves update the manual value but **never reset the timer**.
   - Schedule/automation commands update the baseline but do not replace the manual value. While Lock B is active
     (`manual_blocks_schedule`), they are rejected with a clear error.
   - A route handover uses the effective desired state, so the manual value and deadline carry over to the new
     target.
   - Changing the timer fires `climaterouter_manual_timer_changed`.
3. **End**
   - On expiry, an explicit `off`, or `return_to_schedule`, restore the baseline to the active target.
   - If a handover is pending, store the restored baseline and apply it after the handover.
   - Fire `climaterouter_manual_mode_ended` with `cause` (`expired`, `cancelled`, `replaced`, `off`).
4. **Persistence**
   - Store the manual desired state and an absolute UTC deadline. `None` means infinite.
   - On startup, discard an expired session; restore an infinite session as-is.

### 11.4 Standard-card entities

- `switch.<name>_manual_mode` (on = manual, off = return to schedule)
- `select.<name>_manual_timer` (`off` or minutes)
- `button.<name>_return_to_schedule`
- `binary_sensor.<name>_manual_mode`
- `sensor.<name>_manual_remaining`
- `sensor.<name>_manual_until`
- diagnostic `sensor.<name>_manual_timer_minutes`

The climate entity exposes `manual_mode`, `manual_active`, `manual_until`, `manual_timer_minutes`, and
`manual_remaining_minutes`. A timer that is off reports `null`/unknown rather than a fake countdown.

### 11.5 Schedule command vs manual command

The proxy distinguishes user moves by the service-call context (`context.user_id`):

- A call with a `user_id` is a user move and starts/updates manual mode.
- A call without a `user_id` (Scheduler, automation, script) updates the baseline. While manual mode is active and
  `manual_blocks_schedule` is on, Lock B rejects it.
- `return_to_schedule` is deliberately not gated by Lock B, so an explicit return (including an automation) can end
  manual mode. The UI lock (Lock A) still blocks user-initiated service calls while locked.

### 11.6 Manual mode and routing

- Manual mode applies to the active target; it does not change the route by itself.
- If the route changes during manual mode, the normal handover rules apply and the manual state is forwarded to the
  new target after handover.
- If manual mode expires while a handover is pending, the baseline is stored and applied when the handover
  completes.
- `off` always ends manual mode and turns off all targets.

### 11.7 Interaction with VTherm's own timed override

VTherm supports `versatile_thermostat.set_timed_preset` and an optional `manual_override_duration_min`. These are
useful, but they are **per VTherm** and are lost when the proxy hands over to the other target.

Decision:

- The proxy implements the cross-target manual mode itself.
- The proxy does **not** call VTherm-specific timed-preset services in v1.
- If a VTherm's `timed_preset_manager.is_active` is true and the proxy did not start it, the proxy treats it as an
  **underlying override/guard**, exposes it in diagnostics, and does not start a second timer. This is a conflict
  unless the user intentionally uses the VTherm directly.
- For deterministic behavior, the setup guide recommends either:
  - use proxy manual mode and leave VTherm's `manual_override_duration_min` at `0`; or
  - use VTherm's timed override directly and accept that it is target-local (not recommended with routing).

---

## 12. Conflict handling

See [`CONFLICTS.md`](CONFLICTS.md) for the full matrix. This section defines the policy.

### 12.1 Why conflicts are expected

The underlying VTherms remain visible and controllable in Home Assistant. Other automations, dashboards, physical
remotes, VTherm's own features, or a misconfigured Scheduler may change them directly. The proxy must not silently
fight those changes, because that can cause service-call loops, valve/AC chatter, and confusing UI.

### 12.2 Allowed VTherm-internal changes (guards)

The following are legitimate and must not be treated as external conflicts:

- Window detection (`hvac_mode_reason`/`hvac_off_reason` = Window, `window_state`).
- Presence/motion-driven preset changes.
- Power shedding (`preset_mode = power`, `overpowering_state`).
- Safety mode (`preset_mode = safety`, `safety_state`).
- Central mode.
- Auto-start/stop.
- VTherm's own frost protection.

The proxy exposes a `guard` summary in attributes and suppresses conflict/reassert while a guard is active. When
the guard clears, the proxy may reassert the desired state once (subject to `conflict_policy`).

### 12.3 Detection

For each underlying target, compare actual state to the expected state:

- `hvac_mode`
- `preset_mode`
- `temperature` (target)
- availability
- whether the target is on when it should be off
- whether both targets are on without boost

Detection rules:

1. **Own calls are ignored.** Every forwarded service call uses a dedicated `Context`; its id and parent id are
   recorded with a TTL. State changes carrying that context (or within the `settle_time` window) are not
   conflicts.
2. **Expected state snapshots.** After forwarding, store the expected state per target. During the settle window,
   differences are ignored.
3. **Guard detection.** If the VTherm reports a guard reason, classify the change as `guard`, not `conflict`.
4. **External override detection.** A VTherm `timed_preset_manager.is_active` that the proxy did not start is an
   `underlying_override` conflict/guard.
5. **Non-active target on.** If the non-selected target is on, it is a conflict. If it is idle, optionally turn
   it off (`auto_resolve_idle_targets`). If it is heating/cooling, do not interrupt; wait for idle.
6. **Both active.** If both are on and boost is not active, conflict. If one is idle, optionally turn it off; if
   both are active, do not interrupt.
7. **Stale inputs.** Outdoor sensor staleness is an input warning, not a target conflict. It produces a binary
   sensor and holds the last route.
8. **Setpoint mismatch.** Compare with `temperature_tolerance`; VTherm preset changes may legitimately alter the
   target, so compare against the proxy's desired value only when the desired kind is temperature.

### 12.4 Conflict types

| Type | Example | Default policy |
|---|---|---|
| `setpoint_mismatch` | Active VTherm target temp changed directly. | `monitor`; next proxy command reasserts. |
| `preset_mismatch` | Active VTherm preset changed directly. | `monitor`. |
| `hvac_mode_mismatch` | Active VTherm turned off/heat/cool directly. | `monitor`; guard reasons allowed. |
| `inactive_target_on` | Non-selected VTherm is on. | `monitor`; turn off if idle and enabled. |
| `both_targets_on` | Radiator and AC both on without boost. | `monitor`; turn off idle one if enabled. |
| `target_unavailable` | Active VTherm unavailable. | Fallback if enabled; else unavailable. |
| `underlying_override` | VTherm timed preset active. | `monitor`/guard. |
| `input_stale` | Outdoor sensor stale. | Hold route; binary sensor. |
| `target_mismatch` | Radiator and AC target temperatures or presets differ. | Diagnostic only. |
| `handover_failed` | Old target did not report off. | Conflict; keep old, retry later. |

### 12.5 Policies

| Policy | Behavior |
|---|---|
| `monitor` (default) | Mark conflict, fire event, log once, do not change underlying state. The next proxy command reasserts desired state. |
| `reassert` | After `settle_time` + `conflict_grace`, resend the desired state once. If it still differs, keep the conflict and stop fighting to avoid loops. |
| `adopt` | Accept an external setpoint/preset/mode as the new desired/baseline, clear the conflict, and let the schedule override later. Never adopt guard states or non-active target changes. |

Additional independent switches:

- `auto_resolve_idle_targets` (default true): turn off a non-selected target only when it is idle/off, never while
  heating/cooling.
- `auto_resolve_simultaneous` (default false): if both are on and at least one is idle, turn off the idle
  non-selected one. Never interrupt an active cycle.
- `reassert_attempts` is capped at 1 per conflict episode.

### 12.6 Conflict lifecycle

1. Detect → create/update a `Conflict` record with `first_seen`, `last_seen`, `expected`, `actual`, `source_guess`.
2. Fire `climaterouter_conflict_detected` once per new conflict.
3. Expose `binary_sensor.conflict` on, `sensor.conflict_count` increment, attributes list.
4. If the state matches expected for `conflict_clear_after` (default 60 s), clear and fire
   `climaterouter_conflict_cleared`.
5. `button.clear_conflicts` acknowledges and clears the UI flag without changing underlying state.
6. Keep a bounded history (last 50) for diagnostics.

### 12.7 User guidance

- Schedule/automate only `climate.climaterouter`.
- Exclude `climate.vtherm_radiator` and `climate.vtherm_ac` from Scheduler Card's `include` list.
- Do not enable VTherm's "follow underlying temperature changes" unless you accept external-device conflicts.
- Do not enable VTherm's own manual override timer if you use proxy manual mode.
- Use the conflict sensor in dashboards/notifications.
- If a third-party automation must control a VTherm directly, disable the proxy route or accept the conflict.

---

## 13. Boost preparation

Boost means activating both targets at the same time. The v1 logic is implemented and feature-flagged; more
advanced strategies remain future work.

### 13.1 Data model

- The router returns a **set of targets**, not a single target.
- `active_targets` is a set; normal operation has one element, boost has two.
- `sensor.active_target` reports `both`; binary sensors for radiator/AC are both on.
- State aggregation handles both targets (current temperature average, action any-heating/any-cooling).
- Handover is skipped while boost is active; commands fan out to all active targets.

### 13.2 Feature flag and service

- `boost_enabled` defaults to `false`.
- `climaterouter.set_boost` is registered but raises a clear error when disabled.
- Fields: `duration_minutes`, `targets` (`both`; partial boost is future work). The desired temperature/preset
  already on the proxy is forwarded to both targets.
- `climaterouter.cancel_boost` ends it immediately.
- `binary_sensor.boost_active` and `sensor.boost_remaining` are always present.

### 13.3 Safety interlock (v1)

- Boost is allowed only for `hvac_mode: heat` and only if both targets support heat.
- Reject boost if one target is cooling or if the two targets would use incompatible modes.
- Do not boost while a handover is pending; finish the handover or reject.
- Do not boost if either target is unavailable.
- `off` cancels boost.

### 13.4 Future logic

- Trigger only when indoor temperature is below target by a configurable delta.
- Use outdoor temperature and heat-loss estimate to decide whether the second source helps.
- Cap duration and maximum indoor temperature.
- Add energy/power guards.
- Add a `boost` preset interaction (VTherm already has a `boost` preset; avoid confusing the two).
- Add per-target boost (radiator only / AC only / both).

---

## 14. Availability, startup, persistence, and failure handling

### 14.1 Availability

- The proxy is available when the config entry is loaded and at least one target is available (or fallback is
  possible).
- If the active target is unavailable and fallback is disabled, the proxy becomes unavailable/unknown and the
  conflict sensor is on.
- If the outdoor sensor is stale, the proxy remains available; route holds the last known target.

### 14.2 Startup

- `binary_sensor.ready` is off until reconciliation completes.
- Do not forward commands before ready.
- Reconcile without interrupting active heating.
- If both targets are on and both heating, do not choose arbitrarily; mark conflict and let the user decide.

### 14.3 Persistence

Use a versioned `Store` (`climaterouter.<entry_id>`) for:

- desired baseline state;
- manual mode (desired state, baseline, absolute `until`);
- last route;
- boost state;
- last handover timestamp;
- lock state and absolute auto-relock deadline;
- conflict history/counter (optional).

Entity state can use `RestoreEntity`, but the coordinator store is the source of truth. Migrate the store schema
with a version field.

### 14.4 Failure handling

- Service call timeout → log, mark `handover_failed`/`command_failed`, keep the old target.
- Old target does not report `off` → abort handover; do not turn on the new target.
- New target fails to accept commands → keep old target off, mark conflict, try fallback if configured.
- Outdoor sensor unavailable → hold route, mark stale.
- HA restart during manual mode → restore from the absolute deadline; discard an expired session.
- HA restart during handover → reconcile from actual states; never assume the persisted active target is correct.

### 14.5 Logging

- Info: route changes, handover start/complete, manual-mode start/end, boost start/end.
- Warning: conflict detected, handover aborted, target unavailable, stale input.
- Debug: every command, expected/actual state, suppression windows.
- Avoid repeated warnings: log once per conflict episode, then debug.

---

## 15. Home Assistant implementation plan

### 15.1 Repository layout

```text
climaterouter/
├── custom_components/climaterouter/
│   ├── __init__.py            # setup/unload, services, runtime_data
│   ├── manifest.json
│   ├── const.py               # domain, defaults, enums
│   ├── config_flow.py         # sectioned initial/options/reconfigure flows
│   ├── coordinator.py         # event listeners, watchdog, state store
│   ├── router.py              # pure routing + conflict logic
│   ├── models.py              # dataclasses/enums (Target, DesiredState, ...)
│   ├── climate.py             # proxy climate entity
│   ├── vt_display.py          # read-only VTherm attributes for cards
│   ├── entity.py              # shared coordinator entity + DeviceInfo
│   ├── binary_sensor.py       # operation/conflict sensors
│   ├── sensor.py              # active target, reason, manual/boost, etc.
│   ├── switch.py              # manual-mode switch
│   ├── button.py              # return to schedule, recalc, clear, force handover
│   ├── select.py              # route override + manual timer
│   ├── lock.py                # optional UI lock
│   ├── services.py            # service registration/handlers
│   ├── diagnostics.py         # config entry diagnostics
│   ├── services.yaml
│   ├── strings.json
│   └── translations/
│       └── en.json
├── tests/
│   ├── conftest.py
│   ├── test_router.py         # pure routing
│   ├── test_models.py         # config/desired/manual/boost/conflict models
│   ├── test_vt_display.py     # card-facing attribute selection
│   └── test_translations.py   # strings/en.json and field descriptions
├── docs/
│   ├── PLAN.md
│   ├── HANDOVER.md
│   ├── ARCHITECTURE.md
│   ├── CONFLICTS.md
│   ├── TESTING.md
│   ├── TEST_ENVIRONMENT.md
│   ├── SETUP.md
│   └── ADR/
├── .github/workflows/          # CI + hassfest/HACS validation
├── test_environment/           # Docker lab (reference only)
├── hacs.json
├── pyproject.toml
├── requirements_test.txt
├── LICENSE
└── README.md
```

The planned `test_handover.py`, `test_manual_mode.py`, `test_conflicts.py`, `test_config_flow.py`, `test_services.py`,
and `test_diagnostics.py` do not exist yet; they belong to the integration-test work in section 16.2.

### 15.2 Module responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | Enums/dataclasses: `Target`, `DesiredState`, `UnderlyingState`, `ManualMode`, `BoostState`, `Conflict`, `RouterSnapshot`. No HA service calls. |
| `router.py` | Pure functions: `choose_route`, hysteresis, conflict comparison, boost helpers. Unit-testable without HA. |
| `coordinator.py` | Event coordinator; subscribes to state changes; owns the state machine and store; serializes commands with a lock; watchdog. |
| `climate.py` | `ClimateEntity` adapter; properties from snapshot; service methods delegate to coordinator. |
| `vt_display.py` | Read-only VTherm display attributes for Lovelace cards. |
| `binary_sensor.py` / `sensor.py` | Read-only entities from snapshot. |
| `button.py` / `select.py` / `switch.py` / `lock.py` | Small command and lock entities. |
| `services.py` | Service schemas/handlers; resolve target entry; validation; events. |
| `config_flow.py` | Config/options/reconfigure; validation; unique IDs. |
| `diagnostics.py` | Redacted config + snapshot + underlying state + conflict history. |
| `const.py` | Domain, defaults, event names, platform list. |

### 15.3 `manifest.json`

```json
{
  "domain": "climaterouter",
  "name": "ClimateRouter",
  "codeowners": ["@gume"],
  "config_flow": true,
  "documentation": "https://github.com/gume/climaterouter",
  "issue_tracker": "https://github.com/gume/climaterouter/issues",
  "iot_class": "local_polling",
  "integration_type": "hub",
  "version": "0.8.1",
  "requirements": [],
  "dependencies": ["climate", "lock"]
}
```

`after_dependencies` on `versatile_thermostat` is intentionally not used; the integration waits for the configured
entities at runtime instead, so it can be tested with mock climates.

### 15.4 Setup/unload

`__init__.py`:

- `async_setup_entry`:
  - build config from `entry.data` + `entry.options`;
  - create coordinator and load persisted store;
  - `await coordinator.async_initialize()`;
  - store coordinator in `entry.runtime_data` and `hass.data`;
  - forward platforms: `climate`, `binary_sensor`, `sensor`, `select`, `button`, `lock`, `switch`;
  - register the update listener.
- `async_unload_entry`:
  - unload platforms;
  - cancel listeners/timers;
  - remove coordinator.
- `async_setup` (domain-level): register services once.
- `async_migrate_entry`: version migrations.

### 15.5 Config flow

- `async_step_user`: sectioned form with entity pickers, thresholds, and advanced options.
- `async_step_options`: section menu; each section saves immediately, **Finish** closes.
- `async_step_reconfigure`: change entities and all options in one form.
- Unique ID: `f"{radiator_entity_id}|{ac_entity_id}"`.
- Strings/translations for labels, descriptions, field help, errors, and abort reasons.
- Validation helpers shared with the options flow.

### 15.6 Services and events

Service registration in `services.py`; schemas in `services.yaml`; translations in `strings.json`.

Events:

| Event | Data |
|---|---|
| `climaterouter_route_changed` | `entry_id`, `old_target`, `new_target`, `reason`, `outdoor_temperature`. Fires only when the active target changes. |
| `climaterouter_handover_started` | `entry_id`, `from_target`, `to_target`, `reason`, `old_action`. |
| `climaterouter_handover_completed` | `entry_id`, `from_target`, `to_target`, `duration_s`. |
| `climaterouter_handover_aborted` | `entry_id`, `from_target`, `to_target`, `error`. |
| `climaterouter_manual_mode_started` | `entry_id`, `desired`, `duration_minutes`, `until`. |
| `climaterouter_manual_mode_ended` | `entry_id`, `cause` (`expired`/`cancelled`/`replaced`/`off`). |
| `climaterouter_manual_timer_changed` | `entry_id`, `minutes`, `until`. |
| `climaterouter_conflict_detected` | `entry_id`, `conflict` dict. |
| `climaterouter_conflict_cleared` | `entry_id`, `conflict` dict. |
| `climaterouter_boost_started` / `_ended` | `entry_id`, `until`, `targets`. |

The old `climaterouter_override_started` / `_ended` names are no longer fired; use the manual-mode events.

### 15.7 Diagnostics

`async_get_config_entry_diagnostics` returns:

- entry data/options (thresholds, entity IDs);
- `ready`, active/pending target, route reason;
- desired state;
- manual mode state;
- boost state;
- per-target state (mode, action, preset, target/current temp, availability, guard summary);
- conflicts (current + last 50);
- last handover, last command, conflict count;
- integration version.

No secrets are involved; entity IDs and temperatures are safe for user-initiated diagnostics. If desired, entity
IDs can be redacted behind a constant.

### 15.8 Performance and reliability

- Event-driven; no polling of devices.
- `async_track_state_change_event` for the two climates, outdoor sensor, and route override.
- Watchdog every 30 s for manual/boost expiry, stale inputs, pending handovers, and conflict clearing.
- Route evaluation is immediate; explicit command/handover work is serialized.
- Serialize all command/handover work with an `asyncio.Lock`; never run two handovers concurrently.
- Bound conflict/event history to avoid memory growth.
- Avoid state-write loops by tracking internal contexts and expected states.
- Use `asyncio.timeout` around service calls; never block the event loop.
- No custom frontend; use standard entities and Lovelace cards.

---

## 16. Testing strategy

See [`TESTING.md`](TESTING.md) for the full matrix. Summary:

### 16.1 Unit tests (`router.py`, pure)

- Threshold routing and hysteresis.
- Route override precedence.
- `off` and `cool` precedence.
- Capability/availability fallback.
- Override baseline/expiry helpers.
- Conflict comparison/guard classification.
- Boost target set.

### 16.2 Integration tests (HA test harness)

- Config flow happy path, duplicate, invalid entities, options reload.
- Proxy forwards `set_temperature` only to the active target.
- Handover deferred while old target is heating.
- Handover order: old `off` → new `on`/preset/temp.
- Handover abort when old does not report off.
- Pending command applied after handover.
- Override expiry restores the latest schedule command.
- Override survives a handover.
- Override survives restart (absolute deadline).
- Own service calls do not create conflicts.
- Direct underlying change creates a conflict.
- Guard preset (window/safety/power) does not create a conflict.
- Both targets on creates a conflict.
- Non-selected idle target is turned off when enabled.
- Outdoor sensor stale holds route and sets binary sensor.
- Unavailable active target falls back.
- Services validate input and fire events.
- Diagnostics shape.

### 16.3 Manual acceptance tests

- Scheduler time scheme with heat/preset/off actions.
- Outdoor crossing causes a handover only when idle.
- Dashboard override button returns to schedule.
- Direct VTherm change shows conflict.
- HA restart preserves override/route.
- Both-target-on scenario is detected.
- No service-call loops in logs.

### 16.4 CI

- `ruff check` and `ruff format --check`.
- `pytest --cov=custom_components.climaterouter`.
- `hassfest` validation.
- HACS validation action.
- Python 3.12/3.13, current HA stable via `pytest-homeassistant-custom-component`.
- Coverage target: 90%+ for `router.py`, 80%+ overall.

---

## 17. Milestones and acceptance criteria

### M0 — Plan and repository

- [x] Local git repository initialized on `main`.
- [x] README, plan, architecture, conflict, testing, setup, and ADR docs.
- [x] HACS metadata and license.
- [x] Remote assigned (`gume/climaterouter`).

**Acceptance:** the plan is reviewable; no integration code is required yet.

### M1 — Integration skeleton and config flow

- [x] `custom_components/climaterouter` package with manifest, const, `__init__`.
- [x] Config flow, options flow, reconfigure flow.
- [x] Device and placeholder climate entity (available, reports basic state).
- [x] Services registered with schemas; diagnostics; translations.
- [x] Test harness and CI.

**Acceptance:** the integration loads, creates one device/entity, validates entities, reloads on options change,
and passes lint/tests.

### M2 — Core proxy and routing

- [x] `models.py`/`router.py` pure routing with hysteresis, route override, `off`/`cool`.
- [x] State mirroring from active target.
- [x] Forward `set_temperature`, `set_hvac_mode`, `set_preset_mode`, `turn_on`, `turn_off`.
- [x] Active/pending/route-reason sensors and active/heating/cooling binary sensors.
- [x] Unit tests for routing.

**Acceptance:** Scheduler can control the proxy; commands reach only the selected VTherm; routing tests pass.

### M3 — Safe handover

- [x] Handover state machine with idle detection, off confirmation, timeouts.
- [x] Pending command queue.
- [x] Never turn off an active target on route change.
- [x] Handover events and binary sensor.
- [x] Startup reconciliation.
- [x] Live verification in the test HA (through 0.5.0).
- [ ] Integration tests for handover.

**Acceptance:** outdoor/route-override changes wait for idle; old target is off before new target starts; no
interrupted heating in tests.

### M4 — Manual mode (proxy-owned)

- [x] `ManualMode` model with desired state, baseline, absolute deadline, and timer metadata.
- [x] UI moves and `enter_manual_mode`; repeat moves do not reset the timer.
- [x] `set_manual_timer`, `return_to_schedule`, deprecated aliases.
- [x] Manual-mode switch, timer select, return button, binary sensor, remaining/until sensors.
- [x] Manual mode survives handover and restart; schedule commands update the baseline.
- [x] Lock B (`manual_blocks_schedule`) rejects automation commands.
- [x] Live verification in the test HA (through 0.8.0).
- [ ] Integration tests for expiry, cancel, off, restart, handover.

**Acceptance:** a 45-minute manual session returns to the latest schedule command; `off` ends it immediately.

### M5 — Observability and conflict handling

- [x] Conflict detection with own-context suppression and guard classification.
- [x] Conflict binary sensor, count, attributes, events, clear button.
- [x] Stale outdoor sensor detection; the external manual-switch input was removed in 0.8.0.
- [x] Target mismatch diagnostic (setpoints and presets).
- [x] Conflict policies (`monitor`, `reassert`, `adopt`).
- [x] Diagnostics and documentation.
- [x] Tests for external changes, guards, both-on, unavailable (pure classifier).
- [x] Live verification in the test HA (through 0.8.0).
- [ ] Integration tests for policy behaviour and conflict lifecycle (needs the HA test harness).

**Acceptance:** direct VTherm changes are visible and logged, not silently fought; guards are allowed; no loops.

### M6 — Boost preparation and release hardening

- [x] Set-based target model and boost state.
- [x] Feature-flagged `set_boost`/`cancel_boost`, binary/remaining sensors.
- [x] Safety interlock (heat-only, both capable, no pending handover).
- [x] Persistence, expiry and boost start/end events.
- [x] Safe return from boost to single-target routing through the handover state machine.
- [x] Unit tests for the boost model and pure routing.
- [x] README/setup/dashboard examples updated for boost.
- [x] Hassfest and HACS validation workflow (`.github/workflows/validate.yml`).
- [x] Live verification in the test HA (through 0.8.0).
- [ ] Integration tests for boost start/expiry/cancel/resume (needs the HA test harness).
- [x] The Marketplace installs from `main` by commit; tags/releases are optional owner actions.

**Acceptance:** boost is safely disabled by default; enabling it activates both targets for a bounded time; HACS
and hassfest pass.

### M7 — Proxy rework and display hardening (0.7.0–0.8.1)

- [x] Native UI lock with optional code and persisted auto-relock deadline.
- [x] Proxy-owned manual mode and timer replacing the bounded override.
- [x] Split Lock A (UI) from Lock B (manual/schedule).
- [x] Sectioned setup/options/reconfigure flows with brief field descriptions.
- [x] Read-only VTherm display attributes; identity attributes are opt-in.
- [x] State-dependent radiator/AC icons on the target sensors.
- [x] Live verification through 0.8.0; 0.8.1 (`d3af8b4`) was installed through the Marketplace and its target icons verified live.
- [ ] Integration tests for the flows, locks, and manual mode.

---

## 18. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Handover never happens because old target keeps heating. | Route stays stale; AC not used. | Pending sensor + notification; optional `handover_max_wait` alert; do not force off by default. |
| Route flapping around threshold. | Excessive handovers, device wear. | Hysteresis, `min_route_dwell`, debounce. |
| External automations fight the proxy. | Service loops, valve/AC chatter. | Conflict detection, monitor default, reassert cap, docs. |
| VTherm guard changes look like conflicts. | False alarms. | Guard classification using VTherm attributes/reasons. |
| VTherm manual override and proxy override overlap. | Double timers, surprising restore. | Proxy-level override; docs recommend disabling VTherm timer; detect underlying override. |
| Outdoor sensor stale in shoulder season. | Wrong target. | Hold last route; stale binary sensor; fallback target config. |
| Both targets active. | Energy waste, simultaneous heat/cool. | Conflict detection; turn off idle target if enabled; never interrupt active cycle. |
| HA restart during handover. | Inconsistent active target. | Reconcile from actual states; never trust persisted active target. |
| Scheduler targets underlying VTherm. | Proxy bypassed. | Docs and exclude list; conflict sensor. |
| Preset names differ between targets. | Commands fail. | Intersection + clear error; future preset map. |
| `hvac_action` is unreliable. | Handover too early/late. | Treat unknown as active; idle confirmation delay; watchdog. |
| Proxy state lags. | UI snap-back. | Optimistic window + actual values in attributes. |
| Boost logic unsafe. | Both heat/cool at once. | Feature flag off; heat-only interlock; future design. |

---

## 19. Decisions and remaining questions

Most of the original open questions are settled in the 0.8.x implementation:

1. **Manual routing input.** The external switch was removed. Routing is forced only through
   `select.<name>_route_override` (`auto`/`radiator`/`ac`).
2. **Default thresholds.** `cold=7 °C`, `mild=9 °C`, with hysteresis and a 2 °C deadband.
3. **Override ownership.** Proxy-owned manual mode. VTherm timed presets are not used; an underlying timed preset is
   reported as an `underlying_override` conflict/guard.
4. **Conflict default.** `monitor`, with `reassert` and `adopt` as opt-in policies.
5. **HVAC modes.** `off`/`heat`, plus `cool` when the AC target supports it.
6. **Boost scope.** Feature-flagged `both` only, heat-only, both targets available, no pending handover.
7. **Fan/swing/humidity.** Still deferred; the desired-state model carries `fan_mode`/`swing_mode`, but the climate
   entity does not expose those features yet.
8. **Multiple routers.** Multiple config entries are supported; there is no group entity.
9. **Entity naming.** The first entry gets the natural names; later entries get suffixes.
10. **VTherm manual override setting.** Recommend `manual_override_duration_min = 0` when using proxy manual mode.
11. **Scheduler direct-control policy.** Document and enforce "proxy only"; conflicts are the enforcement signal.

Remaining decisions:

- Keep the 2026.11 version floor or add an older-version import fallback?
- Implement `handover_max_wait` (automatic interruption of a stuck handover) or keep the manual force-handover?
- Add fan/swing/humidity pass-through in a later release?
- Upstream Equinox support for a configurable lock service/entity.

---

## 20. Appendix

### 20.1 Scheduler Card configuration

```yaml
type: custom:scheduler-card
include:
  - climate.climaterouter
exclude:
  - climate.vtherm_radiator
  - climate.vtherm_ac
```

The proxy supports the standard climate actions Scheduler exposes:

- heat / cool / off (HVAC mode);
- set temperature;
- set preset (`eco`, `comfort`, `boost`, `frost`, `none`).

### 20.2 Example service calls

Timed temperature manual mode:

```yaml
action: climaterouter.enter_manual_mode
target:
  entity_id: climate.climaterouter
data:
  temperature: 22.5
  duration_minutes: 45
```

Timed preset manual mode:

```yaml
action: climaterouter.enter_manual_mode
target:
  entity_id: climate.climaterouter
data:
  preset_mode: comfort
  duration_minutes: 90
```

Change or switch off the manual timer:

```yaml
action: climaterouter.set_manual_timer
target:
  entity_id: climate.climaterouter
data:
  minutes: 0
```

Force AC:

```yaml
action: climaterouter.set_route_override
target:
  entity_id: climate.climaterouter
data:
  route: ac
```

Return to schedule:

```yaml
action: climaterouter.return_to_schedule
target:
  entity_id: climate.climaterouter
```

### 20.3 Dashboard ideas

- Thermostat card for `climate.climaterouter`.
- Entity cards for radiator active, AC active, heating, cooling, handover pending, manual mode.
- Gauge/history for outdoor temperature and active target.
- Buttons: "Manual 30 min", "Return to schedule", "Force AC", "Auto route".
- Conditional card showing conflicts with `binary_sensor.climaterouter_conflict`.
- Markdown card showing `sensor.route_reason` and `sensor.pending_target`.

### 20.4 Acceptance checklist for the finished integration

- [x] Scheduler can create a time scheme using only `climate.climaterouter`.
- [x] `set_temperature`, `set_hvac_mode`, `set_preset_mode`, `turn_on`, `turn_off` work.
- [x] Outdoor crossing causes a handover only when the old target is idle.
- [x] Old target is off before the new target starts.
- [x] No target is turned off while actively heating/cooling due to a route change.
- [x] Manual mode returns to the latest schedule command.
- [x] Manual mode survives handover and restart.
- [x] Direct underlying changes are detected and visible.
- [x] Guards (window/power/safety/presence) are not fought.
- [x] Outdoor sensor staleness is visible.
- [x] Both-target-on is detected.
- [x] Boost is feature-flagged and safe.
- [ ] Diagnostics, translations, HACS/hassfest, and tests pass (0.8.1 was installed live; the `e025cf4` sensor fix still needs a clean Marketplace reinstall).
