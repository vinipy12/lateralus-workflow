---
name: lateralus-workflow
description: Alias for the Lateralus Workflow plugin package name. Use when the user explicitly invokes `$lateralus-workflow`, `$lateralus-workflow:`, or asks to use the Lateralus workflow plugin to plan, resume, revise, approve, inspect, cancel, or activate execution.
---

# Lateralus Workflow Alias

This skill is a compatibility alias for users who invoke the plugin by package name.

Use the same contract as `$workflow`. Run the bundled router first, then follow the router output exactly.

Resolve `scripts/...` relative to this skill directory:

- `python3 scripts/workflow_router.py planning-start "<feature request>"`
- `python3 scripts/workflow_router.py bootstrap-start "<project request>"`
- `python3 scripts/workflow_router.py planning-revise "<feedback>"`
- `python3 scripts/workflow_router.py planning-approve`
- `python3 scripts/workflow_router.py execution-start [plan-file]`
- `python3 scripts/workflow_router.py resume`
- `python3 scripts/workflow_router.py status`
- `python3 scripts/workflow_router.py cancel`

Do not treat `$lateralus-workflow: <prompt>` as a normal implementation request. Strip the alias prefix, pass the remaining prompt to the correct router command, and keep the normal Plan, Development, Review, UAT, and Ship gates.
