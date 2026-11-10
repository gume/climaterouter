# Handover — ClimateRouter

**Date:** 2026-11-10
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
| `2b9b300` | `fix: call async_extract_entity_ids with the 2026.11 signature` |
| `081aa85` | `feat: add forced handover and forward commands during pending handover` |
| `bf19c92` | `docs: record the forced-handover commit` |
| `28fbf93` | `feat: expose read-only VTherm attributes for Lovelace cards` |
| `e0634e2` | `docs: record the card attribute commit` |
| `97c620e` | `feat: add native ClimateRouter lock` |
| `38e0ef0` | `refactor: remove the external manual switch routing input` |
| `ce6d163` | `feat: add proxy-owned manual mode with optional timer` |
| `a028adf` | `feat: expose manual mode switch, timer select, sensors, and return button` |
| `40f510c` | `feat: split the proxy UI lock from the manual schedule lock` |
| `e60bbfc` | `feat: sectioned config/options flows with the new manual and display options` |
| `07e04f4` | `feat: gate VTherm identity attributes behind expose_vtherm_identity` |
| `4ebab35` | `fix: seed the manual baseline before the first UI move` |
| `87274cd` | `chore: bump version to 0.8.0` |
| `e4c6678` | `docs: record the 0.8.0 proxy rework and manual-mode entities` |
| `2caed71` | `feat: show radiator/AC icons on the target sensors` |
| `28cd5b3` | `docs: record the 0.8.1 target-sensor icons` |
| `5a7b28e` | `fix: persist last_handover and align config saves` |
| `8c2abc3` | `feat: add brief help text to config and options fields` |
| `baa2d49` | `test: guard translation parity and field descriptions` |
| `50b6d16` | `docs: correct deprecated service descriptions` |
| `b68bdbb` | `docs: align plan and handover with the 0.8.x implementation` |
| `ade30ba` | `test: stop bind-mounting climaterouter in the Docker lab` |
| `f01abcc` | `docs: correct the Marketplace update mechanism and test lab` |
| `d1190df` | `docs: record the Marketplace investigation commits` |
| `e025cf4` | `fix: initialize the sensor icon attribute` |
| `a1c4b66` | `docs: hand over the 0.8.1 live check and sensor fix` |
| `0635928` | `docs: record the handover commit` |
| `243f98f` | `docs: record the clean e025cf4 Marketplace install` |
| `091c4dd` | `docs: record the clean-install commit` |
| `01fd245` | `style: fix ruff lint and formatting failures` |
| `b94e279` | `test: add config flow integration tests and CI HA harness` |
| `a19f2d6` | `fix: expose temperature_unit alongside native_temperature_unit` (superseded by `beda94c`) |
| `fc921bf` | `test: cover coordinator routing, services, and entity platforms` |
| `306ce39` | `docs: record the automated test suite and CI harness` |
| `759bca5` | `fix: register the sectioned options flow explicitly` |
| `e0e17db` | `test: cover duplicate, reconfigure, and options flows` |
| `a41b7e5` | `test: cover fallback, startup adoption, persistence, and handover` |
| `a20e1d9` | `docs: record the expanded integration test coverage` |
| `834781e` | `ci: label the combined test step accurately` |
| `beda94c` | `test: shim the legacy climate unit attribute for older HA harnesses` |
| `ddef6d5` | `test: cover boost activation and cancel` |
| `bfda92e` | `test: cover setpoint conflict detection` |
| `9ac7679` | `test: cover UI lock gating` |
| `590aeb4` | `docs: note the test-harness compatibility shims` |
| `98f0d20` | `docs: record boost, conflict, and lock test coverage` |
| `bd35514` | `fix: support the HA 2025.1.4 service and climate APIs` |
| `06841d0` | `chore: keep the test harness intentionally unpinned` |
| `57d68e2` | `ci: enforce a 75 percent coverage floor` |
| `8c81271` | `fix: complete HA 2025.1.4 climate property compatibility` |
| `bbfcf12` | `test: cover handover transitions and persisted deadlines` |
| `514200b` | `test: cover climate optimism, availability, and auxiliary entities` |
| `2c5c1de` | `fix: support Home Assistant 2025.1.4 and bump to 0.8.2` |
| `724111f` | `test: capture handover-abort events synchronously` |
| `9ee81e2` | `ci: update checkout and setup-python actions` |
| `c560616` | `fix: satisfy hassfest manifest and config schema checks` |
| `aeab87d` | `docs: record the hassfest and HACS validation fixes` |
| `58f0ba5` | `test: cover expiry, relock, and conflict policies` |
| `1b1c818` | `test: cover remaining services and diagnostics` |
| `3419152` | `docs: record 109 tests and 85 percent coverage` |
| `44e73a4` | `test: cover config-flow validation branches` |
| `3201acd` | `docs: record config-flow coverage` |
| `4549614` | `test: assert conflict history and clear events` |
| `821b28d` | `docs: record conflict-clear coverage` |
| `02e1bcd` | `fix: cancel expiry timers when the watchdog fires them` |
| `43e3257` | `docs: record watchdog expiry fix and live 0.8.2 state` |
| `ff3474b` | `chore: bump version to 0.8.3` |
| `bd0305d` | `test: cover service dispatch and inactive target detection` |
| `7160c87` | `test: cover boost handover exit, flows, and display branches` |
| `32c4ae7` | `fix: satisfy strict type checking` |
| `24482c8` | `ci: add mypy and a Python 3.12/3.13 unit matrix` |
| `acd5b02` | `test: cover coordinator command, boost, and lock validation` |
| `a6c1bb3` | `test: cover conflict clear-after ageing and startup auto-relock` |
| `d2ced17` | `test: cover Lock B rejection and manual carry-over across handover` |
| `563ead4` | `feat: add brand icon and detailed conflict/timer sensors` |
| `23290d2` | `feat: explain off-target setpoints in the mismatch detail` |
| `ee0a878` | `docs: point the 0.8.4 handover at the final commit` |
| `1972d1e` | `ci: clarify the local brand asset location` |
| `cf53fc8` | `fix: defer scheduler commands while manual mode is active` |
| `f0d423c` | `fix: adopt direct user changes on the active thermostat as manual moves` |
| `16e56ca` | `feat: proxy the AC fan mode` |
| `2bbaae5` | `fix: report zero remaining time when a timer is inactive` |
| `15e50c7` | `fix: group diagnostic and configuration entities correctly` |
| `f9dd2b1` | `feat: optionally pause Velair during manual mode` |
| `e4c829b` | `feat: stop the AC device thermostat while the VTherm is idle` |
| `28ae295` | `fix: report an already published release instead of failing` |
| `2aaf9d1` | `docs: record the published 0.8.6 release` |
| `fe3168d` | `chore: bump version to 0.8.7` |
| `e8380bb` | `fix: clarify the config field labels` |

Everything through `d0e990d` is on `origin/main`; `v0.8.4` is tagged and released, and the 0.8.5 commits
(`cf53fc8`, `f0d423c`) add the scheduler/manual fix. The test instance still runs the Marketplace release
**v0.8.3** (tag `v0.8.3`, commit `723c5c0`): `update.climaterouter` reported `installed_version` =
`latest_version` = `v0.8.3` at the last live check. The 0.8.4 release was published on 2026-11-09 but has not yet
been installed in the test instance. The 0.8.5 release is cut from the commit that adds this handover update; after
the Marketplace refresh/restart, install it and record the live result. The **0.8.6** release (tag/release
`v0.8.6`, commit `c002372`) adds the fan proxy, inactive-timer reporting, diagnostic grouping, opt-in Velair pause,
and the AC idle bypass. It was published on 2026-11-10 but has not been installed or verified live yet. `28ae295`
follows it with a release-helper fix that reports an already published version cleanly instead of failing on an
empty commit range. The **0.8.7** release (tag/release `v0.8.7`, commit `0d96b48`) is a maintenance release with
the release-helper fix and documentation, and no integration behaviour changes. **0.8.8** (tag/release `v0.8.8`,
commit `9ca79ad`, published 2026-11-10) adds the config field-label review (issue 4). Neither has been installed
or live-verified yet.

