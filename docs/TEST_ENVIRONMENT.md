# Test Environment

This document describes the Docker-based Home Assistant lab used to develop and test ClimateRouter without real
radiator or AC hardware.

The lab has three layers:

1. **`fake_hvac`** — a test-only custom integration that simulates a room, an outdoor sensor, a radiator switch and
   an air conditioner. It is configured from YAML and needs no UI setup.
2. **Versatile Thermostat (VTherm)** — two real VTherm config entries, one `over_switch` radiator and one
   `over_climate` AC, both driven by the fake hardware. VTherm only supports config-flow setup, so this part is done
   once through the UI.
3. **ClimateRouter** — the integration under development, mounted from this repository. It is added as a normal
   config entry and exposes `climate.climaterouter`.

Scheduler Component is added last and should see only the proxy entity.

---

## 1. Prerequisites

- Docker Engine and Docker Compose v2 (`docker compose version`).
- About 1 GB of free disk space for the Home Assistant image and configuration.
- A GitHub account if you install VTherm and Scheduler through HACS (recommended).
- Linux is assumed by the port mapping below. Change the host port in `test_environment/docker-compose.yml` if
  `38123` is already in use.

The repository must be checked out locally because the container bind-mounts both custom components:

```text
test_environment/config                      -> /config
custom_components/climaterouter              -> /config/custom_components/climaterouter (read-only)
test_environment/custom_components/fake_hvac -> /config/custom_components/fake_hvac (read-only)
```

---

## 2. Start Home Assistant

```bash
cd test_environment
docker compose up -d
docker compose logs -f homeassistant
```

Wait for `Home Assistant initialized` in the log, then open <http://localhost:38123>.

On first start:

1. Create the owner account.
2. Skip or complete the onboarding wizard.
3. Confirm that **Settings → Devices & services** shows the `fake_hvac` integration and a `Fake` device (model
   `Fake HVAC Lab`).

If the page does not load, check:

```bash
docker compose ps
docker compose logs --tail=200 homeassistant
```

---

## 3. Fake hardware

`test_environment/config/configuration.yaml` contains the YAML block that creates the simulated system:

```yaml
fake_hvac:
  name: Fake HVAC Lab
  room_temperature: 19.0
  outdoor_temperature: 6.0
  radiator_power_kw: 1.5
  ac_power_kw: 2.5
  loss_coefficient: 0.06
  thermal_mass: 0.5
  update_interval: 5
  time_scale: 60
  simulation_enabled: true
```

The integration imports this block through its config flow and creates these entities:

| Entity | Meaning |
|---|---|
| `sensor.fake_room_temperature` | Simulated room temperature. Also used as the VTherm room sensor. |
| `sensor.fake_outdoor_temperature` | Simulated outdoor temperature. Also used as the VTherm outdoor sensor. |
| `sensor.fake_thermal_power` | Current net thermal power in watts; negative means cooling. |
| `switch.fake_radiator` | Radiator on/off. VTherm `over_switch` controls this. |
| `switch.fake_simulation` | Pause/resume the thermal ticker without stopping Home Assistant. |
| `number.fake_room_temperature_control` | Slider that forces the simulated room temperature. |
| `number.fake_outdoor_temperature_control` | Slider that sets the simulated outdoor temperature. |
| `climate.fake_ac` | Fake AC with `off` / `heat` / `cool`, target temperature and presets. VTherm `over_climate` controls this. |

The two `number` entities are the dashboard-friendly equivalent of `fake_hvac.set_room_temperature` and
`fake_hvac.set_outdoor_temperature`. While the simulation runs, a forced room temperature keeps evolving from the
value you set; turn off `switch.fake_simulation` first if you need it to stay put.

Entity IDs are derived from the names in the integration. If you change the names or already have entities with the
same IDs, check **Developer Tools → States** for the actual IDs and adjust the VTherm setup.

### 3.1 Fake services

All services are under the `fake_hvac` domain and accept an optional `name` when more than one fake system exists.

