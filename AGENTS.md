# Development environment and working rules

This file is the short, operational guide for whoever (human or agent) continues
development in this checkout. Keep it up to date when the environment changes.

## Host / repository rules

- **Commits are allowed, pushes are not.** The repository owner pushes manually.
  Never run `git push`, `git push --tags`, or create remote releases from this
  host unless the owner explicitly asks for it.
- **Commit frequently.** Work in small, self-contained commits so the project can
  be handed over at any moment. Leave the working tree clean after each step.
- Do not commit secrets, access tokens, `.storage`, `test_environment/config`, or
  `opencode.json` (see `.gitignore`).
- Local Python is **3.10**, the project targets **3.12+** and Home Assistant
  **2026.11**. Keep the existing 3.10 compatibility noqa comments unless the local
  tooling baseline is raised.
- Unit tests run locally: `pytest` (already installed). `ruff` may not be
  installed in this environment; use it when available (`ruff check .`,
  `ruff format --check .`).

## Test Home Assistant

- The test Home Assistant **is not this checkout**. It runs remotely/in a
  container and is reachable only through HTTP at <http://localhost:38123>.
- Do **not** try to reach the HA config directory or `.storage` from this host.
  The supported development loop is: change code here → commit → owner pushes a
  new version/tag → update the custom component through HACS in the test HA.
- A real **Versatile Thermostat (VTherm)** setup is present in the test instance;
  the two configured VTherm entities are the intended radiator/AC targets.
- The local Docker test environment in `test_environment/` cannot be started from
  this host. It remains documentation/reference only.

## Testing against the live instance

- Prefer the Home Assistant REST API and WebSocket API. The API requires a
  long-lived access token; keep it in an environment variable (for example
  `HA_TOKEN`) or a local, git-ignored file, never in the repository.
- Useful endpoints:
  - `GET /api/states` (all entities)
  - `GET /api/states/<entity_id>`
  - `POST /api/services/climate/set_temperature`
  - `POST /api/services/homeassistant/restart`
  - `/api/config/config_entries/entry` (REST)
  - WebSocket API for HACS/config-entry operations if needed.
- Check the integration state with entities such as
  `climate.climaterouter`, `sensor.climaterouter_active_target`,
  `binary_sensor.climaterouter_handover_pending`, and the `climaterouter.*`
  services.

## Releasing / updating in the test HA

HACS installs custom components from the GitHub repository. To make a new build
visible in the test instance:

1. Finish and test the change locally (`pytest`, optional `ruff`).
2. Bump the version in **both** places:
   - `custom_components/climaterouter/manifest.json`
   - `custom_components/climaterouter/const.py` (`VERSION`)
3. Commit the change (no push).
4. The owner pushes `main` and creates/pushes the matching tag/release
   (for example `v0.2.0`). HACS uses the normal GitHub source archive; `hacs.json`
   deliberately does not enable `zip_release`, so no release asset is required.
5. In the test HA, update the repository through HACS and restart Home Assistant.
6. Verify through the REST API and record the result in `docs/HANDOVER.md`.

Do not claim a change is verified in the live instance until the API confirms it.

## Handover

`docs/HANDOVER.md` is the authoritative state-of-work document. Update it when a
milestone advances, the live test setup changes, or a new known gap is found.