---

## 1. Where things stand

Milestones M1–M6 from [`PLAN.md`](PLAN.md) are implemented. The owner reports live verification through version
**0.8.0**. **0.8.1** was first installed as `d3af8b4`, which exposed a regression: nine sensors failed to add because
`RouterSensor.icon` returned an uninitialized `_attr_icon`. Fixed in `e025cf4`; **0.8.2** (`aeab87d`) added the HA
2025.1.4 compatibility and hassfest schema fixes. The test instance currently runs the Marketplace release
**v0.8.3** (`723c5c0`); all eleven sensors are available and the target icons are correct.

| Milestone | State | Notes |
|---|---|---|
| M1 — skeleton and config flow | Done | Config/options/reconfigure flows, device, proxy entity, services, diagnostics, translations, CI. |
| M2 — proxy and routing | Done, live-verified | Hysteresis, route override, `off`/`cool`, command forwarding, status entities. The external manual switch was removed in 0.8.0. |
| M3 — safe handover | Done, live-verified | Idle detection, off confirmation, timeout, queued desired state, startup reconciliation, events. The manual forced handover and command forwarding during `PENDING` were verified live in 0.5.0 (see section 6). |
| M4 — manual mode | Done, live-verified through 0.8.0 | Proxy-owned manual mode (temperature/preset/mode), optional timer with configurable default/maximum, baseline capture/restore, non-resetting repeat moves, persistence, handover carry-over, events, switch/select/button/sensors. Replaces the earlier bounded override. |
| M5 — conflicts | Done, live-verified through 0.8.0 | Setpoint/preset/mode mismatch, unavailable targets, underlying timed presets, both-on and inactive-target-on detection; own-context and guard suppression; `monitor`/`reassert`/`adopt` policies, auto-resolve switches, events, history and clear button. Unit coverage is limited to the pure classifier. |
| M6 — boost | Done, live-verified through 0.8.0 | Feature-flagged both-target boost with heat-only/availability/handover interlocks, persistence, expiry, start/end events, active/remaining entities, and a handover back to single-target routing. |

The post-M6 **native lock** (0.7.0) and the **proxy rework** (0.8.0) are live-verified through 0.8.0. The rework
includes proxy-owned manual mode and timer, two separate locks, sectioned config/options flows, and VTherm display
compatibility split into harmless versus identity keys. Iteration 1 (`38e0ef0`) removed the external manual-switch
routing input; iteration 2 (`ce6d163`) added the proxy-owned manual mode model, timer, persistence, and services;
iteration 3 (`a028adf`) exposed the standard-card entities; iteration 4 (`40f510c`) split the accidental-touch UI
lock (Lock A) from the manual/schedule lock (Lock B); iteration 5 (`e60bbfc`) rebuilt the config, options, and
reconfigure forms as sections with a menu-based options flow; iteration 6 (`07e04f4`) made the VTherm identity
attributes opt-in.

Version **0.8.1** is the follow-up batch: state-dependent radiator/AC icons on the target sensors, brief
explanations under the config/options fields, persisted `last_handover`, preset comparison in the target-mismatch
sensor, consistent config storage (schema-only `entry.data`, empty `entry.options`), a translation-sync test, and
the plan/handover alignment. The icon property initially broke the other sensors; `e025cf4` initializes the shared
icon attribute and restores them.

Version **0.8.4** (tag/release `v0.8.4`, commit `9134b58`; code through `1972d1e`) adds the local brand assets, keeps the manual-timer select
available with an `off` state and crossed-out timer icon when unused, keeps the current mode when manual mode
expires without a schedule baseline, and adds text sensors that explain active conflicts and radiator/AC target
mismatches.

Version **0.8.5** makes manual mode authoritative against schedulers. Schedule/automation moves received while
manual mode is active are remembered as the baseline instead of being rejected, so they cannot change the manual
setpoint or turn the target off, and timer expiry/return-to-schedule follows the scheduler's latest move (including
a deferred `off`). If an automation writes directly to the underlying VTherm, the coordinator re-asserts the manual
state; a change that carries a `user_id` (the user moving the VTherm card itself) is adopted into manual mode
instead, keeping the running timer. The manual-timer select remains `off` when inactive. A small service-extraction
compatibility fix also covers Home Assistant releases where `async_extract_entity_ids()` has an `expand_group`
second parameter. The device-info test uses `async_entries_for_config_entry`, which works on both the older CI
harness and Home Assistant 2026.11, so the full suite is green on both.

Version **0.8.6** implements the first batch of owner-reported issues (`issues.txt`):

1. **Fan proxy** — the AC fan mode is stored in the desired state and applied only while the AC is active. A user
   fan change never starts or extends manual mode.
2. **Inactive timers report zero** — `manual_remaining`/`boost_remaining` and the climate/select
   `remaining_minutes` attributes return `0` (not `null`) when the timer is off or expired.
3. **Diagnostic grouping** — the target/reason/detail sensors are `EntityCategory.DIAGNOSTIC`, and the route
   override, manual timer, recalculate and clear-conflict controls are `EntityCategory.CONFIG`.
4. **Opt-in Velair integration** — `velair_enabled` calls `velair.pause` when manual mode starts (including a
   restored session) and `velair.resume_automatic_control` on the ClimateRouter proxy when manual mode ends.
5. **Optional AC idle bypass** — in heat mode, when the AC VTherm reports `idle`, write a VTherm preset temperature
   (`frost`/`eco`/`comfort`, default `frost`) directly to the device thermostat below it. The entity is auto-detected
   from `vtherm_over_climate.underlying_entities` or configured explicitly. Nothing is restored by ClimateRouter;
   the VTherm is expected to restore its own setpoint when heating resumes.

Issue 4 in `issues.txt` ("overview on the filed names") was intentionally skipped by the owner for this batch.

Version **0.8.7** is a maintenance release. It publishes the fixed `scripts/release.sh` (the previous version
failed when re-run after a release because it used the current tag as the previous one) and the updated handover
notes. It contains no integration behaviour changes.

Version **0.8.8** is the config field-label review (issue 4). Only user-facing labels changed; storage keys and
routing/climate behaviour are untouched. Tag/release `v0.8.8` on `9ca79ad`, published 2026-11-10.

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
├── vt_display.py        # read-only VTherm attributes for Lovelace cards
├── entity.py            # shared coordinator entity + DeviceInfo
├── binary_sensor.py     # active/heating/cooling/pending/conflict/stale/ready
├── sensor.py            # active/pending/reason/outdoor/timestamps/counts
├── select.py            # route override + manual timer
├── switch.py            # manual mode on/off
├── button.py            # recalculate, clear conflicts
├── lock.py              # optional native access lock
├── services.py          # service registration and entity resolution
├── diagnostics.py       # config-entry diagnostics
├── config_flow.py       # user/options/reconfigure flows and validation
├── services.yaml
├── strings.json         # source of translations
└── translations/en.json # kept in sync; test_translations.py guards drift

tests/
├── conftest.py          # stubs the `climaterouter` package; no HA needed
├── test_router.py       # routing precedence, hysteresis, fallback (pure)
├── test_models.py       # config parsing, desired-state round-trip, lock source matrix
├── test_vt_display.py   # card-facing VTherm attribute selection and lock exclusion
└── test_translations.py # strings/en.json parity and field-description coverage

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
4. Outdoor hysteresis:
   - current target AC stays AC while `outdoor > cold_threshold`;
   - current target radiator stays radiator while `outdoor <= mild_threshold`;
   - no current target: AC above `mild_threshold`, radiator at/below `cold_threshold`, radiator in the dead band.
