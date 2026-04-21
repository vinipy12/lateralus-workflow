# Lateralus Workflow

Discuss-first planning and stepwise execution workflow for Codex.

## What lives here

- `.codex/workflow/`: workflow engine, schemas, examples, notes
- `.agents/skills/workflow/`: native `$workflow` skill
- `.agents/skills/ship/`: ship skill used by the execution flow
- `tests/scripts/test_codex_workflow.py`: workflow regression tests

## Core entrypoints

- Native skill: `$workflow`
- Router CLI:
  - `python3 .codex/workflow/scripts/workflow_router.py planning-start "<feature request>"`
  - `python3 .codex/workflow/scripts/workflow_router.py resume`
  - `python3 .codex/workflow/scripts/workflow_router.py status`
  - `python3 .codex/workflow/scripts/workflow_router.py cancel`
  - `python3 .codex/workflow/scripts/workflow_router.py execution-start [plan-file]`

## Legacy compatibility

- `.codex/hooks.json` preserves the old `/workflow ...` hook path.
- `$workflow` is the intended interface going forward.

## Development

- Install dev dependencies: `uv sync --dev`
- Run workflow tests: `uv run pytest tests/scripts/test_codex_workflow.py`

## Notes

This extraction intentionally excludes live runtime state from AlphaSearch, such as active `planning_state.json`, `approved-plan.json`, and discovery artifacts, so the repo starts clean.
