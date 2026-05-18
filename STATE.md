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
- When continuing `next-steps.md`, automatically run the ship handoff after a verified PR-sized slice unless the user explicitly asks to stop before PR creation.
- Ship completion now requires explicit repo-memory reconciliation: the shipped transition records branch, PR URL, Codex review status, and the current `STATE.md` digest before `complete` can be set.
- Validation, docs, UAT, and release-alignment steps can declare `validation_ownership` to verify cross-step targets without expanding edit ownership beyond `file_ownership`.

## Release State
- Pre-kernel-stabilization.

## Unresolved Risks
- Packaging shape is still deferred until the kernel stays stable.
- PR stewardship has product direction but no state machine, schema, skill, or test contract yet.
