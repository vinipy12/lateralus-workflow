# Lateralus Workflow

Discuss-first planning and stepwise execution workflow for Codex.

## Development Status

This repo is still in active development. The plugin is usable, but the workflow contract is still evolving and breaking changes are expected while the planning and execution model is being hardened.

Rough phase-completion estimates:

| Phase | Status |
| --- | --- |
| Discuss / context | 70% |
| Planning | 60% |
| Execution / development | 55% |
| Review gate | 65% |
| Shipping | 60% |
| UAT / gap closure | 0% |
| Plugin packaging | 70% |

## What lives here

- `.codex-plugin/plugin.json`: Codex plugin manifest
- `.codex/workflow/`: workflow engine, schemas, examples, notes
- `.agents/skills/workflow/`: native `$workflow` skill
- `.agents/skills/ship/`: ship skill used by the execution flow
- `tests/scripts/test_codex_workflow.py`: workflow regression tests

## Current plugin surface

The plugin currently exposes:

- `$workflow` for planning, resume, approval, status, cancel, and execution activation
- `$ship` for the publish phase after the workflow reaches ship readiness
- repo-local legacy `/workflow ...` hooks defined in `.codex/hooks.json`

Installing the plugin does not activate `.codex/hooks.json`; users who want the legacy `/workflow ...` trigger must wire those hooks into their own Codex config separately. `$workflow` remains the intended interface.
Installed plugin skills use bundled `scripts/` wrappers from the skill directory; the repo-local `.codex/workflow/scripts/...` commands below are for developing this workflow repository directly.

## Installation

This repo now works as a Codex plugin. The simplest local install path is to keep the repo at `~/plugins/lateralus-workflow` so the marketplace entry stays standard.

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

## Core entrypoints

- Native skill: `$workflow`
- Router CLI:
  - `python3 .codex/workflow/scripts/workflow_router.py planning-start "<feature request>"`
  - `python3 .codex/workflow/scripts/workflow_router.py resume`
  - `python3 .codex/workflow/scripts/workflow_router.py status`
  - `python3 .codex/workflow/scripts/workflow_router.py cancel`
  - `python3 .codex/workflow/scripts/workflow_router.py execution-start [plan-file]`

## Development

- Install dev dependencies: `uv sync --dev`
- Run workflow tests: `uv run pytest tests/scripts/test_codex_workflow.py`
- Validate the plugin manifest JSON: `python3 -m json.tool .codex-plugin/plugin.json`

## Notes

This extraction intentionally excludes live runtime state from AlphaSearch, such as active `planning_state.json`, `approved-plan.json`, and discovery artifacts, so the repo starts clean.