```yaml
# Set the outdoor temperature (drives ClimateRouter routing and heat loss)
action: fake_hvac.set_outdoor_temperature
data:
  temperature: 12
```

```yaml
# Force the room temperature (useful to make a VTherm go idle)
action: fake_hvac.set_room_temperature
data:
  temperature: 24
```

```yaml
# Pause or resume the simulation ticker
action: fake_hvac.set_simulation
data:
  enabled: false
```

```yaml
# Make a fake sensor unavailable
action: fake_hvac.set_availability
data:
  outdoor: false
```

```yaml
# Fast-forward the thermal model without waiting for real time
action: fake_hvac.advance
data:
  minutes: 30
```

```yaml
# Return to the configured starting state
action: fake_hvac.reset
```

### 3.2 Simulation model

Every `update_interval` real seconds the integration advances the room temperature by:

```text
heat_kw  = radiator_on * radiator_power_kw + ac_power_on * ac_power_kw
loss_kw  = loss_coefficient * (room_temperature - outdoor_temperature)
dT       = (heat_kw - loss_kw) * (seconds / 3600) / thermal_mass
```

`time_scale` converts real seconds into simulated seconds. With the defaults, a 5-second tick advances 5 simulated
minutes. This is intentionally fast: the room reacts in a few real minutes, so routing and handover tests do not
need hours.

The simulation only affects temperatures. ClimateRouter timers (override duration, handover dwell, staleness) use
real time. Use short timer values in the ClimateRouter config entry when testing those features.

### 3.3 Deterministic tests

Pause the simulation when you want full control:

```yaml
action: fake_hvac.set_simulation
data:
  enabled: false
```

Then use `fake_hvac.set_room_temperature` and `fake_hvac.set_outdoor_temperature` to place the system in an exact
state. Resume the simulation when you want VTherm to react dynamically.

---

## 4. Install VTherm

### Option A — HACS (recommended)

1. Open a shell in the container:

   ```bash
   docker compose exec homeassistant bash
   ```

2. Install HACS with the official script:

   ```bash
   wget -O - https://get.hacs.xyz | bash -
   ```

3. Restart Home Assistant:

   ```bash
   exit
   docker compose restart homeassistant
   ```

4. In Home Assistant, go to **Settings → Devices & services → Add integration → HACS**, complete the GitHub device
   authorization, and restart when prompted.
5. Open **HACS → Integrations**, search for **Versatile Thermostat**, open it, and download it.
6. Restart Home Assistant.

### Option B — manual copy

Download a VTherm release and copy only its integration directory into the test config:

```bash
# Example; adjust the version and source path to the release you downloaded
cp -r /path/to/versatile_thermostat/custom_components/versatile_thermostat \
  test_environment/config/custom_components/versatile_thermostat
docker compose restart homeassistant
```

HACS is easier to update and is what the rest of this guide assumes.

---

## 5. Create the two VTherm entities

VTherm does not support YAML configuration. Create both entries once through the UI. The exact labels vary slightly
between VTherm versions; the important fields are listed below.

### 5.1 Radiator VTherm (`over_switch`)

1. Go to **Settings → Devices & services → Add integration → Versatile Thermostat**.
2. Choose the thermostat type **Thermostat over switch** (or the equivalent `over_switch` option).
3. Name it `VTherm Radiator`.
4. Select `switch.fake_radiator` as the switch/actuator.
5. Select `sensor.fake_room_temperature` as the room temperature sensor.
6. Select `sensor.fake_outdoor_temperature` as the outdoor/external temperature sensor.
7. Keep the default cycle duration and TPI settings; the fake radiator is a simple on/off load.
8. Configure presets consistently with the AC:
   - `eco` — 18 °C
   - `comfort` — 21 °C
   - `boost` — 23 °C
   - `frost` — 7 °C
9. Finish and verify that `climate.vtherm_radiator` exists.

If the entity ID differs, use the actual ID everywhere in this guide and in the ClimateRouter config entry.

### 5.2 AC VTherm (`over_climate`)

