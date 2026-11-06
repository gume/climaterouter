# ADR-0005: Model active targets as a set to prepare for boost

- Status: Accepted
- Date: 2026-11-06

## Context

The first version routes to exactly one target. A future boost mode may activate both the radiator and the AC at
the same time. Retrofitting a set-based model later would touch routing, state mirroring, handover, services, and
every entity.

## Decision

Model active targets as a `frozenset[Target]` from the start:

- Normal operation: one element.
- Off: empty set.
- Boost: two elements.
- Handover is skipped while more than one target is active.
- Commands fan out to all active targets during boost.
- State aggregation handles multiple targets (current temperature average; heating/cooling if any).
- `sensor.active_target` reports `both` when two targets are active.

Boost is feature-flagged off by default. The service and state model exist, but the optimization logic is
intentionally deferred. v1 safety interlock: heat-only, both targets capable, no pending handover, both available.

## Consequences

Positive:

- No large refactor when boost logic is added.
- Entities and diagnostics already represent `both`.
- The routing function has a clean return type.

Negative:

- Slightly more complex state aggregation in v1 for a feature that is not enabled.
- Every command path must handle multiple targets, even if normally one.
- Boost still needs a separate safety/optimization design.

## Alternatives considered

- **Single `Target` enum and refactor later**: simpler v1, but a cross-cutting change later.
- **Implement boost fully in v1**: premature; the logic is not well defined and risks simultaneous heat/cool.
