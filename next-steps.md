# Next Steps

## Current Repo State

- Current checkout branch is `main`.
- `python3 .codex/workflow/scripts/workflow_router.py status` reports no active workflow state.
- The scripts regression suite is green: `uv run pytest tests/scripts/` passed with `139` tests.
- `execution-start` now honors custom `--planning-state-path` and `--execution-state-path` pairs, so custom-path workflows get the same planning/execution guardrails as the default path.
- Planning audits now support `current.direct_verification_matrix`, and the repo no longer relies on placeholder consumer-path test files to prove direct-consumer coverage.
- Focused regression coverage now includes `tests/scripts/test_workflow_router_cli.py`, `tests/scripts/test_planning_audit.py`, `tests/scripts/test_plugin_surface.py`, `tests/scripts/test_workflow_hooks.py`, `tests/scripts/test_review_uat_workflow.py`, and `tests/scripts/test_telemetry_contract.py` alongside a slimmer `tests/scripts/test_codex_workflow.py`.
- Review/UAT control-loop behavior and telemetry contracts are now first-class focused suites instead of assertions buried inside the monolith.
- Execution control hardening is now landed for the current kernel slice:
  deterministic pre-review sensors gate `review_pending`, execution blockers move into explicit `execution_escalated` state with structured metadata, and scorecards now expose escalation categories plus repeated review/UAT loop counts.
- Review-loop hardening now has an explicit `agents_update_required` step contract for durable-guidance changes.
  Passing review cannot advance to `commit_pending` unless required AGENTS guidance updates are recorded.
- PR stewardship is now part of the `$ship` guidance for requested Codex reviews.
  The ship loop watches Codex review comments, applies relevant fixes, requests re-review, and stops only when Codex reports the branch is clean or escalation is required.
  Broader CI and quality-gate stewardship remains a future capability.
- Packaging hardening is now started for Milestone 3:
  `$lateralus-workflow` is a package-name alias for `$workflow`, skill instructions no longer assume the target repo has `.agents/skills/`, and `scripts/lateralus_plugin.py` manages the personal Codex checkout plus installed cache updates.
- Latest dogfood evidence comes from `/home/vinipy/Lateralus/lateralus-legal-intake-ai`.
  The workflow branch reached a complete, PR-opened MVP, and comparison against `main` helped diagnose planning gaps during development.
  That comparison is dogfood evidence, not the normal user-facing workflow contract.
- Planning convergence controls are now landed for the latest kernel slice:
  `context.delivery_contract` keeps greenfield/bootstrap work one-shot by default, `context.clarification_gate` records product-impacting clarification decisions before phase advance, and `current.comparison_diagnostic` keeps dogfood/user-provided comparison findings diagnostic unless the user made the baseline authoritative.
- Ship-time repo-memory reconciliation is now landed for the latest kernel slice:
  `set-step-status ... shipped` records the PR handoff, Codex review status, and `STATE.md` reconciliation digest; `set-workflow-status complete` blocks if UAT, metrics, PR details, or `STATE.md` no longer match.
- Final validation ownership is now landed for the latest kernel slice:
  plans can declare `validation_ownership` for validation, docs, UAT, or release-alignment steps that must verify targets outside their edit ownership, and pre-review sensors treat that field as verification scope only.
- Focused test decomposition is now started for the latest kernel slice:
  plan evaluation and comparison contract tests moved out of `tests/scripts/test_codex_workflow.py` and into `tests/scripts/test_planning_audit.py`, plugin/skill surface checks now live in `tests/scripts/test_plugin_surface.py`, and legacy hook entrypoint checks now live in `tests/scripts/test_workflow_hooks.py`.
  Narrow kernel checks are moving closer to their owning focused modules.

## Product-Direction Lessons From Dogfood

- The legal-intake MVP comparison is the clearest current steering signal.
  The workflow branch became the better portfolio artifact after all steps finished: it produced a focused vertical slice, cleaner domain/API/persistence/AI boundaries, a polished dashboard, validation evidence, local docs, UAT script, and a grounded PR.
- In this dogfood run, `main` existed as a comparable artifact rather than as the product source of truth.
  Its differences still exposed tradeoffs worth noticing:
  an analyze-only intake endpoint, backend-driven option metadata, broader case taxonomy, dynamic demo follow-up dates, and SQLite indexes.
  The right direction is not to preserve `main`; it is to teach planning and convergence to use comparable artifacts as evidence, then explicitly classify each observed difference as a useful lesson, rejected alternative, or deferred follow-up.
- Comparable artifacts are optional development inputs.
  Once the workflow is ready for real use, most greenfield requests will not have a preexisting "other version" to compare against.
  The default product contract is still one-shot delivery from the user's stated need, repository context, and required clarification gates.
- Plan phase did not behave like the intended small `$grill-me`.
  It recorded open product questions around UI language and case taxonomy, then defaulted them instead of asking the user.
  Product-impacting ambiguities should trigger one-at-a-time clarification with a recommended answer, or an explicit `no_material_questions_reason` when the planner chooses not to ask.
- The dogfood run exposed a state-memory reconciliation gap.
  The machine state reached `complete`, UAT passed, and the PR opened, but the human-readable `STATE.md` still said "Execution in progress."
  Ship cannot be considered clean if repo-memory state and workflow JSON disagree.
- The step-4 and step-5 escalations were useful, not noise.
  They showed that validation steps naturally verify outside their narrow file ownership.
  Planning should model final validation as explicit cross-step ownership instead of making later execution clear ownership-mismatch escalations manually.
- Product direction should stay one-shot first.
  During dogfood or explicit user evaluation, comparison can help diagnose whether the workflow missed obvious tradeoffs.
  In normal operation, the workflow should not require or search for a comparable artifact before producing a plan.

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