5. Missing/stale outdoor input holds the last route; with no history it falls back to radiator.
6. Unavailable or mode-incapable targets fall back to the other target when
   `fallback_on_unavailable` is enabled.

The route override is proxy-owned and comes only from the built-in select (or its services). The former external
manual switch input was removed in 0.8.0. `min_route_dwell` suppresses non-explicit route changes after a completed
handover.

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
- A command received while a handover is `PENDING` is forwarded to the currently active target **and** kept in the
  desired state for the pending target. It is not silently ignored while the old target keeps running on its old
  setpoint.

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
- `button.<name>_force_handover` / `climaterouter.force_handover` completes a pending handover immediately. It
  still sends `off` to the old target first, but skips both the idle confirmation and the off-confirm timeout. If
  the old target stays on, normal conflict detection reports the overlap. The button is available only while a
  handover is in progress.
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
- `fan_mode` and `fan_modes` come from the AC target. A fan change is stored in the desired state but only sent to
  an **active** AC; it is replayed on handover. Fan changes never start or extend manual mode.
- Presets are the intersection of both targets' presets, or the union when the intersection is empty, plus `none`.
- `min_temp`, `max_temp` and `target_temperature_step` come from the active target (or the AC/first available one).
- `sensor.<name>_active_target` and `sensor.<name>_pending_target` use a state-dependent icon (`mdi:radiator` for
  radiator, `mdi:air-conditioner` for AC, `mdi:hvac` for both, `mdi:hvac-off` for none) instead of the generic eye.

### 3.6 Manual mode (proxy-owned)

- Manual mode is owned by the proxy and is **not** mirrored to either VTherm.
- A user moving the temperature or changing the preset in the UI enters manual mode automatically. Schedule and
  automation commands (no `user_id` in the context) do not enter manual mode.
- Additional user moves while manual mode is active update the manual value but **never reset the timer**.
- While manual mode is active, schedule/automation commands (including an `off`) are **deferred**: the latest
  command is stored as the schedule baseline but is not applied to the targets. This protects the manual setting
  and makes the timer expiry (or `return_to_schedule`) return to the scheduler's latest move. Automations still
  cannot change manual mode itself (enter/timer) while `manual_blocks_schedule` is on.
- `duration_minutes` defaults to `default_manual_minutes`; `0` means no countdown. The timer can be changed or
  switched off later with `climaterouter.set_manual_timer` (minutes `0` or omitted = infinite).
- The coordinator keeps a **baseline** desired state (the latest schedule command) and a separate `ManualMode`
  (desired state, absolute UTC deadline or `None`, baseline snapshot, start time). The effective desired state is
  the manual desired state while active.
- A user move starts manual mode without modifying the baseline, so `climaterouter.return_to_schedule` restores the
  schedule value rather than the last manual value. Schedule commands received while manual mode is active update
  the baseline but do not replace the manual value.
- Manual mode is authoritative over the active target: if an external scheduler/automation writes directly to the
  underlying VTherm, the coordinator re-sends the manual mode/setpoint (guarded targets are left alone). A direct
  write that carries a `user_id` (the user moving the VTherm card itself) is **adopted** instead: it updates the
  manual value, starts manual mode if it was inactive, and keeps a running timer. Changes to the inactive target,
  and `off`/`unavailable` writes, are not adopted.
- An explicit **user** `off` ends manual mode (`cause=off`). A scheduler/automation `off` is deferred and applied
  when manual mode ends. Timer expiry ends manual mode with `cause=expired`.
- Handovers use the effective desired state, so manual mode and its deadline carry over to the new target. The
  manual mode is persisted with an absolute deadline; expired sessions are discarded on startup, infinite sessions
  are restored as-is.
- Services: `climaterouter.enter_manual_mode`, `set_manual_timer`, `return_to_schedule`; the old
  `set_manual_override` / `cancel_manual_override` names remain as aliases.
- Events: `climaterouter_manual_mode_started`, `climaterouter_manual_mode_ended`, and
  `climaterouter_manual_timer_changed`.
- Standard-card entities: `switch.<name>_manual_mode` (on = manual, off = return to schedule),
  `select.<name>_manual_timer` (`off` or minutes; always available and shows `off` with a crossed-out timer icon
  when no countdown is running), `button.<name>_return_to_schedule`,
  `binary_sensor.<name>_manual_mode`, `sensor.<name>_manual_remaining`, `sensor.<name>_manual_until`, and a
  diagnostic `sensor.<name>_manual_timer_minutes`.
- If manual mode expires (or is ended) before any schedule command exists, the manual state is promoted to the
  baseline so the target keeps running instead of the proxy going blank.
- The climate entity exposes `manual_mode`, `manual_active`, `manual_until`, `manual_timer_minutes`, and
  `manual_remaining_minutes`; the legacy `override` attribute is still present for older cards. A timer that is off
  or expired reports `0` minutes (and the manual-timer select stays `off`) rather than a fake countdown.
- **Optional Velair integration** (`velair_enabled`, default off): when manual mode starts, including a session
  restored after a restart, the coordinator calls the global `velair.pause`; when manual mode ends (timer,
  return-to-schedule, or `off`) it calls `velair.resume_automatic_control` on the ClimateRouter proxy entity. The
  user's Velair setup is expected to manage the proxy while manual mode is not active.

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
- Exposed through `binary_sensor.<name>_conflict`, `sensor.<name>_conflict_count`,
  `sensor.<name>_conflict_detail` (a short human-readable summary plus the full conflict list in its attributes),
  the proxy climate's conflict attributes and diagnostics. During boost each active target is compared; `adopt` is
  skipped because two targets cannot define one baseline.
- `binary_sensor.<name>_target_mismatch` / `sensor.<name>_target_mismatch_detail` compare the radiator and AC with
  each other (setpoint and preset), not with the desired state. The detail sensor names the differing values and
  exposes both targets' temperatures, presets, modes and availability as attributes. It explicitly notes when a
  target is off or unavailable, because a stale setpoint on the inactive target is the usual reason for this
  diagnostic being on.

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

### 3.9 Lovelace card compatibility (Equinox)

Equinox 0.4.4 builds its VTherm view model only when the climate entity exposes VTherm attributes
(`is_over_*`, `configuration`, `specific_states`, ...). The proxy forwards a **read-only** subset from the active
target (`vt_display.py`), split into two groups:

**Always forwarded (harmless display data):**

- `is_over_switch` / `is_over_valve` / `is_over_climate`, `power_percent`, `valve_open_percent`, `on_percent`;
- `configuration` (`type`, `have_valve_regulation`, `proportional_function`);
- read-only managers for power, presence, window, safety and heating-failure;
- `vtherm_over_valve` / `vtherm_over_climate_valve` regulation details.

**Only with `expose_vtherm_identity` (default off):**

- the `is_power_configured` / `is_presence_configured` / `is_motion_configured` / `is_window_configured` /
  `is_window_auto_configured` / `is_safety_configured` / `is_heating_failure_detection_configured` /
  `is_repair_incorrect_state_configured` flags;
- a curated `specific_states` with `messages`/`hvac_mode_reason`/`hvac_off_reason` (without `is_locked`).

The identity group makes some cards, HOLM in particular, switch into their full VTherm mode. Those modes render
controls backed by `versatile_thermostat.*` services, which cannot run on a proxy, so they stay off unless a card
explicitly needs them. Enabling the option re-enables the previous 0.6/0.7 behaviour.

When two targets are active (boost), the target that reports a regulation percentage wins, so the gauge shows the
radiator's `power_percent`. An `over_climate` target has no regulation percentage, matching the real VTherm.

