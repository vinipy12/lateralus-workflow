# Workflow Strategy Notes

## Why this exists

These notes capture the current thinking around the startup workflow framework:

- how it differs from GSD
- which GSD ideas are worth borrowing
- what is strong and weak in the current planning design
- how to package the workflow as a Codex skill or plugin later

The goal is not to copy GSD wholesale. The goal is to keep the parts that improve control, reliability, and subagent orchestration without inheriting all of GSD's surface area.

## Main differences vs GSD

### Current workflow approach

- Narrower scope: focused on repo-local planning and execution control rather than a full project operating system.
- Stronger typed contracts: planning and execution state are explicit JSON artifacts with strict validation.
- Approval-first: planning must converge into an approved artifact before execution starts.
- Tighter review intent: the execution state machine already assumes hard review and commit gates.
- More controlled: fewer moving parts, smaller artifact surface, less prompt sprawl.

### GSD approach

- Much broader scope: project init, roadmap, phase context, research, planning, execution, UAT, shipping, milestone management.
- Heavy artifact graph: `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, phase directories, summaries, UAT files, and more.
- Multi-agent orchestration as a core primitive: researchers, planners, checkers, executors, verifiers, debuggers.
- Wave-based execution and dependency grouping.
- Stronger built-in post-execution verification and recovery loop.

### Practical difference

The current workflow is closer to a typed Codex-native execution kernel. GSD is closer to a complete AI development operating system.

That is a valid difference. It is not a weakness by default.

## GSD ideas worth borrowing

Do not copy all of GSD. Copy the parts that improve control loops.

### High priority

- Context capture before planning:
  - add a lightweight `CONTEXT.md` equivalent that records locked decisions, anti-goals, canonical refs, and open questions
  - this prevents planners from inventing product decisions
- Persistent project memory:
  - add repo-level artifacts such as `PROJECT.md`, `REQUIREMENTS.md`, and `STATE.md`
  - this turns the workflow from a feature-request runner into a reusable startup framework
- Brownfield/codebase mapping:
  - formalize architecture, entry points, pattern anchors, blast radius, and verification anchors
  - the current `discovery_dossier.json` is already close to this
- UAT and gap closure:
  - after execution, generate a user-facing verification checklist
  - convert failures directly into fix plans
- Dependency-aware execution:
  - let plans or steps declare `depends_on` and possibly `wave`
  - even if execution stays sequential at first, the planning contract should support orchestration later
- Shipping synthesis:
  - generate PR title/body from plan, verification, and summary artifacts instead of ad hoc shipping

### Lower priority

- worktrees/workstreams
- security/schema/UI specialized gates
- broader research agent network

### Things not worth copying right now

- the huge command surface
- multi-runtime compatibility
- lots of extra UI and TUI ceremony
- specialized spike/sketch flows unless they solve a real bottleneck

## Planning phase: what is working

### Strong parts

- Planning is separated cleanly from execution.
- Planning has its own state, trace, and approval artifact.
- The plan schema is strong:
  - requirements
  - assumptions
  - open questions
  - out of scope
  - explicit steps
  - per-step verification commands
  - planned file scope
  - commit message
- Requirement coverage is enforced mechanically.
- Discovery is treated as shared input, not a side note.
- The direct-consumer verification audit is very good:
  - it catches false confidence when a compatibility-sensitive step only runs one broad end-to-end test
- The idea of using discovery, a default planner, an MVP planner, and a skeptic is directionally correct:
  - discovery grounds facts
  - default planner pushes completeness
  - MVP planner pressures the plan toward minimality
  - skeptic pressures the plan toward realism

### What this gets right conceptually

The planning phase is being treated as a convergence system, not as a single prompt that emits a pretty plan. That is the right instinct.

## Planning phase: what is weak or risky

### The role contracts are still too soft

Right now the system implies:

- discovery
- full planner draft
- MVP planner draft
- skeptic audit

But unless each role has a hard output contract, those can collapse into multiple variants of "planner with a different tone."

### The convergence model is weak

The rule that "Planner A owns the final revised draft" is not strong enough.

That creates anchoring risk:

- the default planner becomes the real planner
- the MVP planner becomes advisory only
- the skeptic becomes a comment stream instead of a true blocking critic

### Audit coverage is still narrow

The strongest current audit is around direct consumer tests. That is good, but planning quality needs more than one audit dimension.

### The schema is not yet orchestration-ready

If the end goal is multiple subagents, planning should eventually encode:

- dependencies
- waves
- traceability from decisions to steps
- risk flags
- context budget or scope budget

### Skeptic findings may be too hidden

Keeping skeptic findings out of the user-facing summary reduces noise, but it can also hide the real tradeoffs from the approval point.

## Planning phase: recommended improvements

### Give each planning subagent a hard job

The roles should not compete for the same output.

#### Discovery

- output facts only
- no implementation planning
- no prioritization beyond evidence-backed impact
- produce:
  - requirements
  - anti-goals
  - success criteria
  - entry points
  - blast radius
  - pattern anchors
  - verification anchors
  - open questions

#### Default planner

- produce the complete plan that satisfies all requirements and discovered constraints
- optimize for correctness and coverage

#### MVP planner

- produce the smallest plan that is still honestly shippable
- explicitly state:
  - what is included
  - what is excluded
  - why the exclusions do not invalidate the milestone goal

#### Skeptic

- produce objections only
- classify objections by category:
  - feasibility
  - scope reduction
  - missing verification
  - dependency mistakes
  - file-scope conflicts
  - hidden migration or blast-radius risk

#### Convergence step

- should be separate from all planner roles
- can be orchestrator-owned
- should merge:
  - discovery facts
  - full-plan coverage
  - MVP pressure
  - skeptic objections

Do not let the default planner own the final truth.

### Expand audits

Add mechanical checks for:

- every discovered requirement is covered by at least one step
- every anti-goal is guarded by a constraint or explicitly irrelevant
- every open question is either resolved or surfaced to the approver
- every blast-radius item is either directly verified or explicitly marked out of scope for the step
- every step fits a scope budget
- every step has coherent file ownership

### Extend the plan contract

Likely future additions:

- `depends_on`
- `wave`
- `decision_ids`
- `risk_flags`
- `estimated_context_cost`
- maybe `verification_targets`

### Show real tradeoffs at approval time

The approval summary should expose:

- what the full plan adds
- what the MVP omits
- what the skeptic still believes is risky
- what remains unresolved

### Add planner-behavior tests

Do not rely only on schema tests.

Create fixed discovery dossiers and assert planner behavior such as:

- coverage is complete
- anti-goals are respected
- blast radius is acknowledged
- file scope stays coherent
- skeptical objections are either resolved or surfaced

This will matter more than prompt polish.

## Suggested next milestones for the framework

### Immediate

- finish planning subagent contracts
- formalize convergence output
- add more planning audits
- extend plan schema for orchestration readiness

### Next

- add a discuss/context phase before discovery and planning
- build execution/development phase
- build hard review gate
- build shipping phase

### After that

- add user-facing UAT and gap closure
- add richer project memory artifacts
- add dependency-aware parallel execution

## Stronger planning model

If the goal is an unsupervised planner that behaves like a staff engineer, the planner cannot be a single smart voice.

It needs:

- a discuss phase to resolve product ambiguity
- a discovery phase to map codebase reality
- narrow role-specific audits that constrain the planner
- a convergence step that merges those constraints into one execution-ready plan
- machine audits that reject vague, oversized, or unverifiable plans

The right model is closer to a startup operating loop than a single planning prompt.

### Target pipeline

1. `intake`
2. `discuss`
3. `discovery`
4. `architecture_audit`
5. `planning`
6. `product_scope_audit`
7. `skeptic_audit`
8. `convergence`
9. `approval`
10. `execution`
11. `review`
12. `ship`
13. `uat`

### Why discuss matters

Planning should not be responsible for discovering what the user actually means.

The `discuss` phase should:

- resolve ambiguity that materially affects scope, UX, architecture, or verification
- propose likely interpretations when the user is unsure
- recommend a default slice
- lock decisions and defaults
- capture non-goals and success criteria
- block if the request is too ambiguous to plan safely

### Recommended discuss artifact

Create a durable artifact such as `context.json` or `CONTEXT.md` with:

- goal
- target user or target workflow
- desired behavior
- examples of good and bad outcomes
- locked decisions
- defaults taken
- open questions
- constraints
- success criteria
- non-goals
- unresolved risks

## Role model for the workflow

Do not treat these roles as broad personas.

Treat them as narrow constraint roles with specific inputs, outputs, and veto rights.

### Planning-side roles

#### Product manager / product scope guard

Primary phase:

- `discuss`
- `product_scope_audit`

Job:

- clarify the actual user problem
- define the smallest valuable slice
- kill nice-to-have work before planning grows around it
- force explicit non-goals, deferred work, and success criteria

Can reject when:

- the plan contains scope bloat
- user value is unclear
- the MVP boundary is not explicit
- future-phase work is mixed into the first slice

Outputs:

- goal
- target user/value
- must-have list
- defer list
- non-goals
- success criteria
- defaults taken for unresolved product choices

#### Discovery analyst

Primary phase:

- `discovery`

Job:

- map codebase reality without solutioning
- identify blast radius, entry points, pattern anchors, verification anchors, and open questions

Can reject when:

- codebase context is too thin to plan safely
- the request depends on files or systems that have not been examined

Outputs:

- requirements grounded in the repo
- anti-goals
- success criteria
- entry points
- blast radius
- pattern anchors
- verification anchors
- open questions
- complexity events

#### Staff engineer / architecture guard

Primary phase:

- `architecture_audit`

Job:

- constrain the solution space before planning is finalized
- prevent reinvention of infrastructure or patterns already present in the repo
- force reuse of existing contracts, libraries, and operational patterns where appropriate

Can reject when:

- the plan invents infrastructure that already exists
- the plan violates established contracts or layering
- the plan introduces an abstraction that is too general for the slice
- the plan expands architecture beyond the milestone goal

Outputs:

- approved patterns to reuse
- required dependencies or existing systems to reuse
- forbidden moves
- preserved interfaces and contracts
- architecture risks
- migration or rollout constraints

#### Planner

Primary phase:

- `planning`

Job:

- produce the executable plan under the constraints defined by discuss, discovery, and architecture audit
- optimize for coverage, coherence, implementation order, and handoff quality

Cannot do:

- invent new product scope
- ignore preserved interfaces
- wave away unresolved ambiguity

Outputs:

- stepwise plan
- requirement coverage
- file ownership
- verification commands
- commit-ready slices

#### MVP planner

Primary phase:

- `planning`

Job:

- pressure the plan toward the smallest honest milestone

Can reject when:

- a step is larger than needed
- the plan introduces future-phase abstractions
- the implementation path is overbuilt for the goal

Outputs:

- included scope
- excluded scope
- reduced-scope alternative
- justification for why the reduced slice is still shippable

#### Skeptic

Primary phase:

- `skeptic_audit`

Job:

- attack weak assumptions, hidden risks, contradictions, and unverifiable claims

Can reject when:

- a requirement is not truly covered
- verification is too vague
- blast radius is under-modeled
- the plan depends on unproven assumptions

Outputs:

- objections only
- issue categories
- unresolved risks
- suggested corrective pressure

#### Convergence orchestrator

Primary phase:

- `convergence`

Job:

- merge the outputs of discuss, discovery, architecture audit, full planning, MVP pressure, and skeptic objections
- produce the final approval candidate

Hard rule:

- this role may reconcile and tighten the plan
- this role should not invent new scope or bypass rejections from higher-priority guard roles

Outputs:

- final approval candidate
- tradeoff summary
- unresolved risks
- explicit explanation of what was included, excluded, and deferred

### Later-phase role

#### Tech lead / production readiness reviewer

Primary phase:

- `review`

Job:

- protect operational quality after implementation
- focus on things that break in production rather than product value or architecture taste

Can reject when:

- tests are missing for important edges
- rollback or migration risk is unclear
- concurrency, timeout, caching, observability, or error-handling gaps are present
- the code violates required contracts or review policy

Outputs:

- findings
- missing verification
- operational risks
- approval or changes requested

## Role priority and veto rules

To avoid role overlap, give each role a narrow domain veto.

Priority order:

1. `product_scope_guard`
2. `architecture_guard`
3. `skeptic`
4. `planner`
5. `convergence`

Interpretation:

- product scope guard decides whether the work belongs in the milestone
- architecture guard decides whether the solution is acceptable for this repo
- skeptic decides whether the plan is actually coherent and defensible
- planner proposes
- convergence merges but does not overrule hard vetoes

The review-phase `production_readiness_reviewer` operates later and should not reopen product scope unless the implementation clearly diverged from the approved plan.

## Planner quality bars from Karpathy-style guidance

These should become hard planning rules and audits, not just style advice.

### Think before coding

Planning must:

- gather enough context before proposing implementation
- distinguish facts from assumptions
- freeze clarified decisions before drafting
- block when ambiguity would materially change the plan

### Simplicity first

Planning must:

- prefer the smallest sufficient design
- reject speculative frameworks or generic abstractions
- explicitly defer nice-to-haves
- keep each step within a scope budget

### Surgical changes

Planning must:

- justify every touched file
- preserve stable contracts unless the requirement demands change
- avoid unrelated cleanup in milestone work
- make file ownership obvious for implementers

### Goal-driven execution

Planning must:

- define concrete `done_when` outcomes
- pair each claim with verification
- translate requirements into implementation slices with measurable outcomes
- make it easy for coding subagents to execute without inventing behavior

## GSD-inspired additions worth copying into the planner

These are the parts of GSD that improve planning quality without forcing you to copy the entire system.

### High value now

- a real `discuss` phase before planning
- durable context artifacts
- persistent project memory such as `PROJECT.md`, `REQUIREMENTS.md`, and `STATE.md`
- richer codebase mapping and blast-radius capture
- dependency-aware planning through `depends_on` and `wave`
- UAT and gap-closure planning after implementation
- shipping synthesis based on plan plus verification artifacts

### Nice to have later

- workstreams or worktrees for parallel execution
- specialized gates for schema, security, or UI-heavy changes
- broader research and verifier agent networks

## Recommended planning artifacts

To support all of the above, the planner phase should eventually write more than a single plan file.

Recommended artifact set:

- `context.json` or `CONTEXT.md`
- `discovery_dossier.json`
- `architecture_constraints.json`
- `scope_contract.json`
- `planning_trace.json`
- `approved-plan.json`
- later: `uat.md` or `uat.json`

### What each artifact is for

- `context`: clarified intent, defaults, and product boundaries
- `discovery_dossier`: codebase facts and blast radius
- `architecture_constraints`: required reuse, forbidden moves, preserved interfaces
- `scope_contract`: must-have, defer, non-goals, success criteria
- `planning_trace`: planner history, objections, revisions, and decisions
- `approved-plan`: the final execution-ready implementation contract

## Planner contract improvements

The current plan schema is already good, but a stronger subagent handoff contract should add fields such as:

- `depends_on`
- `wave`
- `decision_ids`
- `risk_flags`
- `blast_radius`
- `verification_targets`
- `avoid_touching`
- `interfaces_to_preserve`
- `files_read_first`
- `rollback_notes`
- `operational_watchpoints`
- `agents_update_required`

## Machine audits to add

For an unsupervised planner, audits matter more than prompt polish.

Add mechanical checks for:

- every discovered requirement is covered by at least one step
- every non-goal is either protected by a constraint or explicitly deferred
- every open question is either resolved, defaulted, or surfaced
- every touched file is justified by scope or blast radius
- every step stays within a size budget
- every compatibility claim has direct consumer verification
- every `done_when` statement maps to at least one verification target
- every preserved interface is acknowledged by the relevant steps
- every deferred item is absent from the approved plan
- every risk flag is owned by a step or surfaced to approval

## What coding subagents should receive

The planner is only strong if implementation becomes easy to follow.

Each execution step should be renderable into a worker brief with:

- step goal
- files to read first
- allowed files to change
- files to avoid
- preserved interfaces
- constraints and forbidden moves
- done-when conditions
- verification commands
- known risks
- exact commit message

That is the handoff quality bar to aim for.

## Baseline comparison workflow

The current approved plan can act as a `v0` baseline so later planner changes can be compared against a fixed output.

Committed baseline artifacts:

- `.codex/workflow/approved-plan-v0.json`
- `.codex/workflow/discovery-dossier-v0.json`

Comparison command:

```bash
python3 .codex/workflow/scripts/planning_state.py compare-plan
```

By default this compares:

- baseline: `.codex/workflow/approved-plan-v0.json`
- candidate: `.codex/workflow/approved-plan.json`
- discovery context: `.codex/workflow/discovery-dossier-v0.json`

What the comparison checks:

- direct consumer verification coverage
- verification target breadth
- completion detail per step
- step size discipline
- largest step blast radius
- oversized step count
- constraint completeness
- step justification coverage

The goal is not just to diff JSON.

The goal is to answer:

- is the new plan safer
- is the new plan smaller or more disciplined
- is the new plan easier for coding subagents to execute

Typical loop:

1. change the planner roles, prompts, audits, or schema
2. generate a new `.codex/workflow/approved-plan.json`
3. run `compare-plan`
4. inspect regressions and warnings
5. keep the new planner only if the plan is stronger or the tradeoffs are intentional

## Packaging this for Codex

## Important distinction

Codex skills and Codex plugins are related but different:

- skills are the authoring format for reusable workflows
- plugins are the installable distribution unit for reusable skills and integrations

If the workflow is only for this repo or for your personal usage, start with a skill.

If you want others to install it cleanly, package it as a plugin that bundles one or more skills.

## How to turn it into a skill

### What a skill is

A skill is a directory with:

- `SKILL.md` required
- optional `scripts/`
- optional `references/`
- optional `assets/`
- optional `agents/openai.yaml`

The trigger logic is based on the metadata in `SKILL.md`, especially:

- `name`
- `description`

### Where skills live

Codex docs describe these locations:

- repo-scoped:
  - `$CWD/.agents/skills`
  - `$REPO_ROOT/.agents/skills`
- user-scoped:
  - `$HOME/.agents/skills`
- admin-scoped:
  - `/etc/codex/skills`

### Minimal skill shape

Example:

```md
---
name: workflow
description: Use when the user wants to start, revise, approve, inspect, or continue the custom repo workflow and needs Codex to follow the repository's planning and execution process.
---

