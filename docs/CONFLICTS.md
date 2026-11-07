# Conflict Handling

The proxy owns routing, but the underlying VTherms remain visible and controllable. Other automations, users,
physical remotes, VTherm's own features, or a misconfigured Scheduler can change them. This document defines what
the proxy considers a conflict, what it allows, and how it reacts.

## 1. Principles

1. **Do not silently fight.** The default is to detect, expose, and log a conflict. Reasserting is opt-in.
2. **Never interrupt an active cycle.** A target that is heating/cooling is not turned off because of a conflict or
   a route change. Wait for it to become idle.
3. **Allow VTherm guards.** Window, presence, power, safety, central mode, and auto-start/stop are legitimate
   restrictions. The proxy must not override them.
4. **One owner.** Only the proxy should forward commands to the VTherms. Direct changes are conflicts.
5. **No loops.** Reassert at most once per conflict episode; then stop and wait for the user/automation to settle.
6. **Explain.** Every conflict has a type, expected/actual values, a source guess, and a timestamp.

## 2. Sources of conflict

| Source | Example | Detection |
|---|---|---|
| User changes VTherm directly | User sets `climate.vtherm_ac` to 25 °C. | State change without proxy context, not a guard. |
| Automation changes VTherm | Automation calls `climate.set_hvac_mode` on radiator. | Same. |
| Scheduler targets VTherm | Scheduler includes `climate.vtherm_radiator`. | Same; docs recommend excluding. |
| VTherm internal guard | Window opens; VTherm turns off. | `hvac_mode_reason`/`preset_mode`/state attributes. |
| VTherm timed override | `versatile_thermostat.set_timed_preset` called directly. | `timed_preset_manager.is_active`. |
| Physical device change | AC remote changes mode; VTherm follows underlying. | VTherm target/mode changes; `follow_underlying_temp_change`. |
| Both targets on | Radiator and AC both on. | Both `hvac_mode != off`, boost inactive. |
| Non-selected target on | Radiator on while AC is selected. | Target state. |
| Unavailable target | VTherm unavailable after restart. | `unavailable`/`unknown`. |
| Stale input | Outdoor sensor no update for an hour. | `last_updated`. |
| Handover failure | Old target does not report off. | Timeout. |

## 3. Allowed changes (not conflicts)

The following are expected and must not trigger `binary_sensor.conflict`:

- VTherm window detection turning off or changing preset.
- Presence/motion-driven preset changes.
- Power shedding (`power` preset, `overpowering_state`).
- Safety mode (`safety` preset, `safety_state`).
- Central mode.
- Auto-start/stop.
- Frost protection.
- TPI cycling changing `hvac_action` between heating/idle (action changes are normal).
- VTherm self-regulation changing the underlying device setpoint (not the VTherm `temperature` attribute).
- The proxy's own forwarded calls.
- Startup transitions before `ready`.
- Handover transitions while `handover_state` is not `STEADY`.

These are surfaced as `guard` in diagnostics, not as conflicts.

## 4. Detection algorithm

For each target, after the settle window:

```python
def classify(target_state, expected, conflict_policy) -> Conflict | None:
    if not target_state.available:
        return Conflict(type="target_unavailable", ...)
    if target_state.guard:
        return None  # allowed; surface as guard
    if target_state.timed_preset_active and not expected.started_by_proxy:
        return Conflict(type="underlying_override", ...)
    if target_state.hvac_mode != expected.hvac_mode:
        return Conflict(type="hvac_mode_mismatch", ...)
    if expected.setpoint_kind == "temperature" and not close(
        target_state.target_temperature, expected.target_temperature, tolerance
    ):
        return Conflict(type="setpoint_mismatch", ...)
    if expected.setpoint_kind == "preset" and target_state.preset_mode != expected.preset_mode:
        return Conflict(type="preset_mismatch", ...)
    return None
```

Global checks:

```python
if not boost_active and both_targets_on:
    conflict("both_targets_on")
if not boost_active and non_selected_target_on:
    conflict("inactive_target_on")
if outdoor_stale:
    warning("input_stale", "outdoor")
if radiator_temp != ac_temp beyond tolerance:
    diagnostic("target_mismatch")
```

### 4.1 Own-context suppression

Every forwarded service call gets a `Context`. The coordinator stores `context.id` and, if present,
`context.parent_id` for 30 seconds. State-change events with those ids are ignored for conflict purposes.
A settle window (`settle_time`, default 10 s) suppresses comparisons while the target reacts.

### 4.2 Guard detection

Read VTherm custom attributes defensively; they are not part of the standard climate contract:

```python
specific = attrs.get("specific_states", {})
reason = specific.get("hvac_mode_reason") or specific.get("hvac_off_reason")
if reason in {"Window", "Safety", "Power", "Central mode", "Auto-start/stop"}:
    return "guard"
if attrs.get("preset_mode") in {"power", "safety"}:
    return "guard"
if attrs.get("window_state") == "on" or attrs.get("safety_state") == "on":
    return "guard"
if attrs.get("timed_preset_manager", {}).get("is_active"):
    return "underlying_override"
```

If the attributes are absent (non-VTherm climate), skip guard detection.

### 4.3 Source guess

Use, in order:

1. Own context → `proxy`.
2. Guard attributes → `vtherm_guard`.
3. Timed preset active → `vtherm_timed_preset`.
4. Event context `user_id` present → `user`.
5. Event context `parent_id` present but not own → `automation`.
6. No context and no guard → `unknown`.

The source guess is diagnostic only; it does not change the policy.