The **lock is deliberately not forwarded**. Equinox's lock button is hard-wired to
`versatile_thermostat.lock`/`unlock` on the card entity. Those are VTherm platform entity services, so a
ClimateRouter proxy cannot receive them; exposing `is_lock_configured` would only render a button that fails.
Options are:

1. Set `hide_lock_button: true` on the Equinox card when it targets the proxy.
2. Lock the underlying VTherm entities with `lock_users=true` and `lock_automations=false`, so the VTherm UI is
   protected while ClimateRouter can still control them.
3. Use the native ClimateRouter lock described in §3.10; Equinox upstream support for a configurable
   lock service/entity is still needed before its lock button can drive it.

### 3.10 Two proxy locks

**Lock A — accidental-touch UI lock.** Optional and disabled by default. Enable `lock_enabled` in the options,
optionally set a 4–8 digit `lock_code`, and set `auto_relock_sec` (0 disables auto-relock).

- The integration creates `lock.<name>_lock` (displayed as "UI lock"). Standard `lock.lock`/`lock.unlock` and the
  `climaterouter.lock`/`climaterouter.unlock` services are available. The services accept an optional `code`.
- It only rejects **user-initiated** commands (service-call context has a `user_id`). Schedule/automation commands
  are never blocked, so handovers and scheduled operation continue while the UI is locked.
- Locking does not require a code. Unlocking with a configured code requires the exact code; a wrong or missing
  code raises `HomeAssistantError` and leaves the lock locked.
- Unlock is intentionally brief: an auto-relock deadline is scheduled and persisted as an absolute UTC timestamp;
  after a restart the remaining delay is resumed (or the router locks immediately when the deadline already
  passed). The lock state is cleared from persisted state when the feature is disabled.
- Blocked: `set_temperature`, `set_hvac_mode`, `set_preset_mode`, `turn_on`, `turn_off`, manual-mode entry/timer,
  and boost.

**Lock B — manual/schedule lock.** Controlled by `manual_blocks_schedule` (default on) and the manual-mode state
itself; it is not mirrored to either VTherm.

- While manual mode is active, climate commands without a `user_id` (Scheduler, Velair, automations, scripts) are
  **deferred**: they update the schedule baseline but do not change the active target. An `off` from a scheduler is
  deferred too, so it cannot stop a manual session; it becomes the state applied when manual mode ends. User
  commands are always accepted, so the manual setpoint and timer can be adjusted without unlocking.
- A direct write to the active VTherm that carries a `user_id` is adopted as a manual move (see section 5): it is not
  re-asserted, so a user moving the VTherm card itself is not fought by the protection. Writes without a `user_id`
  are re-asserted.
- Automation calls that try to change manual mode itself (`enter_manual_mode`, `set_manual_timer`) are still
  rejected while manual mode is active.
- `climaterouter.return_to_schedule` is deliberately not gated, so an explicit return (including an automation)
  can end manual mode. Lock A still blocks user-initiated service calls when locked.
- The manual-mode switch (`switch.<name>_manual_mode`) is the user-facing Lock B control: on enters manual mode,
  off returns to the schedule.
- `sensor.<name>_manual_mode`, `sensor.<name>_manual_remaining`, `sensor.<name>_manual_until`, and the
  `schedule_locked` climate attribute expose Lock B. The proxy climate does **not** expose `is_lock_configured`,
  `lock_manager`, or `is_locked`, so Equinox does not render a broken lock button. Diagnostics expose both lock
  states and redact `lock_code`.

### 3.11 Config, options and reconfigure flows

All three flows share the same sectioned schema (`config_flow.py`):

| Section | Contents |
|---|---|
| Thermostats | name, radiator, AC, outdoor sensor, AC idle-bypass entity/flag/preset |
| Routing | thresholds, dwell, handover/off/startup/settle timings, fallback |
| Manual mode | `default_manual_minutes`, `max_manual_minutes`, `manual_blocks_schedule`, `velair_enabled` |
| Conflicts | policy, auto-resolve flags, outdoor staleness, setpoint tolerance |
| Boost | `boost_enabled` |
| UI lock | `lock_enabled`, `lock_code`, `auto_relock_sec` |
| Lovelace display | `expose_vtherm_identity` |

- Setup and reconfigure show every section in one form. Sections other than Thermostats start collapsed.
- The options flow is a menu: each entry opens that section, submits and saves immediately, then returns to the
  menu. **Finish** closes the flow. This avoids a single long options form.
- Every field has a brief `data_description` helper text in `strings.json` and `translations/en.json`;
  `tests/test_translations.py` enforces that both files match and that no field is missing help.
- Every save writes a cleaned, schema-only config into `entry.data` and clears `entry.options`. The coordinator
  still merges `{**entry.data, **entry.options}`.
- `default_manual_minutes=0` means new manual sessions start without a countdown. It must not exceed
  `max_manual_minutes`.
- The former `default_override_minutes` / `max_override_minutes` keys and the `lock_users` / `lock_automations`
  flags are no longer part of the schema. `RouterConfig.from_mapping` still reads the old override keys as a
  fallback for entries created before 0.8.0; the schema-only save drops them from `entry.data`.
- There is no manual-switch configuration: routing is forced only through the built-in route-override `select`.
- Entity categories: the active/pending target, route reason, conflict detail, mismatch detail, timer minutes and
  other explanatory read-only entities are `EntityCategory.DIAGNOSTIC`; the route-override/manual-timer selects and
  the recalculate/clear-conflict buttons are `EntityCategory.CONFIG`.

#### 3.11.1 Field-label review (0.8.8)

Issue 4 was a review of the configuration field names. The storage keys were deliberately kept stable so existing
entries keep working; only the user-facing labels in `strings.json` / `translations/en.json` were clarified:

- Routing: "Outdoor cold threshold" / "Outdoor mild threshold" instead of the ambiguous "Cold/Mild threshold";
  "Minimum route dwell time" and "Handover idle confirmation time" spell out the timing fields; the fallback field
  now says "Fall back when a target is unavailable".
- Conflicts: "Turn off non-selected targets when idle" and "Turn off the idle target when both are on" replace the
  ambiguous "idle non-selected targets" / "simultaneous" wording; "Outdoor sensor stale after" replaces
  "Outdoor sensor staleness".
- AC idle bypass: the optional entity is labelled "Device thermostat below the AC VTherm", the flag is "Enable AC
  idle bypass", and the preset is "Preset used for the idle setpoint".
- Manual mode: "Pause Velair in manual mode".
- Boost: the stale "(experimental)" suffix was removed.

No config keys were renamed, so no migration is needed. `RouterConfig.from_mapping` continues to read the same
keys, and the schema-only save behaviour is unchanged.

### 3.12 AC idle bypass

Some AC units keep a minimum compressor/indoor-fan speed while the VTherm reports `idle`, so the room keeps
heating slowly. The optional AC idle bypass writes a low setpoint directly to the **device thermostat below the AC
VTherm**:

- Enabled with `ac_idle_bypass_enabled` (default off); `ac_idle_bypass_preset` selects a VTherm preset
  (`frost`, `eco`, or `comfort`; default `frost`) and its `preset_temperatures` value is used as the idle setpoint.
  There is no fixed 7 °C option; the preset comes from the VTherm configuration.
- `ac_idle_bypass_entity_id` may be empty. Auto-detection uses the first `climate.*` entry in the AC VTherm's
  `vtherm_over_climate.underlying_entities`. A configured entity equal to the AC VTherm is ignored.
- It applies only while the desired mode is `heat`, the AC is the active target, the AC VTherm is in `heat` with
  `hvac_action=idle`, and no VTherm guard or timed preset is active. It is applied once per idle episode; a later
  idle episode after the VTherm has heated again triggers a new write.
