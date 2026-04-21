# Code Review Policy

Use this policy for repo-local review gates and PR reviews.

## Primary Goal

Find real issues that the original author would want to fix before shipping.

## Review Scope

- Default to the current execution step's diff, not the whole branch history.
- Focus on behavior, correctness, regressions, and operational risk.
- Treat stale `AGENTS.md` guidance as a real issue when the step changed durable conventions or verification rules.

## Findings

- Present findings first.
- Order findings by severity.
- Include file references whenever practical.
- Do not add style-only commentary unless it hides a correctness problem.

## What Counts

- broken behavior
- missing or incorrect verification
- missing tests where the risk is material
- unsafe migrations or config changes
- invalid assumptions about data shape or API contracts
- concurrency, retry, idempotency, or state-machine bugs
- stale durable agent guidance after the step changed module expectations

## Pass Condition

The step passes only when there are no new material findings.

## Required Checks Before Pass

- relevant verification commands ran, or the blocker is explicitly reported
- review scope stayed inside the current execution step
- relevant `AGENTS.md` files were checked and updated when needed

## Output Style

If there are findings, keep the summary short and lead with the issues.

If there are no findings, say so explicitly and mention any residual testing gaps.