## 5. Conflict types and default actions

| Type | Severity | Default action | Can auto-resolve? |
|---|---|---|---|
| `setpoint_mismatch` | warning | Mark, log, event; next proxy command reasserts. | No (unless `adopt`). |
| `preset_mismatch` | warning | Mark, log. | No (unless `adopt`). |
| `hvac_mode_mismatch` | warning | Mark, log; guard reasons excluded. | No (unless `adopt`). |
| `inactive_target_on` | warning | Mark; turn off if idle and `auto_resolve_idle_targets`. | Yes, if idle. |
| `both_targets_on` | warning | Mark; turn off idle non-selected if enabled. | Yes, if one idle. |
| `target_unavailable` | error | Fallback if enabled; else proxy unavailable. | Yes, on recovery. |
| `underlying_override` | warning | Mark; do not start a second timer. | When VTherm timer ends. |
| `input_stale` | warning | Hold last route/switch; binary sensor. | When fresh data arrives. |
| `target_mismatch` | info | Diagnostic only. | When temps converge. |
| `handover_failed` | error | Abort handover, keep old target, mark. | On retry/success. |

## 6. Policies

### `monitor` (default)

- Create/update conflict.
- Fire `climaterouter_conflict_detected` once.
- Log at warning once per episode; subsequent changes at debug.
- Do not change underlying state.
- Next proxy command reasserts the desired state naturally.
- Clear when actual matches expected for `conflict_clear_after` (60 s).

### `reassert`

- After `settle_time` + `conflict_grace` (default 15 s), resend the desired state once.
- If the target still differs, keep the conflict and stop reasserting.
- Never reassert while a guard is active or while the target is actively heating/cooling and the mismatch is a mode
  change that would interrupt it.
- Max one reassert per conflict episode.

### `adopt`

- Accept an external `temperature`/`preset`/`hvac_mode` change as the new desired/baseline.
- Clear the conflict.
- Do not adopt:
  - guard changes;
  - non-active target changes;
  - both-targets-on;
  - unavailable/stale states.
- The next schedule command overwrites the adopted state.

### Independent switches

- `auto_resolve_idle_targets` (default true): turn off a non-selected target only if `hvac_action` is `idle` or
  `off`. This prevents a standby target from being left on.
- `auto_resolve_simultaneous` (default false): if both are on and at least one is idle, turn off the idle
  non-selected one. Never interrupt an active cycle.

## 7. Resolution matrix

| Scenario | `monitor` | `reassert` | `adopt` |
|---|---|---|---|
| Active target temp changed | Mark; next command reasserts | Reassert once | Adopt as desired |
| Active target preset changed | Mark | Reassert once | Adopt as desired |
| Active target mode changed | Mark | Reassert once if safe | Adopt as desired |
| Non-active target turned on (idle) | Mark; optional off | Mark; optional off | Mark; optional off |
| Non-active target turned on (heating) | Mark; wait | Mark; wait | Mark; wait |
| Both on, one idle | Mark; optional off idle | Same | Same |
| Both on, both active | Mark; wait | Mark; wait | Mark; wait |
| Guard active | Guard sensor | Guard sensor | Guard sensor |
| Underlying timed preset | Mark/guard | Do not reassert | Do not adopt |
| Target unavailable | Fallback/offline | Fallback/offline | Fallback/offline |
| Outdoor stale | Hold route | Hold route | Hold route |

## 8. Conflict record

```python
@dataclass(frozen=True)
class Conflict:
    key: str  # stable: f"{type}:{target}"
    type: str
    target: Target | None
    expected: Any
    actual: Any
    first_seen: datetime
    last_seen: datetime
    source_guess: str
    resolved: bool
```

- `key` prevents duplicate records for the same ongoing issue.
- `first_seen`/`last_seen` show duration.
- `expected`/`actual` are JSON-safe values.
- Keep the last 50 records in memory and diagnostics.
- `sensor.conflict_count` increments when a new `key` appears.

## 9. Events

```yaml
event: climaterouter_conflict_detected
data:
  entry_id: ...
  conflict:
    key: setpoint_mismatch:ac
    type: setpoint_mismatch
    target: ac
    expected: 21.0
    actual: 24.0
    source_guess: user
    first_seen: "2026-11-06T10:00:00+00:00"
```

`climaterouter_conflict_cleared` has the same shape plus `resolved_at`.

## 10. User-facing guidance

- Use only `climate.climaterouter` in Scheduler and dashboards.
- Exclude the underlying VTherms from Scheduler Card.
- Watch `binary_sensor.climaterouter_conflict`; add a notification automation if desired.
- Do not enable VTherm's "follow underlying temperature changes" unless you accept external device changes.
- Do not use VTherm's timed preset directly while relying on the proxy override.
- If another automation must control a VTherm directly, either:
  - route the automation through the proxy; or
  - accept the conflict and use `monitor` policy; or
  - disable the proxy route while the automation runs.

## 11. Example notification

```yaml
automation:
  - alias: ClimateRouter conflict notification
    trigger:
      - platform: state
        entity_id: binary_sensor.climaterouter_conflict
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: ClimateRouter conflict
          message: >
            {{ state_attr('climate.climaterouter', 'conflicts') }}
```

## 12. Non-goals

- Preventing direct service calls to the underlying VTherms. Home Assistant has no per-entity ACL for that in a
  custom integration. The proxy detects and reports.
- Automatic arbitration with arbitrary third-party logic. The user remains the final authority.
- Resolving simultaneous heating/cooling by force. Safety first: detect, expose, and wait.