- ClimateRouter does **not** restore the device setpoint. Versatile Thermostat is expected to restore its own
  setpoint when heating resumes. The write is skipped when the device is missing/unavailable, when the VTherm has
  no usable preset temperature, or when the device is already within `temperature_tolerance` of the target.

---

## 4. Test lab state

Defined in `test_environment/`; full instructions in [`TEST_ENVIRONMENT.md`](TEST_ENVIRONMENT.md).

- Container: `climaterouter-ha` (Compose project `climaterouter-test`).
- URL: <http://localhost:38123> (host port 38123 → container 8123).
- HA image: `ghcr.io/home-assistant/home-assistant:stable`, currently **2026.11.0**, Python 3.14 inside.
- The live instance runs Home Assistant **2026.11**, where the built-in **Marketplace** replaced HACS. ClimateRouter
  was originally installed by bind-mounting the checkout into the container, so the Marketplace did not track it.
  The mount has been removed and ClimateRouter is now a Marketplace-managed custom repository
  (`gume/climaterouter`, repository id `1448098130`). The container runs on this host and mounts
  `test_environment/config` as `/config`; that directory is git-ignored runtime state.
- The Marketplace can identify a custom repository by release/tag as well as by commit. The live update entity
  currently reports `installed_version` = `latest_version` = **v0.8.3** and a `release_url` for tag `v0.8.3`
  (`723c5c0`), so the Marketplace is following the published release. Earlier live tests covered `aeab87d`
  (version **0.8.2**, commit-based), `e025cf4` (version **0.8.1**) and `fd009ea` (version **0.8.0**). Releases
  `v0.8.4` (2026-11-09) and `v0.8.5` now exist; after the next Marketplace refresh the update entity should offer
  `v0.8.5`.
- Installed custom repositories refresh their metadata at Home Assistant startup and then every **48 hours**
  (`marketplace/base.py`, `timedelta(hours=48)`). A push or release made after the last startup is therefore not
  visible until Home Assistant restarts, the repository is refreshed from the Marketplace, or 48 hours pass.
- The owner tests remotely with a long-lived Home Assistant token; the component itself is not bind-mounted.
- Live-entering v0.4.0 exposed a real service bug: HA 2026.11 changed `async_extract_entity_ids()` to take only the
  `ServiceCall`. The previous `(hass, call)` call made every `climaterouter.*` service fail with
  `AttributeError: 'HomeAssistant' object has no attribute 'hass'`. Fixed in `2b9b300` (version 0.4.1) and verified
  live: `climaterouter.recalculate` returns HTTP 200.
- The config entry was recreated during the Marketplace migration. Current entry id
  **`01M6TG5YKCZCM4B5N5WM29AVJ4`** (created 2026-11-07); the device is in area `living_room` and the entity ids use
  the `living_room_climaterouter_*` form (e.g. `climate.living_room_climaterouter`) so existing dashboards and
  Scheduler references keep working.
- `fake_hvac` entries: one system, `Fake HVAC Lab`, exposing `climate.living_room_fake_ac`,
  `sensor.living_room_fake_room_temperature`, `sensor.living_room_fake_outdoor_temperature`,
  `switch.living_room_fake_radiator`, and the matching `number` controls.
- Router entry **`ClimateRouter`** (entry id `01M6TG5YKCZCM4B5N5WM29AVJ4`), read from the live config entry:
  - radiator `climate.living_room_room_radiator`, AC `climate.living_room_room_ac`;
  - outdoor sensor `sensor.living_room_fake_outdoor_temperature`;
  - `cold_threshold=-10`, `mild_threshold=-5`, `min_route_dwell=60`, `handover_idle_confirm=30`,
    `off_confirm_timeout=30`, `startup_grace=10`, `settle_time=10`, `outdoor_stale_after=3600`;
  - `conflict_policy=monitor`, `auto_resolve_idle_targets=true`, `auto_resolve_simultaneous=true`,
    `fallback_on_unavailable=true`;
  - `default_manual_minutes=60`, `max_manual_minutes=1440`, `manual_blocks_schedule=true`,
    `expose_vtherm_identity=true`, `temperature_tolerance=0.2`, `boost_enabled=false`;
  - `lock_enabled=false`, a lock code is stored, `auto_relock_sec=30`. The stale
    `lock.living_room_climaterouter_ui_lock` entity restores as `unavailable` while the lock is disabled.
  The entry was created before 0.8.0 and may still store the removed external manual-switch key. That key is ignored;
  open **Configure** once after updating and save any section to rewrite the stored config in the new shape. The
  schema-only save also drops the key from `entry.data`.
- Live router entities use the `living_room_climaterouter` slug, e.g.
  `climate.living_room_climaterouter`, `sensor.living_room_climaterouter_active_target`,
  `binary_sensor.living_room_climaterouter_conflict`.
- VTherm entities expose the common presets `none`/`frost`/`eco`/`comfort`/`boost`; both currently support
  `heat` and the AC also supports `cool`.
- Baseline state after the 0.5.0 verification: `active_target=ac`, radiator `off`, AC `heat` at 23.5 °C,
  outdoor 6.0 °C fresh, `route_reason=hysteresis`, no pending handover. The earlier both-on/stale state was cleaned
  up.

The `.storage` directory is git-ignored. `test_environment/reset.sh` removes it, so test entries are disposable; do
not encode assumptions about them in code.

The HA long-lived token is kept outside the repository at `~/.config/climaterouter/ha_token` (mode `600`) and is
read by the verification commands; never copy it into the checkout or commit it.

---

## 5. Running checks

Local machine here uses Python 3.10, while the project targets 3.12+ and HA 2026.11. The unit tests are written to
run on 3.10 (`str, Enum` with `# noqa: UP042`, `timezone.utc` with `# noqa: UP017`).

```bash
# lint / format / full test suite (venv with requirements_test.txt)
/path/to/venv/bin/ruff check .
/path/to/venv/bin/ruff format --check .
/path/to/venv/bin/pytest

# pure tests only: the integration directory is skipped without Home Assistant
python3 -m pytest

# Home Assistant lab
cd test_environment
docker compose up -d
docker compose logs -f homeassistant
```

CI installs `requirements_test.txt` (ruff, pytest and the Home Assistant test harness) and runs both the pure unit
tests and the integration tests under `tests/integration/`. A separate `Validate` workflow runs
`home-assistant/actions/hassfest` and `hacs/action` (integration category, brands ignored because the domain has no
brand assets yet).

The PyPI snapshot reachable from this host only offers `pytest-homeassistant-custom-component` 0.13.205, which pins
Home Assistant 2025.1.4 rather than 2026.11. CI installs the newest release, which tracks 2026.11. The production
code handles both without test-only shims: `services.py` picks the correct `async_extract_entity_ids` signature at
import time, and `climate.py` exposes the legacy `temperature_unit`/`current_temperature`/`target_temperature`
properties only when the base class lacks the `native_*` ones. The integration tests exercise those real
compatibility paths.

Without the harness installed, `pytest` still passes the 56 pure tests and skips the integration directory.

---

## 6. What was verified manually

Run against the live Home Assistant through the REST/WebSocket API with a long-lived token. M1–M3 used the two fake
ACs; later versions use the two VTherm entities described in section 4.

