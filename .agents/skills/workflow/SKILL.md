---
name: workflow
description: Start, resume, revise, approve, or inspect the repo-local workflow engine that manages discuss-first planning and stepwise execution. Use when the user wants to plan a feature, continue an active workflow, approve a plan, check workflow status, cancel workflow state, or activate execution from an approved plan artifact.
---

# Workflow

Use this skill as the native entrypoint for the repo-local workflow engine.

## Router First

Prefer the router CLI over editing workflow JSON by hand:

- `python3 .codex/workflow/scripts/workflow_router.py planning-start "<feature request>"`
- `python3 .codex/workflow/scripts/workflow_router.py planning-revise "<feedback>"`
- `python3 .codex/workflow/scripts/workflow_router.py planning-approve`
- `python3 .codex/workflow/scripts/workflow_router.py execution-start [plan-file]`
- `python3 .codex/workflow/scripts/workflow_router.py resume`
- `python3 .codex/workflow/scripts/workflow_router.py status`
- `python3 .codex/workflow/scripts/workflow_router.py cancel`

After running the router, treat its printed context as the canonical workflow instruction for the current phase. Do not ask the user to run setup commands that the router already handled.

## Planning

For a new feature request:

1. Run `planning-start`.
2. Follow the discuss-first planning instructions from the router output.
3. Keep the work inside `.codex/workflow/` artifacts until the plan is approval-ready.
4. Before approval, run `python3 .codex/workflow/scripts/planning_state.py audit-plan`.
5. When the plan is ready, use `planning-approve` to transition into execution.

For plan revisions:

1. Run `planning-revise "<feedback>"`.
2. Stay in planning. Do not start implementation.

## Execution

For an active execution workflow:

1. Run `resume` to load the exact next instruction for the current step.
2. Use `.codex/workflow/scripts/workflow_state.py` only for step-status updates during implementation, review, commit, and ship.
3. When the workflow reaches ship, use `$ship`.

For direct activation from an approved plan artifact:

1. Run `execution-start [plan-file]`.
2. If the plan file contains multiple JSON plans, pass `--plan-id <id>`.

## Status And Cancellation

- Use `status` when the user asks what is currently active.
- Use `cancel` when the user explicitly wants to clear workflow state.
- Cancellation should preserve planning artifacts such as discovery, trace, and approved plans unless the user asks to delete them.

## Rules

- Treat `$workflow` as the canonical UX. `/workflow` is a legacy hook-based compatibility path.
- Read `AGENTS.md` before acting on execution steps.
- Keep planning JSON-first and execution stepwise.
- Do not bypass the router unless you are already inside a live workflow step and only need a lower-level state update.
