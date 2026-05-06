# Lateralus Workflow

Discuss-first planning and stepwise execution workflow for Codex.

## Kernel Status

The workflow kernel currently includes:

- hard-gated planning phases with deterministic advancement
- repo-root project memory in `PROJECT.md`, `REQUIREMENTS.md`, and `STATE.md`
- approval-time planning audits
- explicit discovery-driven direct verification matrices via `current.direct_verification_matrix`
- orchestration-ready plan metadata such as `depends_on`, `wave`, `file_ownership`, `rollback_notes`, `operational_watchpoints`, and `agents_update_required`
- stepwise execution with implement, review, fix, commit, UAT, and ship gates
- repo-local UAT artifacts in `.codex/workflow/uat.json`
- local telemetry artifacts in `.codex/workflow/metrics/events.jsonl` and `.codex/workflow/metrics/scorecard.json`
- greenfield bootstrap planning through the existing router
- focused router, planning-audit, review/UAT, and telemetry regression modules under `tests/scripts/`
- canonical `compare-plan` baseline fixtures inside `.codex/workflow/`

Still intentionally deferred:

- broader packaging or multi-skill splitting beyond `$workflow` and `$ship`
- post-ship PR stewardship for CI watching, quality gates, reviewer-comment triage, re-review loops, and merge-ready summaries
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
- `tests/scripts/`: workflow regression suite, including focused router, planning-audit, review/UAT, telemetry, and cross-subsystem integration coverage

## Current Surface

The plugin currently exposes:

- `$workflow` for brownfield planning, greenfield bootstrap planning, revision, approval, resume, status, cancel, and execution activation
- `$lateralus-workflow` as a package-name alias for users who try to invoke the plugin by its install name
- `$ship` for the publish phase after the workflow reaches ship readiness
- repo-local legacy `/workflow ...` hooks defined in `.codex/hooks.json`

Installing the plugin does not activate `.codex/hooks.json`; users who want the legacy `/workflow ...` trigger must wire those hooks into their own Codex config separately. `$workflow` remains the intended interface.

Installed plugin skills use the bundled wrappers under each skill's `scripts/` directory and operate on the active project checkout. Do not copy `.agents/skills/` into every target repo.
When developing this repository directly, use the repo-local `.codex/workflow/scripts/...` commands below.

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

For compatibility-sensitive discovery, `current.direct_verification_matrix` can map discovered entry points to the exact direct verification targets the approval audit should require. The audit uses that explicit mapping first and falls back to inferred test paths only when no matrix entry exists.

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

When using non-default workflow files, pass the matching `--planning-state-path` and `--execution-state-path` values to router commands that cross the planning/execution boundary, including `execution-start`, so guardrails inspect the same workflow session.
- Planning state CLI:
  - `python3 .codex/workflow/scripts/planning_state.py show`
  - `python3 .codex/workflow/scripts/planning_state.py validate`
  - `python3 .codex/workflow/scripts/planning_state.py validate-phase`
  - `python3 .codex/workflow/scripts/planning_state.py advance [phase]`
  - `python3 .codex/workflow/scripts/planning_state.py audit-plan`
  - `python3 .codex/workflow/scripts/planning_state.py compare-plan`
- Execution state CLI:
  - `python3 .codex/workflow/scripts/workflow_state.py set-step-status <step-id> <status>`
  - Review fail: `python3 .codex/workflow/scripts/workflow_state.py set-step-status <step-id> fix_pending --review-summary "..." --scope-confirmed true --verification-status passed --agents-checked AGENTS.md --agents-updated false --finding-count 1`
  - Review pass: `python3 .codex/workflow/scripts/workflow_state.py set-step-status <step-id> commit_pending --review-summary "review passed" --scope-confirmed true --verification-status passed --agents-checked AGENTS.md --agents-updated false --finding-count 0`
  - `python3 .codex/workflow/scripts/workflow_state.py resolve-escalation`
  - `python3 .codex/workflow/scripts/workflow_state.py set-uat-status <passed|failed-gap|failed-replan> --summary "..."`
  - `python3 .codex/workflow/scripts/workflow_state.py set-workflow-status complete`
  - `python3 .codex/workflow/scripts/workflow_state.py set-workflow-status <status> --override-reason "..."`

## Execution Model

Execution now ends with a blocking post-code control loop:

