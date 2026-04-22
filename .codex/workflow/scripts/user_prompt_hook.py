#!/usr/bin/env python3
from __future__ import annotations

import json
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from planning_lib import DEFAULT_PLANNING_STATE_PATH
from workflow_router_lib import (
    activate_execution,
    approve_current_plan,
    cancel_workflow,
    revise_planning,
    start_planning,
    status_summary,
)
from workflow_lib import (
    DEFAULT_BASE_BRANCH,
    DEFAULT_REVIEW_PATH,
    DEFAULT_SHIP_SKILL,
    DEFAULT_STATE_PATH,
)


DEFAULT_PLAN_SOURCE = Path(".codex/workflow/approved-plan.json")


@dataclass(frozen=True)
class ActivationRequest:
    source: Path
    plan_id: str | None
    mode: str
    base_branch: str
    review_path: str
    ship_skill: str
    request_codex_review: bool


@dataclass(frozen=True)
class WorkflowRequest:
    action: str
    source: Path | None = None
    plan_id: str | None = None
    mode: str | None = None
    base_branch: str | None = None
    review_path: str | None = None
    ship_skill: str | None = None
    request_codex_review: bool | None = None
    feature_request: str | None = None
    feedback: str | None = None


def main() -> int:
    payload = json.load(sys.stdin)
    request = parse_workflow_request(payload.get("prompt", ""))
    if request is None:
        return 0

    if request.action == "activate_execution":
        return _handle_execution_activation(request)
    if request.action == "start_planning":
        return _handle_start_planning(request)
    if request.action == "start_bootstrap":
        return _handle_start_bootstrap(request)
    if request.action == "revise_planning":
        return _handle_revise_planning(request)
    if request.action == "approve_planning":
        return _handle_approve_planning()
    if request.action == "status":
        return _handle_status()
    if request.action == "cancel":
        return _handle_cancel()
    if request.action == "usage_error":
        return _print_response(
            "workflow command missing subcommand or feature request",
            (
                "Treat the user's prompt as a legacy workflow usage error. Explain that `$workflow` is now the "
                "canonical path, and that `/workflow` remains a compatibility shim. Supported legacy commands:\n"
                "- `/workflow <feature request>` to start planning\n"
                "- `/workflow bootstrap <project request>` to start greenfield bootstrap planning\n"
                "- `/workflow revise <feedback>` to revise the active plan\n"
                "- `/workflow approve` to transition from plan to execution\n"
                "- `/workflow status` to report the active workflow state\n"
                "- `/workflow cancel` to clear the active workflow state\n"
                "- `/workflow start <plan-file>` to activate an already-approved plan directly"
            ),
        )
    raise ValueError(f"unsupported workflow action: {request.action}")


def parse_workflow_request(prompt: str) -> WorkflowRequest | None:
    stripped = (prompt or "").strip()
    if not stripped.startswith("/workflow"):
        return None

    command_body = stripped[len("/workflow") :].strip()
    if not command_body:
        return WorkflowRequest(action="usage_error")

    parts = shlex.split(stripped)
    if len(parts) >= 2 and parts[1] in {"start", "activate"}:
        activation = _parse_activation_command(parts)
        return WorkflowRequest(
            action="activate_execution",
            source=activation.source,
            plan_id=activation.plan_id,
            mode=activation.mode,
            base_branch=activation.base_branch,
            review_path=activation.review_path,
            ship_skill=activation.ship_skill,
            request_codex_review=activation.request_codex_review,
        )
    if parts[1] == "approve":
        return WorkflowRequest(action="approve_planning")
    if parts[1] == "status":
        return WorkflowRequest(action="status")
    if parts[1] == "cancel":
        return WorkflowRequest(action="cancel")
    if parts[1] == "bootstrap":
        feature_request = command_body[len("bootstrap") :].strip() or None
        return WorkflowRequest(action="start_bootstrap", feature_request=feature_request)
    if parts[1] == "revise":
        feedback = command_body[len("revise") :].strip() or None
        return WorkflowRequest(action="revise_planning", feedback=feedback)
    return WorkflowRequest(action="start_planning", feature_request=command_body)


