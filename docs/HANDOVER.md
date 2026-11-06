# Handover — ClimateRouter

**Date:** 2026-11-06
**Branch:** `main`
**Relevant commits:**

| Commit | Summary |
|---|---|
| `ff86494` | `feat: implement ClimateRouter M1-M3` |
| `1e14b3f` | `test: use native temperature properties in fake_ac` |
| `95cb4cd` | `test: expose HA on port 38123 instead of host networking` |
| `f4dfcaa` | `test: add room/outdoor temperature controls to fake_hvac` |

The working tree is clean. Nothing after `95cb4cd` has been pushed (the assistant had no GitHub credentials); push
the local commits before starting new work.

---

## 1. Where things stand

Milestones M1–M3 from [`PLAN.md`](PLAN.md) are implemented and validated manually in a real Home Assistant 2026.11
container.

| Milestone | State | Notes |
|---|---|---|
| M1 — skeleton and config flow | Done | Config/options/reconfigure flows, device, proxy entity, services, diagnostics, translations, CI. |
| M2 — proxy and routing | Done | Hysteresis, manual switch, route override, `off`/`cool`, command forwarding, status entities. |
| M3 — safe handover | Done | Idle detection, off confirmation, timeout, queued desired state, startup reconciliation, events. |
| M4 — manual override | Not started | `OverrideState` model and placeholder sensor/entity exist; no service or timer yet. |
| M5 — conflicts | Not started | `Conflict` model, guard extraction and own-context registry exist but are unused; `conflicts` is always empty. |
| M6 — boost and release | Not started | `boost_enabled` config and `choose_route(boost_active=True)` exist; the coordinator cannot drive two targets yet. |

The next developer should start with section 8 (Next steps).

---

## 2. Repository map

```text
custom_components/climaterouter/
├── __init__.py          # setup/unload, runtime_data, update listener
├── manifest.json        # domain, version, dependencies
├── const.py             # domain, config keys, services, events, timers
├── models.py            # HA-free dataclasses and enums
├── router.py            # HA-free choose_route() and helpers
├── coordinator.py       # event listeners, routing, handover, forwarding, persistence
├── climate.py           # proxy climate entity
├── entity.py            # shared coordinator entity + DeviceInfo
├── binary_sensor.py     # active/heating/cooling/pending/conflict/stale/ready
├── sensor.py            # active/pending/reason/outdoor/timestamps/counts
├── select.py            # route override (auto/radiator/ac)
├── button.py            # recalculate, clear conflicts
├── services.py          # service registration and entity resolution
├── diagnostics.py       # config-entry diagnostics
├── config_flow.py       # user/options/reconfigure flows and validation
├── services.yaml
├── strings.json         # source of translations
└── translations/en.json # must be kept in sync manually

tests/
├── conftest.py          # stubs the `climaterouter` package; no HA needed
├── test_router.py       # routing precedence, hysteresis, fallback (pure)
└── test_models.py       # config parsing, desired-state round-trip

.github/workflows/ci.yml # ruff + pytest on Python 3.13
test_environment/        # Docker HA lab, fake_hvac, docs/TEST_ENVIRONMENT.md
```

The domain layer (`models.py`, `router.py`) deliberately has **no Home Assistant imports** so it can be unit-tested
without an HA runtime. Keep it that way.

---

## 3. Runtime behaviour

### 3.1 Routing

`router.choose_route()` implements the precedence from `PLAN.md` §7.2:

1. `off` wins — no active target.
2. Explicit `cool` forces the AC.
3. `select.<name>_route_override` (`radiator` / `ac`) wins over automatic routing.
4. The optional manual switch (`switch` / `input_boolean` / `input_select`) forces its configured target.
5. Outdoor hysteresis:
   - current target AC stays AC while `outdoor > cold_threshold`;
   - current target radiator stays radiator while `outdoor <= mild_threshold`;
   - no current target: AC above `mild_threshold`, radiator at/below `cold_threshold`, radiator in the dead band.
