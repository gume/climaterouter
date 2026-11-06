# Testing Plan

## 1. Test layers

| Layer | Scope | Tooling |
|---|---|---|
| Unit | Pure routing, hysteresis, override helpers, conflict classification | `pytest`, no HA runtime |
| Integration | Config flow, coordinator, entity state, service calls, handover, persistence | `pytest-homeassistant-custom-component` |
| Manual | Real VTherm + Scheduler + HA instance | HA test instance / dev container |
| Static | Lint, format, manifest, HACS | `ruff`, `hassfest`, HACS action |

Coverage targets:

- `router.py`: 90%+.
- Overall integration: 80%+.
- Every conflict type and handover transition has at least one test.

## 2. Test fixtures

`tests/conftest.py`:

- `hass` from `pytest-homeassistant-custom-component`.
- `enable_custom_integrations` autouse fixture.
- A mock climate platform with two entities (`climate.test_radiator`, `climate.test_ac`) that:
  - supports configurable `hvac_modes`, `preset_modes`, `min_temp`, `max_temp`, `target_temp_step`;
  - records every service call (service, data, context);
  - can be set to `heating`, `cooling`, `idle`, `off`, `unavailable`;
  - can simulate delayed state transitions and failures.
- Mock outdoor sensor (`sensor.test_outdoor`) with controllable state/timestamp.
- Mock manual switch (`input_boolean.test_manual`).
- A config entry factory with sensible defaults.
- `freeze_time` / `async_fire_time_changed` helpers for override and timeout tests.

Example mock climate skeleton:

```python
class MockClimate(ClimateEntity):
    _attr_should_poll = False

    def __init__(self, name: str) -> None:
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
        self._attr_preset_modes = ["none", "eco", "comfort", "boost", "frost"]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
        )
        self._attr_target_temperature = 20.0
        self._attr_current_temperature = 19.0
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_preset_mode = "comfort"
        self._attr_hvac_action = HVACAction.IDLE
        self.calls = []

    async def async_set_temperature(self, **kwargs):
        self.calls.append(("set_temperature", kwargs))
        self._attr_target_temperature = kwargs["temperature"]
        self.async_write_ha_state()

    # ... set_hvac_mode, set_preset_mode, turn_on/off
```

## 3. Unit test matrix (`tests/test_router.py`)

| Test | Input | Expected |
|---|---|---|
| `test_route_ac_above_mild` | no current, 10 °C, cold=7, mild=9 | AC, `outdoor_mild` |
| `test_route_radiator_at_or_below_cold` | no current, 7 °C | radiator, `outdoor_cold` |
| `test_route_deadband_no_history` | no current, 8 °C | radiator, `deadband_default` |
| `test_route_deadband_holds_ac` | current AC, 8 °C | AC, `hysteresis` |
| `test_route_deadband_holds_radiator` | current radiator, 8 °C | radiator, `hysteresis` |
| `test_route_ac_to_radiator_at_cold` | current AC, 6 °C | radiator |
| `test_route_radiator_to_ac_above_mild` | current radiator, 10 °C | AC |
| `test_route_manual_switch_forces_ac` | switch on, 0 °C | AC, `manual_switch` |
| `test_route_manual_switch_forces_radiator` | switch on, 20 °C, on_target=radiator | radiator |
| `test_route_override_beats_switch` | select=radiator, switch on=ac | radiator, `manual_route` |
| `test_route_cool_forces_ac` | mode=cool, 0 °C | AC, `hvac_mode_cool` |
| `test_route_off_wins` | mode=off, switch on | no targets, `off` |
| `test_route_outdoor_stale_holds_last` | stale, current AC | AC, `fallback_outdoor` |
| `test_route_outdoor_stale_no_history` | stale, no current | radiator |
| `test_route_unavailable_target_fallback` | route AC, AC unavailable, fallback true | radiator, `fallback_unavailable` |
| `test_route_unavailable_no_fallback` | route AC, AC unavailable, fallback false | no target / error |
| `test_boost_targets_both` | boost active | both |
| `test_override_expiry_helper` | until in past | expired |
| `test_override_baseline_preset` | baseline preset comfort | restore preset |
| `test_override_baseline_temperature` | baseline temp 21 | restore temp |
| `test_conflict_guard_allowed` | guard=window | no conflict |
| `test_conflict_setpoint_mismatch` | expected 21, actual 24, tol 0.2 | conflict |
| `test_conflict_within_tolerance` | expected 21, actual 21.1, tol 0.2 | no conflict |
| `test_conflict_both_targets_on` | both on, boost off | conflict |
| `test_conflict_inactive_target_on` | radiator on, active AC | conflict |
| `test_conflict_underlying_timed_preset` | timed preset active | underlying_override |