def parse_activation_request(prompt: str) -> ActivationRequest | None:
    request = parse_workflow_request(prompt)
    if request is None or request.action != "activate_execution":
        return None
    return ActivationRequest(
        source=request.source or DEFAULT_PLAN_SOURCE,
        plan_id=request.plan_id,
        mode=request.mode or "ship",
        base_branch=request.base_branch or DEFAULT_BASE_BRANCH,
        review_path=request.review_path or DEFAULT_REVIEW_PATH,
        ship_skill=request.ship_skill or DEFAULT_SHIP_SKILL,
        request_codex_review=True if request.request_codex_review is None else request.request_codex_review,
    )


def _parse_activation_command(parts: list[str]) -> ActivationRequest:
    if len(parts) < 2:
        raise ValueError("workflow activation command missing action")

    source = DEFAULT_PLAN_SOURCE
    index = 2
    if index < len(parts) and not parts[index].startswith("--"):
        source = Path(parts[index])
        index += 1

    plan_id: str | None = None
    mode = "ship"
    base_branch = DEFAULT_BASE_BRANCH
    review_path = DEFAULT_REVIEW_PATH
    ship_skill = DEFAULT_SHIP_SKILL
    request_codex_review = True

    while index < len(parts):
        token = parts[index]
        if token == "--plan-id":
            index += 1
            plan_id = _require_value(parts, index, "--plan-id")
        elif token == "--mode":
            index += 1
            mode = _require_value(parts, index, "--mode")
        elif token == "--base-branch":
            index += 1
            base_branch = _require_value(parts, index, "--base-branch")
        elif token == "--review-path":
            index += 1
            review_path = _require_value(parts, index, "--review-path")
        elif token == "--ship-skill":
            index += 1
            ship_skill = _require_value(parts, index, "--ship-skill")
        elif token == "--request-codex-review":
            request_codex_review = True
        elif token == "--no-request-codex-review":
            request_codex_review = False
        else:
            raise ValueError(f"unsupported workflow activation flag: {token}")
        index += 1

    if mode not in {"stepwise", "ship"}:
        raise ValueError(f"unsupported workflow mode: {mode}")

    return ActivationRequest(
        source=source,
        plan_id=plan_id,
        mode=mode,
        base_branch=base_branch,
        review_path=review_path,
        ship_skill=ship_skill,
        request_codex_review=request_codex_review,
    )


def _handle_execution_activation(request: WorkflowRequest) -> int:
    if request.source is None:
        raise ValueError("execution activation requires a plan source")

    response = activate_execution(
        request.source,
        plan_id=request.plan_id,
        review_path=request.review_path or DEFAULT_REVIEW_PATH,
        ship_skill=request.ship_skill or DEFAULT_SHIP_SKILL,
        base_branch=request.base_branch or DEFAULT_BASE_BRANCH,
        mode=request.mode or "ship",
        request_codex_review=True if request.request_codex_review is None else request.request_codex_review,
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
        execution_state_path=DEFAULT_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _handle_start_planning(request: WorkflowRequest) -> int:
    response = start_planning(
        request.feature_request,
        planning_mode="brownfield",
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
        execution_state_path=DEFAULT_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _handle_start_bootstrap(request: WorkflowRequest) -> int:
    response = start_planning(
        request.feature_request,
        planning_mode="greenfield",
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
        execution_state_path=DEFAULT_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _handle_revise_planning(request: WorkflowRequest) -> int:
    response = revise_planning(
        request.feedback,
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _handle_approve_planning() -> int:
    response = approve_current_plan(
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
        execution_state_path=DEFAULT_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _handle_status() -> int:
    response = status_summary(
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
        execution_state_path=DEFAULT_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _handle_cancel() -> int:
    response = cancel_workflow(
        planning_state_path=DEFAULT_PLANNING_STATE_PATH,
        execution_state_path=DEFAULT_STATE_PATH,
    )
    return _print_response(response.message, response.additional_context)


def _print_response(system_message: str, additional_context: str) -> int:
    response = {
        "systemMessage": system_message,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": additional_context,
        },
    }
    print(json.dumps(response))
    return 0


def _require_value(parts: list[str], index: int, flag: str) -> str:
    if index >= len(parts):
        raise ValueError(f"missing value for {flag}")
    return parts[index]


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"workflow activation failed: {exc}", file=sys.stderr)
        raise
