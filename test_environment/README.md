# ClimateRouter test environment

A disposable Home Assistant instance with a simulated room, outdoor sensor, radiator and air conditioner. It is
meant for developing and manually testing the `climaterouter` integration without real hardware.

```text
┌────────────────────────────── Docker ──────────────────────────────┐
│ Home Assistant                                                     │
│                                                                    │
│  fake_hvac integration                                             │
│    sensor.fake_room_temperature ───────┐                           │
│    sensor.fake_outdoor_temperature ────┤                           │
│    switch.fake_radiator ───────────────┤                           │
│    climate.fake_ac ────────────────────┤                           │
│                                        ▼                           │
│                            Versatile Thermostat                    │
│                     climate.vtherm_radiator (over_switch)          │
│                     climate.vtherm_ac       (over_climate)         │
│                                        ▼                           │
│                            climate.climaterouter                   │
│                                        ▲                           │
│                            Scheduler Component                     │
└────────────────────────────────────────────────────────────────────┘
```

## Quick start

```bash
cd test_environment
docker compose up -d
docker compose logs -f homeassistant
```

Open <http://localhost:8123>, create the owner account, then follow
[`../docs/TEST_ENVIRONMENT.md`](../docs/TEST_ENVIRONMENT.md) to install VTherm, Scheduler and the integrations.

The fake hardware is configured entirely from
[`config/configuration.yaml`](config/configuration.yaml); no UI setup is needed for it. VTherm itself only supports
config-flow setup, so its two thermostats are created once through the UI.

## Layout

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Home Assistant container, mounts and timezone. |
| `reset.sh` | Stops the container and deletes generated HA state while keeping tracked config. |
| `config/configuration.yaml` | `default_config`, fake lab hardware, helper switches, logging. |
| `config/.gitignore` | Keeps generated HA state out of git; only `configuration.yaml` is tracked. |
| `custom_components/fake_hvac/` | Test-only fake sensors, radiator switch and AC climate. |

## Useful commands

```bash
# Follow logs
docker compose logs -f homeassistant

# Restart after changing a custom component
docker compose restart homeassistant

# Shell inside the container
docker compose exec homeassistant bash

# Stop and remove the container (the bind-mounted config stays)
docker compose down

# Stop and delete all generated Home Assistant state, keeping tracked config
./reset.sh
```

See [`../docs/TEST_ENVIRONMENT.md`](../docs/TEST_ENVIRONMENT.md) for the full setup, test scenarios and reset
instructions.
