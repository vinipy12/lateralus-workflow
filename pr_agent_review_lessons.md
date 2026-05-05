# PR-Agent Review Lessons

This document captures the parts of `pr-agent` that are most relevant to this repository's review architecture.

Scope:

- Focus on review architecture and review-adjacent core abilities.
- Ignore GitHub Actions packaging, slash-command UX, and PR-comment delivery mechanics except where they reveal a useful architectural pattern.
- Bias toward lessons that can be translated into a repo-local, plan-driven workflow instead of a GitHub-bot product.

## Core Lessons

### 1. Review should measure contract compliance, not just generic code quality

One of the strongest ideas in `pr-agent` is that review can check whether code matches the intended change, not only whether the code "looks good".

Relevant ideas:

- linked ticket or issue is treated as a source of truth for intent
- review can classify compliance level instead of emitting only prose
- review can detect additional unrelated content in the PR
- review can distinguish "code appears aligned" from "more manual validation is still needed"

The right translation for this repo is:

- replace ticket context with the approved plan and current step contract
- ask whether implementation satisfied the approved `requirement_ids`
- check whether the change stayed inside `planned_updates`, `file_ownership`, and `avoid_touching`
- check whether any `out_of_scope` or deferred work leaked into the implementation
- keep an intermediate outcome for "code verified, but UAT/manual validation still needed"

This is the single best idea to borrow.

### 2. Diff and context packing are first-class review subsystems

`pr-agent` does not treat prompt construction as an afterthought. It has explicit strategies for compression and context expansion.

Relevant ideas:

- exclude binary and non-code files from deep analysis
- treat small and large diffs differently
- for small diffs, add more surrounding hunk context
- for large diffs, prioritize additions over deletions
- tokenize patches and fit the highest-value patches first
- summarize the remaining modified files instead of pretending the model saw everything
- expand context asymmetrically, with more context before the change than after
- expand toward enclosing functions or classes instead of relying only on fixed line windows

Lessons for this repo:

- build a deterministic review packer instead of dumping the raw step diff into the prompt
- rank files and hunks by workflow metadata first, then by generic heuristics
- give priority to `files_read_first`, `file_ownership`, `verification_targets`, `interfaces_to_preserve`, `risk_flags`, and high-blast-radius files
- include an explicit omitted-context summary so the review result is honest about what was and was not deeply inspected

### 3. Review dimensions should be explicit and configurable

`pr-agent` treats review as a bundle of named dimensions rather than one vague "review this PR" prompt. Its configuration exposes switches such as:

- `require_tests_review`
- `require_security_review`
- `require_ticket_analysis_review`
- `require_can_be_split_review`
- `require_estimate_effort_to_review`
- `require_score_review`
- `require_todo_scan`
- `num_max_findings`

That design is correct. The review engine should know which questions it is answering.

Good candidate dimensions for this repo:

- correctness and regressions
- plan compliance
- scope contamination
- verification adequacy
- preserved interface risk
- operational and migration risk
- security
- durable guidance drift in `AGENTS.md`, `PROJECT.md`, `REQUIREMENTS.md`, and `STATE.md`

Less useful as blocking dimensions here:

- review effort
- splitability

Those are better treated as diagnostics or planning-quality signals than as hard execution gates.

### 4. Generate findings first, then run a reflection and re-ranking pass

`pr-agent` has a self-reflection pass that scores and re-ranks its own output, dropping weak or incorrect items.

This is a strong pattern for review findings too.

Good translation:

1. generate candidate findings
2. run a second pass that scores confidence, severity, and usefulness
3. drop weak findings
4. publish only the highest-signal items

Guardrails:

- deterministic failures must always survive
- reflection may suppress or reorder LLM findings, but must not clear hard sensor failures
- the published result should stay capped to a small number of top findings

### 5. Versioned compliance checklists are a strong control surface

`pr-agent` ships a repo-level `pr_compliance_checklist.yaml`, and the surrounding checklist/template ecosystem treats compliance rules as versioned artifacts owned by the repository or organization.

That is the right model for durable review policy.

Lessons:

- keep review standards under version control
- make the rules specific, contextual, and organization-approved
- focus checklist items on issues that linting, typing, and unit tests do not capture well
- avoid turning the checklist into a style guide or formatter substitute

For this repo, the checklist should likely encode step-scope and workflow-specific concerns, such as:

- implementation stayed inside the current execution step
- verification evidence covers the declared verification targets
- preserved interfaces were actually protected
- no non-goal or deferred-scope work leaked in
- `AGENTS.md` and repo memory were updated if durable guidance changed

### 6. Machine-readable outcomes matter more than prose

`pr-agent` uses labels and optional merge-blocking as machine-readable review outputs. The GitHub-specific label mechanism is not the important part; the important part is that review emits state, not only text.

This repo should preserve that lesson but use repo-local artifacts and workflow states instead of PR labels.

A good review result should include:

- overall status
- category-level results
- top findings
- confidence and severity
- evidence paths
- what was reviewed in full
- what was summarized only

Useful outcome states:

- `pass`
- `needs_fix`
- `needs_human`
- `spec_mismatch`
- `verified_needs_uat`

### 7. Persistent review artifacts beat noisy repeated output

`pr-agent` supports persistent comments and bounded finding count. The deeper lesson is that reruns should update a stable review artifact rather than scatter fresh output everywhere.

Good translation for this repo:

- keep one canonical repo-local review result artifact per step or workflow
- update it on rerun
- retain a concise current summary plus structured detail
- preserve a small history if needed, but keep one authoritative latest result