| Scenario | Result |
|---|---|
| Config flow creates entry and entities | OK |
| Cold outdoor, `heat` → radiator | OK |
| Outdoor 12, radiator idle → handover to AC | OK: radiator off, then AC on, queued setpoint applied |
| Outdoor 0, AC idle → handover back to radiator | OK |
| Handover while old target is heating | stays `pending`; old target is not interrupted |
| Proxy `off` | both targets off, handover cancelled |
| Route override `radiator` / `ac` | OK |
| Setpoint change during pending handover | 0.5.0: forwarded to the active AC immediately (23.5) and kept for the pending radiator; old target no longer overwrites it |
| Forced handover button/service | 0.5.0: AC off, radiator started at 23.5 without waiting for idle, `last_handover` updated, button unavailable afterwards |
| Temperature forwarding while steady | OK |
| Restart with persisted `heat` | resumes without crashing when targets start late |
| No prior command, underlying target already on | adopted, no commands sent |
| Diagnostics endpoint | OK |
| 0.8.1 install through the Marketplace | Installed `d3af8b4`; `update.climaterouter` went from `fd009ea` to `d3af8b4` and then to `off` |
| 0.8.1 target icons | `sensor.*_active_target` = `ac` with `mdi:air-conditioner`; `sensor.*_pending_target` = `none` with `mdi:hvac-off` |
| 0.8.1 sensor regression | Nine sensors (`route_reason`, `outdoor_temperature`, manual/boost/last-handover/last-command/conflict) failed to add with `AttributeError: 'RouterSensor' object has no attribute '_attr_icon'` |
| 0.8.1 sensor fix (`e025cf4`) | Hot-patched first, then installed cleanly through the Marketplace after the push; all nine sensors are available and there are no `Error adding entity` lines |
| 0.8.1 clean `e025cf4` build | `update.climaterouter` = `off`, `installed_version` = `e025cf4`; eleven `sensor.*` entities available; `active_target` = `ac` (`mdi:air-conditioner`), `pending_target` = `none` (`mdi:hvac-off`) |
| 0.8.2 install (`aeab87d`) | `update.climaterouter` = `off` with `installed_version` = `latest_version` = `aeab87d`; the config entry is loaded and the ClimateRouter entities are available |
| 0.8.2 entity state | `active_target` = `ac`, `pending_target` = `none`, `outdoor_sensor_stale` = `off`, route reason `hysteresis`, `conflict_count` = 0 |
| 0.8.3 install (`v0.8.3`) | `update.climaterouter` = `off` with `installed_version` = `latest_version` = `v0.8.3`, `release_url` = tag `v0.8.3`; all ClimateRouter entities load |
| 0.8.3 live state (2026-11-09) | `active_target` = `ac`, `pending_target` = `none`, `route_reason` = `fallback_outdoor`, `outdoor_sensor_stale` = `on`, `target_mismatch` = `on` (radiator off at 23.0/none vs AC heat at 20.5/comfort), `conflict` = `off`, manual timer select `unavailable` (the 0.8.4 `off` badge is not installed) |
| 0.8.4 release published | Tag/release `v0.8.4` on `9134b58` (2026-11-09); not installed in the test instance yet |
| 0.8.5 release published | Tag/release `v0.8.5` cut from this handover commit; pending Marketplace install and live check |
| 0.8.6 release published | Tag/release `v0.8.6` on `c002372` (2026-11-10); not installed in the test instance yet |
| 0.8.7 release published | Tag/release `v0.8.7` on `0d96b48` (2026-11-10); release-helper fix and docs only |
| 0.8.8 release published | Tag/release `v0.8.8` on `9ca79ad` (2026-11-10); pending Marketplace install and live check |

The owner reports live verification through version **0.8.0** for M4 manual mode, M5 conflicts, M6 boost, the native
lock, the 0.8.0 proxy rework, and the read-only VTherm display pass-through. The live instance currently runs the
Marketplace release **v0.8.3** (`723c5c0`): the update entity reports `installed_version` = `latest_version` =
`v0.8.3`, all ClimateRouter entities load, and the route/conflict sensors report the expected state. The 0.8.4
brand/sensor batch and the 0.8.5 manual/scheduler fixes are released and waiting for installation.

The remaining checks are the interactive ones that need the UI: saving the config/options sections, the field
descriptions, and a real handover to confirm `last_handover` persistence.

Automated coverage now includes natural manual/boost expiry callbacks, conflict `reassert`/`adopt`/auto-resolve,
both-targets-on and `inactive_target_on` detection, auto-relock persistence, the remaining services, diagnostics,
config-flow validation, expiry during an active spare target and the VTherm display branches. The remaining gap is
mostly defensive/error handling in `coordinator.py`; `mypy` and a Python 3.12/3.13 unit matrix are now in CI. See
section 8.2 for the full list.

---

## 7. Known gaps and deviations

1. **Version floor is 2025.1.4.** `hacs.json` now declares `2025.1.4`. The 2026.11-era APIs are handled at runtime:
   `ATTR_TEMPERATURE` is imported from `homeassistant.const` (available in 2025.1.4 as well), `services.py` selects
   the correct `async_extract_entity_ids` signature, and `climate.py` exposes the legacy temperature properties when
   the base class lacks the `native_*` ones. The suite passes on a 2025.1.4 harness; CI tracks the newest harness.
   Intermediate releases are expected to work but are not individually tested.
2. **Automated coverage is still partial (91 %, gate 75 %).** High-risk handover, persistence, manual start/return,
   expiry, boost start/cancel, conflict policies, lock, services, diagnostics and entity behaviour are covered. See
   section 8.2 for the remaining gaps; `coordinator.py` (85 %) is the largest untested area.
3. **Manual mode is live-verified through 0.8.0 and well covered.** Start/return, `off`, conflicting-argument
   rejection, deadline persistence, watchdog expiry, handover carry-over and Lock B (`manual_blocks_schedule`)
   automation rejection are automated. A user temperature/preset move
   started while the proxy has no mode/active target updates the baseline but does not by itself start heating; start
   the proxy (`heat`/`cool`) first.
4. **M5 is live-verified through 0.8.0 and well covered.** Monitor, `reassert`, `adopt`, `both_targets_on`, startup
   conflicts, context suppression, settle windows, `inactive_target_on` and history/clear are automated. The
   reassert grace across a reload is still only partially asserted. Detection deliberately pauses during
   handover and during the post-command settle window, so very short mismatches may never be reported.
   `_guess_source()` is heuristic.
5. **Boost is live-verified through 0.8.0 and partially covered.** Activation on both targets, cancel, the feature
   flag, both-target routing, deadline persistence and the expiry callback are automated; expiry triggered through
   the watchdog and during a pending handover are not. It is feature-flagged and only supports `targets=both`. It
   requires heat mode, both targets available and no pending handover. The return to single-target routing reuses
   the handover state machine, so the dropped target is only stopped once idle; if it never becomes idle the normal
   off-confirm timeout applies.
6. **`handover_max_wait` from the plan is not implemented.** `off_confirm_timeout` bounds the off confirmation, and
   the manual `force_handover` button/service can end a stuck handover. There is still no automatic timeout that
   interrupts an active old target.
7. **`command_confirm_timeout` is not implemented.** The optimistic window uses `settle_time`; there is no separate
   per-command confirmation timeout.
8. **`strings.json` and `translations/en.json` are duplicated.** `tests/test_translations.py` now fails if they drift
   and also requires a `data_description` for every config/options field.
9. `binary_sensor.target_mismatch` compares the two targets' setpoints and presets with each other; it is not the
   full M5 mismatch detector. `sensor.<name>_target_mismatch_detail` explains the difference and exposes both
   values. Use `binary_sensor.<name>_conflict` / `sensor.<name>_conflict_detail` for the desired-vs-actual
   comparison.
10. **Swing/humidity pass-through is not exposed.** `DesiredState` carries `swing_mode`, but the climate entity
    only advertises temperature, preset, fan mode, turn-on and turn-off. Fan mode is proxied from the AC since
    0.8.6 and is applied only to an active AC.
