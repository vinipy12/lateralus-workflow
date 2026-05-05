# Next Steps

## Current Repo State

- Current development branch is `stage`.
- `python3 .codex/workflow/scripts/workflow_router.py status` reports no active workflow state.
- The scripts regression suite is green: `uv run pytest tests/scripts/` passed with `107` tests.
- `execution-start` now honors custom `--planning-state-path` and `--execution-state-path` pairs, so custom-path workflows get the same planning/execution guardrails as the default path.
- Planning audits now support `current.direct_verification_matrix`, and the repo no longer relies on placeholder consumer-path test files to prove direct-consumer coverage.
- Focused regression coverage now includes `tests/scripts/test_workflow_router_cli.py`, `tests/scripts/test_planning_audit.py`, `tests/scripts/test_review_uat_workflow.py`, and `tests/scripts/test_telemetry_contract.py` alongside a slimmer `tests/scripts/test_codex_workflow.py`.
- Review/UAT control-loop behavior and telemetry contracts are now first-class focused suites instead of assertions buried inside the monolith.
- Execution control hardening is now landed for the current kernel slice:
  deterministic pre-review sensors gate `review_pending`, execution blockers move into explicit `execution_escalated` state with structured metadata, and scorecards now expose escalation categories plus repeated review/UAT loop counts.
- Review-loop hardening now has an explicit `agents_update_required` step contract for durable-guidance changes.
  Passing review cannot advance to `commit_pending` unless required AGENTS guidance updates are recorded.
- PR stewardship is now a planned post-ship capability, not the current `$ship` contract.
  The intended direction is a PR steward loop that watches CI, quality gates, and reviewer comments, applies relevant fixes, requests re-review, and stops only when the PR is merge-ready or escalation is required.
- Until PR stewardship is implemented, PR-sized slices should be pushed and opened as grounded PRs, then handed back to the user for manual babysitting of reviewer comments and coding-change suggestions.

## Distance To Production Ready

- This repo is still not close to production ready.
- The current release state is effectively pre-kernel-stabilization: the core control loops exist, but they are not yet covered, packaged, and proven strongly enough to treat the workflow as a dependable production tool.
- The biggest gap is not one bug or one missing feature. The gap is that execution-control hardening, convergence/bootstrap behavior, audit completeness, and install/distribution readiness are still not hardened enough to treat the workflow as a dependable production tool.
- Production readiness should be treated as a multi-milestone outcome, not the next patch release.

## Production-Ready Means

- Brownfield planning, greenfield bootstrap, execution, review, UAT, ship, resume, status, and cancel all behave deterministically with no silent state corruption or ambiguous manual recovery.
- Planning approval audits are explicit and durable: direct consumer verification, dependency ownership, repo-memory alignment, and scope checks are enforced by stable tests rather than inferred from fragile conventions.
- Review and UAT are hard gates in practice, not just in prompts: fix loops, stale-guidance detection, override handling, and telemetry emission are all mechanically verified.
- Telemetry artifacts under `.codex/workflow/metrics/` are trustworthy enough to audit real runs, including approval, review, UAT, overrides, cancellation, and ship outcomes.
- The plugin and skill entrypoints are installable and usable in a clean repo checkout without hidden local assumptions or repo-author-only setup knowledge.
- The maintained scope is clear: production ready here means reliable planning-through-PR-shipping for maintainers in a live repo checkout, not full deployment orchestration, monitoring, or rollback automation.

## Kernel Readiness Bar

- Passing tests are necessary but not sufficient.
  The kernel is good enough only after it survives real workflow pressure across multiple dogfood tasks.
- A clean install must run planning, approval, execution, review, UAT, and `ship_pending` without repo-author-only knowledge or manual JSON edits.
- State transitions must be deterministic on both happy and failure paths:
  CI failure, review finding, UAT gap, replan-required result, interrupted session, cancellation, resume, and execution escalation.
- Every gate must leave auditable evidence:
  planning audit results, review evidence, UAT outcome, telemetry event, override reason, and ship readiness.
- Illegal transitions must be covered by tests, not only successful workflows.
- A fresh agent must be able to inspect `PROJECT.md`, `REQUIREMENTS.md`, `STATE.md`, and `.codex/workflow/` artifacts and continue the active run correctly.
- When the workflow cannot proceed safely, it must escalate with a concrete reason instead of guessing or silently continuing.

## Milestones To Get There

### Milestone 1: Kernel Stabilization

#### Harness Engineering

- Treat the kernel as a harness problem, not just a prompt-tuning problem.
  Add deterministic feedforward guides and feedback sensors instead of relying on repeated human correction.
- Distribute controls across the lifecycle.
  Run fast computational checks before inferential review, and keep heavier review/UAT checks after integration where they add signal.
- Make execution semantics explicit.
  Continue until completion criteria are met, or escalate with an explicit reason when the workflow cannot safely proceed.
- Use recurring failures as steering input.
  When the same failure or escalation repeats, tighten the harness and promote that lesson into a new control.

#### Execution Control Hardening: Landed