This is especially important for repeated `review_pending -> fix_pending -> review_pending` loops.

### 8. Extra instructions and metadata are legitimate inputs

`pr-agent` exposes `extra_instructions` and supports local/global metadata and best-practice injections. That is the right idea: review quality improves when the model gets durable, repo-specific context.

For this repo, the equivalent inputs are already available:

- approved plan
- current step contract
- `code_review.md`
- `PROJECT.md`
- `REQUIREMENTS.md`
- `STATE.md`
- relevant `AGENTS.md` files
- step-level risk and ownership metadata

The lesson is not "add more prompt text". The lesson is "make policy and context explicit, structured inputs to the review engine".

### 9. Review should separate code-complete from fully-release-ready

`pr-agent` includes an outcome shape like "PR Code Verified" for cases where code appears to satisfy the ticket but additional manual validation is still required.

That is useful here because this workflow already separates review from UAT and ship.

The good translation is:

- review can say "implementation looks correct relative to the plan"
- UAT still decides whether the workflow is actually ready to ship

This avoids overloading review with every release decision.

### 10. Incremental re-review is a real use case

`pr-agent` has explicit incremental-review settings such as:

- `require_all_thresholds_for_incremental_review`
- `minimal_commits_for_incremental_review`
- `minimal_minutes_for_incremental_review`

The underlying lesson is that re-review should have first-class support.

For this repo:

- after a failed review, prefer diffing from the previous failed review point, not always re-reading the entire step from scratch
- keep the full step contract visible
- narrow the changed-code payload to the delta plus impacted context when possible

### 11. Noise control is part of the architecture

`pr-agent` explicitly caps findings and provides knobs that reduce noisy output.

The right lesson is:

- a review engine should prefer a few strong findings over exhaustive low-confidence chatter
- no-issue output should stay short and explicit
- weak, duplicative, and style-only remarks should be aggressively filtered

Signal discipline is not presentation polish. It directly affects reviewer trust.

### 12. Compliance rules should target contextual judgement, not what existing tools already cover

The public checklist/template material around `pr-agent` makes an important point: compliance rules should focus on architecture, maintainability, framework pitfalls, performance, and security issues that require context.

That is exactly right.

Bad checklist targets:

- formatting
- import order
- trivial syntax
- anything already enforced mechanically elsewhere

Good checklist targets:

- plan adherence
- operational risk
- interface stability
- risky migrations
- cross-cutting behavior changes
- repo-specific process invariants

## What Not To Copy

The following parts are much less useful for this repo:

- GitHub-bot product shape as the primary interface
- slash commands and PR comments as the main storage layer
- labels as the primary review artifact
- PR-centric assumptions when this workflow is step-centric
- review-effort or splitability as hard blockers
- a single-pass LLM-only review without deterministic scope and verification checks

These are delivery details or mismatched assumptions, not the core value.

## Translation Into Lateralus Terms

Useful mapping between `pr-agent` concepts and this repo's workflow:

- ticket or issue context -> approved plan plus current execution step contract
- ticket compliance -> plan compliance
- extra unrelated content -> scope contamination outside current step ownership or plan scope
- persistent review comment -> repo-local `review_result` artifact
- PR labels -> workflow status plus structured review result status
- "PR Code Verified" -> review passed but UAT/manual validation still required
- compliance checklist YAML -> repo-owned review checklist or policy artifact
- extra instructions -> review policy plus repo memory plus per-step annotations
- incremental review -> re-review only the delta since the last failed pass plus impacted context

## Suggested Architectural Pattern To Borrow

If these lessons are applied here, the resulting review flow should look roughly like this:

1. Run deterministic pre-review sensors.
2. Build a structured review pack.
3. Run LLM review against explicit dimensions.
4. Run a reflection and re-ranking pass.
5. Persist a structured review result artifact.
6. Map the outcome to workflow state.

The review pack should contain at least:

- current step contract
- approved-plan context relevant to that step
- repo-memory snippets relevant to review
- changed files and patch data
- verification evidence
- dynamic context for the highest-risk hunks
- a summary of omitted files or partially reviewed files

## Comparison Axes For Later

When comparing `pr-agent` against this repo's current review architecture, the highest-value questions are:

- What is the review source of truth?
- How is unrelated scope detected?
- What deterministic checks run before the model?
- How is prompt context packed for large diffs?
- Are review dimensions explicit and configurable?
- Is there a second-pass filter for weak findings?
- Does review emit machine-readable state?
- Is verification evidence persisted and reviewable?
- Can review distinguish "code looks right" from "ready to ship"?
- Are standards versioned and repo-owned?

## Source Links

Primary references:

- `pr-agent` review docs: https://docs.pr-agent.ai/tools/review/
- ticket context docs: https://docs.pr-agent.ai/core-abilities/fetching_ticket_context/
- compression strategy docs: https://docs.pr-agent.ai/core-abilities/compression_strategy/
- dynamic context docs: https://docs.pr-agent.ai/core-abilities/dynamic_context/
- self-reflection docs: https://docs.pr-agent.ai/core-abilities/self_reflection/
- public configuration file: https://raw.githubusercontent.com/The-PR-Agent/pr-agent/main/pr_agent/settings/configuration.toml
- main repo: https://github.com/The-PR-Agent/pr-agent

Checklist-related references:

- `pr-agent` repo root includes `pr_compliance_checklist.yaml`
- public checklist templates repo: https://github.com/qodo-ai/pr-compliance-templates

Note:

- Some checklist observations above are inferred from the public checklist artifact and template repository rather than from a dedicated architecture doc page.
