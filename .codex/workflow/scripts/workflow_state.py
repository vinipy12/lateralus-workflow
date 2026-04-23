#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from metrics_lib import append_metrics_event, load_metrics_events
from workflow_lib import (
    DEFAULT_STATE_PATH,
    VALID_STEP_STATUSES,
    VALID_WORKFLOW_STATUSES,
    clear_execution_escalation,
    current_step,
    enter_execution_escalation,
    evaluate_pre_review_sensors,
    find_execution_blocker,
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

    resolve_parser = subparsers.add_parser(
        "resolve-escalation",
        help="Clear the active execution escalation after the blocker is fixed.",
    )
    resolve_parser.add_argument("--path", type=Path, default=DEFAULT_STATE_PATH)

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
        if state["workflow_status"] == "execution_escalated":
            raise SystemExit(
                "set-step-status is blocked while workflow_status is execution_escalated; "
                "fix the blocker and run `resolve-escalation` first"
            )
        previous_status = state["workflow_status"]
        step = _find_step(state, args.step_id)
        if args.status == "review_pending":
            sensor_result = evaluate_pre_review_sensors(state, step=step)
            if not sensor_result["ok"]:
                blocker = dict(sensor_result["failures"][0])
                blocker["details"] = sensor_result["failures"]
                state, _ = enter_execution_escalation(state, blocker)
                save_state(state, args.path)
                _emit_deterministic_sensor_failure(state, step, sensor_result["failures"])
                _emit_execution_escalation_entered(state, previous_status=previous_status)
                raise SystemExit(_render_sensor_failure_message(sensor_result["failures"]))
        _validate_step_status_change(state, step, new_status=args.status)
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
        override_reason = _normalize_override_reason(args.override_reason)
        step = current_step(state)
        previous_status = state["workflow_status"]
        _validate_workflow_status_change(state, step, new_status=args.status, override_reason=override_reason)
        if args.status == "execution_escalated":
            state, _ = enter_execution_escalation(
                state,
                {
                    "code": "manual_override",
                    "summary": override_reason or "manual escalation requested",
                    "blocking_step_id": step["id"],
                    "details": {"command": "set-workflow-status", "target_status": args.status},
                },
            )
        else:
            if previous_status == "execution_escalated":
                state, cleared_escalation, _ = clear_execution_escalation(state, next_status=args.status)
                _emit_execution_escalation_cleared(
                    state,
                    previous_escalation=cleared_escalation,
                    resolved_to_status=args.status,
                )
            else:
                state["workflow_status"] = args.status
                state["escalation"] = None
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
        if previous_status != "execution_escalated" and state["workflow_status"] == "execution_escalated":
            _emit_execution_escalation_entered(state, previous_status=previous_status)
        _emit_override_if_needed(
            state,
            command="set-workflow-status",
            reason=override_reason,
            target=args.status,
        )
        print(f"workflow_status -> {args.status}")
        return 0

    if args.command == "resolve-escalation":
        state = _require_state(args.path)
        if state["workflow_status"] != "execution_escalated" or state.get("escalation") is None:
            raise SystemExit("resolve-escalation requires workflow_status execution_escalated")
        blocker = find_execution_blocker(state, include_active_escalation=False)
        if blocker is not None:
            raise SystemExit(
                f"resolve-escalation blocked: {blocker['summary']}"
            )
        state, previous_escalation, _ = clear_execution_escalation(state, next_status="active")
        save_state(state, args.path)
        _emit_execution_escalation_cleared(
            state,
            previous_escalation=previous_escalation,
            resolved_to_status="active",
        )
        print("execution escalation cleared")
        return 0

    if args.command == "set-uat-status":
        state = _require_state(args.path)
        status = args.status.replace("-", "_")
        repeated_uat_gap = False
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
            repeated_uat_gap = _is_repeated_uat_gap_loop(state, step_id=step["id"])
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
        if status == "failed_gap" and repeated_uat_gap:
            append_metrics_event(
                state["metrics_dir"],
                "uat_gap_repeated",
                details={
                    "workflow_name": state["workflow_name"],
                    "current_step_id": step["id"],
                    "category": "failed_gap",
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


def _validate_step_status_change(state: dict, step: dict, *, new_status: str) -> None:
    if new_status in {"fix_pending", "commit_pending"} and step["status"] != "review_pending":
        raise SystemExit(
            f"set-step-status {new_status} requires the current step to be review_pending, got {step['status']}"
        )
    if new_status == "committed" and step["status"] != "commit_pending":
        raise SystemExit(
            f"set-step-status committed requires the current step to be commit_pending, got {step['status']}"
        )
    if new_status != "shipped":
        return
    if step["id"] != state["current_step_id"]:
        raise SystemExit(
            f"set-step-status shipped requires the current step, got `{step['id']}` while current_step_id is "
            f"`{state['current_step_id']}`"
        )
    if state["workflow_status"] != "ship_pending":
        raise SystemExit(
            f"set-step-status shipped requires workflow_status ship_pending, got {state['workflow_status']}"
        )
    if step["status"] != "committed":
        raise SystemExit(
            f"set-step-status shipped requires the current step to be committed, got {step['status']}"
        )


def _validate_workflow_status_change(
    state: dict,
    step: dict,
    *,
    new_status: str,
    override_reason: str | None,
) -> None:
    if new_status == "execution_escalated":
        if override_reason is None:
            raise SystemExit(
                "set-workflow-status execution_escalated is a manual override; rerun with --override-reason \"<why>\""
            )
        return
    if new_status == "complete":
        if state["workflow_status"] != "ship_pending":
            raise SystemExit(
                f"set-workflow-status complete requires workflow_status ship_pending, got {state['workflow_status']}"
            )
        if step["status"] != "shipped":
            raise SystemExit(
                f"set-workflow-status complete requires the current step to be shipped, got {step['status']}"
            )
        return

    if override_reason is None:
        raise SystemExit(
            f"set-workflow-status {new_status} is a manual override; rerun with --override-reason \"<why>\""
        )


def _normalize_override_reason(reason: str | None) -> str | None:
    if not isinstance(reason, str):
        return None
    normalized = reason.strip()
    return normalized or None


def _emit_step_metrics(state: dict, step: dict, *, status: str, review_summary: str | None) -> None:
    details = {
        "workflow_name": state["workflow_name"],
        "step_id": step["id"],
        "step_title": step["title"],
        "review_summary": review_summary or step.get("review_summary"),
    }
    if status == "fix_pending":
        repeated_review_failure = _is_repeated_review_failure(state, step_id=step["id"])
        append_metrics_event(state["metrics_dir"], "review_failed", details=details)
        if repeated_review_failure:
            append_metrics_event(
                state["metrics_dir"],
                "review_failed_repeated",
                details={
                    "workflow_name": state["workflow_name"],
                    "step_id": step["id"],
                    "category": "review_failed",
                },
            )
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


def _emit_deterministic_sensor_failure(state: dict, step: dict, failures: list[dict]) -> None:
    primary = failures[0]
    append_metrics_event(
        state["metrics_dir"],
        "deterministic_sensor_failed",
        details={
            "workflow_name": state["workflow_name"],
            "step_id": step["id"],
            "step_title": step["title"],
            "category": primary["code"],
            "summary": primary["summary"],
            "failure_count": len(failures),
        },
    )


def _emit_execution_escalation_entered(state: dict, *, previous_status: str) -> None:
    escalation = state.get("escalation")
    if not isinstance(escalation, dict):
        return
    append_metrics_event(
        state["metrics_dir"],
        "execution_escalation_entered",
        details={
            "workflow_name": state["workflow_name"],
            "current_step_id": state["current_step_id"],
            "previous_status": previous_status,
            "workflow_status": state["workflow_status"],
            "category": escalation["code"],
            "summary": escalation["summary"],
            "occurrence_count": escalation["occurrence_count"],
        },
    )


def _emit_execution_escalation_cleared(
    state: dict,
    *,
    previous_escalation: dict | None,
    resolved_to_status: str,
) -> None:
    if not isinstance(previous_escalation, dict):
        return
    append_metrics_event(
        state["metrics_dir"],
        "execution_escalation_cleared",
        details={
            "workflow_name": state["workflow_name"],
            "current_step_id": state["current_step_id"],
            "resolved_to_status": resolved_to_status,
            "category": previous_escalation["code"],
            "summary": previous_escalation["summary"],
            "occurrence_count": previous_escalation["occurrence_count"],
        },
    )


def _render_sensor_failure_message(failures: list[dict]) -> str:
    lines = ["set-step-status review_pending blocked by deterministic pre-review sensors:"]
    for failure in failures:
        lines.append(f"- [{failure['code']}] {failure['summary']}")
    return "\n".join(lines)


def _is_repeated_review_failure(state: dict, *, step_id: str) -> bool:
    return _has_prior_unresolved_event(
        state,
        step_id=step_id,
        target_event="review_failed",
        reset_events={"review_passed", "step_committed", "workflow_canceled"},
    )


def _is_repeated_uat_gap_loop(state: dict, *, step_id: str) -> bool:
    return _has_prior_unresolved_event(
        state,
        step_id=step_id,
        target_event="uat_failed_gap",
        reset_events={"uat_passed", "uat_failed_replan", "workflow_canceled", "workflow_shipped"},
    )


def _has_prior_unresolved_event(
    state: dict,
    *,
    step_id: str,
    target_event: str,
    reset_events: set[str],
) -> bool:
    metrics_dir = state.get("metrics_dir")
    if not isinstance(metrics_dir, str) or not metrics_dir.strip():
        return False
    events = load_metrics_events(metrics_dir)
    for event in reversed(events):
        event_name = str(event.get("event") or "").strip()
        if not event_name:
            continue
        event_step_id = event.get("step_id", event.get("current_step_id"))
        same_step = event_step_id == step_id
        if event_name in reset_events and (event_step_id is None or same_step):
            return False
        if event_name == target_event and same_step:
            return True
    return False


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"workflow_state.py error: {exc}", file=sys.stderr)
        raise