1. Deterministic execution sensors now gate `review_pending` before inferential review.
2. Continue-or-escalate behavior is now explicit in router and execution state transitions through `execution_escalated`.
3. Telemetry now records deterministic sensor failures, escalation categories, escalation clear events, and repeated review/UAT loops in the scorecard.

#### Next Coding Slice

1. Keep shrinking `tests/scripts/test_codex_workflow.py` where narrow kernel contracts are still mixed into integration coverage.
2. Continue tightening the review loop against `code_review.md`.
   The `agents_update_required` stale-guidance check is now mechanical; remaining work should focus on any review pass checks that are still prompt-only.
3. Harden planning convergence and bootstrap contracts after the control slice above if they still represent the highest residual kernel risk.
4. Verify telemetry as a contract beyond the execution slice where needed, now that repeated failure and escalation categories are part of the harness contract.
5. Keep PR stewardship out of the implementation slice until the kernel can reliably reach `ship_pending` and produce grounded PRs.

### Milestone 2: Audit Completeness

- Expand explicit consumer verification matrices beyond the first migrated compatibility-plan cases.
  Move more compatibility coverage onto discovery-driven direct verification mappings and keep filesystem inference only as a compatibility fallback.
- Make approval audits fully explicit about why a plan passes or fails.
  Reduce reliance on prompt interpretation and ensure the main planning audits are understandable, reproducible, and test-backed.
- Close remaining brownfield and greenfield audit gaps.
  Brownfield and bootstrap plans should both hit the same standard for memory alignment, verification specificity, and execution handoff quality.

### Milestone 3: Packaging And Operational Readiness

- Revisit packaging and distribution shape after the kernel stays stable.
  Production readiness requires a clean install story, stable wrapper behavior, and confidence that non-authors can use the plugin without special repo knowledge.
- Tighten release-facing documentation.
  README, skill instructions, examples, and schemas should all describe the same contract and the same supported operational path.
- Define a production-ready support boundary.
  Be explicit about what is intentionally supported, what is deferred, and which manual overrides remain acceptable in production use.

### Milestone 4: PR Stewardship

- Add a post-ship PR lifecycle phase after the current kernel and packaging milestones are stable.
  The current `$ship` behavior remains branch push, PR creation, optional review request, and workflow completion until this phase exists explicitly.
- Introduce a PR steward state machine:
  `pr_opened`, `pr_stewardship_active`, `pr_fixing`, `pr_review_requested`, `merge_ready`, and `pr_stewardship_escalated`.
- Prefer GitHub MCP for PR metadata, comments, review threads, status checks, and review requests.
  CLI fallback can stay available for local development but should not define the primary contract.
- Add a structured quality gate comment that checks for code smells, material test coverage gaps, duplicated code, regression risk, stale durable guidance, and verification gaps.
- Treat external reviewer comments as candidate findings, not commands.
  The steward must classify each comment, apply relevant fixes, explain rejected or stale comments, push updates, and request re-review.
- Add loop limits and escalation rules for repeated review cycles, architecture-changing suggestions, conflicting reviewer comments, failing CI with unclear root cause, or fixes that would expand materially beyond the approved plan.
- Finish with a merge-ready summary only when CI is green, the quality gate passes, and no material reviewer suggestions remain open.

## Milestone Completeness Snapshot

- Milestone 1: about 75% complete. Router, planning-audit, review/UAT, telemetry, and execution-control escalation mechanics now have focused coverage. The main remaining kernel gaps are stale-guidance review enforcement plus convergence/bootstrap hardening if they remain the highest residual risk.
- Milestone 2: about 30% complete. Direct verification matrices and some approval explicitness exist, but broader audit explainability and brownfield/greenfield parity are still incomplete.
- Milestone 3: about 15% complete. The plugin shape and core docs exist, but clean-install validation, packaging confidence, and operational support boundaries are still early.
- Milestone 4: about 0% complete. PR stewardship is product direction only; no current workflow state, schema, skill, or test contract supports it yet.

## Not The Production Goal

- Production rollout orchestration beyond PR shipping.
- Monitoring and rollback automation for downstream systems.
- Telemetry polish beyond the local scorecard before the kernel contracts are stable.
- Broader packaging or multi-skill splitting before the kernel milestone is proven.
- Automatic merge, production deploy, incident monitoring, or rollback as part of the first PR stewardship slice.

## Exit Criteria

- `tests/scripts/` covers the kernel with focused suites for router behavior, planning audits, execution transitions, review/UAT loops, telemetry, and bootstrap flows.
- The remaining control-loop risks can be described as edge cases, not as whole areas that are still only partially specified.
- The audit contract no longer depends on placeholder inference or repo-author context to stay honest.
- A clean install in a normal repo checkout can start, approve, resume, review, UAT, and ship a workflow through the supported path without undocumented setup.
- Several real dogfood runs reach `ship_pending` without manual state edits, and any blocked run leaves enough evidence for a fresh agent to resume or escalate correctly.
- PR-sized dogfood slices end with a pushed branch, grounded PR title/body, and explicit handoff for manual review babysitting before the next unrelated slice begins.
- At that point, it is reasonable to call the repo production ready for its intended scope.
