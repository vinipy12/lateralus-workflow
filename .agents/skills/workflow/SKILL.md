---
name: workflow
description: Start, resume, revise, approve, or inspect the repo-local workflow engine that manages discuss-first planning and stepwise execution. Use when the user wants to plan a feature, continue an active workflow, approve a plan, check workflow status, cancel workflow state, or activate execution from an approved plan artifact.
---

# Workflow

Use this skill as the native entrypoint for the repo-local workflow engine.

## Router First

Prefer the bundled wrapper CLI over editing workflow JSON by hand. Resolve `scripts/...` relative to this skill directory; do not assume the target project has `.agents/skills/` checked in.

- `python3 scripts/workflow_router.py planning-start "<feature request>"`
- `python3 scripts/workflow_router.py bootstrap-start "<project request>"`
- `python3 scripts/workflow_router.py planning-revise "<feedback>"`
- `python3 scripts/workflow_router.py planning-approve`
- `python3 scripts/workflow_router.py execution-start [plan-file]`
- `python3 scripts/workflow_router.py resume`
- `python3 scripts/workflow_router.py status`
- `python3 scripts/workflow_router.py cancel`

After running the router, treat its printed context as the canonical workflow instruction for the current phase. Do not ask the user to run setup commands that the router already handled.
The wrapper scripts operate on `.codex/workflow/*.json` artifacts in the current project.

## Planning

For a new feature request:

1. Run `planning-start`.
2. Follow the phase-specific planning contract from the router output.
3. Keep the work inside `.codex/workflow/` artifacts until the plan is approval-ready.
4. Advance phases mechanically with `python3 scripts/planning_state.py advance [phase]`; do not jump phases by editing `status` in JSON.
5. Use the repo-root memory docs while planning:
   - `PROJECT.md` for product intent and durable constraints
   - `REQUIREMENTS.md` for active backlog, accepted requirements, deferred scope, and milestone commitments
   - `STATE.md` for active initiative, latest decisions, release state, and unresolved risks
6. In `context.json`, keep `delivery_contract.mode` set to `one_shot` and `comparison_required` set to `false`; the normal contract is to satisfy the user's stated need from the request, repo context, and bounded clarification.
7. Use `clarification_gate` for product-impacting ambiguity: ask one question at a time with a recommended answer, then record the resolution, or record `no_material_questions_reason` when no material question is needed.
8. Before approval, run `python3 scripts/planning_state.py audit-plan`.
9. When the plan is ready, use `planning-approve` to transition into execution.
10. When a step changes durable agent guidance, workflow conventions, or verification rules, set `agents_update_required: true` on that step and include the relevant `agents_paths`.
11. When a validation, docs, UAT, or release-alignment step must verify targets outside its edit ownership, declare those paths in `validation_ownership`; this is verification scope only, not permission to edit outside `file_ownership`.

For greenfield/bootstrap work:

1. Run `bootstrap-start "<project request>"`.
2. Stay on the same planning phases, but produce `stack_runtime_decision.json` during `architecture_audit`.
3. Produce `bootstrap_expectations.json` before `approval_ready`.
4. Do not require a comparable artifact for greenfield work. When the user provides one, or maintainers are dogfooding, record it as `current.comparison_diagnostic` with findings classified as `lesson`, `rejected_alternative`, `deferred_follow_up`, or `adopt_now`.
5. Use `adopt_now` only when the user made the baseline authoritative; otherwise comparison findings stay diagnostic.
6. Keep the bootstrap plan JSON-first and auditable like the brownfield path.

For plan revisions:

1. Run `planning-revise "<feedback>"`.
2. Stay in planning. Do not start implementation.
3. Re-enter the correct phase with `python3 scripts/planning_state.py advance <phase>` only after the revised artifacts validate cleanly.

## Execution

For an active execution workflow:

1. Run `resume` to load the exact next instruction for the current step.
2. Keep the phase boundary explicit:
   - Development ends only when the current step reaches `committed`.
   - `set-step-status ... review_pending` runs deterministic pre-review sensors before inferential review.
   - Review is a hard gate before commit; do not bypass it.
   - Record review outcomes inline on `set-step-status ... fix_pending|commit_pending` with `--review-summary`, `--scope-confirmed true|false`, repeatable `--scope-reviewed-path` for reviewed step-owned paths, `--verification-status passed|blocked`, repeatable `--verification-command` for every command that ran when verification passed, `--verification-note` when blocked, repeatable `--agents-checked`, `--agents-updated true|false`, `--finding-count <n>`, and one repeatable `--review-finding` JSON object per finding when the review fails.
   - If the current step has `agents_update_required: true`, a passing review must record `--agents-updated true`; stale durable guidance remains a material finding until then.
   - Deployment begins only after UAT moves the workflow to `ship_pending`.
3. Use `python3 scripts/workflow_state.py` only for step-status updates during implementation, review, commit, and ship.
   Ship must record `--branch`, `--pr-url`, `--codex-review-status`, `--state-memory-status`, and `--state-memory-summary` on `set-step-status ... shipped`.
4. If execution enters `execution_escalated`, fix the blocker and clear it with `python3 scripts/workflow_state.py resolve-escalation`; that restores the workflow to its pre-escalation phase before normal execution resumes.
5. Record UAT outcomes with `python3 scripts/workflow_state.py set-uat-status <passed|failed-gap|failed-replan> --summary "..."`.
6. Treat `set-workflow-status complete` as the final ship-only transition. It validates the ship handoff against UAT, metrics, PR details, and the current `STATE.md` digest. Other manual workflow-status edits require `--override-reason`.
7. When the workflow reaches `ship_pending`, use `$ship` instead of starting the next unrelated kernel slice.

For direct activation from an approved plan artifact:

1. Run `execution-start [plan-file]`.
2. If the plan file contains multiple JSON plans, pass `--plan-id <id>`.
3. If the workflow uses non-default state files, pass both `--planning-state-path` and `--execution-state-path` so activation checks the matching planning session.

## Status And Cancellation

- Use `status` when the user asks what is currently active.
- Use `cancel` when the user explicitly wants to clear workflow state.
- Cancellation should preserve planning artifacts such as discovery, trace, and approved plans unless the user asks to delete them.

## Rules

- Treat `$workflow` as the canonical UX. `/workflow` is a legacy hook-based compatibility path.
- Treat `$lateralus-workflow` as a compatibility alias for users who invoke the plugin by package name.
- Read `AGENTS.md` before acting on execution steps.
- Keep planning JSON-first and execution stepwise.
- Treat `.codex/workflow/metrics/` and `.codex/workflow/uat.json` as auditable local artifacts, not scratch files.
- When a completed slice is PR-sized, push it and open a grounded PR before continuing broader kernel work; if Codex review is requested, babysit Codex review comments until Codex reports the branch is clean or a concrete blocker requires user input.
- When the user asks to follow or continue `next-steps.md`, treat the ship handoff as part of the work for any PR-sized completed slice; do not wait for a separate "ship" prompt unless the user explicitly pauses before PR creation.
- Respect phase ownership:
  - planning updates `PROJECT.md` only when product intent or durable constraints change
  - planning updates `REQUIREMENTS.md` when scope or backlog commitments change
  - execution and ship update `STATE.md`
- Do not bypass the router unless you are already inside a live workflow step and only need a lower-level state update.