6. Missing/stale outdoor input holds the last route; with no history it falls back to radiator.
7. Unavailable or mode-incapable targets fall back to the other target when
   `fallback_on_unavailable` is enabled.

The coordinator computes the effective override as: built-in select first, then an `input_select` manual switch,
then `auto`. `min_route_dwell` suppresses non-explicit route changes after a completed handover.

### 3.2 Command handling

The proxy entity (`climate.py`) delegates to coordinator methods. Important edge cases:

- `async_evaluate()` never issues commands before the first user command. If an underlying thermostat is already
  on after a restart, it is **adopted** (`_adopt_from_active`), not commanded.
- A bare `set_temperature` (without `set_hvac_mode`) is forwarded only to an already-active target. It does not
  start a target and does not trigger a route change.
- With a `heat`/`cool` mode command, the coordinator starts/adopts a target, or begins a handover.
- Explicit commands raise `HomeAssistantError` if no target can serve the requested mode. Non-explicit evaluation
  (state changes, watchdog, startup) only publishes `route_reason=unavailable`.
- Commands are sent with `blocking=True` and a per-call `Context`; the context id is stored in `_contexts` for
  M5 conflict suppression (currently unused).

### 3.3 Handover state machine

Implemented in `coordinator.py`:

```text
STEADY ──route change──▶ PENDING (old target active)
                          │ old target idle for handover_idle_confirm
                          ▼
                       STOPPING_OLD (send hvac_mode=off)
                          │ old confirms off
                          ▼
                       STARTING_NEW (set mode / temperature / preset)
                          ▼
                       STEADY
```

- A route change while the old target is **active** only records the pending target. The old target keeps heating.
- Once the old target has been idle for `handover_idle_confirm` seconds, it is switched off. Off confirmation is
  bounded by `off_confirm_timeout`; on timeout the state becomes `CONFLICT` and a
  `climaterouter_handover_aborted` event fires.
- `STARTING_NEW` applies the queued desired state (temperature or preset) to the new target.
- Time-based transitions schedule their own follow-up evaluation via `_schedule_check()` /
  `_async_scheduled_check()`. Do not remove this: state-change events alone can leave an idle-confirmation or
  timeout stuck until the 30 s watchdog.
- `hvac_action` unknown is treated as **active** so a handover never interrupts an invisible cycle.
- `off` through the proxy bypasses the state machine and turns every available target off immediately.

Events fired on the HA bus:

- `climaterouter_route_changed` (only when the active target actually changes),
- `climaterouter_handover_started`,
- `climaterouter_handover_completed` (includes `duration_s`),
- `climaterouter_handover_aborted`.

### 3.4 Startup and persistence

- `startup_grace` delays reconciliation; with `0` it runs immediately.
- `_async_reconcile()` adopts one on-target without commanding it. Two active targets produce
  `handover_state=conflict` (full conflict handling is M5).
- Reconciliation calls `async_evaluate()` **non-explicitly**: at startup the underlying platforms may not be
  loaded yet, and an explicit call would raise and fail entry setup.
- Desired state and last route are persisted in `homeassistant.helpers.storage.Store` under
  `climaterouter.<entry_id>` (`STORAGE_VERSION = 1`).
- `last_handover`, pending target and active target are deliberately **not** persisted. After a restart the route
  is rebuilt from actual entity states.
- If a persisted `heat`/`cool` mode exists, heating resumes on startup. A persisted setpoint with no mode does not
  start anything.

### 3.5 Entity state

- The proxy is available when at least one target is available.
- `hvac_mode`, `target_temperature` and `preset_mode` are optimistic for `settle_time` seconds after a command,
  then mirror the active target.
- `current_temperature` averages the active targets (one in normal operation).
- `hvac_modes` always contains `off`/`heat`; `cool` is offered when the AC target advertises it.
- Presets are the intersection of both targets' presets, or the union when the intersection is empty, plus `none`.
- `min_temp`, `max_temp` and `target_temperature_step` come from the active target (or the AC/first available one).

