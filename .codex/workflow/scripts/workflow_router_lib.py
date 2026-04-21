#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from planning_lib import (
    DEFAULT_PLANNING_STATE_PATH,
    append_trace_event,
    apply_revision_feedback,
    approve_planning,
    build_planning_state,
    clear_planning_state,
    execution_status_summary,
    initialize_planning_artifacts,
    load_planning_state,
    planning_activation_prompt,
    render_planning_status,
    save_planning_state,
)
from workflow_lib import (
    DEFAULT_BASE_BRANCH,
    DEFAULT_REVIEW_PATH,
    DEFAULT_SHIP_SKILL,
    DEFAULT_STATE_PATH,
    activation_prompt,
    build_state_from_plan_spec,
    load_plan_spec,
    load_state,
    next_stop_decision,
    save_state,
)


DEFAULT_PLAN_SOURCE = Path(".codex/workflow/approved-plan.json")


@dataclass(frozen=True)
class WorkflowRouteResponse:
    status: str
    mode: str
    message: str
    additional_context: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def start_planning(
    feature_request: str | None,
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> WorkflowRouteResponse:
    feature_request = str(feature_request or "").strip()
    if not feature_request:
        return _workflow_blocked(
            "planning",
            "workflow planning requires a feature request after `$workflow`",
        )

    planning_state, planning_error = _load_planning_state_safe(planning_state_path)
    if planning_error is not None:
        return _workflow_blocked(
            "planning",
            f"planning state at `{planning_state_path}` is invalid: {planning_error}",
        )
    if planning_state is not None:
        return _workflow_blocked(
            "planning",
            (
                f"an active planning session already exists with status `{planning_state['status']}`; "
                "use `$workflow` to revise, approve, resume, check status, or cancel it"
            ),
        )

    execution_state = _load_execution_state(execution_state_path)
    if execution_state is not None and execution_state["workflow_status"] != "complete":
        return _workflow_blocked(
            "planning",
            (
                f"an execution workflow is already active for `{execution_state['workflow_name']}`; "
                "finish or cancel it before starting a new plan"
            ),
        )

    state = build_planning_state(feature_request)
    state = _rebase_planning_artifacts(state, planning_state_path.parent)
    save_planning_state(state, planning_state_path)
    initialize_planning_artifacts(state)
    return WorkflowRouteResponse(
        status="ok",
        mode="planning",
        message="workflow planning started",
        additional_context=(
            "Treat the user's prompt as a workflow planning trigger, not as a normal implementation request. "
            "The planning state and shared artifacts have already been created. Do not ask the user to run setup "
            "commands.\n\n"
            f"{planning_activation_prompt(state)}"
        ),
    )


def revise_planning(
    feedback: str | None,
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
) -> WorkflowRouteResponse:
    state, planning_error = _load_planning_state_safe(planning_state_path)
    if planning_error is not None:
        return _workflow_blocked(
            "planning",
            f"planning state at `{planning_state_path}` is invalid: {planning_error}",
        )
    if state is None:
        return _workflow_blocked("planning", "there is no active planning session to revise")

    updated_state = apply_revision_feedback(state, feedback)
    save_planning_state(updated_state, planning_state_path)
    detail = feedback or "revision requested without additional guidance"
    append_trace_event(updated_state, "revision_requested", detail)
    return WorkflowRouteResponse(
        status="ok",
        mode="planning",
        message="workflow planning revision requested",
        additional_context=(
            "Treat the user's prompt as a planning revision trigger. Stay in the Plan phase, revise the "
            "existing plan artifacts, and do not start implementation.\n\n"
            f"{planning_activation_prompt(updated_state, revision_mode=True)}"
        ),
    )


def approve_current_plan(
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> WorkflowRouteResponse:
    state, planning_error = _load_planning_state_safe(planning_state_path)
    if planning_error is not None:
        return _workflow_blocked(
            "planning",
            f"planning state at `{planning_state_path}` is invalid: {planning_error}",
        )
    if state is None:
        return _workflow_blocked("planning", "there is no active planning session to approve")

    execution_state = approve_planning(
        state,
        planning_state_path=planning_state_path,
        execution_state_path=execution_state_path,
    )
    return WorkflowRouteResponse(
        status="ok",
        mode="execution",
        message="workflow planning approved",
        additional_context=(
            "Treat the user's prompt as approval to transition from Plan to Development. The execution state "
            "has already been created.\n\n"
            f"{activation_prompt(execution_state)}"
        ),
    )


def activate_execution(
    source: Path = DEFAULT_PLAN_SOURCE,
    *,
    plan_id: str | None = None,
    mode: str = "ship",
    base_branch: str = DEFAULT_BASE_BRANCH,
    review_path: str = DEFAULT_REVIEW_PATH,
    ship_skill: str = DEFAULT_SHIP_SKILL,
    request_codex_review: bool = True,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> WorkflowRouteResponse:
    plan_spec = load_plan_spec(source, plan_id=plan_id)
    state = build_state_from_plan_spec(
        plan_spec,
        plan_path=_relative_or_source(source),
        review_path=review_path,
        ship_skill=ship_skill,
        base_branch=base_branch,
        mode=mode,
        request_codex_review=request_codex_review,
    )
    save_state(state, execution_state_path)
    return WorkflowRouteResponse(
        status="ok",
        mode="execution",
        message=f"workflow activated from {source}",
        additional_context=(
            "Treat the user's prompt as a workflow activation trigger, not as a normal task request. "
            "The live workflow state has already been created. Do not ask the user to run ingestion commands.\n\n"
            f"{activation_prompt(state)}"
        ),
    )


def resume_workflow(
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> WorkflowRouteResponse:
    planning_state, planning_error = _load_planning_state_safe(planning_state_path)
    if planning_error is not None:
        return _workflow_blocked(
            "status",
            f"planning state at `{planning_state_path}` is invalid: {planning_error}",
        )
    if planning_state is not None:
        revision_mode = planning_state["status"] == "revising"
        return WorkflowRouteResponse(
            status="ok",
            mode="planning",
            message="workflow planning resumed",
            additional_context=(
                "Treat the user's prompt as a workflow resume request. Continue the active planning phase and do "
                "not start implementation.\n\n"
                f"{planning_activation_prompt(planning_state, revision_mode=revision_mode)}"
            ),
        )

    execution_state = _load_execution_state(execution_state_path)
    if execution_state is None:
        return _workflow_blocked("status", "there is no active workflow state to resume")

    next_state, decision, changed = next_stop_decision(execution_state)
    if changed:
        save_state(next_state, execution_state_path)

    if decision.action == "noop":
        return WorkflowRouteResponse(
            status="ok",
            mode="status",
            message="workflow already complete",
            additional_context=(
                "Treat the user's prompt as a workflow status request and report only the current state.\n\n"
                f"{execution_status_summary(next_state)}"
            ),
        )

    return WorkflowRouteResponse(
        status="ok",
        mode="execution",
        message="workflow execution resumed",
        additional_context=(
            "Treat the user's prompt as a workflow resume request. Follow the current workflow instruction and "
            "do not ask the user to rerun state commands.\n\n"
            f"{decision.prompt}"
        ),
    )


def status_summary(
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> WorkflowRouteResponse:
    planning_state, planning_error = _load_planning_state_safe(planning_state_path)
    if planning_error is not None:
        return _workflow_blocked(
            "status",
            f"planning state at `{planning_state_path}` is invalid: {planning_error}",
        )
    if planning_state is not None:
        return WorkflowRouteResponse(
            status="ok",
            mode="status",
            message="workflow planning status loaded",
            additional_context=(
                "Treat the user's prompt as a workflow status request and report only the current state.\n\n"
                f"{render_planning_status(planning_state)}"
            ),
        )

    execution_state = _load_execution_state(execution_state_path)
    if execution_state is not None:
        return WorkflowRouteResponse(
            status="ok",
            mode="status",
            message="workflow execution status loaded",
            additional_context=(
                "Treat the user's prompt as a workflow status request and report only the current state.\n\n"
                f"{execution_status_summary(execution_state)}"
            ),
        )

    return WorkflowRouteResponse(
        status="ok",
        mode="status",
        message="no active workflow state",
        additional_context=(
            "Treat the user's prompt as a workflow status request and report that there is no active planning or "
            "execution workflow."
        ),
    )


def cancel_workflow(
    *,
    planning_state_path: Path = DEFAULT_PLANNING_STATE_PATH,
    execution_state_path: Path = DEFAULT_STATE_PATH,
) -> WorkflowRouteResponse:
    cleared_labels: list[str] = []

    if clear_planning_state(planning_state_path):
        cleared_labels.append("planning state")

    if execution_state_path.exists():
        execution_state_path.unlink()
        cleared_labels.append("execution state")

    if not cleared_labels:
        message = "no active workflow state to cancel"
    else:
        message = "cleared " + " and ".join(cleared_labels)

    return WorkflowRouteResponse(
        status="ok",
        mode="cancel",
        message=message,
        additional_context=(
            "Treat the user's prompt as a workflow cancellation request. Report the cleared workflow state and "
            "note that discovery, trace, and approved-plan artifacts were preserved."
        ),
    )


def _workflow_blocked(mode: str, message: str) -> WorkflowRouteResponse:
    return WorkflowRouteResponse(
        status="blocked",
        mode=mode,
        message=f"workflow request blocked: {message}",
        additional_context=(
            "Treat the user's prompt as a workflow request that could not proceed. Explain the blocker "
            "concisely and do not start implementation.\n\n"
            f"Blocker:\n{message}"
        ),
    )


def _load_execution_state(path: Path) -> dict | None:
    try:
        return load_state(path)
    except Exception:
        return None


def _load_planning_state_safe(path: Path) -> tuple[dict | None, str | None]:
    try:
        return load_planning_state(path), None
    except Exception as exc:
        return None, str(exc)


def _rebase_planning_artifacts(state: dict, planning_root: Path) -> dict:
    rebased = dict(state)
    planning_root = planning_root.resolve()
    repo_root = planning_root
    if planning_root.name == "workflow" and planning_root.parent.name == ".codex":
        repo_root = planning_root.parent.parent
    rebased["approved_plan_path"] = str(planning_root / "approved-plan.json")
    rebased["context_path"] = str(planning_root / "context.json")
    rebased["discovery_dossier_path"] = str(planning_root / "discovery_dossier.json")
    rebased["scope_contract_path"] = str(planning_root / "scope_contract.json")
    rebased["architecture_constraints_path"] = str(planning_root / "architecture_constraints.json")
    rebased["product_scope_audit_path"] = str(planning_root / "product_scope_audit.json")
    rebased["skeptic_audit_path"] = str(planning_root / "skeptic_audit.json")
    rebased["convergence_summary_path"] = str(planning_root / "convergence_summary.json")
    rebased["planning_trace_path"] = str(planning_root / "planning_trace.json")
    rebased["project_memory_path"] = str(repo_root / "PROJECT.md")
    rebased["requirements_memory_path"] = str(repo_root / "REQUIREMENTS.md")
    rebased["state_memory_path"] = str(repo_root / "STATE.md")
    return rebased


def _relative_or_source(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
