---
name: ship
description: Finish a ship-ready branch by validating the final workflow state, pushing the current branch, generating the PR title/body in memory, creating the pull request, and optionally requesting `@codex review`. Use when the user says ship, open the PR, publish the branch, or finish the workflow after execution has reached `ship_pending`.
---

# Ship

Use this skill for the final publication phase after execution has reached `ship_pending`.
Use the bundled `scripts/workflow_state.py` wrapper when you need to update workflow state. Resolve it relative to this skill directory; do not assume the target project has `.agents/skills/` checked in.

## Inputs

- Repo-local workflow state: `.codex/workflow/state.json`
- Repo-local UAT artifact: `.codex/workflow/uat.json`
- Base branch: from the workflow state, usually `origin/main`
- Current branch: resolve from git

## Workflow

1. Inspect `.codex/workflow/state.json` first.
2. Confirm the workflow is ready to ship:
   - `workflow_status` is `ship_pending`, which means UAT has already passed and deployment is now allowed
   - the current step is already `committed`
3. Review branch state locally:
   - confirm the branch name
   - confirm whether the branch already has an upstream
   - confirm there are no unexpected unstaged changes that would make the PR misleading
4. Generate the PR title and body in memory from the committed branch diff.
5. Push the branch with local git.
6. Prefer GitHub MCP to create the PR and to post a PR comment; fall back to `gh` only if MCP is unavailable.
7. If `request_codex_review` is `true`, post `@codex review` to the PR after creation.
8. Report that the PR is ready for the user to manually babysit review comments and coding-change suggestions.
9. Mark the workflow complete:
   - Deployment scope here is branch push, PR creation, optional `@codex review`, and workflow completion only.
   - Update `STATE.md` if shipping changed release state, latest decisions, or unresolved risks.
   - `python3 scripts/workflow_state.py set-step-status <current-step-id> shipped`
   - `python3 scripts/workflow_state.py set-workflow-status complete`

## Rules

- Do not create an intermediate `PR_DESCRIPTION.md` file.
- Keep the PR body concise and outcome-focused:
  - Summary
  - Testing
  - Risks
- Prefer information from the actual diff and executed checks over generic prose.
- If push or PR creation fails, stop and report the exact blocker instead of guessing.
- Do not use this skill before the workflow reaches `ship_pending`.
- Do not ship if the workflow state still indicates an earlier step is uncommitted.
- Do not continue into new kernel work after opening a PR for a PR-sized slice; hand the PR back to the user for manual babysitting.

## GitHub

- Preferred path: GitHub MCP for PR creation and PR comments.
- Fallback path: `gh pr create` and `gh pr comment`.

## Output

Report:

- branch name
- base branch
- PR title
- PR URL
- whether `@codex review` was requested
- that the PR is ready for manual user babysitting
