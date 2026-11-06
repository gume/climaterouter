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
| `0279d7a` | `feat: add override model helpers and serialization` |
| `0589679` | `feat: implement coordinator-level manual override with persistence` |
| `b9ff8d2` | `feat: expose manual override entities, services, and translations` |
| `a9e59a8` | `fix: end the previous override episode before replacing it` |
| `ce0d040` | `docs: mark M4 implemented and record remaining verification work` |
| `a461449` | `chore: let HACS install from the GitHub source archive` |
| `2cfbb3c` | `feat: add pure conflict classification and conflict serialization` |
| `d4815bc` | `feat: detect and expose target conflicts with monitor/reassert/adopt policies` |
| `36a2465` | `docs: record M5 conflict handling and bump to 0.3.0` |
| `90aefd5` | `feat: implement bounded both-target boost with safe single-target return` |
| `a9be862` | `fix: interrupt the boosted spare target on an explicit cool command` |
| `fa4899e` | `docs: record M6 boost behaviour and verification steps` |
| `1719d3d` | `ci: add hassfest and HACS validation workflow` |

The working tree is clean. Nothing after `95cb4cd` has been pushed (the assistant has no GitHub credentials); the
owner must push the local commits and tag a release before the live test instance can be updated.

---

## 1. Where things stand

Milestones M1–M6 from [`PLAN.md`](PLAN.md) are implemented. M1–M3 were validated manually in a real Home Assistant
2026.11 container; M4–M6 still need live verification.

| Milestone | State | Notes |
|---|---|---|
| M1 — skeleton and config flow | Done | Config/options/reconfigure flows, device, proxy entity, services, diagnostics, translations, CI. |
| M2 — proxy and routing | Done | Hysteresis, manual switch, route override, `off`/`cool`, command forwarding, status entities. |
| M3 — safe handover | Done | Idle detection, off confirmation, timeout, queued desired state, startup reconciliation, events. |
| M4 — manual override | Implemented, not live-verified | Temperature/preset/mode override, absolute deadline, baseline capture/restore, persistence, handover forwarding, events, binary sensor, remaining sensor and cancel button. Unit coverage is limited to the pure model helpers. |
| M5 — conflicts | Implemented, not live-verified | Setpoint/preset/mode mismatch, unavailable targets, underlying timed presets, stale manual switch, both-on and inactive-target-on detection; own-context and guard suppression; `monitor`/`reassert`/`adopt` policies, auto-resolve switches, events, history and clear button. Unit coverage is limited to the pure classifier. |
| M6 — boost | Implemented, not live-verified | Feature-flagged both-target boost with heat-only/availability/handover interlocks, persistence, expiry, start/end events, active/remaining entities, and a handover back to single-target routing. |

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
- Commands are sent with `blocking=True` and a per-call `Context`; the context id is stored in `_contexts` so the
  coordinator can ignore state changes caused by its own commands during conflict detection.

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
  `handover_state=conflict`, which the M5 conflict detector also reports.
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

### 3.6 Manual override (M4)

- Services: `climaterouter.set_manual_override` and `climaterouter.cancel_manual_override`, plus
  `button.<name>_cancel_override`.
- `set_manual_override` requires exactly one of `temperature`, `preset_mode`, or `hvac_mode`. `hvac_mode: off`
  cancels the override and turns the proxy off. `duration_minutes` defaults to `default_override_minutes` and is
  capped by `max_override_minutes`.
- The coordinator keeps a **baseline** desired state (the latest schedule/proxy command) and a separate
  `OverrideState` (kind, value, absolute UTC deadline, baseline snapshot, start time). The effective desired state
  is the baseline with the override applied.
- Starting an override when the baseline is empty snapshots the active target's actual state. Starting a second
  override keeps the original baseline and replaces the value/deadline.
- Schedule commands received during an override update the baseline but do **not** replace the override value.
  An explicit `off` cancels the override (`cause=off`).
- Handovers use the effective desired state, so the override is automatically applied to the new target after a
  handover. Expiry/cancel restores the baseline and forwards it to the active target (or queues it while a
  handover is pending).
- Expiry is scheduled exactly at the deadline and is also checked by the 30 s watchdog. The override is stored in
  the existing `Store` as an absolute UTC timestamp plus baseline; expired overrides are discarded on startup.
- Events: `climaterouter_override_started` and `climaterouter_override_ended` (causes: `expired`, `cancelled`,
  `replaced`, `off`).
- The climate entity exposes the active override in its `override` attribute; `binary_sensor.<name>_manual_override`
  is on while it is active and `sensor.<name>_override_remaining` counts whole minutes rounded up.

### 3.7 Conflict detection (M5)

- Detection runs only in `STEADY`, `OFF` and `BOOST`, after startup reconciliation, and is skipped while a
  handover/reconciliation settle window is active. Changes caused by the router's own service calls are ignored
  through `_contexts` (bounded by `CONTEXT_TTL`).
- `router.target_conflict()` compares the effective desired state with the active target. Guards, unavailable
  targets and underlying timed presets are classified separately; guarded targets never produce a conflict.
