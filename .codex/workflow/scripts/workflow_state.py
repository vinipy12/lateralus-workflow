#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from metrics_lib import append_metrics_event
from workflow_lib import (
    DEFAULT_STATE_PATH,
    VALID_STEP_STATUSES,
    VALID_WORKFLOW_STATUSES,
    current_step,
    load_state,
    save_state,
    update_uat_artifact_result,
    validate_state,
)


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
    step_parser.add_argument("--override-reason", default=None)
    step_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    current_parser = subparsers.add_parser("set-current-step", help="Point current_step_id at a new step.")
    current_parser.add_argument("step_id")
    current_parser.add_argument("--override-reason", default=None)
    current_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    workflow_parser = subparsers.add_parser("set-workflow-status", help="Update the workflow_status field.")
    workflow_parser.add_argument("status", choices=sorted(VALID_WORKFLOW_STATUSES))
    workflow_parser.add_argument("--override-reason", default=None)
    workflow_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

    uat_parser = subparsers.add_parser("set-uat-status", help="Record the current UAT result.")
    uat_parser.add_argument("status", choices=("passed", "failed-gap", "failed-replan"))
    uat_parser.add_argument("--summary", default=None)
    uat_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

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
        _emit_step_metrics(state, step, status=args.status, review_summary=args.review_summary)
        _emit_override_if_needed(state, command="set-step-status", reason=args.override_reason, target=args.step_id)
        print(f"{args.step_id} -> {args.status}")
        return 0

    if args.command == "set-current-step":
        state = _require_state(args.path)
        _find_step(state, args.step_id)
        state["current_step_id"] = args.step_id
        save_state(state, args.path)
        _emit_override_if_needed(state, command="set-current-step", reason=args.override_reason, target=args.step_id)
        print(f"current_step_id -> {args.step_id}")
        return 0

    if args.command == "set-workflow-status":
        state = _require_state(args.path)
        state["workflow_status"] = args.status
        save_state(state, args.path)
        if args.status == "complete":
            append_metrics_event(
                state["metrics_dir"],
                "workflow_shipped",
                details={
                    "workflow_name": state["workflow_name"],
                    "workflow_status": args.status,
                    "current_step_id": state["current_step_id"],
                },
            )
        _emit_override_if_needed(
            state,
            command="set-workflow-status",
            reason=args.override_reason,
            target=args.status,
        )
        print(f"workflow_status -> {args.status}")
        return 0

    if args.command == "set-uat-status":
        state = _require_state(args.path)
        status = args.status.replace("-", "_")
        if state["workflow_status"] not in {"uat_pending", "gap_closure_pending"}:
            raise SystemExit(
                f"set-uat-status requires workflow_status uat_pending or gap_closure_pending, got {state['workflow_status']}"
            )

        step = current_step(state)
        if step["status"] != "committed":
            raise SystemExit(
                f"set-uat-status requires the current step to be committed, got {step['status']}"
            )

        summary = args.summary.strip() if isinstance(args.summary, str) and args.summary.strip() else None
        if status == "passed":
            state["workflow_status"] = "ship_pending"
            event_name = "uat_passed"
        elif status == "failed_gap":
            state["workflow_status"] = "gap_closure_pending"
            step["status"] = "implementing"
            if summary is not None:
                step["review_summary"] = summary
            event_name = "uat_failed_gap"
        else:
            state["workflow_status"] = "replan_required"
            event_name = "uat_failed_replan"

        update_uat_artifact_result(Path(state["uat_artifact_path"]), status, summary)
        save_state(state, args.path)
        append_metrics_event(
            state["metrics_dir"],
            event_name,
            details={
                "workflow_name": state["workflow_name"],
                "summary": summary,
                "current_step_id": step["id"],
                "workflow_status": state["workflow_status"],
            },
        )
        print(f"uat_status -> {args.status}")
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


def _emit_step_metrics(state: dict, step: dict, *, status: str, review_summary: str | None) -> None:
    details = {
        "workflow_name": state["workflow_name"],
        "step_id": step["id"],
        "step_title": step["title"],
        "review_summary": review_summary or step.get("review_summary"),
    }
    if status == "fix_pending":
        append_metrics_event(state["metrics_dir"], "review_failed", details=details)
    elif status == "commit_pending":
        append_metrics_event(state["metrics_dir"], "review_passed", details=details)
    elif status == "committed":
        append_metrics_event(state["metrics_dir"], "step_committed", details=details)


def _emit_override_if_needed(state: dict, *, command: str, reason: str | None, target: str) -> None:
    if not isinstance(reason, str) or not reason.strip():
        return
    append_metrics_event(
        state["metrics_dir"],
        "override_used",
        details={
            "workflow_name": state["workflow_name"],
            "command": command,
            "target": target,
            "reason": reason.strip(),
        },
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"workflow_state.py error: {exc}", file=sys.stderr)
        raise
