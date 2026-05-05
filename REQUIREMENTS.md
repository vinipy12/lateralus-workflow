# Requirements

## Active Backlog
- Keep the UAT gate, telemetry artifacts, and bootstrap path stable.
- Revisit packaging and distribution shape after kernel validation.
- Preserve PR stewardship as the next product capability without folding it into the current `$ship` contract prematurely.

## Accepted Requirements
- Approved plans must pass audit before execution starts.
- Execution must preserve review, UAT, and ship gates.
- Parallel-ready plans must declare ownership and dependency metadata.
- The current ship boundary remains branch push, grounded PR creation, optional review request, and workflow completion.
- A completed slice that is large enough to justify a PR should be pushed and opened as a grounded pull request before starting the next unrelated kernel slice.
- After opening the PR, the agent must report that it is ready for the user to manually babysit reviewer comments and coding-change suggestions.

## Deferred Scope
- Packaging and distribution revisit.
- Additional telemetry polish beyond the local scorecard.
- Additional bootstrap refinements beyond the current router path.
- PR stewardship loop:
  - watch opened PRs for CI status, quality-gate results, reviewer comments, and review-thread state
  - post or refresh a structured quality gate covering code smells, material test coverage gaps, duplicated code, regression risk, stale durable guidance, and verification gaps
  - classify reviewer comments as required fixes, optional improvements, irrelevant or stale comments, or user-decision blockers
  - patch relevant findings, push updates, request re-review, and repeat until the PR is clean or an escalation threshold is reached
  - produce a final merge-ready summary once CI is green, quality gate passes, and no material reviewer suggestions remain open

## Milestone Commitments
- Keep the kernel local, auditable, and ready for broader packaging only after the control loops stay stable.
- Add PR stewardship only as an explicit phase with its own state, evidence, loop limits, and escalation behavior.
