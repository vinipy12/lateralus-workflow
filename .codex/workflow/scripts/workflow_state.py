#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from workflow_lib import DEFAULT_STATE_PATH, VALID_STEP_STATUSES, VALID_WORKFLOW_STATUSES, load_state, save_state, validate_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the repo-local Codex workflow state file.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="Print the current workflow state.")
    show_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    validate_parser = subparsers.add_parser("validate", help="Validate a workflow state file.")
    validate_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    init_parser = subparsers.add_parser("init", help="Initialize state.json from a prepared JSON file.")
    init_parser.add_argument("source", type=Path)
    init_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    step_parser = subparsers.add_parser("set-step-status", help="Update the status for a single step.")
    step_parser.add_argument("step_id")
    step_parser.add_argument("status", choices=sorted(VALID_STEP_STATUSES))
    step_parser.add_argument("--review-summary", default=None)
    step_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    current_parser = subparsers.add_parser("set-current-step", help="Point current_step_id at a new step.")
    current_parser.add_argument("step_id")
    current_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    workflow_parser = subparsers.add_parser("set-workflow-status", help="Update the workflow_status field.")
    workflow_parser.add_argument("status", choices=sorted(VALID_WORKFLOW_STATUSES))
    workflow_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    args = parser.parse_args()

    if args.command == "show":
        state = _require_state(args.path)
        print(json.dumps(state, indent=2))
        return 0

    if args.command == "validate":
        state = _require_state(args.path)
        validate_state(state)
        print(f"workflow state valid: {args.path}")
        return 0

    if args.command == "init":
        state = json.loads(args.source.read_text(encoding="utf-8"))
        save_state(state, args.path)
        print(f"workflow state initialized at {args.path}")
        return 0

    if args.command == "set-step-status":
        state = _require_state(args.path)
        step = _find_step(state, args.step_id)
        step["status"] = args.status
        if args.review_summary is not None:
            step["review_summary"] = args.review_summary
        save_state(state, args.path)
        print(f"{args.step_id} -> {args.status}")
        return 0

    if args.command == "set-current-step":
        state = _require_state(args.path)
        _find_step(state, args.step_id)
        state["current_step_id"] = args.step_id
        save_state(state, args.path)
        print(f"current_step_id -> {args.step_id}")
        return 0

    if args.command == "set-workflow-status":
        state = _require_state(args.path)
        state["workflow_status"] = args.status
        save_state(state, args.path)
        print(f"workflow_status -> {args.status}")
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


def _require_state(path: Path) -> dict:
    state = load_state(path)
    if state is None:
        raise SystemExit(f"workflow state not found: {path}")
    return state


def _find_step(state: dict, step_id: str) -> dict:
    for step in state["steps"]:
        if step["id"] == step_id:
            return step
    raise SystemExit(f"step not found: {step_id}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"workflow_state.py error: {exc}", file=sys.stderr)
        raise
