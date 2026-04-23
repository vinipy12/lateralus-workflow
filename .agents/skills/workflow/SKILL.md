---
name: workflow
description: Start, resume, revise, approve, or inspect the repo-local workflow engine that manages discuss-first planning and stepwise execution. Use when the user wants to plan a feature, continue an active workflow, approve a plan, check workflow status, cancel workflow state, or activate execution from an approved plan artifact.
---

# Workflow

Use this skill as the native entrypoint for the repo-local workflow engine.

## Router First

Prefer the repo-local wrapper CLI over editing workflow JSON by hand:

- `python3 .agents/skills/workflow/scripts/workflow_router.py planning-start "<feature request>"`
- `python3 .agents/skills/workflow/scripts/workflow_router.py bootstrap-start "<project request>"`
- `python3 .agents/skills/workflow/scripts/workflow_router.py planning-revise "<feedback>"`
- `python3 .agents/skills/workflow/scripts/workflow_router.py planning-approve`
- `python3 .agents/skills/workflow/scripts/workflow_router.py execution-start [plan-file]`
- `python3 .agents/skills/workflow/scripts/workflow_router.py resume`
- `python3 .agents/skills/workflow/scripts/workflow_router.py status`
- `python3 .agents/skills/workflow/scripts/workflow_router.py cancel`

After running the router, treat its printed context as the canonical workflow instruction for the current phase. Do not ask the user to run setup commands that the router already handled.
The repo-local wrapper scripts live under `.agents/skills/workflow/scripts/` and operate on `.codex/workflow/*.json` artifacts in the current project.

## Planning

For a new feature request:

1. Run `planning-start`.
2. Follow the phase-specific planning contract from the router output.
3. Keep the work inside `.codex/workflow/` artifacts until the plan is approval-ready.
4. Advance phases mechanically with `python3 .agents/skills/workflow/scripts/planning_state.py advance [phase]`; do not jump phases by editing `status` in JSON.
5. Use the repo-root memory docs while planning:
   - `PROJECT.md` for product intent and durable constraints
   - `REQUIREMENTS.md` for active backlog, accepted requirements, deferred scope, and milestone commitments
   - `STATE.md` for active initiative, latest decisions, release state, and unresolved risks
6. Before approval, run `python3 .agents/skills/workflow/scripts/planning_state.py audit-plan`.
7. When the plan is ready, use `planning-approve` to transition into execution.

For greenfield/bootstrap work:

1. Run `bootstrap-start "<project request>"`.
2. Stay on the same planning phases, but produce `stack_runtime_decision.json` during `architecture_audit`.
3. Produce `bootstrap_expectations.json` before `approval_ready`.
4. Keep the bootstrap plan JSON-first and auditable like the brownfield path.

For plan revisions:

1. Run `planning-revise "<feedback>"`.
2. Stay in planning. Do not start implementation.
3. Re-enter the correct phase with `planning_state.py advance <phase>` only after the revised artifacts validate cleanly.

## Execution

For an active execution workflow:

1. Run `resume` to load the exact next instruction for the current step.
2. Keep the phase boundary explicit:
   - Development ends only when the current step reaches `committed`.
   - `set-step-status ... review_pending` runs deterministic pre-review sensors before inferential review.
   - Review is a hard gate before commit; do not bypass it.
   - Deployment begins only after UAT moves the workflow to `ship_pending`.
3. Use `python3 .agents/skills/workflow/scripts/workflow_state.py` only for step-status updates during implementation, review, commit, and ship.
4. If execution enters `execution_escalated`, fix the blocker and clear it with `python3 .agents/skills/workflow/scripts/workflow_state.py resolve-escalation`; that restores the workflow to its pre-escalation phase before normal execution resumes.
5. Record UAT outcomes with `python3 .agents/skills/workflow/scripts/workflow_state.py set-uat-status <passed|failed-gap|failed-replan> --summary "..."`.
6. Treat `set-workflow-status complete` as the final ship-only transition. Other manual workflow-status edits require `--override-reason`.
7. When the workflow reaches `ship_pending`, use `$ship`.

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
- Read `AGENTS.md` before acting on execution steps.
- Keep planning JSON-first and execution stepwise.
- Treat `.codex/workflow/metrics/` and `.codex/workflow/uat.json` as auditable local artifacts, not scratch files.
- Respect phase ownership:
  - planning updates `PROJECT.md` only when product intent or durable constraints change
  - planning updates `REQUIREMENTS.md` when scope or backlog commitments change
  - execution and ship update `STATE.md`
- Do not bypass the router unless you are already inside a live workflow step and only need a lower-level state update.