---

## 4. Test lab state

Defined in `test_environment/`; full instructions in [`TEST_ENVIRONMENT.md`](TEST_ENVIRONMENT.md).

- Container: `climaterouter-ha` (Compose project `climaterouter-test`).
- URL: <http://localhost:38123> (host port 38123 → container 8123).
- HA image: `ghcr.io/home-assistant/home-assistant:stable`, currently **2026.11.0**, Python 3.14 inside.
- The integration and `fake_hvac` are bind-mounted read-only, so code edits need only
  `docker compose restart homeassistant`; config flows reload a changed entry automatically.
- `fake_hvac` entries:
  - `Fake HVAC Lab` from YAML — `climate.fake_ac`, `sensor.fake_room_temperature`,
    `sensor.fake_outdoor_temperature`, radiator and simulation switches, temperature `number` entities;
  - `Fake HVAC Lab 2` — a second system created through the UI during validation, exposing `climate.fake_ac_2`.
- `fake_hvac` services require a `name` field once more than one system exists
  (`"Fake HVAC Lab"` / `"Fake HVAC Lab 2"`).
- Test router entry **`ClimateRouter Test`** (local `.storage` only, entry id
  `01M6S30VNZAM426275PKQQ5G2Z`) points at `climate.fake_ac` (radiator role) and `climate.fake_ac_2` (AC role),
  with `min_route_dwell=0`, `handover_idle_confirm=1`, `off_confirm_timeout=5`, `startup_grace=0`,
  `settle_time=1`. It is currently **off**.
- **Versatile Thermostat is not installed yet.** The two real VTherm entries are the main outstanding setup task.

The `.storage` directory is git-ignored. `test_environment/reset.sh` removes it, so test entries are disposable; do
not encode assumptions about them in code.

---

## 5. Running checks

Local machine here uses Python 3.10, while the project targets 3.12+ and HA 2026.11. The unit tests are written to
run on 3.10 (`str, Enum` with `# noqa: UP042`, `timezone.utc` with `# noqa: UP017`).

```bash
# lint / format / unit tests (venv used during development)
/path/to/venv/bin/ruff check .
/path/to/venv/bin/ruff format --check .
/path/to/venv/bin/pytest

# Home Assistant lab
cd test_environment
docker compose up -d
docker compose logs -f homeassistant
```

`requirements_test.txt` lists `pytest-homeassistant-custom-component`, but the current tests do not need it and it
was **not** installed locally. CI installs only `pytest` and `ruff`.

---

## 6. What was verified manually

Run against the live container through the REST API, with the proxy wired to the two fake ACs:

| Scenario | Result |
|---|---|
| Config flow creates entry and entities | OK |
| Cold outdoor, `heat` → radiator | OK |
| Outdoor 12, radiator idle → handover to AC | OK: radiator off, then AC on, queued setpoint applied |
| Outdoor 0, AC idle → handover back to radiator | OK |
| Handover while old target is heating | stays `pending`; old target is not interrupted |
| Proxy `off` | both targets off, handover cancelled |
| Route override `radiator` / `ac` | OK |
| Setpoint change during pending handover | queued and applied on completion |
| Temperature forwarding while steady | OK |
| Restart with persisted `heat` | resumes without crashing when targets start late |
| No prior command, underlying target already on | adopted, no commands sent |
| Diagnostics endpoint | OK |

Not yet covered by automated tests: config flow, coordinator, handover, persistence, event payloads.

---

## 7. Known gaps and deviations

1. **Version floor is 2026.11.** `hacs.json` now declares `2026.11.0`, because `coordinator.py` imports
   `ATTR_TEMPERATURE` from `homeassistant.const` (it moved out of `homeassistant.components.climate.const` in
   2026.11). If wider compatibility is wanted, add a `try/except` import and test on the oldest target release
   before lowering the floor.