- Reported types: `target_unavailable`, `hvac_mode_mismatch`, `setpoint_mismatch`, `preset_mismatch`,
  `underlying_override`, `both_targets_on`, `inactive_target_on`. Setpoint comparison uses
  `temperature_tolerance`.
- `conflict_policy`:
  - `monitor` (default) reports only;
  - `reassert` re-sends the desired setpoint/preset once after `CONFLICT_REASSERT_GRACE` seconds while the mode
    still matches;
  - `adopt` replaces the baseline with the externally observed state instead of reporting it.
- `auto_resolve_simultaneous` turns off non-active targets when both are on; `auto_resolve_idle_targets` turns off
  an idle inactive target. A running target is never interrupted by these switches.
- Each active conflict keeps its `first_seen`; resolved conflicts are retained in a bounded 50-entry history.
  Events: `climaterouter_conflict_detected` and `climaterouter_conflict_cleared` (payload includes
  `conflict.to_dict()`).
- `button.<name>_clear_conflicts` / `climaterouter.clear_conflicts` acknowledges current conflicts, records them
  as resolved and publishes the cleared state; it does not change the underlying targets.
- Exposed through `binary_sensor.<name>_conflict`, `sensor.<name>_conflict_count`, the proxy climate's conflict
  attributes and diagnostics. During boost each active target is compared; `adopt` is skipped because two targets
  cannot define one baseline.

### 3.8 Boost (M6)

- Disabled by default. `boost_enabled` must be on, then `climaterouter.set_boost` activates both targets with the
  current desired mode/setpoint/preset for `duration_minutes` (default 30, maximum 180).
- Interlocks: the desired mode must be `heat`, both targets must be available, support heat, and not currently be
  cooling; boost is rejected while a handover is `pending`/`stopping_old`/`starting_new`.
- `set_boost` with boost already active replaces the episode (`cause=replaced`). `cancel_boost`, proxy `off` and
  non-heat mode commands end it immediately. `off` also stops both targets through the normal path.
- Boost is persisted as an absolute UTC deadline and restored after a restart if it has not expired. Expiry is
  scheduled at the exact deadline and re-checked by the watchdog.
- While boost is active, `_handover_state=BOOST`, commands fan out to both active targets, and the proxy reports
  `active_target=both`. Both-on is not a conflict during boost.
- Ending boost (expiry/cancel/off/mode change) returns to normal routing through the handover state machine: the
  non-selected target is stopped after it becomes idle (immediately for an explicit `cool` command), then the
  selected target is configured. This reuses `_handover_from` so a two-target active set can be reduced safely.
- Events: `climaterouter_boost_started` and `climaterouter_boost_ended` (payloads include `until` and `targets`).
- Exposed through `binary_sensor.<name>_boost_active`, `sensor.<name>_boost_remaining`, the proxy climate's
  `boost_active`/`boost_until`/`boost_targets` attributes and diagnostics.

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
- **Versatile Thermostat is now installed and configured** in the live test instance (the owner completed this
  outside this checkout). The exact VTherm entity IDs and the router entry wiring must be read back through the HA
  API; they are not in this repository.

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
was **not** installed locally. CI installs only `pytest` and `ruff`. A separate `Validate` workflow runs
`home-assistant/actions/hassfest` and `hacs/action` (integration category, brands ignored because the domain has no
brand assets yet).

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

The M4 override, M5 conflict and M6 boost implementations have **not** been exercised in the live instance yet:
version `0.4.0` still needs to be pushed/released and installed there. Not yet covered by automated tests: config
flow, coordinator, handover, override expiry/cancel/handover/restart, conflict policies, boost safety/expiry/return,
persistence, event payloads.

---

## 7. Known gaps and deviations

1. **Version floor is 2026.11.** `hacs.json` now declares `2026.11.0`, because `coordinator.py` imports
   `ATTR_TEMPERATURE` from `homeassistant.const` (it moved out of `homeassistant.components.climate.const` in
   2026.11). If wider compatibility is wanted, add a `try/except` import and test on the oldest target release
   before lowering the floor.
2. **No automated integration tests.** `tests/` covers only the pure domain/routing layer. CI deliberately does not
   install HA to stay fast.
3. **M4 is implemented but only unit-tested at the model layer.** Coordinator expiry/cancel/handover/restart
   behaviour still needs live verification and integration tests. A temperature/preset override started while the
   proxy has no mode/active target is stored and counted down but does not by itself start heating; start the proxy
   (`heat`/`cool`) first. The `hvac_mode` override variant is implemented but not part of the normal dashboard flow.
4. **M5 is implemented but only unit-tested at the classifier layer.** Coordinator policy behaviour (context
   suppression, settle windows, reassert grace, adopt, auto-resolve, history/clear) still needs integration tests
   and live verification. Detection deliberately pauses during handover and during the post-command settle window,
   so very short mismatches may never be reported. `_guess_source()` is heuristic.
5. **Boost is feature-flagged and only supports `targets=both`.** It is implemented but has no coordinator
   integration tests and no live verification. It requires heat mode, both targets available and no pending
   handover. The return to single-target routing reuses the handover state machine, so the dropped target is only
   stopped once idle; if it never becomes idle the normal off-confirm timeout applies.
