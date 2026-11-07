# Setup Guide

This guide describes the intended user setup. It is written for the planned integration and will be updated when
the package is installable.

## 1. Prerequisites

- Home Assistant 2025.1+.
- [Versatile Thermostat](https://github.com/jmcollin78/versatile_thermostat) installed.
- Two VTherm climate entities:
  - `climate.vtherm_radiator` — type `over_switch` (TPI), supports `heat`/`off`.
  - `climate.vtherm_ac` — type `over_climate`, supports `heat`/`cool`/`off`.
- An outdoor temperature sensor, e.g. `sensor.outdoor_temperature`.
- [Scheduler Component](https://github.com/nielsfaber/scheduler-component) and
  [Scheduler Card](https://github.com/nielsfaber/scheduler-card) for scheduling.

Both VTherms should control the same room and use the same room temperature sensor. Configure their preset
temperatures consistently (eco/comfort/boost/frost) so a preset means the same thing on both targets.

## 2. VTherm configuration recommendations

### Radiator (`over_switch`)

- Thermostat type: `over_switch`.
- TPI coefficients tuned for the radiator.
- Presets configured: `eco`, `comfort`, `boost`, `frost`.
- Window/presence/power/safety features as desired.
- Keep VTherm's own manual override timer at `0` if you intend to use the proxy override
  (`manual_override_duration_min: 0`).
- Do not schedule the radiator VTherm directly.

### AC (`over_climate`)

- Thermostat type: `over_climate`.
- Enable AC mode if the unit supports cooling.
- Presets configured consistently with the radiator.
- Window/presence/power/safety features as desired.
- Keep VTherm's own manual override timer at `0` if you use the proxy override.
- Disable "Follow underlying temperature changes" unless you accept that physical remote changes will be detected
  as conflicts.
- Do not schedule the AC VTherm directly.

### Why disable VTherm's timed override?

VTherm's `set_timed_preset` and `manual_override_duration_min` are per-target. If the proxy hands over to the other
target, the timed override does not follow. ClimateRouter therefore keeps the cross-target override in the proxy.
If you prefer VTherm's own timer, use it directly on the active VTherm and accept that it is target-local; the
proxy will surface it as an underlying override.

## 3. Add the integration

1. Install ClimateRouter via HACS (custom repository) or copy `custom_components/climaterouter` into your HA
   configuration directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → ClimateRouter**.
4. Fill in:
   - name;
   - radiator VTherm;
   - AC VTherm;
   - outdoor temperature sensor;
   - thresholds and timings (defaults are fine to start).
5. Finish. A device with `climate.climaterouter` and the diagnostic entities is created.

## 4. Scheduler configuration

Use only the proxy in Scheduler Card:

```yaml
type: custom:scheduler-card
include:
  - climate.climaterouter
exclude:
  - climate.vtherm_radiator
  - climate.vtherm_ac
```

Create schedules with the standard climate actions:

- **Heat** / **Cool** / **Off** — HVAC mode.
- **Set temperature** — e.g. 21 °C.
- **Set preset** — `eco`, `comfort`, `boost`, `frost`, `none`.

The proxy forwards the command to the selected VTherm. If a handover is pending, the command is queued and applied
to the new target when it is safe.

### Example time scheme

| Time | Action |
|---|---|
| 06:00 | Heat, preset comfort |
| 08:00 | Heat, preset eco |
| 17:00 | Heat, preset comfort |
| 22:30 | Off |

In shoulder seasons, the outdoor temperature may route the same schedule to the AC instead of the radiator.

## 5. Route override

`select.climaterouter_route_override` forces routing without an external helper:

- `auto` — automatic outdoor-temperature routing;
- `radiator` — always use the radiator;
- `ac` — always use the AC.

Use it for temporary overrides from a dashboard. The route override is cleared on restart by design; the
`climaterouter.set_route_override` / `climaterouter.clear_route_override` services provide the same control from
scripts and automations.

## 6. Manual override

Use the service from a script or dashboard button:

```yaml
script:
  climaterouter_override_30:
    alias: "ClimateRouter override 22 °C for 30 min"
    sequence:
      - action: climaterouter.set_manual_override
        target:
          entity_id: climate.climaterouter
        data:
          temperature: 22
          duration_minutes: 30
```

Preset override:

```yaml
script:
  climaterouter_comfort_90:
    alias: "ClimateRouter comfort for 90 min"
    sequence:
      - action: climaterouter.set_manual_override
        target:
          entity_id: climate.climaterouter
        data:
          preset_mode: comfort
          duration_minutes: 90
```

Cancel:

```yaml
script:
  climaterouter_cancel_override:
    alias: "ClimateRouter cancel override"
    sequence:
      - action: climaterouter.cancel_manual_override
        target:
          entity_id: climate.climaterouter
```

When the override expires, the latest schedule command is restored. If a handover is pending at expiry, the
baseline is applied after the handover.

## 7. Dashboard example

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.climaterouter

  - type: entities
    title: ClimateRouter status
    entities:
      - binary_sensor.climaterouter_radiator_active
      - binary_sensor.climaterouter_ac_active
      - binary_sensor.climaterouter_heating
      - binary_sensor.climaterouter_cooling
      - binary_sensor.climaterouter_handover_pending
      - binary_sensor.climaterouter_manual_override
      - binary_sensor.climaterouter_conflict
      - sensor.climaterouter_active_target
      - sensor.climaterouter_pending_target
      - sensor.climaterouter_route_reason
      - sensor.climaterouter_outdoor_temperature
      - sensor.climaterouter_override_remaining
      - select.climaterouter_route_override

  - type: horizontal-stack
    cards:
      - type: button
        name: Override 30 min
        icon: mdi:timer-edit-outline
        tap_action:
          action: call-service
          service: climaterouter.set_manual_override
          target:
            entity_id: climate.climaterouter
          data:
            temperature: 22
            duration_minutes: 30
      - type: button
        name: Cancel override
        icon: mdi:timer-off-outline
        tap_action:
          action: call-service
          service: climaterouter.cancel_manual_override
          target:
            entity_id: climate.climaterouter
```

## 8. Notifications

Notify on conflicts:

```yaml
automation:
  - alias: ClimateRouter conflict
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

Notify on handover completion:

```yaml
automation:
  - alias: ClimateRouter handover
    trigger:
      - platform: event
        event_type: climaterouter_handover_completed
    action:
      - service: notify.mobile_app
        data:
          title: ClimateRouter
          message: >
            Switched from {{ trigger.event.data.from_target }}
            to {{ trigger.event.data.to_target }}.
```

## 9. Troubleshooting

| Symptom | Check |
|---|---|
| Scheduler does not see the proxy | Entity is created and available; Scheduler Card `include` has `climate.climaterouter`. |
| Commands go to the wrong VTherm | `sensor.active_target`, `sensor.route_reason`, outdoor sensor value, route override. |
| Handover does not happen | `binary_sensor.handover_pending`; old target may still be heating. Wait for its cycle to end. |
| Override does not return to schedule | `sensor.override_remaining`, baseline attributes, Scheduler command during override. |
| Conflict sensor on | `climate.climaterouter` attributes `conflicts`; check direct VTherm changes or guards. |
| Both VTherms on | Conflict; check `auto_resolve_idle_targets`; do not force off while heating. |
| Outdoor route flapping | Increase the gap between `cold_threshold` and `mild_threshold`; increase `min_route_dwell`. |
| Proxy unavailable | At least one target unavailable and fallback disabled; check VTherm entities. |
| VTherm timed override appears | The proxy treats it as an underlying override; use one override layer consistently. |

## 10. Upgrade notes

- Back up HA before upgrading.
- Read the release notes for config/store schema migrations.
- After upgrading, check **Settings → Devices & services → ClimateRouter → Diagnostics**.
- If the store schema changes, `async_migrate_entry` runs automatically; keep a backup of `.storage/climaterouter.*`
  until the upgrade is verified.