#### Planning Convergence Controls: Landed

1. Greenfield/bootstrap planning now records a one-shot `delivery_contract` in `context.json`, with comparison artifacts explicitly not required.
2. Discovery can record optional `comparison_diagnostic` evidence from dogfood or user-provided baselines, but `adopt_now` is blocked unless the baseline is authoritative.
3. Discuss-phase validation now requires product-impacting ambiguity to flow through `clarification_gate` with a recommended answer and resolution, or a durable reason that no material question was needed.

#### Next Coding Slice

#### Ship-Time Repo-Memory Reconciliation: Landed

1. `set-step-status ... shipped` records branch, PR URL, Codex review status, repo-memory action, `STATE.md` summary, and the current `STATE.md` digest.
2. `set-workflow-status complete` validates workflow JSON state, passed UAT, `uat_passed` metrics, PR handoff details, and `STATE.md` digest before closing the workflow.
3. `$ship` guidance now requires the handoff arguments and treats completion failures as reconciliation blockers.

#### Final Validation Ownership: Landed

1. Approved plans can declare `validation_ownership` for verification-only cross-step targets.
2. Planning audits and plan comparisons flag undeclared verification targets outside `file_ownership`.
3. Pre-review sensors allow verification targets covered by either `file_ownership` or `validation_ownership`, while edit scope remains limited to `file_ownership`.

#### Focused Test Decomposition: Landed

1. Plan comparison and `evaluate_plan_spec` contract tests now live in `tests/scripts/test_planning_audit.py`.
2. Plugin manifest, skill scaffolding, wrapper, and README/roadmap surface checks now live in `tests/scripts/test_plugin_surface.py`.
3. Legacy user-prompt hook parsing and stop-hook escalation metrics now live in `tests/scripts/test_workflow_hooks.py`.
4. `tests/scripts/test_codex_workflow.py` is smaller and remains focused on cross-subsystem integration and wrapper behavior.
5. Full scripts regression remains green with `139` tests.

#### Remaining Slice Candidates

1. Continue shrinking `tests/scripts/test_codex_workflow.py` where narrow kernel contracts are still mixed into integration coverage.
2. Continue tightening the review loop against `code_review.md`.
   The `agents_update_required` stale-guidance check is now mechanical; remaining work should focus on any review pass checks that are still prompt-only.
3. Harden planning convergence and bootstrap contracts further if they still represent the highest residual kernel risk after more dogfood runs.
4. Verify telemetry as a contract beyond the execution slice where needed, now that repeated failure and escalation categories are part of the harness contract.
5. Keep full PR-stewardship state-machine work out of the next implementation slice until the kernel can reliably reach `ship_pending` and produce grounded PRs.
   The current `$ship` guidance can keep lightweight Codex-review babysitting, but persisted PR lifecycle states should wait.

### Milestone 2: Audit Completeness

- Expand explicit consumer verification matrices beyond the first migrated compatibility-plan cases.
  Move more compatibility coverage onto discovery-driven direct verification mappings and keep filesystem inference only as a compatibility fallback.
- Add optional comparative product-direction evidence to approval audits.
  Greenfield plans should be internally coherent without any comparison artifact.
  When a user-provided comparison branch, existing draft, or prior implementation exists, the audit should show what was learned from it without treating it as scope authority unless the user explicitly says it is.
- Make approval audits fully explicit about why a plan passes or fails.
  Reduce reliance on prompt interpretation and ensure the main planning audits are understandable, reproducible, and test-backed.
- Close remaining brownfield and greenfield audit gaps.
  Brownfield and bootstrap plans should both hit the same standard for memory alignment, verification specificity, and execution handoff quality.

### Milestone 3: Packaging And Operational Readiness

- Revisit packaging and distribution shape after the kernel stays stable.
  Production readiness requires a clean install story, stable wrapper behavior, and confidence that non-authors can use the plugin without special repo knowledge.
- Keep the personal install/update path working:
  `scripts/lateralus_plugin.py install`, `check`, and `update` should continue to cover `~/.codex/plugins/lateralus-workflow`, `~/.agents/plugins/marketplace.json`, and installed cache copies under `~/.codex/plugins/cache/`.
- Tighten release-facing documentation.
  README, skill instructions, examples, and schemas should all describe the same contract and the same supported operational path.
- Define a production-ready support boundary.
  Be explicit about what is intentionally supported, what is deferred, and which manual overrides remain acceptable in production use.

### Milestone 4: PR Stewardship

- Add a post-ship PR lifecycle phase after the current kernel and packaging milestones are stable.
  The current `$ship` behavior remains branch push, PR creation, optional review request, lightweight Codex-review babysitting, and workflow completion until this phase exists explicitly.
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

- Milestone 1: about 80% complete. Router, planning-audit, review/UAT, telemetry, execution-control escalation, ship reconciliation, and final validation ownership mechanics now have focused coverage. The main remaining kernel gaps are review-loop tightening plus convergence/bootstrap hardening if they remain the highest residual risk.
- Milestone 2: about 30% complete. Direct verification matrices and some approval explicitness exist, but broader audit explainability and brownfield/greenfield parity are still incomplete.
- Milestone 3: about 30% complete. The plugin shape, alias trigger, bundled-script instructions, and local install/update helper exist, but clean-install validation across a fresh repo and release-channel semantics still need dogfood proof.
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
- PR-sized dogfood slices end with a pushed branch, grounded PR title/body, and Codex review babysitting until the branch is clean or a concrete blocker is escalated before the next unrelated slice begins.
- At that point, it is reasonable to call the repo production ready for its intended scope.