1. Add another **Versatile Thermostat** entry.
2. Choose **Thermostat over climate** (`over_climate`).
3. Name it `VTherm AC`.
4. Select `climate.fake_ac` as the underlying climate entity.
5. Select `sensor.fake_room_temperature` as the room temperature sensor.
6. Select `sensor.fake_outdoor_temperature` as the outdoor/external temperature sensor.
7. Enable cooling/AC mode if the flow asks; the fake AC supports `heat`, `cool` and `off`.
8. Configure the same presets as the radiator (`eco` 18 °C, `comfort` 21 °C, `boost` 23 °C, `frost` 7 °C).
9. Finish and verify that `climate.vtherm_ac` exists.

### 5.3 Smoke-test VTherm

Before involving ClimateRouter, verify each VTherm can drive its fake device.

**Radiator:**

```yaml
action: climate.set_hvac_mode
target:
  entity_id: climate.vtherm_radiator
data:
  hvac_mode: heat
```

```yaml
action: climate.set_temperature
target:
  entity_id: climate.vtherm_radiator
data:
  temperature: 22
```

The room is 19 °C, so `switch.fake_radiator` should turn on and `sensor.fake_room_temperature` should rise.

**AC:**

```yaml
action: climate.set_hvac_mode
target:
  entity_id: climate.vtherm_ac
data:
  hvac_mode: heat
```

```yaml
action: climate.set_temperature
target:
  entity_id: climate.vtherm_ac
data:
  temperature: 22
```

`climate.fake_ac` should enter `heat` and its compressor should run while the room is below the target.

Turn both VTherms off before continuing:

```yaml
action: climate.set_hvac_mode
target:
  entity_id:
    - climate.vtherm_radiator
    - climate.vtherm_ac
data:
  hvac_mode: "off"
```

---

## 6. Add ClimateRouter

The integration implements milestones M1–M3: config flow, proxy routing and safe handover. It is mounted from this
repository, so code changes only need a container restart.

1. Ensure the container is running and the integration appears under **Settings → Devices & services → Add
   integration → ClimateRouter**. If it does not appear, check that the bind mount exists and restart the
   container.
2. Create an entry with:
   - name: `ClimateRouter`;
   - radiator entity: `climate.vtherm_radiator`;
   - AC entity: `climate.vtherm_ac`;
   - outdoor sensor: `sensor.fake_outdoor_temperature`;
   - thresholds: `cold_threshold: 7`, `mild_threshold: 9`;
   - short test timings, for example:
     - `min_route_dwell: 60`
     - `handover_idle_confirm: 5`
     - `off_confirm_timeout: 15`
     - `startup_grace: 5`
     - `settle_time: 2`
     - `outdoor_stale_after: 300`
     - `default_override_minutes: 1`
     - `max_override_minutes: 5`
3. Finish and verify that `climate.climaterouter` and the diagnostic entities exist.

Until the two VTherms exist, the router can also be pointed directly at `climate.fake_ac` (radiator role) and a
second fake system's AC (AC role). Services on `fake_hvac` then need a `name` field to say which system to change.

If no command has been received yet, the proxy stays off even when an underlying thermostat is on: it adopts that
thermostat's state without sending commands. A plain `set_temperature` while the proxy is off only records the
setpoint; send `set_hvac_mode: heat` (or `cool`) to start a target.

---

## 7. Scheduler

1. Install **Scheduler Component** through HACS (**HACS → Integrations → Scheduler Component**) and restart.
2. Install **Scheduler Card** through HACS (**HACS → Frontend → Scheduler Card**).
3. Add the Scheduler Card resource if HACS did not do it automatically.
4. Add the card to a dashboard:

   ```yaml
   type: custom:scheduler-card
   include:
     - climate.climaterouter
   exclude:
     - climate.vtherm_radiator
     - climate.vtherm_ac
   ```

5. Create a schedule with standard climate actions: **Heat**, **Cool**, **Off**, **Set temperature**, **Set
   preset**.

Scheduler must never target the two VTherm entities directly. Direct changes are treated as conflicts by design.