Read `.codex/workflow/...` artifacts first.

If the user is starting planning:
- create or update the planning artifacts
- do not implement code

If the user is approving:
- ingest the approved plan into execution state

...
```

### How users invoke a skill

Codex docs say skills can be activated:

- explicitly:
  - run `/skills`
  - or type `$` to mention a skill directly
- implicitly:
  - Codex may choose the skill if the task matches the `description`

For your workflow, the Codex-native explicit form is not `/workflow`.
It is more like:

- `$workflow`
- `$workflow-planning`
- `$workflow-ship`

depending on how you split the skills.

### Recommended skill shape for this project

Do not make one giant skill if you want control.

Prefer a small set such as:

- `workflow-router`
- `workflow-planning`
- `workflow-execution`
- `workflow-review`
- `workflow-ship`

The router can decide which artifact or phase to activate.

## Why `/workflow` currently does nothing

Per current Codex CLI docs, slash commands are built-in CLI controls like:

- `/model`
- `/permissions`
- `/agent`
- `/status`
- `/plugins`

They are not the same thing as skills.

So a custom `/workflow` is not a normal skill entry point.

If you want a true Codex-native reusable entry point, use a skill and invoke it with `$workflow` or from `/skills`.

In this repo specifically, `/workflow` is implemented as a hook-driven convention, not a built-in Codex slash command:

- `.codex/hooks.json` routes `UserPromptSubmit` into `python3 .codex/workflow/scripts/user_prompt_hook.py`
- `user_prompt_hook.py` then checks whether the prompt starts with `/workflow`

So if `/workflow` feels inert, the likely problem is hook loading or session configuration, not missing workflow logic.

## If you really want `/workflow`

That is a separate pattern.

You would keep using a hook-based dispatcher that interprets a literal prompt beginning with `/workflow` and rewrites or enriches the session context.

That is not the same as registering a custom slash command in Codex CLI.

In other words:

- `$workflow` = Codex skill model
- `/workflow ...` = your own hook-driven command convention

You can support both, but they are different mechanisms.

## How to package it as a plugin for others

### Minimal plugin shape

Codex docs describe a plugin folder with:

- `.codex-plugin/plugin.json` required
- `skills/` optional
- `.app.json` optional
- `.mcp.json` optional
- `assets/` optional

Minimal example:

```json
{
  "name": "startup-workflow",
  "version": "1.0.0",
  "description": "Structured planning, review, and shipping workflow for Codex.",
  "skills": "./skills/"
}
```

### Plugin folder example

```text
startup-workflow/
  .codex-plugin/
    plugin.json
  skills/
    workflow-router/
      SKILL.md
    workflow-planning/
      SKILL.md
    workflow-review/
      SKILL.md
    workflow-ship/
      SKILL.md
