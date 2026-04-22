# Next Steps

## Current Repo State

- Current development branch is `stage`.
- `python3 .codex/workflow/scripts/workflow_router.py status` reports no active workflow state.
- The scripts regression suite is green: `uv run pytest tests/scripts/` passed with `80` tests.
- `execution-start` now honors custom `--planning-state-path` and `--execution-state-path` pairs, so custom-path workflows get the same planning/execution guardrails as the default path.
- Planning audits now support `current.direct_verification_matrix`, and the repo no longer relies on placeholder consumer-path test files to prove direct-consumer coverage.
- Focused regression coverage now includes `tests/scripts/test_workflow_router_cli.py`, `tests/scripts/test_planning_audit.py`, `tests/scripts/test_review_uat_workflow.py`, and `tests/scripts/test_telemetry_contract.py` alongside a slimmer `tests/scripts/test_codex_workflow.py`.
- Review/UAT control-loop behavior and telemetry contracts are now first-class focused suites instead of assertions buried inside the monolith.

## Distance To Production Ready

- This repo is still not close to production ready.
- The current release state is effectively pre-kernel-stabilization: the core control loops exist, but they are not yet covered, packaged, and proven strongly enough to treat the workflow as a dependable production tool.
- The biggest gap is not one bug or one missing feature. The gap is that convergence behavior, bootstrap behavior, audit completeness, and install/distribution readiness are still not hardened enough to treat the workflow as a dependable production tool.
- Production readiness should be treated as a multi-milestone outcome, not the next patch release.

## Production-Ready Means

- Brownfield planning, greenfield bootstrap, execution, review, UAT, ship, resume, status, and cancel all behave deterministically with no silent state corruption or ambiguous manual recovery.
- Planning approval audits are explicit and durable: direct consumer verification, dependency ownership, repo-memory alignment, and scope checks are enforced by stable tests rather than inferred from fragile conventions.
- Review and UAT are hard gates in practice, not just in prompts: fix loops, stale-guidance detection, override handling, and telemetry emission are all mechanically verified.
- Telemetry artifacts under `.codex/workflow/metrics/` are trustworthy enough to audit real runs, including approval, review, UAT, overrides, cancellation, and ship outcomes.
- The plugin and skill entrypoints are installable and usable in a clean repo checkout without hidden local assumptions or repo-author-only setup knowledge.
- The maintained scope is clear: production ready here means reliable planning-through-PR-shipping for maintainers in a live repo checkout, not full deployment orchestration, monitoring, or rollback automation.

## Milestones To Get There

### Milestone 1: Kernel Stabilization

- Keep shrinking `tests/scripts/test_codex_workflow.py` where narrow kernel contracts are still mixed into integration coverage.
  Review/UAT and telemetry now have focused suites; the remaining extraction targets are mainly convergence, bootstrap, and any residual single-subsystem assertions.
- Harden planning convergence and bootstrap contracts.
  Make discovery, planner, MVP, skeptic, and convergence outputs more mechanical and add fixed regression fixtures for greenfield and bootstrap flows.
- Tighten the review loop against `code_review.md`.
  Add tests for stale-guidance detection and required-check enforcement so review remains a blocking kernel gate instead of a prompt convention.
- Verify telemetry as a contract.
  Extend the focused telemetry suite beyond the extracted execution slice where needed, especially if later bootstrap or convergence work adds new metrics semantics.

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

## Milestone Completeness Snapshot

- Milestone 1: about 60% complete. Router, planning-audit, review/UAT, and telemetry contracts now have focused coverage, but convergence and bootstrap hardening are still the largest kernel-stability gaps.
- Milestone 2: about 30% complete. Direct verification matrices and some approval explicitness exist, but broader audit explainability and brownfield/greenfield parity are still incomplete.
- Milestone 3: about 15% complete. The plugin shape and core docs exist, but clean-install validation, packaging confidence, and operational support boundaries are still early.

## Not The Production Goal

- Production rollout orchestration beyond PR shipping.
- Monitoring and rollback automation for downstream systems.
- Telemetry polish beyond the local scorecard before the kernel contracts are stable.
- Broader packaging or multi-skill splitting before the kernel milestone is proven.

## Exit Criteria

- `tests/scripts/` covers the kernel with focused suites for router behavior, planning audits, execution transitions, review/UAT loops, telemetry, and bootstrap flows.
- The remaining control-loop risks can be described as edge cases, not as whole areas that are still only partially specified.
- The audit contract no longer depends on placeholder inference or repo-author context to stay honest.
- A clean install in a normal repo checkout can start, approve, resume, review, UAT, and ship a workflow through the supported path without undocumented setup.
- At that point, it is reasonable to call the repo production ready for its intended scope.