2. **No automated integration tests.** `tests/` covers only the pure domain/routing layer. CI deliberately does not
   install HA to stay fast.
3. **M4 is a skeleton.** `OverrideState` exists; `sensor.override_remaining` is always `0`,
   `binary_sensor.manual_override` is always `off`, and `set_manual_override` / `cancel_manual_override` services and
   the cancel button do not exist.
4. **M5 is a skeleton.** `Conflict` and `_extract_guard()` exist; `_contexts` records outbound call contexts but is
   never consulted; `RouterSnapshot.conflicts` is always empty, `conflict_count` always `0`, and
   `clear_conflicts` only republishes. Config fields `conflict_policy`, `auto_resolve_idle_targets`,
   `auto_resolve_simultaneous` are parsed but unused.
5. **Boost is not wired.** `boost_enabled` is a config option and `choose_route` can return both targets, but
   `_single_target()` makes the coordinator treat that as “no target”. The route override deliberately offers only
   `auto` / `radiator` / `ac`. Do not expose `both` until the set-based start/stop path exists.
6. **`handover_max_wait` from the plan is not implemented.** `off_confirm_timeout` bounds the off confirmation;
   there is no forced interruption of an active old target.
7. **`last_handover` is not persisted**, so `sensor.last_handover` is `unknown` after a restart.
8. **`route_changed` fires only when the active target changes**, not when only `route_reason` changes.
9. **Options flow writes every field into `entry.options`** (the entry data stays as originally created). The
   coordinator merges `{**entry.data, **entry.options}`. Reconfigure writes everything into `entry.data` and clears
   options. This works but is inconsistent; simplify when touching the flow.
10. **`strings.json` and `translations/en.json` are duplicated** and must be edited together.
11. `binary_sensor.target_mismatch` only compares the two targets' setpoints; it is not the full M5 mismatch
    detector.

---

## 8. Next steps

### 8.1 Immediate

1. Push the four commits above.
2. Install **Versatile Thermostat** through HACS and create two entries once in the UI:
   - `over_switch` radiator using `switch.fake_radiator`;
   - `over_climate` AC using `climate.fake_ac`;
   - both with `sensor.fake_room_temperature` and `sensor.fake_outdoor_temperature`.
   Follow `TEST_ENVIRONMENT.md` §5. Config entries persist across restarts, so this is a one-time step.
3. Reconfigure `ClimateRouter Test` to use `climate.vtherm_radiator` / `climate.vtherm_ac` (or delete it and create
   a fresh entry named `ClimateRouter`). Repeat the scenarios in §8 of `TEST_ENVIRONMENT.md` with VTherm.
4. Decide whether to keep the new 2026.11 version floor or add an older-version import fallback
   (section 7.1).

### 8.2 Automated tests

Add `pytest-homeassistant-custom-component` integration tests and update CI to install `requirements_test.txt`
with a Python version matching the supported HA. Suggested coverage:

- config flow: happy path, duplicate unique id, missing entity, threshold order, reconfigure, options reload;
- coordinator: routing precedence, fallback on unavailable, stale outdoor hold, manual switch;
- handover: active → pending → idle → off → start; off-confirm timeout; route revert during pending;
- startup: adopt one on-target; persisted desired state; targets not loaded yet;
- persistence: desired state and last route across reload;
- services: target resolution, route override, clear override;
- entity state: optimistic window, mirroring, attributes.

### 8.3 M4 — manual override

- Implement `climaterouter.set_manual_override` and `cancel_manual_override` in `services.py` with the schema from
  `PLAN.md` §11.
- Add coordinator state: capture baseline `DesiredState`, absolute deadline using `dt_util.utcnow()`, persistence
  alongside desired state, restore on expiry/cancel.
- Route schedule commands into the baseline while an override is active; keep the override across handovers.
- Wire `binary_sensor.manual_override`, `sensor.override_remaining`, and the cancel button.
- Emit `climaterouter_override_started` / `climaterouter_override_ended`.
- Add expiry tests with `freezegun` (already in `requirements_test.txt`).

