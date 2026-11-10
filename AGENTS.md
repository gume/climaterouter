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

- The test Home Assistant runs in the Docker container `climaterouter-ha`
  (Compose project `climaterouter-test`) on this host, reachable at
  <http://localhost:38123>. Its `/config` is the git-ignored
  `test_environment/config/` directory.
- Never commit or print runtime state from `test_environment/config/.storage`;
  it contains credentials (for example the Marketplace GitHub token).
- The supported development loop is: change code here → commit → owner pushes
  `main` → refresh/restart the Marketplace in the test HA → install the update.
- A real **Versatile Thermostat (VTherm)** setup is present in the test instance;
  the two configured VTherm entities are the intended radiator/AC targets.
- The Docker lab in `test_environment/` is started and stopped with
  `docker compose` from that directory.

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
  - WebSocket API for Marketplace/config-entry operations if needed
    (`marketplace/repository/refresh` forces a commit re-read).
- Check the integration state with entities such as
  `climate.climaterouter`, `sensor.climaterouter_active_target`,
  `binary_sensor.climaterouter_handover_pending`, and the `climaterouter.*`
  services.

## Releasing / updating in the test HA

ClimateRouter is installed through the Home Assistant **Marketplace** as the
custom repository `gume/climaterouter`. The Marketplace installs the latest
commit on `main` and shows the short commit hash as the version; no tag or
release is required.

To make a new build visible in the test instance:

1. Finish and test the change locally (`pytest`, optional `ruff`).
2. Bump the version in **all three** places:
   - `custom_components/climaterouter/manifest.json`
   - `custom_components/climaterouter/const.py` (`VERSION`)
   - `pyproject.toml` (`version`)
3. Commit the change (no push); the owner pushes `main`. The owner can use
   `scripts/release.sh` for the push: it is a dry run by default, runs the checks,
   derives the version and release notes automatically from the source files and
   `git log`, then `--push` pushes `main`, creates/pushes `v<version>` and creates
   the GitHub release.
4. Refresh the Marketplace metadata. Installed custom repositories re-read
   `last_commit` at Home Assistant startup and then only every **48 hours**, so
   either restart Home Assistant or use the repository **Refresh** action in the
   Marketplace.
5. Install the offered update in the Marketplace and restart Home Assistant.
6. Verify through the REST API and record the result in `docs/HANDOVER.md`.

Do not claim a change is verified in the live instance until the API confirms it.

## Handover

`docs/HANDOVER.md` is the authoritative state-of-work document. Update it when a
milestone advances, the live test setup changes, or a new known gap is found.
`issues.txt` is the owner-facing issue list with resolved/open status; update it
when an issue is implemented, deferred, or clarified.