```

### Marketplace wiring

To make a local plugin appear in Codex:

- repo marketplace:
  - `$REPO_ROOT/.agents/plugins/marketplace.json`
- personal marketplace:
  - `~/.agents/plugins/marketplace.json`

Each plugin entry points to the plugin directory with a `./`-relative path.

Example marketplace entry:

```json
{
  "name": "local-example-plugins",
  "interface": {
    "displayName": "Local Example Plugins"
  },
  "plugins": [
    {
      "name": "startup-workflow",
      "source": {
        "source": "local",
        "path": "./plugins/startup-workflow"
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

Then restart Codex and open `/plugins`.

### How users use the plugin

After install:

- they can describe the task directly and let Codex choose the bundled skills
- or explicitly invoke the bundled skills by name, the same way normal skills are invoked

For example:

- `$workflow-router`
- `$workflow-planning`

Skills bundled in the plugin become available immediately after installation.

### Public distribution status

Official docs currently say official public plugin publishing is coming soon.

So the practical path right now is:

- build the plugin
- publish the source repository
- provide a marketplace file or marketplace repo that points to it
- have users install through that marketplace or a local/personal marketplace entry

## Recommended rollout path

### Phase 1

Create repo-local skills first:

- easiest to iterate
- no plugin packaging friction
- lets you tune triggers and instructions

### Phase 2

Bundle the stable skills into one plugin:

- `.codex-plugin/plugin.json`
- `skills/`
- optional helper scripts and references

### Phase 3

Add marketplace metadata for easy installation in Codex.

## Practical recommendation for this workflow

If the main goal is for other people to use the workflow in Codex:

1. define the workflow as one or more skills first
2. make the skill entry point Codex-native:
   - `$workflow`
   - `$workflow-planning`
   - etc.
3. keep `/workflow ...` only as a compatibility layer if you want your current hook-based UX
4. once stable, wrap the skills into a plugin

That gives you:

- cleaner authoring
- clearer explicit invocation
- easier installation for other developers
- the option to add MCP/app integrations later without changing the workflow abstraction

## Current implementation note

The current repo-local implementation now uses:

- `$workflow` as the intended Codex-native skill entrypoint
- `.agents/skills/workflow/SKILL.md` as the top-level workflow skill
- `.codex/workflow/scripts/workflow_router.py` as the deterministic backend router
- `/workflow ...` only as a compatibility shim through `user_prompt_hook.py`

That means the engine still lives in `.codex/workflow/scripts/...`, but the intended UX has shifted from hook-first to skill-first.

## Useful references

- OpenAI Codex skills docs:
  - https://developers.openai.com/codex/skills
- OpenAI Codex plugins overview:
  - https://developers.openai.com/codex/plugins
- OpenAI Codex plugin build guide:
  - https://developers.openai.com/codex/plugins/build
- OpenAI Codex CLI slash commands:
  - https://developers.openai.com/codex/cli/slash-commands