### 8.4 M5 — conflict handling

- Compare desired state with the active target on every state change; ignore state changes caused by our own
  contexts (`_contexts`, `CONTEXT_TTL`).
- Populate `RouterSnapshot.conflicts`, `conflict_count`, attributes and the conflict binary sensor.
- Classify VTherm guards with `_extract_guard()`; guarded/idle states are not conflicts.
- Implement `monitor` / `reassert` / `adopt` policies and the configured auto-resolve switches.
- Fire `climaterouter_conflict_detected` / `climaterouter_conflict_cleared`; make `clear_conflicts` real.
- Handle both-targets-on, unavailable target, stale outdoor sensor and target mismatch.

### 8.5 M6 — boost and release

- Convert the coordinator from single-target helpers (`_single_active`, `_single_target`) to set-based operations.
- Implement feature-flagged `set_boost` / `cancel_boost` with a bounded deadline, heat-only interlock, capability
  checks and no pending handover requirement.
- Fan out commands to both targets only while boost is active; keep `off`/`cool` semantics safe.
- Add `hassfest`, HACS validation, a release workflow and the `v0.1.0` tag.
- Finish README/setup/dashboard examples.

---

## 9. Gotchas

- **Home Assistant 2026.11 moved constants.** `ATTR_TEMPERATURE` is now in `homeassistant.const`; most other
  climate attributes are still in `homeassistant.components.climate.const`.
- **Use `native_*` climate properties.** `temperature_unit`, `current_temperature` and `target_temperature`
  properties are deprecated in 2026.11; the code uses `native_temperature_unit`, `native_current_temperature`,
  `native_target_temperature`. `fake_hvac` was fixed the same way.
- **Do not call `async_evaluate(explicit=True)` from reconciliation or startup callbacks.** Targets may not be
  loaded yet, and it raises `HomeAssistantError`, failing entry setup.
- **Re-entrant lock hazard.** `async_evaluate()` takes `self._lock`; `_async_reconcile()` must release the lock
  before calling it. A previous version deadlocked here.
- **Time-based handover transitions need `_schedule_check()`.** The watchdog is only 30 s; do not rely on it for
  `handover_idle_confirm` or `off_confirm_timeout`.
- **`fake_hvac` services need `name` when multiple systems exist.**
- **The proxy can point at raw fake ACs** while VTherm is absent. That is how the current test entry is wired.
- **Restart readiness.** `docker logs ... | grep "Home Assistant initialized"` can match a previous boot because
  Docker keeps old logs. Poll `/api/states` for `climate.climaterouter*` instead.
- **Local Python is 3.10.** Keep `str, Enum` + `# noqa: UP042` and `timezone.utc` + `# noqa: UP017` unless you
  raise the local/tooling baseline. CI uses 3.13.
- **The `.storage` test entries are not in git.** A fresh clone has no `ClimateRouter Test` or
  `Fake HVAC Lab 2`.

---

## 10. Useful commands

```bash
# container lifecycle
cd test_environment
docker compose up -d
docker compose restart homeassistant
docker compose logs -f homeassistant

# only integration logs
docker compose logs -f homeassistant | grep -i climaterouter

# unit tests / lint
/path/to/venv/bin/pytest -q
/path/to/venv/bin/ruff check .
/path/to/venv/bin/ruff format --check .

# fake hardware (name required when several systems exist)
# Developer Tools -> Actions -> fake_hvac.set_outdoor_temperature
#   temperature: 12
#   name: Fake HVAC Lab
# fake_hvac.set_room_temperature, fake_hvac.set_simulation, fake_hvac.reset

# inspect router attributes
curl -s http://localhost:38123/api/states/climate.climaterouter_test \
  -H "Authorization: Bearer <token>" | jq '.attributes'
```

The REST API needs a long-lived or short-lived access token created in the HA profile page. Do not commit tokens
or `.storage`.