11. **Equinox's lock button still cannot drive the native lock.** Equinox hard-codes
    `versatile_thermostat.lock`/`unlock` on the card entity, and those are VTherm platform entity services, so a
    ClimateRouter proxy cannot receive them. `vt_display.py` therefore never forwards `is_lock_configured` or
    `lock_manager`. Use `hide_lock_button: true` with the native `lock.<name>_lock` entity (0.7.0) or the
    `climaterouter.lock`/`unlock` services, and request upstream Equinox support for a configurable lock
    service/entity.
12. **0.8.6 features are tested but not live-verified.** The AC idle bypass depends on the AC VTherm exposing both
    `preset_temperatures` and `vtherm_over_climate.underlying_entities`; when auto-detection is not possible, set
    `ac_idle_bypass_entity_id` explicitly or the bypass is skipped. It deliberately does not restore the device
    setpoint, relying on Versatile Thermostat to do so when heating resumes.

---

## 8. Next steps

### 8.1 Immediate

1. **Done:** `v0.8.5` is tagged and released from this commit. Next: refresh the Marketplace or restart Home
   Assistant, install the update, and confirm the brand icon, all entities, the timer `off` badge, the
   scheduler/manual protection, and the conflict/mismatch detail sensors. Do not re-add the old
   `custom_components/climaterouter` bind mount: it makes the folder a mount point (`EBUSY`) and the Marketplace
   cannot back it up before replacing it.
2. 0.8.6 is pushed and released as `v0.8.6` (`c002372`). Refresh the Marketplace and verify:
   - the fan mode card control mirrors the AC and survives a handover;
   - inactive manual/boost timers show `0`/`off`, not `unknown`;
   - diagnostic entities are grouped separately and configuration controls show under configuration;
   - with Velair enabled, a manual session pauses Velair and returning to schedule resumes it on the proxy;
   - with the AC idle bypass enabled, `climate.<device>` receives the chosen preset temperature while the AC
     VTherm is idle in heat, and the VTherm restores its own setpoint when heating resumes. Record the entity and
     preset used in section 6.
2. Open **Configure** once after the update and save any section. The schema-only save drops the removed
   manual-switch key from `entry.data`. Confirm the collapsed sections render correctly, that the brief
   explanations appear under the fields, that the options menu returns after each section save, and that **Finish**
   closes it.
3. Verify the interactive 0.8.1 changes in the live instance:
   - `sensor.<name>_active_target` and `sensor.<name>_pending_target` show the radiator/AC icon;
   - all eleven sensors are available (the `e025cf4` regression fix);
   - `sensor.<name>_last_handover` survives a restart after a real handover;
   - `binary_sensor.<name>_target_mismatch` also reacts to differing presets;
   - diagnostics show the cleaned config and an empty `options` block.
4. **Done:** the version floor was lowered to 2025.1.4 and the runtime compatibility paths are covered by tests
   (sections 7.1 and 8.2). Revisit only if an intermediate release turns out to need its own adaptation.
5. Request upstream Equinox support for a configurable lock service/entity; the card button still cannot target the
   proxy's native lock.
6. Owner: add repository topics on GitHub (`gh repo edit gume/climaterouter --add-topic home-assistant --add-topic
   home-assistant-custom-component --add-topic hacs --add-topic integration`). The HACS validation fails until the
   repository has at least one topic.

### 8.2 Automated tests and CI

Status as of 2026-11-10:

| Check | Result |
|---|---|
| `ruff check .` | clean |
| `ruff format --check .` | clean |
| Pure unit tests (no HA) | 59 passed |
| Integration tests (HA harness) | 105 passed |
| Full suite (HA harness) | 164 passed, 0 failures |
| `mypy custom_components/climaterouter` | clean |
| CI installs `requirements_test.txt` | yes (intentionally unpinned, includes `mypy`) |
| CI matrix | full HA suite on Python 3.13; pure unit tests on Python 3.12 and 3.13 |
| GitHub CI run confirmed | green through `1972d1e`; the 0.8.5 release run is green after the device-lookup test fix |
| Measured statement coverage | **91 %** (91.0 %, gate 75 %) |

`pytest-homeassistant-custom-component` is wired into `tests/conftest.py`, and the integration suite lives in
`tests/integration/`. Without the harness, pytest runs the pure tests and skips the integration directory.

#### Done

- [x] CI lint/format failures fixed (`01fd245`); CI installs `requirements_test.txt` (`b94e279`).
- [x] config flow: happy path, missing entities, same entities, threshold order, duplicate unique id,
      reconfigure, options section save and finish.
- [x] coordinator: cold/mild hysteresis, route override, manual-mode start/return, off safety.
- [x] routing robustness: unavailable-target fallback, missing/stale outdoor hold.
- [x] startup: adopt one already-running target.
- [x] boost: both-target activation, cancel, feature-flag rejection.
- [x] conflicts: setpoint mismatch under `monitor`.
- [x] lock: user commands blocked, automations allowed, code validation.
- [x] services: route override, enter manual mode, manual timer, return to schedule, argument validation.
- [x] entity platforms: registry coverage, device info, conditional lock platform.
- [x] handover: forced handover away from an active target; active → pending → idle → off → start; off-confirm
      timeout conflict; route revert while pending; `handover_aborted` event payload.
- [x] startup: restored desired state while targets are missing, then routing resumes when they appear.
- [x] persistence across reload: desired state, manual deadline/timer, boost deadline.
- [x] entity behaviour: optimistic setpoint window and mirroring, unavailable proxy, select/button/switch actions.
- [x] runtime HA 2025.1.4 compatibility (no test-only shims): dual `async_extract_entity_ids` signature and legacy
      climate properties (`bd35514`, `8c81271`).
- [x] CI coverage gate at 75 % (`57d68e2`); `requirements_test.txt` intentionally unpinned (`06841d0`).
- [x] manual/boost expiry callbacks, auto-relock scheduling and deadline persistence (`58f0ba5`).
- [x] conflict `reassert`/`adopt`, `both_targets_on` auto-resolve and startup conflicts (`58f0ba5`).
- [x] remaining services: clear route override, manual-override alias/cancel, set/cancel boost, lock/unlock,
      foreign-entity and missing-target rejection (`1b1c818`).
- [x] diagnostics serialization and lock-code redaction (`1b1c818`).
- [x] config-flow validation: wrong entity domain, manual order, lock code, tolerance/duration ranges, duplicate
      reconfigure and options-section error handling (`44e73a4`).
- [x] conflict detection/clear events and resolved history.
- [x] watchdog-driven manual/boost expiry; the watchdog now cancels the pending expiry handles instead of leaving
      them scheduled (`02e1bcd`).
- [x] service dispatch for recalculate/clear-conflicts/force-handover and `inactive_target_on` detection
      (`bd0305d`).
- [x] boost expiry while the spare target is active, starting a pending handover (`7160c87`).
- [x] reconfigure with an unknown entry id, the remaining options sections, and legacy flat form data
      (`7160c87`).
- [x] `vt_display.py` ranking and valve-regulation branches; coverage attribution fixed by measuring the source
      directory instead of the package name (`7160c87`, `24482c8`).
- [x] `mypy` clean and wired into CI; Python 3.12/3.13 pure-unit matrix added (`32c4ae7`, `24482c8`).
- [x] coordinator command validation (empty command, invalid mode/route, no handover), boost duration/target/state
      rejection, manual duration bounds and timer toggling, lock feature-flag rejection (`acd5b02`).
- [x] conflict clear-after ageing and an auto-relock deadline that expired while unloaded (`a6c1bb3`).
- [x] manual mode defers scheduler/automation moves (including `off`), returns to the latest schedule on expiry, and
      re-asserts direct VTherm writes while active (`cf53fc8`).

#### Missing

- [ ] `coordinator.py` edge branches: a few defensive handover/restore and persistence-error paths. These are the
      remaining untested areas.
- [x] owner: push the 0.8.5 commits and confirm the full CI run (including mypy and the matrix); keep the
      repository topics in place so HACS validation stays green.
