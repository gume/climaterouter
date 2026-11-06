"""Constants for the fake HVAC test integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "fake_hvac"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.CLIMATE]

CONF_NAME = "name"
CONF_ROOM_TEMPERATURE = "room_temperature"
CONF_OUTDOOR_TEMPERATURE = "outdoor_temperature"
CONF_RADIATOR_POWER_KW = "radiator_power_kw"
CONF_AC_POWER_KW = "ac_power_kw"
CONF_LOSS_COEFFICIENT = "loss_coefficient"
CONF_THERMAL_MASS = "thermal_mass"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_TIME_SCALE = "time_scale"
CONF_SIMULATION_ENABLED = "simulation_enabled"

DEFAULT_NAME = "Fake HVAC Lab"
DEFAULT_ROOM_TEMPERATURE = 20.0
DEFAULT_OUTDOOR_TEMPERATURE = 5.0
DEFAULT_RADIATOR_POWER_KW = 1.5
DEFAULT_AC_POWER_KW = 2.5
DEFAULT_LOSS_COEFFICIENT = 0.06
DEFAULT_THERMAL_MASS = 0.5
DEFAULT_UPDATE_INTERVAL = 5
DEFAULT_TIME_SCALE = 60.0
DEFAULT_SIMULATION_ENABLED = True

DEFAULT_AC_TARGET_TEMPERATURE = 21.0
MIN_TEMP = 7.0
MAX_TEMP = 35.0
TEMP_TOLERANCE = 0.3

PRESET_TEMPERATURES = {
    "eco": 18.0,
    "comfort": 21.0,
    "boost": 23.0,
    "frost": 7.0,
}

SERVICE_SET_OUTDOOR_TEMPERATURE = "set_outdoor_temperature"
SERVICE_SET_ROOM_TEMPERATURE = "set_room_temperature"
SERVICE_SET_SIMULATION = "set_simulation"
SERVICE_SET_AVAILABILITY = "set_availability"
SERVICE_ADVANCE = "advance"
SERVICE_RESET = "reset"

ATTR_NAME = "name"
ATTR_TEMPERATURE = "temperature"
ATTR_ENABLED = "enabled"
ATTR_MINUTES = "minutes"
ATTR_ROOM = "room"
ATTR_OUTDOOR = "outdoor"
