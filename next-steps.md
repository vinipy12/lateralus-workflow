# Next Steps

## Completed Baseline

- Kernel hardening first is complete.
- `execution-start` no longer clobbers active planning or non-terminal execution state.
- Workflow completion now requires the real ship path: `ship_pending` plus a current step that is already `shipped`.
- Manual workflow-status jumps are now explicit override operations with `--override-reason`.

## Plan

### Ready next

- Strengthen planning audits beyond direct-consumer coverage.
- Formalize subagent role contracts and convergence outputs.
- Add planner-behavior regression fixtures, not just schema tests.

### Later

- Improve approval summaries with explicit tradeoffs and unresolved risk.
- Add richer brownfield and greenfield memory-alignment checks.
- Tighten orchestration-readiness metadata budgets.

### Ready Definition

- Plans are decision-complete, auditable, and stable enough for another agent to execute without guessing.

## Development

### Ready next

- Harden state transitions and single-active-workflow invariants.
- Tighten allowed manual overrides.
- Add better sequential execution guardrails around step progression.

### Later

- Add dependency-aware parallel execution for unrelated steps using existing `depends_on` and `wave`.
- Add explicit recovery flows for interrupted or partially completed runs.

### Ready Definition

- Development state cannot be silently clobbered or advanced into impossible states.

## Review

### Ready next

- Make review gate expectations more mechanical and more visible.
- Add tests for review-driven fix loops and stale-guidance detection.

### Later

- Promote review into a more explicit first-class warfront if the embedded gate becomes too opaque.
- Add production-readiness review profiles for riskier changes.

### Ready Definition

- Review outcomes are reproducible, blocking, and auditable.

## Deployment

### Ready next

- Keep scope to PR shipping only.
- Ensure completion can happen only from valid ship-ready state.
- Align `$ship`, metrics, and completion events.

### Later

- Add optional release-readiness artifacts.
- Add optional deploy and runbook metadata if real usage demands it.

### Not yet

- Production rollout orchestration.
- Monitoring and rollback automation.

### Ready Definition

- A ship-ready workflow can reliably publish a correct PR and close state without faking completion.
