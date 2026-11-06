#!/usr/bin/env bash
#
# Remove all generated Home Assistant state from the test lab while keeping the
# tracked configuration. The Home Assistant container writes files as root, so
# a normal `git clean` cannot always remove them; this script uses a short-lived
# root container instead.
set -euo pipefail

cd "$(dirname "$0")"

docker compose down

docker run --rm -v "$PWD/config:/config" alpine sh -c '
  rm -rf \
    /config/.storage \
    /config/.cloud \
    /config/blueprints \
    /config/tts \
    /config/deps \
    /config/backups \
    /config/media \
    /config/www \
    /config/custom_components/hacs \
    /config/custom_components/versatile_thermostat \
    /config/custom_components/scheduler \
    /config/home-assistant_v2.db \
    /config/home-assistant_v2.db-shm \
    /config/home-assistant_v2.db-wal \
    /config/home-assistant.log \
    /config/home-assistant.log.1 \
    /config/.ha_run.lock \
    /config/.HA_VERSION
  rm -f /config/*.log
  rmdir /config/custom_components/climaterouter /config/custom_components/fake_hvac 2>/dev/null || true
'

echo "Test environment reset. Tracked configuration was kept."