6. **`handover_max_wait` from the plan is not implemented.** `off_confirm_timeout` bounds the off confirmation;
   there is no forced interruption of an active old target.
7. **`last_handover` is not persisted**, so `sensor.last_handover` is `unknown` after a restart.
8. **`route_changed` fires only when the active target changes**, not when only `route_reason` changes.
9. **Options flow writes every field into `entry.options`** (the entry data stays as originally created). The
   coordinator merges `{**entry.data, **entry.options}`. Reconfigure writes everything into `entry.data` and clears
   options. This works but is inconsistent; simplify when touching the flow.
10. **`strings.json` and `translations/en.json` are duplicated** and must be edited together.
11. `binary_sensor.target_mismatch` only compares the two targets' setpoints; it is not the full M5 mismatch
    detector. Use `binary_sensor.<name>_conflict` for the desired-vs-actual comparison.

---

## 8. Next steps

### 8.1 Immediate

1. Owner: push `main` and tag/release **`v0.4.0`** (the manifest and `const.VERSION` are already bumped).
   `hacs.json` no longer sets `zip_release`, so HACS installs from the normal GitHub source archive; no release
   asset needs to be uploaded.
2. Update ClimateRouter in the test HA through HACS and restart Home Assistant.
3. Read the actual VTherm entity IDs and the router entry configuration back through the REST API, then re-run the
   routing/handover scenarios with VTherm instead of the fake ACs.
4. Exercise M4 in the live instance: start a short temperature override, confirm it reaches the active VTherm,
   cause a handover while it is active, let it expire, and confirm the baseline is restored. Repeat with
   `cancel_manual_override` and `hvac_mode: off`. Record the results here.
5. Exercise M5 in the live instance: change the active VTherm setpoint externally with `conflict_policy: monitor`;
   confirm the conflict binary sensor/count/attributes and both events; repeat under `reassert` and `adopt`; turn
   the inactive VTherm on manually; make a target unavailable. Record the results here.
6. Exercise M6 in the live instance (enable `boost_enabled` first): start heat, call `set_boost` for a short
   duration, confirm both VTherms run and `active_target=both`; cancel and let it expire; confirm the dropped
   target stops only when idle and normal routing resumes. Also confirm boost is rejected before heat and while a
   handover is pending. Record the results here.
7. Decide whether to keep the 2026.11 version floor or add an older-version import fallback (section 7.1).

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

### 8.3 M4 — manual override (implemented in this checkout)

- [x] `climaterouter.set_manual_override` / `cancel_manual_override` with the schema from `PLAN.md` §11.
- [x] Baseline `DesiredState`, absolute UTC deadline, persistence, restore on expiry/cancel.
- [x] Schedule commands update the baseline while the override keeps winning.
- [x] Override is re-applied after a handover and persisted across restart (expired deadlines are discarded).
- [x] `binary_sensor.manual_override`, `sensor.override_remaining`, cancel button.
- [x] `climaterouter_override_started` / `climaterouter_override_ended` events.
- [x] Unit tests for the model helpers (`with_override`, serialization, expiry/remaining).
- [ ] Integration tests for expiry, cancel, off, restart and handover (needs HA test harness).
- [ ] Live verification in the 2026.11 test instance.

### 8.4 M5 — conflict handling (implemented in this checkout)

- [x] Compare desired state with the active target; ignore state changes caused by our own contexts
      (`_contexts`, `CONTEXT_TTL`) and settle windows.
- [x] Populate `RouterSnapshot.conflicts`, `conflict_count`, attributes and the conflict binary sensor.
- [x] Classify VTherm guards with `_extract_guard()`; guarded/idle states are not conflicts.
- [x] Implement `monitor` / `reassert` / `adopt` policies and the configured auto-resolve switches.
- [x] Fire `climaterouter_conflict_detected` / `climaterouter_conflict_cleared`; make `clear_conflicts` real.
- [x] Handle both-targets-on, unavailable targets, stale outdoor sensor and target mismatch.
- [x] Unit tests for the pure classifier (`target_conflict`) and `Conflict.to_dict()`.
- [ ] Integration tests for policy behaviour (needs the HA test harness).
- [ ] Live verification in the 2026.11 test instance.

### 8.5 M6 — boost and release (implemented in this checkout)

- [x] Support multiple active targets in routing, snapshots and conflict detection.
- [x] Implement feature-flagged `set_boost` / `cancel_boost` with a bounded deadline, heat-only interlock,
  capability checks and no pending handover requirement.
- [x] Fan out commands to both targets only while boost is active; keep `off`/`cool` semantics safe.
- [x] Persist boost across restart, expire it on the exact deadline, and emit start/end events.
- [x] Return to single-target routing through the handover state machine.
- [x] Unit tests for `BoostState` and pure boost routing.
- [x] Add hassfest and HACS validation workflow (`.github/workflows/validate.yml`, brands ignored).
- [ ] Integration tests for boost start/expiry/cancel/restart and return handover.
- [ ] Live verification in the test HA.
- [ ] Tag/release `v0.4.0` (owner action).

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