- [ ] live re-check after installing 0.8.5 (brand icon, timer badge, manual/scheduler protection, expiry and conflict
      details).

#### Coverage snapshot

| Module | Coverage |
|---|---|
| `binary_sensor.py`, `config_flow.py`, `const.py`, `diagnostics.py`, `entity.py`, `switch.py` | 100 % |
| `router.py`, `select.py`, `sensor.py`, `services.py`, `vt_display.py` | 98 % |
| `button.py` | 97 % |
| `models.py` | 95 % |
| `__init__.py`, `climate.py`, `lock.py` | 94 % |
| `coordinator.py` | 85 % |
| **Total** | **92 %** |

The local PyPI snapshot only offers `pytest-homeassistant-custom-component` 0.13.205 (HA 2025.1.4), not 2026.11.
CI installs the newest release. Production code supports both versions; no test-only shims remain.

Run the suite with the HA venv:

```bash
/tmp/opencode/cr-venv/bin/python -m pytest -q
/tmp/opencode/cr-venv/bin/python -m pytest -q --cov=custom_components.climaterouter \
    --cov-report=term-missing --cov-fail-under=75
```

### 8.3 M4 — proxy-owned manual mode (implemented in this checkout)

- [x] `ManualMode` model with desired state, optional absolute deadline (`None` = infinite), baseline and timer
      metadata; legacy bounded overrides migrate on load.
- [x] UI temperature/preset moves start manual mode; repeat moves update the value without resetting the timer.
- [x] `climaterouter.enter_manual_mode`, `set_manual_timer`, `return_to_schedule`; deprecated aliases retained.
- [x] `switch.manual_mode`, `select.manual_timer`, `button.return_to_schedule`, `binary_sensor.manual_mode`,
      `sensor.manual_remaining`, `sensor.manual_until`, diagnostic `sensor.manual_timer_minutes`.
- [x] Persistence, handover carry-over, Lock B (`manual_blocks_schedule`) automation rejection.
- [x] Unit tests for the model helpers (`with_manual_mode`, serialization, expiry/remaining, migration).
- [x] Integration tests for start/return, `off`, conflicting arguments and deadline persistence.
- [x] Integration tests for natural timer expiry, handover carry-over and Lock B automation rejection
      (`58f0ba5`, `d2ced17`).
- [x] Live verification in the 2026.11 test instance (through 0.8.0).

### 8.4 M5 — conflict handling (implemented in this checkout)

- [x] Compare desired state with the active target; ignore state changes caused by our own contexts
      (`_contexts`, `CONTEXT_TTL`) and settle windows.
- [x] Populate `RouterSnapshot.conflicts`, `conflict_count`, attributes and the conflict binary sensor.
- [x] Classify VTherm guards with `_extract_guard()`; guarded/idle states are not conflicts.
- [x] Implement `monitor` / `reassert` / `adopt` policies and the configured auto-resolve switches.
- [x] Fire `climaterouter_conflict_detected` / `climaterouter_conflict_cleared`; make `clear_conflicts` real.
- [x] Handle both-targets-on, unavailable targets, stale outdoor sensor and target mismatch.
- [x] Unit tests for the pure classifier (`target_conflict`) and `Conflict.to_dict()`.
- [x] Integration tests for the `monitor` and `reassert`/`adopt` paths, auto-resolve switches,
      both-targets-on and `inactive_target_on`.
- [x] Live verification in the 2026.11 test instance (through 0.8.0).

### 8.5 M6 — boost and release (implemented in this checkout)

- [x] Support multiple active targets in routing, snapshots and conflict detection.
- [x] Implement feature-flagged `set_boost` / `cancel_boost` with a bounded deadline, heat-only interlock,
  capability checks and no pending handover requirement.
- [x] Fan out commands to both targets only while boost is active; keep `off`/`cool` semantics safe.
- [x] Persist boost across restart, expire it on the exact deadline, and emit start/end events.
- [x] Return to single-target routing through the handover state machine.
- [x] Unit tests for `BoostState` and pure boost routing.
- [x] Add hassfest and HACS validation workflow (`.github/workflows/validate.yml`, brands ignored).
- [x] Integration tests for start, cancel, both-target routing and deadline persistence.
- [x] Integration tests for natural expiry and expiry during a pending handover (`7160c87`).
- [x] Live verification in the test HA (through 0.8.0).
- [x] The Marketplace installs from `main` by commit; tags/releases are optional owner actions.

### 8.6 0.7.0–0.8.1 proxy rework and follow-up

- [x] Native UI lock with optional code and persisted auto-relock deadline.
- [x] Proxy-owned manual mode and timer replacing the bounded override.
- [x] Split Lock A (UI) from Lock B (manual/schedule).
- [x] Sectioned setup/options/reconfigure flows with brief field descriptions.
- [x] Read-only VTherm display attributes; identity attributes are opt-in.
- [x] State-dependent radiator/AC icons on the target sensors.
- [x] Persist `last_handover`; compare presets in `binary_sensor.target_mismatch`.
- [x] Schema-only config saves (drop removed keys, keep `entry.options` empty).
- [x] Translation-sync and field-description tests.
- [x] Live verification through 0.8.0.
- [x] Install commit `d3af8b4` (0.8.1) through the Marketplace; the target icons were verified live.
- [x] Fix the nine-sensor icon regression in `e025cf4` and reinstall that clean build through the Marketplace.
- [x] Integration tests for the flows, locks, and manual mode (through `d2ced17`).
- [x] Local brand assets (black pattern, white dark variant) under `custom_components/climaterouter/brand/`.
- [x] Manual timer select stays available and reports `off` with a crossed-out icon when unused.
- [x] Manual expiry without a schedule baseline keeps the current mode running.
- [x] `sensor.<name>_conflict_detail` and `sensor.<name>_target_mismatch_detail` explain the two diagnostic binary
      sensors, with full values in their attributes and an explicit off/unavailable note for the mismatch case.

### 8.7 0.8.6 owner-issue batch

Source: the owner's `issues.txt`, now tracked and kept as the resolved/open issue list. Issue 4 ("overview on the
filed names") is the only open item and is intentionally skipped for this batch.

- [x] Fan mode proxied from the AC, stored while inactive, applied/replayed only to an active AC (`16e56ca`).
- [x] Inactive/expired manual and boost timers report `0` minutes; the manual-timer select stays `off` (`2bbaae5`).
- [x] Diagnostic entities use `EntityCategory.DIAGNOSTIC`; configuration controls use `EntityCategory.CONFIG`
      (`15e50c7`).
- [x] Opt-in Velair pause/resume around manual mode (`f9dd2b1`).
- [x] Optional AC idle bypass using the VTherm `frost`/`eco`/`comfort` preset temperature, with explicit or
      auto-detected device entity (`e4c829b`).
- [x] Integration tests for all five features and the new config-flow fields; full suite 164 passed.
- [x] Tag/release published as `v0.8.6` (`c002372`) on 2026-11-10.
- [x] Release helper reports an already published version cleanly (`28ae295`).
- [x] 0.8.7 maintenance release published: `v0.8.7` on `0d96b48`, containing the release-helper fix and docs.
- [x] Config field-label review applied and committed (`e8380bb`); ships in 0.8.8.
- [x] Tag/release published as `v0.8.8` (`9ca79ad`) on 2026-11-10.
- [ ] Owner: refresh the Marketplace, install 0.8.8 and record the live result.
- [ ] Live verification in the test HA after the Marketplace update is installed.

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
- **Ruff format drift.** The tree was reformatted with ruff 0.17.x in `01fd245`, so `ruff check .` and
  `ruff format --check .` are clean and CI enforces them. Run the formatter before committing.
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

# release plan (dry run; safe) and the owner-only push
scripts/release.sh
scripts/release.sh --push

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