1. Development owns implementation through `committed` for each step
2. `set-step-status ... review_pending` runs deterministic pre-review sensors before inferential review
3. `execution_escalated` blocks the workflow when deterministic sensors fail or execution state becomes ambiguous
4. Review remains embedded in execution and blocks promotion to commit
   - `fix_pending` and `commit_pending` now require inline review evidence: summary, scope confirmation, verification result or blocker note, checked `AGENTS.md` paths, whether AGENTS changed, and the material finding count
5. `uat_pending` after the last committed step
6. `gap_closure_pending` for fixable UAT gaps inside the same workflow
7. `replan_required` when UAT shows a scope or architecture mismatch
8. `ship_pending` only after UAT passes
9. Deployment is intentionally limited to branch push, PR creation, optional `@codex review`, and workflow completion

Clear normal execution escalations with `python3 .codex/workflow/scripts/workflow_state.py resolve-escalation` after the blocker is fixed; the workflow returns to the pre-escalation phase instead of always dropping back to `active`. Manual workflow-status jumps are still override-only operations. `set-workflow-status complete` is reserved for the real ship path after the current step is already `shipped`.

Telemetry stays local and auditable under `.codex/workflow/metrics/`, including escalation categories and repeated review/UAT loop counts in the scorecard.

## Installation And Updates

This repo works as a Codex plugin. The supported personal install keeps the source checkout under Codex home at `~/.codex/plugins/lateralus-workflow` and writes a marketplace entry that points there.

From a checkout of this repo, run:

```bash
python3 scripts/lateralus_plugin.py install
```

That command clones or reuses `~/.codex/plugins/lateralus-workflow`, writes `~/.agents/plugins/marketplace.json`, and updates any installed cache copies it can find under `~/.codex/plugins/cache/`.

The generated marketplace entry uses this shape:

```json
{
  "name": "lateralus-local",
  "interface": {
    "displayName": "Lateralus Local"
  },
  "plugins": [
    {
      "name": "lateralus-workflow",
      "source": {
        "source": "local",
        "path": "./.codex/plugins/lateralus-workflow"
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

After installation:

1. Restart Codex and open `/plugins`.
2. Install or re-enable `Lateralus Workflow`.
3. Start a new thread.
4. Use `$workflow <request>` or `$lateralus-workflow: <request>`.

To check for updates without changing files:

```bash
python3 ~/.codex/plugins/lateralus-workflow/scripts/lateralus_plugin.py check
```

To fast-forward both the source checkout and installed cache copies:

```bash
python3 ~/.codex/plugins/lateralus-workflow/scripts/lateralus_plugin.py update
```

Restart Codex after updating installed plugin files so the active session reloads the new skills.

## Development

- Install dev dependencies: `uv sync --dev`
- Run workflow tests: `uv run pytest tests/scripts/`
- Run focused router CLI tests: `uv run pytest tests/scripts/test_workflow_router_cli.py`
- Run focused planning audit tests: `uv run pytest tests/scripts/test_planning_audit.py`
- Run focused review/UAT tests: `uv run pytest tests/scripts/test_review_uat_workflow.py`
- Run focused telemetry tests: `uv run pytest tests/scripts/test_telemetry_contract.py`
- Inspect workflow status: `python3 .codex/workflow/scripts/workflow_router.py status`
- Install or update the personal plugin checkout: `python3 scripts/lateralus_plugin.py install`
- Check installed plugin copies for updates: `python3 scripts/lateralus_plugin.py check`
- Start greenfield bootstrap planning: `python3 .codex/workflow/scripts/workflow_router.py bootstrap-start "..."`
- Clear an execution escalation after fixing the blocker: `python3 .codex/workflow/scripts/workflow_state.py resolve-escalation`
- Record a UAT outcome: `python3 .codex/workflow/scripts/workflow_state.py set-uat-status passed --summary "..."`
- Compare baseline vs candidate plan quality: `python3 .codex/workflow/scripts/planning_state.py compare-plan`
- Validate the plugin manifest JSON: `python3 -m json.tool .codex-plugin/plugin.json`

## Notes

- Treat `$workflow` as the canonical interface. `/workflow ...` is compatibility-only.
- Do not commit live runtime state unless it is intentionally an example or baseline artifact.
- When changing the workflow contract, update the schemas, examples, skill instructions, and tests together.
