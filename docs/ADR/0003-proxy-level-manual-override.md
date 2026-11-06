# ADR-0003: Implement manual override in the proxy, not only in VTherm

- Status: Accepted
- Date: 2026-11-06

## Context

VTherm supports:

- `versatile_thermostat.set_timed_preset` with a preset and duration;
- `manual_override_duration_min`, which reverts a manual temperature change to the previous preset.

Both are per VTherm. ClimateRouter may hand over from radiator to AC during an override. A VTherm-local timer would
not follow the handover, and a manual temperature override would be lost or would restore a preset on the wrong
target.

## Decision

ClimateRouter owns the cross-target manual override:

- `climaterouter.set_manual_override` captures a baseline (`hvac_mode`, preset or temperature) and an absolute
  deadline.
- The override is applied to the active target and re-applied to the new target after a handover.
- On expiry/cancel/off, the baseline is restored to the current active target.
- The override is persisted with an absolute UTC deadline so it survives restart.
- The proxy does not call VTherm-specific timed-preset services in v1.
- If a VTherm timed override is active and the proxy did not start it, the proxy surfaces it as an underlying
  override/guard and does not start a second timer.

The setup guide recommends setting VTherm's `manual_override_duration_min` to `0` when using the proxy override, to
avoid two timers competing.

## Consequences

Positive:

- Override behavior is consistent across routing changes and restarts.
- The baseline is always the latest schedule command, independent of which VTherm is active.
- No dependency on VTherm's internal timed-preset implementation.

Negative:

- The proxy duplicates a small amount of timer/restore logic.
- Users who prefer VTherm's timed preset must choose one layer, not both.
- Temperature override is not delegated to VTherm's native manual override.

## Alternatives considered

- **Delegate to VTherm timed preset**: preset-only, target-local, lost on handover.
- **Delegate to VTherm manual override**: temperature-only under specific conditions, target-local, restores a
  preset rather than an arbitrary baseline.
- **Hybrid**: use VTherm when no handover is expected, proxy otherwise; more complex and inconsistent.
