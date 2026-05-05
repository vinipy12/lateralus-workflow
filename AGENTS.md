# Repository Guidelines

## Structure
`.codex/workflow/` contains the workflow engine, schemas, examples, and strategy notes. `.agents/skills/` contains the Codex-facing skills, currently `workflow` and `ship`. Tests live under `tests/scripts/`, with focused router and planning-audit modules alongside the broader workflow regression suite.

## Commands
Install dependencies with `uv sync --dev`. Run the focused regression suite with `uv run pytest tests/scripts/`. Use `python3 .codex/workflow/scripts/workflow_router.py status` to inspect live workflow state and `python3 .codex/workflow/scripts/planning_state.py compare-plan` to compare planning outputs.

## Style
Target Python 3.13, keep modules and functions in `snake_case`, classes in `PascalCase`, and prefer small repo-local JSON-first utilities over framework-heavy abstractions. Keep the workflow deterministic: shared state on disk, explicit transitions, and auditable prompts.

## Workflow Development
Treat `$workflow` as the canonical interface. Keep `/workflow ...` only as legacy compatibility through the hook files. Do not commit live runtime state unless it is intentionally an example or baseline artifact. When changing the workflow contract, update the schemas, examples, skill instructions, and tests together.

## Slice Handoff
When a completed slice is large enough to justify a pull request, stop expanding the implementation, push the branch, and open a PR with a grounded title and description based on the actual diff and verification. After the PR is open, report that it is ready for the user to manually babysit review comments and coding-change suggestions.

## Review
Use `code_review.md` for review-gate behavior. Findings should focus on correctness, regressions, state-machine drift, stale instructions, and missing verification.
