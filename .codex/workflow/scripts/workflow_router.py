#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow_router_lib import (
    DEFAULT_PLAN_SOURCE,
    WorkflowRouteResponse,
    activate_execution,
    approve_current_plan,
    cancel_workflow,
    resume_workflow,
    revise_planning,
    start_planning,
    status_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Route the repo-local workflow through a skill-friendly CLI.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print structured JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("planning-start", help="Start a new planning session.")
    start_parser.add_argument("feature_request")
    start_parser.add_argument("--planning-state-path", type=Path, default=None)
    start_parser.add_argument("--execution-state-path", type=Path, default=None)

    bootstrap_parser = subparsers.add_parser("bootstrap-start", help="Start a new greenfield bootstrap planning session.")
    bootstrap_parser.add_argument("feature_request")
    bootstrap_parser.add_argument("--planning-state-path", type=Path, default=None)
    bootstrap_parser.add_argument("--execution-state-path", type=Path, default=None)

    revise_parser = subparsers.add_parser("planning-revise", help="Revise the active planning session.")
    revise_parser.add_argument("feedback")
    revise_parser.add_argument("--planning-state-path", type=Path, default=None)

    approve_parser = subparsers.add_parser("planning-approve", help="Approve the active planning session.")
    approve_parser.add_argument("--planning-state-path", type=Path, default=None)
    approve_parser.add_argument("--execution-state-path", type=Path, default=None)

    execution_parser = subparsers.add_parser("execution-start", help="Activate execution from an approved plan.")
    execution_parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_PLAN_SOURCE)
    execution_parser.add_argument("--plan-id")
    execution_parser.add_argument("--mode", default="ship")
    execution_parser.add_argument("--base-branch")
    execution_parser.add_argument("--review-path")
    execution_parser.add_argument("--ship-skill")
    execution_parser.add_argument("--request-codex-review", action="store_true", default=True)
    execution_parser.add_argument("--no-request-codex-review", action="store_false", dest="request_codex_review")
    execution_parser.add_argument("--execution-state-path", type=Path, default=None)

    resume_parser = subparsers.add_parser("resume", help="Resume the active planning or execution workflow.")
    resume_parser.add_argument("--planning-state-path", type=Path, default=None)
    resume_parser.add_argument("--execution-state-path", type=Path, default=None)

    status_parser = subparsers.add_parser("status", help="Show workflow planning or execution status.")
    status_parser.add_argument("--planning-state-path", type=Path, default=None)
    status_parser.add_argument("--execution-state-path", type=Path, default=None)

    cancel_parser = subparsers.add_parser("cancel", help="Cancel the active workflow state.")
    cancel_parser.add_argument("--planning-state-path", type=Path, default=None)
    cancel_parser.add_argument("--execution-state-path", type=Path, default=None)

    args = parser.parse_args()

    planning_state_path = getattr(args, "planning_state_path", None)
    execution_state_path = getattr(args, "execution_state_path", None)

    if args.command == "planning-start":
        response = start_planning(
            args.feature_request,
            planning_mode="brownfield",
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    elif args.command == "bootstrap-start":
        response = start_planning(
            args.feature_request,
            planning_mode="greenfield",
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    elif args.command == "planning-revise":
        response = revise_planning(
            args.feedback,
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
        )
    elif args.command == "planning-approve":
        response = approve_current_plan(
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    elif args.command == "execution-start":
        response = activate_execution(
            args.source,
            plan_id=args.plan_id,
            mode=args.mode,
            base_branch=args.base_branch or "origin/main",
            review_path=args.review_path or ".codex/workflow/code_review.md",
            ship_skill=args.ship_skill or "ship",
            request_codex_review=args.request_codex_review,
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    elif args.command == "resume":
        response = resume_workflow(
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    elif args.command == "status":
        response = status_summary(
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    elif args.command == "cancel":
        response = cancel_workflow(
            planning_state_path=planning_state_path or Path(".codex/workflow/planning_state.json"),
            execution_state_path=execution_state_path or Path(".codex/workflow/state.json"),
        )
    else:
        parser.error(f"unsupported command: {args.command}")
        return 2

    _emit_response(response, json_output=args.json_output)
    return 0


def _emit_response(response: WorkflowRouteResponse, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(response.as_dict(), indent=2))
        return

    print(response.message)
    if response.additional_context:
        print()
        print(response.additional_context)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"workflow_router.py error: {exc}", file=sys.stderr)
        raise