## 4. Integration test matrix

### 4.1 Config flow (`test_config_flow.py`)

| Test | Expected |
|---|---|
| Happy path | Entry created, unique ID set, device/entities created. |
| Same radiator/AC entity | Form error, no entry. |
| Invalid domain | Form error. |
| Missing outdoor sensor | Form error. |
| Non-temperature outdoor sensor | Warning/confirmation path. |
| `cold > mild` | Form error. |
| Duplicate pair | Abort `already_configured`. |
| Options change thresholds | Entry reloads, coordinator uses new values. |
| Reconfigure entities | Entry reloads, unique ID updated/rejected appropriately. |

### 4.2 Routing and forwarding (`test_climate.py`)

| Test | Expected |
|---|---|
| `set_temperature` with route radiator | Only radiator receives `set_temperature`. |
| `set_temperature` with route AC | Only AC receives it. |
| `set_preset_mode` | Active target receives preset; desired temp cleared. |
| `set_hvac_mode(off)` | Both targets receive `off`; pending canceled. |
| `set_hvac_mode(cool)` | AC receives `cool`; radiator is stopped if active. |
| `turn_on` | Active target receives `heat`. |
| `turn_off` | Both targets off. |
| Unsupported preset | `HomeAssistantError` with available presets. |
| Unsupported mode | Fallback or error as configured. |
| Redundant command | Not forwarded if target already matches. |
| State mirror | `current_temperature`, `target_temperature`, `preset_mode`, `hvac_mode`, `hvac_action` match active target. |
| Optimistic window | Desired value shown briefly, then actual. |
| Attributes | Active/pending target, route reason, desired/actual values present. |

### 4.3 Handover (`test_handover.py`)

| Test | Expected |
|---|---|
| Route changes while old heating | State `PENDING`; no `off` sent; binary sensor on. |
| Old becomes idle | Wait `handover_idle_confirm`, then `off` old. |
| Old off confirmed | New target configured after old off. |
| Command order | `set_hvac_mode` before `set_preset_mode`/`set_temperature`. |
| Pending command | Latest desired applied to new target. |
| Route reverts while pending | No `off`; desired applied to old target. |
| `off` while pending | Pending canceled; all off. |
| `cool` while pending | Old stopped; AC configured. |
| Old does not report off | Handover aborted; conflict; new target not turned on. |
| New target fails | Conflict; old stays off; fallback if configured. |
| `min_route_dwell` | No second handover before dwell. |
| Unknown `hvac_action` | Treated as active; handover waits. |
| Startup one target heating | Adopted; no `off` during reconciliation. |
| Startup both heating | Conflict; no forced off. |
| Startup both idle | Non-route target off if enabled. |
| Restart during handover | Reconciled from actual states, not persisted active target. |

### 4.4 Manual override (`test_override.py`)

| Test | Expected |
|---|---|
| Start temperature override | Active target receives temp; binary sensor on; remaining > 0. |
| Start preset override | Active target receives preset; desired temp cleared. |
| Expiry | Baseline restored; binary sensor off; event fired. |
| Cancel | Baseline restored immediately; event `cancelled`. |
| `off` during override | Override canceled; all off; event `off`. |
| Schedule command during override | Baseline updated; override continues (`hold`). |
| Override during handover | Applied to new target after handover. |
| Override survives restart | Absolute deadline restored; baseline restored on expiry. |
| Expired during restart | Baseline restored immediately. |
| Second override | Baseline preserved; value/duration replaced. |
| Invalid duration | `ServiceValidationError`. |
| Both temp and preset | Validation error. |
| Underlying guard during override | Guard wins; override remains. |

### 4.5 Conflicts (`test_conflicts.py`)

