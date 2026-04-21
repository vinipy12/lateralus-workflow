#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from planning_lib import (
    DEFAULT_APPROVED_PLAN_PATH,
    DEFAULT_DISCOVERY_DOSSIER_PATH,
    DEFAULT_PLANNING_STATE_PATH,
    DEFAULT_V0_DISCOVERY_BASELINE_PATH,
    DEFAULT_V0_PLAN_BASELINE_PATH,
    VALID_PLANNING_STATUSES,
    audit_planning_artifacts,
    compare_plan_specs,
    clear_planning_state,
    load_discovery_dossier,
    render_plan_comparison,
    load_planning_state,
    save_planning_state,
    validate_planning_state,
)
from workflow_lib import load_plan_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the repo-local Codex planning state file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="Print the current planning state.")
    show_parser.add_argument("--path", type=Path, default=DEFAULT_PLANNING_STATE_PATH)

    validate_parser = subparsers.add_parser("validate", help="Validate a planning state file.")
    validate_parser.add_argument("--path", type=Path, default=DEFAULT_PLANNING_STATE_PATH)

    audit_parser = subparsers.add_parser(
        "audit-plan",
        help="Audit the approved plan against the discovery dossier before approval.",
    )
    audit_parser.add_argument("--path", type=Path, default=DEFAULT_PLANNING_STATE_PATH)

    compare_parser = subparsers.add_parser(
        "compare-plan",
        help="Compare two approved-plan outputs and report whether the candidate is stronger than the baseline.",
    )
    compare_parser.add_argument("--baseline", type=Path, default=DEFAULT_V0_PLAN_BASELINE_PATH)
    compare_parser.add_argument("--candidate", type=Path, default=DEFAULT_APPROVED_PLAN_PATH)
    compare_parser.add_argument("--baseline-discovery", type=Path, default=DEFAULT_V0_DISCOVERY_BASELINE_PATH)
    compare_parser.add_argument("--candidate-discovery", type=Path, default=DEFAULT_DISCOVERY_DOSSIER_PATH)
    compare_parser.add_argument("--touch-budget", type=int, default=8)
    compare_parser.add_argument("--create-budget", type=int, default=4)
    compare_parser.add_argument("--json", action="store_true", dest="json_output")

    status_parser = subparsers.add_parser("set-status", help="Update the planning status.")
    status_parser.add_argument("status", choices=sorted(VALID_PLANNING_STATUSES))
    status_parser.add_argument("--path", type=Path, default=DEFAULT_PLANNING_STATE_PATH)

    feedback_parser = subparsers.add_parser("set-feedback", help="Record the latest user feedback.")
    feedback_parser.add_argument("feedback")
    feedback_parser.add_argument("--path", type=Path, default=DEFAULT_PLANNING_STATE_PATH)

    clear_parser = subparsers.add_parser("clear", help="Delete the current planning state file.")
    clear_parser.add_argument("--path", type=Path, default=DEFAULT_PLANNING_STATE_PATH)

    args = parser.parse_args()

    if args.command == "show":
        state = _require_state(args.path)
        print(json.dumps(state, indent=2))
        return 0

    if args.command == "validate":
        state = _require_state(args.path)
        validate_planning_state(state)
        print(f"planning state valid: {args.path}")
        return 0

    if args.command == "audit-plan":
        state = _require_state(args.path)
        issues = audit_planning_artifacts(state)
        if issues:
            print("approved plan audit failed:")
            for issue in issues:
                print(f"- {issue}")
            return 1
        print("approved plan audit passed")
        return 0

    if args.command == "compare-plan":
        baseline_plan = load_plan_spec(args.baseline)
        candidate_plan = load_plan_spec(args.candidate)
        baseline_discovery = _load_optional_discovery(args.baseline_discovery)
        candidate_discovery = _load_optional_discovery(args.candidate_discovery)
        comparison = compare_plan_specs(
            baseline_plan,
            candidate_plan,
            baseline_discovery=baseline_discovery,
            candidate_discovery=candidate_discovery or baseline_discovery,
            touch_budget=args.touch_budget,
            create_budget=args.create_budget,
        )
        if args.json_output:
            print(json.dumps(comparison, indent=2))
        else:
            print(
                render_plan_comparison(
                    comparison,
                    baseline_label=str(args.baseline),
                    candidate_label=str(args.candidate),
                )
            )
        return 0

    if args.command == "set-status":
        state = _require_state(args.path)
        state["status"] = args.status
        save_planning_state(state, args.path)
        print(f"planning status -> {args.status}")
        return 0

    if args.command == "set-feedback":
        state = _require_state(args.path)
        state["latest_user_feedback"] = args.feedback
        save_planning_state(state, args.path)
        print("latest_user_feedback updated")
        return 0

    if args.command == "clear":
        removed = clear_planning_state(args.path)
        message = "planning state cleared" if removed else "planning state already absent"
        print(message)
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


def _require_state(path: Path) -> dict:
    state = load_planning_state(path)
    if state is None:
        raise SystemExit(f"planning state not found: {path}")
    return state


def _load_optional_discovery(path: Path | None) -> dict | None:
    if path is None:
        return None
    return load_discovery_dossier(path)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"planning_state.py error: {exc}", file=sys.stderr)
        raise
