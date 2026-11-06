# ADR-0004: Default to monitor, not reassert, for underlying conflicts

- Status: Accepted
- Date: 2026-11-06

## Context

The underlying VTherms are visible and controllable. Users, automations, physical remotes, VTherm guards, and a
misconfigured Scheduler can change them. A proxy that automatically reasserts its desired state can create
service-call loops, valve/AC chatter, and a fight with safety features. A proxy that ignores changes leaves the user
confused about why the room is not following the schedule.

## Decision

The default conflict policy is `monitor`:

- Detect the mismatch.
- Expose `binary_sensor.conflict`, conflict count, and attributes.
- Fire an event and log once.
- Do not change underlying state.
- The next proxy command naturally reasserts the desired state.
- Clear the conflict when the state matches expected for `conflict_clear_after`.

Optional policies:

- `reassert`: resend desired state once per episode, then stop.
- `adopt`: accept an external setpoint/preset/mode as the new desired/baseline (never for guards or non-active
  targets).

Independent safe auto-resolution:

- `auto_resolve_idle_targets` (default true): turn off a non-selected target only when idle.
- `auto_resolve_simultaneous` (default false): turn off the idle non-selected target when both are on.

No policy may turn off a target that is actively heating/cooling because of a conflict.

## Consequences

Positive:

- No fight with VTherm safety/window/power features.
- No service-call loops.
- The user gets a clear, actionable signal.
- Reassert/adopt remain available for users who want them.

Negative:

- The schedule may not be enforced until the next command if a third party keeps changing a VTherm.
- The user must notice the conflict sensor/notification.

## Alternatives considered

- **Reassert by default**: stronger enforcement, but risks loops and safety conflicts.
- **Ignore silently**: no loops, but poor observability.
- **Adopt by default**: follows external changes, but can silently abandon the schedule.
