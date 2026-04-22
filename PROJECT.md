# Project

## Product Intent
- Build a kernel-first repo-local workflow that turns planning and execution control into auditable code.

## Target Users
- Maintainers using Codex to plan, implement, review, and ship changes inside a live repository checkout.

## Durable Constraints
- Keep `$workflow` as the canonical interface and `/workflow` as compatibility-only.
- Keep workflow state deterministic, on disk, and easy to audit.
- Prefer small repo-local utilities over framework-heavy abstractions.

## Strategy
- Stabilize the workflow kernel before revisiting packaging or distribution shape.

## Current Priorities
- Enforce planning phases as code.
- Add repo-root project memory.
- Make approved plans orchestration-ready.
