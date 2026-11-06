# ADR-0001: Use a single proxy climate entity

- Status: Accepted
- Date: 2026-11-06
- Deciders: ClimateRouter design

## Context

Scheduler Component and the user need one stable climate entity. The installation has two independent VTherm
entities (radiator and AC), each with its own regulation and presets. Scheduler has no concept of "route this
schedule to one of two thermostats based on outdoor temperature".

## Decision

Create one custom `climate.climaterouter` proxy entity that implements the standard Home Assistant climate
interface. It owns routing, handover, cross-target override, and conflict detection. It forwards standard
`climate.*` services to exactly one underlying VTherm (two during boost).

The proxy does not subclass or wrap a VTherm entity. It reads their states and calls their services.

## Consequences

Positive:

- Scheduler and users see one ordinary climate entity.
- The underlying VTherms remain independent and fully functional.
- Routing can be tested with mock climate entities.
- No dependency on VTherm internals for command forwarding.
- A future non-VTherm climate could be used behind the proxy.

Negative:

- The proxy must mirror state and handle availability/optimistic updates.
- The proxy must detect direct changes to the underlying entities.
- Two layers of presets/overrides must be documented clearly.

## Alternatives considered

- **Climate group**: forwards to all members, not a selected one; no handover.
- **Generic thermostat**: adds its own regulation and fights VTherm.
- **Automation/script**: no single climate entity for Scheduler, no state mirroring, no handover.
- **VTherm plugin**: more coupling and a smaller audience; a standalone integration is reusable.
