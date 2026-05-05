# Project

## Product Intent
- Build a kernel-first repo-local workflow that turns planning and execution control into auditable code.
- Grow the workflow toward PR stewardship: driving opened pull requests to a merge-ready state through CI checks, quality gates, reviewer-comment triage, targeted fixes, and re-review loops.

## Target Users
- Maintainers using Codex to plan, implement, review, and ship changes inside a live repository checkout.
- Agent-heavy engineers who want trusted autonomy for routine coding work without giving up explicit approval, verification evidence, or auditability.

## Durable Constraints
- Keep `$workflow` as the canonical interface and `/workflow` as compatibility-only.
- Keep workflow state deterministic, on disk, and easy to audit.
- Prefer small repo-local utilities over framework-heavy abstractions.

## Strategy
- Stabilize the workflow kernel before revisiting packaging or distribution shape.
- Treat PR stewardship as the next major product capability after the kernel can reliably reach `ship_pending` and create grounded PRs.

## Current Priorities
- Keep the UAT gate, telemetry artifacts, and bootstrap path auditable.
- Revisit packaging only after the kernel milestone stays stable.
- Keep `$ship` scoped to branch push, PR creation, optional review request, and workflow completion until PR stewardship becomes an explicit workflow phase.