---

## 8. Test scenarios

The scenarios below assume `climate.climaterouter`, `climate.vtherm_radiator` and `climate.vtherm_ac` exist. Use
**Developer Tools → Actions** to call the services.

### 8.1 Cold route: radiator only

1. Set outdoor temperature to `5`:

   ```yaml
   action: fake_hvac.set_outdoor_temperature
   data:
     temperature: 5
   ```

2. Set the proxy to heat at 21 °C:

   ```yaml
   action: climate.set_hvac_mode
   target:
     entity_id: climate.climaterouter
   data:
     hvac_mode: heat
   ```

   ```yaml
   action: climate.set_temperature
   target:
     entity_id: climate.climaterouter
   data:
     temperature: 21
   ```

3. Verify:
   - `sensor.climaterouter_active_target` is `radiator`;
   - `climate.vtherm_radiator` received the mode and setpoint;
   - `climate.vtherm_ac` stayed `off`;
   - `switch.fake_radiator` cycles as VTherm regulates.

### 8.2 Mild route: AC only

1. Set outdoor temperature to `12`.
2. If the radiator is actively heating, verify:
   - `binary_sensor.climaterouter_handover_pending` is `on`;
   - the radiator keeps heating;
   - `climate.vtherm_ac` is still `off`.
3. Make the radiator idle by raising the room temperature above its target:

   ```yaml
   action: fake_hvac.set_room_temperature
   data:
     temperature: 24
   ```

   Or wait for its TPI cycle to end.
4. Verify the handover:
   - `climate.vtherm_radiator` goes `off`;
   - only then `climate.vtherm_ac` receives `heat` and the setpoint;
   - `sensor.climaterouter_active_target` becomes `ac`;
   - `sensor.climaterouter_last_handover` updates.

### 8.3 Route override

With outdoor temperature at `5`, force the AC through the built-in select:

```yaml
action: select.select_option
target:
  entity_id: select.climaterouter_route_override
data:
  option: ac
```

Verify the route moves to `ac` (subject to the normal handover rules), and
`sensor.climaterouter_route_reason` reports `manual_route`.

Select `auto` to return to automatic outdoor routing.

### 8.4 Manual mode and timer

Start a one-minute manual mode:

```yaml
action: climaterouter.enter_manual_mode
target:
  entity_id: climate.climaterouter
data:
  temperature: 22.5
  duration_minutes: 1
```

Verify:

- `binary_sensor.climaterouter_manual_mode` is `on`;
- `sensor.climaterouter_manual_remaining` counts down;
- the active VTherm receives 22.5 °C;
- after one minute the previous schedule setpoint is restored.

Repeat with `preset_mode: comfort`. While manual mode is active, move the temperature again and verify the value
changes but the deadline does not reset. Switch the timer off through
`select.climaterouter_manual_timer` (`off`) and verify the remaining sensor becomes unknown. Return with
`button.climaterouter_return_to_schedule` or `climaterouter.return_to_schedule`.

With `manual_blocks_schedule` on, send `climate.set_temperature` from an automation (no `user_id`) and verify it is
rejected while manual mode is active. User moves must still work.

### 8.5 Direct VTherm change (conflict)

While the AC is the active target:

```yaml
action: climate.set_temperature
target:
  entity_id: climate.vtherm_ac
data:
  temperature: 25
```

Verify:

- `binary_sensor.climaterouter_conflict` turns `on`;
- `climate.climaterouter` attributes list the expected and actual values;
- the proxy does not silently fight the change under the default `monitor` policy;
- the next command through the proxy reasserts the desired state.

### 8.6 Both targets on

1. Turn on both VTherms directly.
2. Verify `binary_sensor.climaterouter_conflict` is `on`.
3. If one is idle and `auto_resolve_idle_targets` is enabled, it should be turned off.
4. If both are heating, neither should be interrupted.

### 8.7 Stale outdoor sensor

```yaml
action: fake_hvac.set_availability
data:
  outdoor: false
```

Verify:

