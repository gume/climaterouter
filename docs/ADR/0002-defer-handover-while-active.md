# ADR-0002: Defer route handover while the old target is active

- Status: Accepted
- Date: 2026-11-06

## Context

The route can change at any time because the outdoor temperature crosses a threshold or the user toggles the manual
switch. Turning off a radiator or AC in the middle of a heating/cooling cycle wastes energy, increases wear, and can
leave the room uncomfortable. The requirement is explicit: do not interrupt actual heating; switch only when the
climates are not active.

## Decision

A route-driven handover waits until the old target is idle:

- Active means `hvac_mode != off` and `hvac_action in {heating, cooling}`.
- Unknown `hvac_action` is treated as active (conservative).
- The old target must be idle for `handover_idle_confirm` (default 30 s) before it is turned off.
- The old target is turned off and confirmed before the new target is configured.
- `handover_max_wait` defaults to `0` (wait indefinitely). The proxy exposes `binary_sensor.handover_pending` and
  does not force off by default.

Explicit `off` and explicit `cool` are user intent and may stop an active cycle immediately; this exception is
logged and surfaced in events.

## Consequences

Positive:

- No interrupted heating/cooling on outdoor or manual-switch changes.
- No overlap where both targets are on during a handover.
- Predictable sequence: old off → confirm → new on.

Negative:

- A handover may be delayed for a long time if the old target keeps heating.
- The user needs the pending sensor/notification to understand why the AC is not active yet.
- A forced timeout is an opt-in risk, not the default.

## Alternatives considered

- **Immediate off/on**: simple, but violates the requirement and interrupts active cycles.
- **Overlap (turn new on before old off)**: risks simultaneous heating/cooling and energy waste.
- **Force off after timeout by default**: risks comfort and device wear; made opt-in only.
