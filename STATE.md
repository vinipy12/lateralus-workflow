# State

## Workflow Status
- Kernel upgrade in progress.

## Active Initiative
- UAT, telemetry, and bootstrap kernel stabilization.

## Latest Decisions
- Treat execution handoff metadata, UAT, and telemetry as part of the kernel.
- Keep `$workflow` as the primary interface and `$ship` as the terminal publish skill.
- Treat PR stewardship as the next planned product capability after kernel stabilization, without expanding the current `$ship` contract yet.
- Treat PR opening as the handoff point for PR-sized slices: push the branch, open a grounded PR, and let the user manually babysit reviewer feedback for now.

## Release State
- Pre-kernel-stabilization.

## Unresolved Risks
- Packaging shape is still deferred until the kernel stays stable.
- PR stewardship has product direction but no state machine, schema, skill, or test contract yet.