| Test | Expected |
|---|---|
| Direct setpoint change | Conflict `setpoint_mismatch`, event, sensor on. |
| Direct preset change | Conflict `preset_mismatch`. |
| Direct mode change | Conflict `hvac_mode_mismatch`. |
| Own service call | No conflict. |
| Settle window | No conflict during settle. |
| Guard preset safety/window/power | No conflict; guard attribute. |
| Underlying timed preset | `underlying_override`, no proxy timer. |
| Non-selected idle target on | Conflict; turned off if enabled. |
| Non-selected active target on | Conflict; not interrupted. |
| Both on, one idle | Conflict; idle one off if enabled. |
| Both on, both active | Conflict; wait. |
| Conflict clears | Binary sensor off after `conflict_clear_after`. |
| `reassert` policy | One reassert, then stop. |
| `adopt` policy | Desired updated, conflict cleared. |
| `adopt` guard | Not adopted. |
| Unavailable target | Fallback/offline; conflict. |
| Outdoor stale | Binary sensor on; route held. |
| Manual switch stale | Binary sensor/attribute; last state held. |
| Target temperature mismatch | Diagnostic sensor on. |

### 4.6 Services and diagnostics (`test_services.py`, `test_diagnostics.py`)

| Test | Expected |
|---|---|
| `set_manual_override` missing value | `ServiceValidationError`. |
| `set_manual_override` target not proxy | `ServiceValidationError`. |
| `cancel_manual_override` no override | No-op / clear error. |
| `set_route_override` valid | Select state changes, route recalculated. |
| `clear_route_override` | Back to auto. |
| `set_boost` disabled | `ServiceValidationError`. |
| `set_boost` enabled, incompatible modes | Rejected. |
| `set_boost` enabled, valid | Both targets active, sensor on, expiry works. |
| `recalculate` | Route re-evaluated, event if changed. |
| `clear_conflicts` | UI conflict flag cleared, underlying unchanged. |
| `force_handover` while steady | `ServiceValidationError` / nothing to do. |
| `force_handover` while pending | old target switched off, new target started without waiting for idle. |
| Diagnostics | Contains config, snapshot, targets, conflicts, no exceptions. |
| Event payloads | Required keys present. |

### 4.7 Card-facing VTherm attributes (`test_vt_display.py`)

| Test | Expected |
|---|---|
| No active targets | No VTherm attributes. |
| Active `over_switch` target | `is_over_switch`, `power_percent`, managers and curated `specific_states` are forwarded. |
| Lock configured on the target | `is_lock_configured`, `lock_manager` and `specific_states.is_locked` are **not** forwarded. |
| Boost / both targets active | The target with a regulation percentage supplies the gauge. |
| Active `over_climate` target | No `power_percent`, matching the real VTherm. |
| Plain climate target | No VTherm attributes. |

## 5. Manual acceptance tests

### 5.1 Scheduler time scheme

1. Configure Scheduler Card with `include: climate.climaterouter` and exclude both VTherms.
2. Create a time scheme:
   - 06:00 heat / comfort;
   - 08:00 heat / eco;
   - 22:00 off.
3. Verify:
   - commands arrive at the proxy;
   - only the selected VTherm receives them;
   - `sensor.route_reason` and `sensor.active_target` match the outdoor conditions;
   - no underlying VTherm appears in Scheduler's entity list.

### 5.2 Outdoor handover

1. Set outdoor sensor above `mild_threshold` while radiator is heating.
2. Verify `binary_sensor.handover_pending` is on and radiator keeps heating.
3. Let radiator become idle.
4. Verify radiator receives `off`, then AC receives mode/preset/temperature.
5. Verify no gap where both are on (unless boost).
6. Verify `sensor.last_handover` updates.

### 5.2a Forced handover and commands during a pending handover

1. Make the old target stay active so the handover stalls in `pending`.
2. Set a new target temperature on the proxy; verify the **active** target receives it immediately and the proxy
   keeps showing it after the settle window, while the pending target still gets it when it starts.
3. Press `button.<name>_force_handover` (or call `climaterouter.force_handover`); verify the old target is sent
   `off` and the new target starts without waiting for `handover_idle_confirm`.
4. Verify `sensor.last_handover` updates and the button becomes unavailable once no handover is in progress.

### 5.2b Equinox card on the proxy