- `binary_sensor.climaterouter_outdoor_sensor_stale` is `on`;
- the route holds the last target;
- no handover flapping occurs.

Restore it with `outdoor: true`.

### 8.8 Restart during operation

1. Leave a target heating.
2. Restart Home Assistant:

   ```bash
   docker compose restart homeassistant
   ```

3. Verify after startup:
   - `binary_sensor.climaterouter_ready` turns `on`;
   - the heating target is not turned off during reconciliation;
   - the desired state and any override are restored;
   - no service-call loop appears in the log.

### 8.9 Off and cool intent

- `climate.set_hvac_mode(off)` through the proxy must turn off both targets immediately and cancel any pending
  handover or override.
- `climate.set_hvac_mode(cool)` must route to the AC and may stop an active radiator cycle, because it is explicit
  user intent rather than a route-driven change.

---

## 9. Reading the logs

```bash
docker compose logs -f homeassistant | grep -E 'climaterouter|fake_hvac|versatile_thermostat'
```

Useful log lines:

- route changes and reasons;
- handover start, wait, abort and completion;
- override start/end and cause;
- conflict detection and clearing;
- service-call failures and timeouts.

The `logger` block in `configuration.yaml` sets `custom_components.climaterouter` and
`custom_components.fake_hvac` to `debug`.

---

## 10. Reset the lab

### Soft reset (keep integrations and VTherm entries)

```yaml
action: fake_hvac.reset
```

This restores the configured room/outdoor temperatures, turns the radiator and AC off, and resumes the simulation.

### Full reset (delete all Home Assistant runtime data)

```bash
cd test_environment
./reset.sh
```

The script stops the container and removes `.storage`, the recorder database, logs, HACS, VTherm, Scheduler and
other generated files. The tracked `configuration.yaml`, `.gitignore` and `.gitkeep` remain. You will need to
create the owner account and reinstall the integrations afterwards.

A plain `git clean -fdX test_environment/config` may fail because Home Assistant writes some files as root. The
script uses a short-lived root container to remove them safely.

To remove the container image as well:

```bash
cd test_environment
docker compose down --rmi local
```

---

## 11. Troubleshooting

| Symptom | Check |
|---|---|
| `fake_hvac` does not appear | `docker compose config` shows the bind mount; the directory contains `manifest.json`; restart the container; check for YAML/import errors in the log. |
| Fake entities have different IDs | Names were changed or IDs collided. Check **Developer Tools → States** and use the actual IDs in VTherm and ClimateRouter. |
| VTherm cannot find the radiator switch | `switch.fake_radiator` exists and is not unavailable. |
| VTherm cannot find the AC climate | `climate.fake_ac` exists, supports `heat`/`cool`/`off`, and is not unavailable. |
| VTherm setup asks for a feature the fake AC lacks | Disable fan/swing/humidity options in the VTherm flow; the fake AC only implements temperature, mode and preset. |
| Room temperature never changes | `simulation_enabled` is true, `update_interval > 0`, and the radiator/AC is actually on. Check `sensor.fake_thermal_power`. |
| Routing never changes | The old target may still be heating. Check `binary_sensor.climaterouter_handover_pending`; make it idle or wait for the cycle to end. |
| Override does not expire quickly | Override uses real time, not `time_scale`. Use `duration_minutes: 1` for tests. |
| Entities disappear after restart | Check that the bind mounts still exist and that the container was not recreated with a different config path. |
| Port 38123 already in use | Stop the other Home Assistant instance or change the host port in `docker-compose.yml`. |

---

## 12. What is intentionally not simulated

- Real TPI valve/relay behavior and hydraulic inertia.
- AC defrost, compressor minimum run times, fan curves and swing.
- Window/door sensors, presence sensors, power meters and safety guards. Add ordinary HA helpers or template
  sensors if a scenario needs them.
- Scheduler's own persistence and UI behavior beyond the standard climate actions.
- Network failures between HA and physical devices.

The fake hardware is deliberately small. It exists to make routing, handover, override and conflict behavior
reproducible, not to model a building.
