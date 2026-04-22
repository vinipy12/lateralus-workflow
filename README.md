# Lateralus Workflow

Discuss-first planning and stepwise execution workflow for Codex.

## Kernel Status

The workflow kernel currently includes:

- hard-gated planning phases with deterministic advancement
- repo-root project memory in `PROJECT.md`, `REQUIREMENTS.md`, and `STATE.md`
- approval-time planning audits
- orchestration-ready plan metadata such as `depends_on`, `wave`, `file_ownership`, `rollback_notes`, and `operational_watchpoints`
- stepwise execution with implement, review, fix, commit, UAT, and ship gates
- repo-local UAT artifacts in `.codex/workflow/uat.json`
- local telemetry artifacts in `.codex/workflow/metrics/events.jsonl` and `.codex/workflow/metrics/scorecard.json`
- greenfield bootstrap planning through the existing router
- canonical `compare-plan` baseline fixtures inside `.codex/workflow/`

Still intentionally deferred:

- broader packaging or multi-skill splitting beyond `$workflow` and `$ship`
- telemetry polish beyond the local scorecard
- bootstrap refinements beyond the current router path

## What Lives Here

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `.codex/workflow/`: workflow engine, schemas, examples, baseline fixtures, and strategy notes
- `.agents/skills/workflow/`: native `$workflow` skill and repo-local wrappers
- `.agents/skills/ship/`: `$ship` skill and repo-local wrapper
- `PROJECT.md`: durable product intent and constraints
- `REQUIREMENTS.md`: active backlog, accepted requirements, deferred scope, and milestone commitments
- `STATE.md`: current initiative, latest decisions, release state, and unresolved risks
- `tests/scripts/test_codex_workflow.py`: focused workflow regression suite

## Current Surface

The plugin currently exposes:

- `$workflow` for brownfield planning, greenfield bootstrap planning, revision, approval, resume, status, cancel, and execution activation
- `$ship` for the publish phase after the workflow reaches ship readiness
- repo-local legacy `/workflow ...` hooks defined in `.codex/hooks.json`

Installing the plugin does not activate `.codex/hooks.json`; users who want the legacy `/workflow ...` trigger must wire those hooks into their own Codex config separately. `$workflow` remains the intended interface.

Installed plugin skills use the bundled wrappers under `.agents/skills/*/scripts/`. When developing this repository directly, use the repo-local `.codex/workflow/scripts/...` commands below.

## Planning Model

The planning kernel uses these phases:

1. `discuss`
2. `discovery`
3. `architecture_audit`
4. `planning`
5. `product_scope_audit`
6. `skeptic_audit`
7. `convergence`
8. `approval_ready`

Each phase has explicit artifact expectations and validator checks. Advancement is mechanical; do not edit planning status by hand.

Greenfield work reuses the same phase machine with `planning_mode=greenfield`. That path adds:

- `stack_runtime_decision.json` during `architecture_audit`
- `bootstrap_expectations.json` before `approval_ready`

Planning reads repo memory from:

- `PROJECT.md` for product intent and durable constraints
- `REQUIREMENTS.md` for scope and backlog commitments
- `STATE.md` for current initiative and delivery state

## Core Entrypoints

- Native skill: `$workflow`
- Ship skill: `$ship`
- Router CLI:
  - `python3 .codex/workflow/scripts/workflow_router.py planning-start "<feature request>"`
  - `python3 .codex/workflow/scripts/workflow_router.py bootstrap-start "<project request>"`
  - `python3 .codex/workflow/scripts/workflow_router.py planning-revise "<feedback>"`
  - `python3 .codex/workflow/scripts/workflow_router.py planning-approve`
  - `python3 .codex/workflow/scripts/workflow_router.py execution-start [plan-file]`
  - `python3 .codex/workflow/scripts/workflow_router.py resume`
  - `python3 .codex/workflow/scripts/workflow_router.py status`
  - `python3 .codex/workflow/scripts/workflow_router.py cancel`
- Planning state CLI:
  - `python3 .codex/workflow/scripts/planning_state.py show`
  - `python3 .codex/workflow/scripts/planning_state.py validate`
  - `python3 .codex/workflow/scripts/planning_state.py validate-phase`
  - `python3 .codex/workflow/scripts/planning_state.py advance [phase]`
  - `python3 .codex/workflow/scripts/planning_state.py audit-plan`
  - `python3 .codex/workflow/scripts/planning_state.py compare-plan`
- Execution state CLI:
  - `python3 .codex/workflow/scripts/workflow_state.py set-step-status <step-id> <status>`
  - `python3 .codex/workflow/scripts/workflow_state.py set-uat-status <passed|failed-gap|failed-replan> --summary "..."`
  - `python3 .codex/workflow/scripts/workflow_state.py set-workflow-status <status>`

## Execution Model

Execution now ends with a blocking post-code control loop:

1. implementation, review, and commit per step
2. `uat_pending` after the last committed step
3. `gap_closure_pending` for fixable UAT gaps inside the same workflow
4. `replan_required` when UAT shows a scope or architecture mismatch
5. `ship_pending` only after UAT passes

Telemetry stays local and auditable under `.codex/workflow/metrics/`.

## Installation

This repo works as a Codex plugin. The simplest local install path is to keep it at `~/plugins/lateralus-workflow` so the marketplace entry stays standard.

1. Clone the repo into `~/plugins/lateralus-workflow`.
2. Add an entry to `~/.agents/plugins/marketplace.json` like this:

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "lateralus-workflow",
      "source": {
        "source": "local",
        "path": "./plugins/lateralus-workflow"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

3. Restart Codex and open `/plugins`.
4. Install `Lateralus Workflow`.
5. Start using `$workflow`.

## Development

- Install dev dependencies: `uv sync --dev`
- Run workflow tests: `uv run pytest tests/scripts/test_codex_workflow.py`
- Inspect workflow status: `python3 .codex/workflow/scripts/workflow_router.py status`
- Start greenfield bootstrap planning: `python3 .codex/workflow/scripts/workflow_router.py bootstrap-start "..."`
- Record a UAT outcome: `python3 .codex/workflow/scripts/workflow_state.py set-uat-status passed --summary "..."`
- Compare baseline vs candidate plan quality: `python3 .codex/workflow/scripts/planning_state.py compare-plan`
- Validate the plugin manifest JSON: `python3 -m json.tool .codex-plugin/plugin.json`

## Notes

- Treat `$workflow` as the canonical interface. `/workflow ...` is compatibility-only.
- Do not commit live runtime state unless it is intentionally an example or baseline artifact.
- When changing the workflow contract, update the schemas, examples, skill instructions, and tests together.