1. Point an Equinox card at `climate.<name>` and set `hide_lock_button: true`.
2. With the radiator active, verify the power gauge shows `power_percent` and the state icons reflect the active
   target's window/presence/safety messages.
3. Hand over to the AC; verify the gauge disappears (VTherm `over_climate` has no regulation percentage) and the
   card still shows mode/preset/temperature.
4. Verify the card has no lock button and no `is_lock_configured` attribute is exposed by the proxy.

### 5.2c Native ClimateRouter lock

1. Enable **native lock** in the integration options, set a 4–8 digit code and a short auto-relock delay
   (for example 15 s), then reload the entry.
2. Verify `lock.<name>_lock` exists and is unlocked.
3. Call `climaterouter.lock` (or `lock.lock`) and verify the entity shows locked.
4. Try `climate.set_temperature` from a dashboard user and from an automation/script. With **Block commands from
   users** / **Block commands from automations** enabled, the blocked source gets an error and the target does not
   change; the other source still works.
5. Call `climaterouter.unlock` with a wrong or missing code; verify the call fails and the lock stays locked, then
   unlock with the right code.
6. Wait for the auto-relock delay; verify the entity locks itself and commands are blocked again.
7. Unlock, restart HA before the delay expires; verify the lock comes back after the remaining delay (the deadline
   is persisted).
8. Verify the proxy climate does **not** expose `is_lock_configured`, `lock_manager` or `is_locked`.
9. Disable the native lock in options; verify the lock entity disappears and commands are accepted again.

### 5.3 Manual override

1. Start a 30-minute temperature override at 22.5 °C.
2. Verify `binary_sensor.manual_override` and `sensor.override_remaining`.
3. Change the schedule during the override; verify the baseline updates but the override continues.
4. Let it expire; verify the latest schedule preset/temperature is restored.
5. Repeat with a preset override.
6. Restart HA mid-override; verify remaining time and restore behavior.

### 5.4 Conflict detection

1. Directly set `climate.vtherm_ac` to 25 °C.
2. Verify `binary_sensor.conflict` on, event fired, log warning, attributes show expected/actual.
3. Wait for the conflict to clear after the next proxy command.
4. Open a window (VTherm window detection); verify guard, not conflict.
5. Turn on the non-selected VTherm; verify conflict and optional idle-off.

### 5.5 Both targets on

1. Manually turn on both VTherms.
2. Verify conflict; if one is idle and `auto_resolve_idle_targets`, it is turned off.
3. If both heating, verify neither is interrupted and the conflict remains.

### 5.6 Stale inputs

1. Make the outdoor sensor unavailable.
2. Verify `binary_sensor.outdoor_sensor_stale`, route holds, no flapping.
3. Make the manual switch unavailable; verify last state held and diagnostic attribute.

### 5.7 Restart

1. Restart HA with a route active.
2. Verify startup reconciliation does not turn off a heating target.
3. Verify desired state/override restored.
4. Verify no duplicate commands/loops in logs.

## 6. CI

```yaml
name: CI
on:
  push:
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements_test.txt
      - run: ruff check .
      - run: ruff format --check .

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements_test.txt
      - run: pytest --cov=custom_components.climaterouter --cov-report=term-missing

  hassfest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: home-assistant/actions/hassfest@master

  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with:
          category: integration
```

Add the workflows in M1 when `manifest.json` and the package exist, so the initial planning commit does not fail CI.

## 7. Test data and time control

- Use `freezegun` or HA's `async_fire_time_changed` for:
  - override expiry;
  - `handover_idle_confirm`;
  - `off_confirm_timeout`;
  - `settle_time`;
  - `conflict_clear_after`;
  - `min_route_dwell`;
  - stale sensor thresholds.
- Avoid real `asyncio.sleep` in tests; use HA's time helpers.
- Use UTC datetimes in stored state; convert for display only.

## 8. Definition of done for tests

- All unit and integration tests pass on current HA stable.
- `ruff` and `ruff format --check` pass.
- `hassfest` and HACS validation pass.
- Manual acceptance checklist completed on a real VTherm + Scheduler setup.
- No warnings/errors in the HA log during a 24-hour soak test.
- No service-call loops when an underlying VTherm is changed directly.
